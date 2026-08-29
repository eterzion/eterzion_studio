# Atualização automática

## O estado atual

Implementada. `electron-updater` verifica ao abrir e a cada seis horas,
baixa em segundo plano e instala quando o app é fechado. O feed é o de
releases do GitHub (`provider: github`, `eterzion/eterzion_studio`), então
não há infraestrutura própria a manter.

O comportamento é deliberadamente discreto: nenhum diálogo interrompe um
upscale em andamento e nada força reinício. Falha de rede é registrada e
ignorada — ficar sem internet ou atrás de um proxy corporativo é normal e
não pode impedir ninguém de usar o programa.

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
vale para quem instalar dali em diante, não retroativamente — e é exatamente
por isso que `assets.ericinacio.com` precisa continuar respondendo até a base
instalada girar.

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
