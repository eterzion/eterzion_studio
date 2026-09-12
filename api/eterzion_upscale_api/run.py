"""Entrypoint for the packaged binary (see eterzion-studio-api.spec) and for running
the API directly with `python run.py` instead of `uvicorn app.main:app`.

Também é a porta de entrada do WORKER ISOLADO quando o app está empacotado.

Fora do bundle, `jobs.py` lança o worker com `sys.executable -m app.jobs`. Num
bundle do PyInstaller não existe interpretador Python: `sys.executable` é este
próprio executável, e o bootloader ignora `-m`. O que acontecia era o comando
subir uma SEGUNDA cópia da API — verificado em produção, a 1.0.7 respondia na
porta 8051 quando lançada com os argumentos do worker. O `Listener` nunca
recebia conexão, e todo processamento morria no timeout de 45 segundos, com o
erro chegando à interface sem mensagem.

A saída é a padrão para executáveis congelados: o binário se relança com uma
sentinela própria e desvia para o worker antes de tocar no uvicorn. Precisa vir
ANTES de qualquer import pesado — o worker não usa uvicorn nem FastAPI.
"""
import multiprocessing
import sys

#: Primeiro argumento quando este executável está atuando como worker isolado.
#: `jobs.py` monta o spawn com ele; qualquer nome serve, desde que os dois lados
#: concordem — por isso a constante é importada de lá, e não repetida.
if __name__ == '__main__':
    multiprocessing.freeze_support()

    from app.jobs import FROZEN_WORKER_FLAG, main as worker_main

    if len(sys.argv) > 1 and sys.argv[1] == FROZEN_WORKER_FLAG:
        # `main()` lê o endereço de sys.argv[1]; remover a sentinela deixa os
        # argumentos exatamente como no caminho não empacotado.
        del sys.argv[1]
        worker_main()
        raise SystemExit(0)

    import logging

    import uvicorn

    from app.config import settings
    from app.main import app

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    )
    uvicorn.run(app, host='127.0.0.1', port=settings.port, log_config=None)
