# Atualização automática — o que existe e o que falta

Levantado durante a migração de domínio para `eterzion.com`, quando foi
preciso saber quanto tempo uma correção leva para alcançar a base instalada.

## O estado atual

**Não existe atualização automática.** Não é um feed mal configurado: é
funcionalidade ausente.

- `electron-updater` não está nas dependências de `interface/package.json`;
- não há `autoUpdater` em nenhum lugar do processo principal;
- `electron-builder.yml` e `dev-app-update.yml` trazem
  `publish: provider: generic, url: https://example.com/auto-updates`, que é
  o valor de template do electron-vite — nunca foi apontado para lugar
  nenhum.

## Por que isso importa mais do que parece

Toda correção — de segurança, de bug, de domínio — só alcança um usuário se
ele baixar e instalar de novo, por conta própria. Não há como saber quantos
fizeram, nem como forçar.

Isso apareceu de forma concreta na migração de domínio: o CSP em
`index.html` é empacotado, então uma cópia instalada **bloqueia**
`assets.eterzion.com` mesmo depois de o servidor passar a respondê-lo.
Nenhuma mudança de infraestrutura conserta uma cópia instalada.

## O que foi feito agora

O CSP passa a aceitar os dois domínios e o logo aponta para o novo. Isso não
conserta nada retroativamente — vale para a próxima versão que alguém
instalar. Enquanto houver base relevante em versões antigas,
`assets.ericinacio.com` precisa continuar respondendo.

## O que falta, e por que não foi feito junto

Implementar atualização automática é funcionalidade, não configuração:

1. adicionar `electron-updater`;
2. instanciar o `autoUpdater` no processo principal, tratando os eventos de
   verificação, download e erro;
3. decidir a interface: silencioso, aviso, ou pergunta;
4. apontar `publish` para `provider: github` — os releases já são publicados
   pela organização, então não é preciso hospedar feed;
5. assinar os artefatos, sem o que o Windows e o macOS reclamam na instalação;
6. testar o caminho de atualização de verdade, entre duas versões.

Fazer isso sob a pressão de uma janela de migração é como se entrega um
atualizador quebrado para usuários que, justamente por isso, não podem
receber a correção. Merece o seu próprio ciclo.

## A identidade do app

`appId: com.astrosupscale.app` e `productName: Astros Upscale` **não foram
alterados**, apesar do rename do resto. Trocar o `appId` faz a versão nova
instalar **ao lado** da antiga em vez de atualizá-la, deixando duas cópias na
máquina do usuário.

Se a marca for mudar, essa é uma decisão de produto com custo visível para o
usuário — uma desinstalação manual — e deve ser tomada de propósito, não como
efeito colateral de uma migração de infraestrutura. O melhor momento seria
junto da versão que introduzir a atualização automática, que já vai exigir
instalação manual de qualquer forma.
