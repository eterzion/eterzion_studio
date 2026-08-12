# Phase 1 Data Model: Reorganização e simplificação de interface/

Esta feature é estrutural (reorganização/renomeação/extração de código-fonte já existente) e
**não introduz, altera, nem remove nenhuma entidade de dado de domínio, tipo de estado persistido,
ou schema de comunicação com a API**. `types.ts` (o único tipo verdadeiramente compartilhado,
`NavKey`) não muda. Os tipos definidos em `apiClient.ts` (era `backend.ts`) continuam espelhando
`app/models/schemas.py` do backend, sem alteração de forma.

## Mapeamento de caminho (origem → destino)

| Origem | Destino |
|---|---|
| `src/renderer/src/api.ts` | `src/renderer/src/nativeBridge.ts` |
| `src/renderer/src/backend.ts` | `src/renderer/src/apiClient.ts` |
| `src/renderer/src/components/Versions.vue` | *(removido)* |
| *(lógica hoje duplicada em 5 views)* | `src/renderer/src/composables/useFileIntake.ts` |
| `views/ImageEditorView.vue` linhas 72-131 | `src/renderer/src/composables/useViewportPanZoom.ts` |
| `views/ImageEditorView.vue` linhas 198-262 | `src/renderer/src/composables/useDenoisePreview.ts` |
| `views/ImageEditorView.vue` linhas 359-401 | `src/renderer/src/composables/useExportPanel.ts` |

Nenhuma outra entidade requer documentação nesta fase.
