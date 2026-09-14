# Novidades por versão

Um arquivo por versão, `<versão>.md` (ex.: `1.1.6.md`), com duas ou três linhas
em linguagem de usuário — o que muda para quem usa o app, não o que mudou no
código. Uma linha por item, começando com `- `.

O workflow de release copia o arquivo da versão para `build/release-notes.md`;
o electron-builder o coloca no `latest.yml`, e o app mostra as linhas na seção
**Configurações → Versão e atualizações** enquanto a versão nova baixa e quando fica
pronta. O texto é exibido como texto puro: markdown além do `- ` não é
interpretado.

Sem o arquivo, a versão sai sem novidades e o app só não as mostra.
