# Atualização automática

## O estado atual

Implementada. `electron-updater` verifica ao abrir e a cada seis horas,
baixa em segundo plano e instala quando o app é fechado. O feed é o CDN
privado do Studio (`cdn.eterzion.com/studio/updates`, bucket `eterzion-studio`
no R2), servido só com a assinatura que o servidor de licenças emite para
licença ativa — ver `src/main/updater.ts`.

O comportamento é deliberadamente discreto: nenhum diálogo interrompe um
upscale em andamento e nada força reinício. Falha de rede é registrada e
aparece só como "tente novamente mais tarde" — ficar sem internet ou atrás
de um proxy corporativo é normal e não pode impedir ninguém de usar o
programa.

**O que a pessoa vê** (desde a 1.1.6):

- quando a versão nova termina de baixar, um aviso no canto, uma vez por
  versão, com "Reiniciar e atualizar";
- o selo da versão na barra lateral vira "Atualização pronta" (com a barra
  recolhida, um ponto no ícone de Configurações) e leva à seção
  **Configurações → Atualizações**: versão instalada, estado, progresso do
  download, novidades e o botão "Procurar atualizações";
- reiniciar com processamento em andamento pede confirmação, porque cancela
  o que estiver rodando;
- "Procurar atualizações automaticamente" desligada: o app só procura quando
  se clica no botão.

As novidades de cada versão ficam em `interface/release-notes/<versão>.md`
(ver o README de lá).

## O que havia antes

Nada. Não era feed mal configurado: `electron-updater` não estava nas
dependências, não havia `autoUpdater` no processo principal, e o
`publish: url: https://example.com/auto-updates` era valor de template do
electron-vite, nunca apontado para lugar nenhum.

## Por que isso importa mais do que parece

Toda correção — de segurança, de bug, de domínio — só alcança um usuário se
ele baixar e instalar de novo, por conta própria. Não há como saber quantos
fizeram, nem como forçar.

Isso apareceu de forma concreta na migração de domínio: o CSP em
`index.html` é empacotado, então uma cópia instalada **bloqueia**
`assets.eterzion.com` mesmo depois de o servidor passar a respondê-lo.
Nenhuma mudança de infraestrutura conserta uma cópia instalada.

## Sobre o domínio

O CSP passou a aceitar `assets.eterzion.com` e o logo aponta para lá. Isso
vale para quem instalar dali em diante, não retroativamente.

Esta seção dizia que `assets.ericinacio.com` precisava continuar respondendo
até a base instalada girar. **Medido em 30/08/2026, isso já não protege
nada.** O arquivo que as builds antigas pedem,
`assets.ericinacio.com/branding/logo-256.webp`, foi removido do CDN em
13/08/2026 (`eterzion_assets` 4c9610bf1, `11856 -> 0 bytes`), quando a marca
do site passou a ter um diretório por variante. O logo dessas cópias está
quebrado desde então — semanas antes de o subdomínio parar de responder.

O host hoje resolve no DNS (177.107.64.5) mas não completa o TLS: o vhost
saiu junto dos outros subdomínios antigos. Ressuscitá-lo não devolveria o
logo, porque o arquivo pedido não existe mais.

Redirecionar também não é opção, e vale registrar por quê: o CSP empacotado
das cópias antigas libera apenas `assets.ericinacio.com` no `img-src`. Um 301
para `assets.eterzion.com` seria bloqueado pelo próprio CSP. Para servir
aquelas cópias seria preciso o host antigo **entregar os bytes**, sob o
caminho antigo — o que significa manter um caminho de marca aposentado vivo
por tempo indeterminado, para consertar um logo. Não vale.

## O que ainda falta

**Assinatura de código.** Sem ela, o Windows mostra aviso do SmartScreen na
instalação e o macOS recusa abrir sem intervenção do usuário. O atualizador
funciona, mas cada atualização faz o usuário passar por um alerta — o que na
prática reduz quem atualiza. Exige certificado adquirido e configuração no
`electron-builder.yml`.

**A primeira versão ainda é manual.** Quem está numa build antiga não recebe
esta por atualização automática, porque a build antiga não sabe procurar.
Essa versão precisa ser distribuída à mão, uma última vez. Da próxima em
diante o caminho se resolve sozinho.

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
