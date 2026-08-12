# Quickstart: validação da reorganização de interface/

Guia de validação a rodar depois da implementação (`/speckit-implement`), antes de considerar a
feature concluída. Cada passo mapeia para um Success Criterion de `spec.md`.

## 1. Nomes corrigidos e camada de acesso isolada (SC-001, SC-005)

```bash
cd interface
grep -rn "from '\.\./api'\|from '\./api'" src/renderer/src   # deve retornar vazio
grep -rn "from '\.\./backend'\|from '\./backend'" src/renderer/src   # deve retornar vazio
grep -rln "fetch(" src/renderer/src/components src/renderer/src/views   # deve retornar vazio —
                                                                          # nenhum componente/view chama fetch direto
```

## 2. Zero código morto / import não usado (SC-002)

```bash
cd interface
npm run lint   # eslint já reporta imports/variáveis não usados como erro/warning
find src/renderer/src -iname "Versions.vue"   # deve retornar vazio
```

## 3. Build/lint/typecheck sem regressão (SC-003)

```bash
cd interface
npm run typecheck
npm run lint
npm run build   # ou electron-vite build
```

Comparar contagem de erros/avisos com a linha de base capturada antes da reorganização — deve ser
igual ou menor.

## 4. Nenhuma regressão visual/funcional (SC-004)

```bash
cd interface
npm run dev
```

Abrir o app e percorrer manualmente: Home → cada categoria (Imagem/Vídeo/Áudio/Otimizar/Converter)
→ importar arquivo (via seletor, drag-drop, e colar/paste) → processar → exportar → Configurações
→ Modelos → Histórico → ativação de licença. Nenhuma tela deve ter diferença visual ou de
comportamento perceptível em relação ao estado anterior.

Testar especificamente `useFileIntake` nas 5 views que passam a usá-lo (Imagem, Vídeo, Áudio,
Otimizar, Converter): seletor de arquivo, drag-and-drop, e colar (paste) devem continuar
funcionando exatamente como antes em cada uma.
