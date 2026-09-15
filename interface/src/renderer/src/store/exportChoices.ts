import { reactive } from 'vue'
import { settingsState } from './settings'
import type { ConflictMode, Profile, VideoContainer } from '../services/api'
import type { CompressionExport } from '../services/compression'
import type { AudioExport } from '../components/audio/AudioExportPanel.vue'
import type { ImageExport } from './jobs'

// As escolhas de exportacao de cada modo (formato, qualidade, pasta, conflito).
//
// Viviam dentro de cada tela, e sair da tela e voltar as trazia de volta ao
// padrao: quem escolheu JPG e uma pasta, foi olhar o Historico e voltou,
// encontrava PNG e "mesma pasta do original". Aqui elas sobrevivem a troca de
// tela durante a sessao. Nao ficam salvas entre aberturas do app: o padrao de
// cada abertura e' o das Configuracoes.
//
// O nome do arquivo nao entra: vale para o arquivo ativo, e cada tela o limpa
// ao trocar de arquivo.

export interface VideoExportChoices {
  container: VideoContainer
  profile: Profile
  directory: string | null
  conflict: ConflictMode
}

interface ExportChoices {
  image: ImageExport | null
  video: VideoExportChoices | null
  audio: Omit<AudioExport, 'filename'> | null
  compression: CompressionExport | null
}

const escolhas = reactive<ExportChoices>({
  image: null,
  video: null,
  audio: null,
  compression: null
})

/** Criadas no primeiro uso, e nao na carga do modulo: a pasta padrao das
 *  Configuracoes vale como estiver quando a tela abre pela primeira vez. */
export function imageExportChoices(): ImageExport {
  escolhas.image ??= {
    format: settingsState.defaultExportFormat,
    profile: settingsState.defaultImageProfile,
    directory: settingsState.defaultOutputFolder,
    conflict: 'rename'
  }
  return escolhas.image
}

export function videoExportChoices(): VideoExportChoices {
  escolhas.video ??= {
    container: 'mp4',
    profile: 'balanced',
    directory: settingsState.defaultOutputFolder,
    conflict: 'rename'
  }
  return escolhas.video
}

export function audioExportChoices(): Omit<AudioExport, 'filename'> {
  escolhas.audio ??= {
    format: 'keep',
    profile: 'balanced',
    directory: settingsState.defaultOutputFolder,
    conflict: 'rename'
  }
  return escolhas.audio
}

export function compressionExportChoices(): CompressionExport {
  escolhas.compression ??= {
    directory: settingsState.defaultOutputFolder,
    naming_pattern: '{filename}_compressed',
    conflict_policy: 'rename'
  }
  return escolhas.compression
}

/** Para os testes: volta tudo ao estado de antes do primeiro uso. */
export function resetExportChoices(): void {
  escolhas.image = null
  escolhas.video = null
  escolhas.audio = null
  escolhas.compression = null
}
