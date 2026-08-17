import { onBeforeUnmount, ref, type Ref } from 'vue'
import type { VideoAdjustments } from './useVideoEdits'

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

void main() {
  vec3 rgb = texture(u_frame, v_uv).rgb;
  vec3 yuv = RGB_TO_YUV * rgb;

  // Luma: contrast about the midpoint, then additive brightness, then gamma —
  // the order vf_eq.c uses. Reordering these is not equivalent.
  float y = u_contrast * (yuv.x - 0.5) + 0.5 + u_brightness;
  y = clamp(y, 0.0, 1.0);
  y = pow(y, 1.0 / u_gamma);

  // Chroma is centred on zero here (it is centred on 128 in 8-bit YUV), so
  // saturation scales directly rather than about an offset.
  vec2 uv = yuv.yz * u_saturation;
  uv = vec2(uv.x * u_hueCos - uv.y * u_hueSin, uv.x * u_hueSin + uv.y * u_hueCos);

  fragColor = vec4(clamp(YUV_TO_RGB * vec3(y, uv), 0.0, 1.0), 1.0);
}`

export interface PreviewPipeline {
  /** False when WebGL2 is unavailable. The caller must then fall back to the
      untouched <video>, and say that adjustments are not being previewed —
      never show an unfiltered frame as if it were filtered. */
  supported: Ref<boolean>
  start: (video: HTMLVideoElement, canvas: HTMLCanvasElement) => boolean
  stop: () => void
  apply: (adjustments: VideoAdjustments) => void
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
  let source: HTMLVideoElement | null = null
  let rafHandle: number | null = null
  let current: VideoAdjustments | null = null

  function draw(): void {
    if (!gl || !program || !source || source.readyState < 2) {
      rafHandle = requestAnimationFrame(draw)
      return
    }
    const canvas = gl.canvas as HTMLCanvasElement
    if (canvas.width !== source.videoWidth || canvas.height !== source.videoHeight) {
      canvas.width = source.videoWidth
      canvas.height = source.videoHeight
      gl.viewport(0, 0, canvas.width, canvas.height)
    }

    gl.bindTexture(gl.TEXTURE_2D, texture)
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, source)

    const a = current ?? {
      brightness: 0,
      contrast: 1,
      saturation: 1,
      gamma: 1,
      hue_degrees: 0,
      sharpness: 0
    }
    const radians = (a.hue_degrees * Math.PI) / 180
    gl.uniform1f(gl.getUniformLocation(program, 'u_brightness'), a.brightness)
    gl.uniform1f(gl.getUniformLocation(program, 'u_contrast'), a.contrast)
    gl.uniform1f(gl.getUniformLocation(program, 'u_saturation'), a.saturation)
    // Guarded: gamma 0 would divide by zero in the shader and render black.
    gl.uniform1f(gl.getUniformLocation(program, 'u_gamma'), Math.max(0.1, a.gamma))
    gl.uniform1f(gl.getUniformLocation(program, 'u_hueCos'), Math.cos(radians))
    gl.uniform1f(gl.getUniformLocation(program, 'u_hueSin'), Math.sin(radians))

    gl.drawArrays(gl.TRIANGLES, 0, 6)
    rafHandle = requestAnimationFrame(draw)
  }

  function start(video: HTMLVideoElement, canvas: HTMLCanvasElement): boolean {
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
  }

  onBeforeUnmount(stop)

  return { supported, start, stop, apply }
}

/** The CPU-side twin of the shader's luma path, exported so a test can pin it
 *  against what video_edits.py builds. Parity is an assertion, not a comment. */
export function eqLuma(
  value: number,
  a: Pick<VideoAdjustments, 'brightness' | 'contrast' | 'gamma'>
): number {
  const contrasted = a.contrast * (value - 0.5) + 0.5 + a.brightness
  return Math.pow(Math.min(1, Math.max(0, contrasted)), 1 / Math.max(0.1, a.gamma))
}
