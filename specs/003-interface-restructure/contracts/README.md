# Contracts: Reorganização e simplificação de interface/

Esta feature **não adiciona nem modifica nenhum contrato HTTP/WebSocket** com `api/`. O cliente
HTTP/WS (`apiClient.ts`, antes `backend.ts`) continua chamando exatamente as mesmas rotas com
exatamente os mesmos payloads — só o nome do arquivo muda.

O único "contrato" real desta feature é a assinatura do novo composable compartilhado, já que ele
passa a ser usado por 5 views diferentes:

## `useFileIntake` — contrato do composable

```ts
function useFileIntake(options: {
  onFile: (described: DescribedFile) => void | Promise<void>
  errorRef: Ref<string | null>
}): {
  pickFiles: () => Promise<void>
  pickFolder: () => Promise<void>       // opcional — só views que hoje suportam pasta o usam
  handleFilesDropped: (files: File[]) => Promise<void>
  handlePaste: (event: ClipboardEvent) => Promise<void>
}
```

Cada view continua definindo seu próprio `onFile` (a validação/formato de job específico dela) —
o composable só assume o "casco" comum de abrir o seletor nativo, checar `hasNativeApi`, e
percorrer os arquivos resultantes. A assinatura exata é refinada durante `/speckit-tasks`/
`/speckit-implement` com base na comparação linha-a-linha das 5 implementações atuais.

Ver `quickstart.md` para os passos de validação.
