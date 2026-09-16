"""Gera as imagens do instalador do Windows a partir do icone do app.

O instalador mostrava a arte generica do NSIS (`nsis3-metro.bmp`: um quadrado
riscado e uma seta entrando num notebook, em azul) porque
`installerSidebar.bmp` nao existia -- o electron-builder so' cai no padrao dele
quando o arquivo falta (NsisTarget.js). A primeira tela que alguem ve do
produto era de outro produto.

As imagens sao geradas, e nao desenhadas a mao, para nao virarem binarios sem
origem no repositorio: mexeu no icone, roda de novo.

    python interface/build/gerar-imagens-do-instalador.py

BMP de 24 bits, sem transparencia: o MUI do NSIS desenha o bitmap direto, e
canal alfa sai como lixo cinza. 164x314 e' o tamanho que o MUI reserva para a
faixa da esquerda nas paginas de boas-vindas e de conclusao.
"""
from pathlib import Path

from PIL import Image

AQUI = Path(__file__).resolve().parent
ICONE = AQUI.parent / 'resources' / 'icon.png'

LARGURA, ALTURA = 164, 314
FUNDO_TOPO = (13, 13, 13)
FUNDO_BASE = (26, 26, 26)
AMARELO = (240, 185, 11)
LADO_DO_LOGO = 96


def fundo() -> Image.Image:
    """Degrade vertical discreto: o preto chapado ao lado do branco da pagina
    fica com cara de retangulo esquecido."""
    imagem = Image.new('RGB', (LARGURA, ALTURA))
    pixels = imagem.load()
    for y in range(ALTURA):
        t = y / (ALTURA - 1)
        cor = tuple(round(topo + (base - topo) * t) for topo, base in zip(FUNDO_TOPO, FUNDO_BASE))
        for x in range(LARGURA):
            pixels[x, y] = cor
    return imagem


def montar() -> Image.Image:
    imagem = fundo()
    # O icone e' opaco, com o proprio quadrado preto -- colado inteiro, ele
    # aparece como um retangulo de preto diferente sobre o degrade. Entao o que
    # se aproveita dele e' so' a marca: o brilho de cada pixel vira a mascara,
    # e a marca e' pintada no amarelo da marca, com as bordas suaves do
    # original preservadas.
    icone = Image.open(ICONE).convert('RGB').resize((LADO_DO_LOGO, LADO_DO_LOGO), Image.LANCZOS)
    # O fundo do icone nao e' preto puro (por volta de 10 de brilho). Um
    # autocontraste o transformaria num amarelo fraquissimo -- que aparece
    # como um quadrado mais claro sobre o degrade. Entao tudo abaixo do corte
    # vira transparente, e so' o que esta' claramente na marca entra.
    corte, cheio = 40, 190
    mascara = icone.convert('L').point(
        lambda v: 0 if v < corte else min(255, round((v - corte) * 255 / (cheio - corte)))
    )
    marca = Image.new('RGB', icone.size, AMARELO)
    imagem.paste(marca, ((LARGURA - LADO_DO_LOGO) // 2, 74), mascara)
    # Fio amarelo no pe': a unica cor da marca na faixa, e o que separa a
    # imagem da borda da janela.
    for y in range(ALTURA - 3, ALTURA):
        for x in range(LARGURA):
            imagem.putpixel((x, y), AMARELO)
    return imagem


def main() -> None:
    imagem = montar()
    for nome in ('installerSidebar.bmp', 'uninstallerSidebar.bmp'):
        imagem.save(AQUI / nome, 'BMP')
        print(f'{nome}: {imagem.size[0]}x{imagem.size[1]}')


if __name__ == '__main__':
    main()
