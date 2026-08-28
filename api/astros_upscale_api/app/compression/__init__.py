"""Central de Compressão de Mídia — specs/008-compression-centre.

Fachada do subsistema: as rotas conhecem este módulo e nada abaixo dele. A
organização é por **domínio de mídia**, não por classe (Princípio XI, e a
Decisão 7 de research.md) — `image`, `video`, `audio` e `animation` são quatro
problemas genuinamente diferentes, enquanto um arquivo por serviço seria a
fragmentação que o princípio existe para impedir.

Este pacote NÃO substitui `astros_upscale.optimize`. Aquele caminho serve o
fluxo de compress/convert que já existe e continua funcionando; esta é a
superfície nova, e o Princípio II proíbe reescrever o que funciona por gosto.
A duplicação entre os dois está registrada em analysis.md, achado 5, com o
motivo medido e a dívida anotada.
"""
