import { onBeforeUnmount, ref, type Ref } from 'vue'
import { effectiveAdjustments, type VideoAdjustments } from './useVideoEdits'

// T044 (specs/007-video-editor-player) — the interactive preview.
//
// research.md Decisão 1: this reproduces FFmpeg's `eq` and `hue` filters, not
// an approximation of them. CSS filters were rejected precisely here — CSS
// brightness multiplies, eq's brightness adds, and no mapping between them is
// exact across the range. A CSS preview would diverge from the export
// systematically and invisibly, which is what FR-015 forbids.
//
// Faithfulness requires working where FFmpeg works. `eq` operates on YUV: it
// applies contrast/brightness/gamma to luma and saturation to chroma, and `hue`
// rotates the chroma plane. Doing the same in RGB would be a different
// operation wearing the same parameter names. So the shader converts to YUV,
// applies the same arithmetic in the same order, and converts back.
//
// From libavfilter/vf_eq.c:
//     v = contrast * (v - 0.5) + 0.5 + brightness
//     v = pow(v, 1.0 / gamma)              (gamma_weight defaults to 1)
// and for chroma:
//     u = (u - 128) * saturation + 128
// from vf_hue.c:
//     u' = u*cos(h) - v*sin(h);  v' = u*sin(h) + v*cos(h)

const VERTEX_SHADER = `#version 300 es
in vec2 a_position;
out vec2 v_uv;
void main() {
  // Flipped vertically: texture space runs the other way from clip space, and a
  // video previewed upside down is a memorable bug to ship.
  v_uv = vec2((a_position.x + 1.0) * 0.5, 1.0 - (a_position.y + 1.0) * 0.5);
  gl_Position = vec4(a_position, 0.0, 1.0);
}`

const FRAGMENT_SHADER = `#version 300 es
precision highp float;

in vec2 v_uv;
out vec4 fragColor;

uniform sampler2D u_frame;
uniform float u_brightness;
uniform float u_contrast;
uniform float u_saturation;
uniform float u_gamma;
uniform float u_hueCos;
uniform float u_hueSin;
// Geometria da Imagem (girar/espelhar), na mesma ordem do FFmpeg: transpose e
// depois hflip/vflip. No Video fica em 0 -- la' a rotacao nao passa por aqui.
uniform int u_rotation;   // quartos de volta no sentido horario: 0..3
uniform bool u_flipH;
uniform bool u_flipV;

// BT.709, the coefficients HD video is encoded with. Using BT.601 here would
// shift colour on exactly the material this editor is for.
const mat3 RGB_TO_YUV = mat3(
  0.2126, -0.114572, 0.5,
  0.7152, -0.385428, -0.454153,
  0.0722, 0.5, -0.045847
);
const mat3 YUV_TO_RGB = mat3(
  1.0, 1.0, 1.0,
  0.0, -0.187324, 1.8556,
  1.5748, -0.468124, 0.0
);

// eq operates on the STORED luma plane, which video carries in limited ("TV")
// range: 16..235 rather than 0..255. Applying it to full-range luma makes
// brightness land 255/219 times too weak, which a measured parity test against
// real FFmpeg caught — see test_video_edits.py's
// test_ffmpeg_eq_matches_the_formula_the_shader_implements. The browser hands us
// full-range RGB, so the conversion has to go through limited range explicitly.
float toStoredLuma(float yFull) { return (16.0 + 219.0 * yFull) / 255.0; }
float fromStoredLuma(float yStored) { return (yStored * 255.0 - 16.0) / 219.0; }

// Do pixel de saida para o de origem: desfaz o espelhamento (aplicado por
// ultimo) e depois o giro.
vec2 origem(vec2 o) {
  if (u_flipH) o.x = 1.0 - o.x;
  if (u_flipV) o.y = 1.0 - o.y;
  if (u_rotation == 1) return vec2(o.y, 1.0 - o.x);
  if (u_rotation == 2) return vec2(1.0 - o.x, 1.0 - o.y);
  if (u_rotation == 3) return vec2(1.0 - o.y, o.x);
  return o;
}

void main() {
  vec4 texel = texture(u_frame, origem(v_uv));
  vec3 rgb = texel.rgb;
  vec3 yuv = RGB_TO_YUV * rgb;

  // Luma: contrast about the midpoint, then additive brightness, then gamma —
  // the order vf_eq.c uses. Reordering these is not equivalent.
  float y = toStoredLuma(yuv.x);
  y = u_contrast * (y - 0.5) + 0.5 + u_brightness;
  y = clamp(y, 0.0, 1.0);
  y = pow(y, 1.0 / u_gamma);
  y = fromStoredLuma(y);

  // Chroma is centred on zero here (it is centred on 128 in 8-bit YUV), so
  // saturation scales directly rather than about an offset. The range question
  // above does not arise: scaling a centred value is the same operation in
  // either range.
  vec2 uv = yuv.yz * u_saturation;
  uv = vec2(uv.x * u_hueCos - uv.y * u_hueSin, uv.x * u_hueSin + uv.y * u_hueCos);

  // O alfa passa intacto: numa imagem transparente a previa nao pode ficar
  // opaca (o arquivo nao fica -- app/exportacao_de_imagem.py).
  fragColor = vec4(clamp(YUV_TO_RGB * vec3(y, uv), 0.0, 1.0), texel.a);
}`

/** Girar e espelhar, para a previa da Imagem. */
export interface PreviewGeometry {
  rotation_degrees: 0 | 90 | 180 | 270
  flip_horizontal: boolean
  flip_vertical: boolean
}

export interface PreviewPipeline {
  /** False when WebGL2 is unavailable. The caller must then fall back to the
      untouched <video>, and say that adjustments are not being previewed —
      never show an unfiltered frame as if it were filtered. */
  supported: Ref<boolean>
  /** Um <video> (redesenha a cada quadro) ou um <img> (redesenha so' quando
   *  algo muda -- reenviar uma foto grande a cada quadro seria trabalho sem
   *  efeito). */
  start: (source: HTMLVideoElement | HTMLImageElement, canvas: HTMLCanvasElement) => boolean
  stop: () => void
  apply: (adjustments: VideoAdjustments) => void
  geometry: (value: PreviewGeometry) => void
}

function isImage(source: HTMLVideoElement | HTMLImageElement): source is HTMLImageElement {
  return typeof HTMLImageElement !== 'undefined' && source instanceof HTMLImageElement
}

function sourceSize(source: HTMLVideoElement | HTMLImageElement): [number, number] {
  return isImage(source)
    ? [source.naturalWidth, source.naturalHeight]
    : [source.videoWidth, source.videoHeight]
}

function sourceReady(source: HTMLVideoElement | HTMLImageElement): boolean {
  return isImage(source) ? source.complete && source.naturalWidth > 0 : source.readyState >= 2
}

function compile(gl: WebGL2RenderingContext, type: number, source: string): WebGLShader | null {
  const shader = gl.createShader(type)
  if (!shader) return null
  gl.shaderSource(shader, source)
  gl.compileShader(shader)
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    gl.deleteShader(shader)
    return null
  }
  return shader
}

export function useVideoPreviewPipeline(): PreviewPipeline {
  const supported = ref(true)

  let gl: WebGL2RenderingContext | null = null
  let program: WebGLProgram | null = null
  let texture: WebGLTexture | null = null
  let source: HTMLVideoElement | HTMLImageElement | null = null
  let rafHandle: number | null = null
  let current: VideoAdjustments | null = null
  let geometria: PreviewGeometry = {
    rotation_degrees: 0,
    flip_horizontal: false,
    flip_vertical: false
  }
  // Imagem: a textura sobe uma vez, e so' se redesenha quando algo muda.
  let textureLoaded = false
  let dirty = true

  function draw(): void {
    if (!gl || !program || !source || !sourceReady(source)) {
      rafHandle = requestAnimationFrame(draw)
      return
    }
    const image = isImage(source)
    if (image && !dirty && textureLoaded) {
      rafHandle = requestAnimationFrame(draw)
      return
    }
    const canvas = gl.canvas as HTMLCanvasElement
    const [largura, altura] = sourceSize(source)
    // Um quarto de volta troca largura e altura do resultado.
    const deitada = geometria.rotation_degrees === 90 || geometria.rotation_degrees === 270
    const [w, h] = deitada ? [altura, largura] : [largura, altura]
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w
      canvas.height = h
      gl.viewport(0, 0, canvas.width, canvas.height)
    }

    gl.bindTexture(gl.TEXTURE_2D, texture)
    try {
      if (!image || !textureLoaded) {
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, source)
        textureLoaded = true
      }
    } catch {
      // A tainted texture throws here — the media scheme is a different origin
      // from the renderer, so the video needs crossorigin AND the handler needs
      // to answer CORS. When either is missing this throws on the first frame,
      // and an unguarded throw kills the requestAnimationFrame loop: the canvas
      // freezes black while the player underneath keeps decoding, which reads
      // as "the video is broken" rather than "the shader is".
      //
      // Falling back means the caller shows the untouched <video> and says the
      // adjusted preview is unavailable — honest, and far better than black.
      supported.value = false
      stop()
      return
    }

    // Através de effectiveAdjustments, não dos valores crus: um controle
    // desligado tem que ler como neutro aqui exatamente como lê na exportação.
    // Ler o valor cru mostraria na prévia um ajuste que o arquivo não teria —
    // a divergência silenciosa que o FR-015 proíbe.
    const a = current
      ? effectiveAdjustments(current)
      : { brightness: 0, contrast: 1, saturation: 1, gamma: 1, hue_degrees: 0, sharpness: 0 }
    const radians = (a.hue_degrees * Math.PI) / 180
    gl.uniform1f(gl.getUniformLocation(program, 'u_brightness'), a.brightness)
    gl.uniform1f(gl.getUniformLocation(program, 'u_contrast'), a.contrast)
    gl.uniform1f(gl.getUniformLocation(program, 'u_saturation'), a.saturation)
    // Guarded: gamma 0 would divide by zero in the shader and render black.
    gl.uniform1f(gl.getUniformLocation(program, 'u_gamma'), Math.max(0.1, a.gamma))
    gl.uniform1f(gl.getUniformLocation(program, 'u_hueCos'), Math.cos(radians))
    gl.uniform1f(gl.getUniformLocation(program, 'u_hueSin'), Math.sin(radians))
    gl.uniform1i(gl.getUniformLocation(program, 'u_rotation'), geometria.rotation_degrees / 90)
    gl.uniform1i(gl.getUniformLocation(program, 'u_flipH'), geometria.flip_horizontal ? 1 : 0)
    gl.uniform1i(gl.getUniformLocation(program, 'u_flipV'), geometria.flip_vertical ? 1 : 0)

    gl.drawArrays(gl.TRIANGLES, 0, 6)
    dirty = false
    rafHandle = requestAnimationFrame(draw)
  }

  function start(video: HTMLVideoElement | HTMLImageElement, canvas: HTMLCanvasElement): boolean {
    stop()
    const context = canvas.getContext('webgl2', { premultipliedAlpha: false })
    if (!context) {
      supported.value = false
      return false
    }
    gl = context

    const vertex = compile(gl, gl.VERTEX_SHADER, VERTEX_SHADER)
    const fragment = compile(gl, gl.FRAGMENT_SHADER, FRAGMENT_SHADER)
    program = vertex && fragment ? gl.createProgram() : null
    if (!program || !vertex || !fragment) {
      supported.value = false
      return false
    }
    gl.attachShader(program, vertex)
    gl.attachShader(program, fragment)
    gl.linkProgram(program)
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      supported.value = false
      return false
    }
    gl.useProgram(program)

    const buffer = gl.createBuffer()
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer)
    // Two triangles covering the clip space — the whole frame is the subject,
    // so there is no geometry beyond a full-screen quad.
    gl.bufferData(
      gl.ARRAY_BUFFER,
      new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]),
      gl.STATIC_DRAW
    )
    const position = gl.getAttribLocation(program, 'a_position')
    gl.enableVertexAttribArray(position)
    gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0)

    texture = gl.createTexture()
    gl.bindTexture(gl.TEXTURE_2D, texture)
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE)
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE)
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR)
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR)
    gl.uniform1i(gl.getUniformLocation(program, 'u_frame'), 0)

    source = video
    textureLoaded = false
    dirty = true
    supported.value = true
    rafHandle = requestAnimationFrame(draw)
    return true
  }

  function stop(): void {
    if (rafHandle !== null) cancelAnimationFrame(rafHandle)
    rafHandle = null
    source = null
  }

  function apply(adjustments: VideoAdjustments): void {
    current = adjustments
    dirty = true
  }

  function geometry(value: PreviewGeometry): void {
    geometria = { ...value }
    dirty = true
  }

  onBeforeUnmount(stop)

  return { supported, start, stop, apply, geometry }
}

/** The CPU-side twin of the shader's luma path, exported so parity with FFmpeg
 *  is an assertion rather than a comment.
 *
 *  `value` is full-range luma in 0..1, as the browser hands it over. The
 *  limited-range hop in the middle is not decoration: eq operates on the stored
 *  plane, which video carries in 16..235, and skipping it makes brightness land
 *  255/219 too weak. A measured test against real FFmpeg is what established
 *  that — the first version of this function did skip it. */
export function eqLuma(
  value: number,
  a: Pick<VideoAdjustments, 'brightness' | 'contrast' | 'gamma'>
): number {
  const stored = (16 + 219 * value) / 255
  const contrasted = a.contrast * (stored - 0.5) + 0.5 + a.brightness
  const gammaed = Math.pow(Math.min(1, Math.max(0, contrasted)), 1 / Math.max(0.1, a.gamma))
  // Clamped on the way out as well as on the way in: a stored luma of 16 maps
  // back to full-range 0, and anything below it to a negative number that is
  // not a colour. The shader clamps at the same point.
  return Math.min(1, Math.max(0, (gammaed * 255 - 16) / 219))
}
