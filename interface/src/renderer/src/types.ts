// 'video-editor' is a MODE of the Vídeo screen, not a sidebar destination:
// AppSidebar builds its list explicitly and does not include it, so adding it
// here reaches the view switch without adding a nav item (FR-032 — the editor
// coexists with the batch flow, it does not replace or outrank it).
export type NavKey =
  | 'home'
  | 'imagem'
  | 'video'
  | 'video-editor'
  | 'audio'
  | 'compressao'
  | 'historico'
  | 'configuracoes'
