#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gerar_pdf.py

Pega as cartas ja redimensionadas (pasta "prontas") e monta um PDF pronto
para mandar pra grafica: varias cartas por pagina, no tamanho real (com
sangria), com linhas de corte finas entre elas.

Uso:
    python gerar_pdf.py --entrada cartas_archidekt/prontas --saida cartas.pdf

    # Pagina em Carta/Letter em vez de A4:
    python gerar_pdf.py --entrada cartas_archidekt/prontas --saida cartas.pdf --pagina letter

    # Ordem customizada de pastas (por padrao: inDeck, sideboard, maybeboard):
    python gerar_pdf.py --entrada cartas_archidekt/prontas --saida cartas.pdf --sem-guias-corte

Requisitos:
    pip install reportlab
"""

import argparse
import os

from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

# tem que bater com o que foi usado no redimensionar_gimp.py
CARTA_LARGURA_MM = 69.0
CARTA_ALTURA_MM = 93.98

EXTENSOES_VALIDAS = (".png", ".jpg", ".jpeg")
SUBPASTAS_PADRAO = ("inDeck", "sideboard", "maybeboard")


def listar_imagens(pasta_entrada):
    """Retorna a lista de caminhos de imagem, olhando subpastas inDeck/sideboard/maybeboard
    se existirem, ou os arquivos direto na pasta caso contrario."""
    subpastas_existentes = [
        os.path.join(pasta_entrada, s) for s in SUBPASTAS_PADRAO
        if os.path.isdir(os.path.join(pasta_entrada, s))
    ]

    arquivos = []
    pastas_para_olhar = subpastas_existentes if subpastas_existentes else [pasta_entrada]

    for pasta in pastas_para_olhar:
        for nome in sorted(os.listdir(pasta)):
            if nome.lower().endswith(EXTENSOES_VALIDAS):
                arquivos.append(os.path.join(pasta, nome))

    return arquivos


def montar_pdf(imagens, caminho_saida, tamanho_pagina, com_guias_corte, margem_mm):
    largura_pagina, altura_pagina = tamanho_pagina
    largura_carta = CARTA_LARGURA_MM * mm
    altura_carta = CARTA_ALTURA_MM * mm
    margem = margem_mm * mm

    area_util_largura = largura_pagina - 2 * margem
    area_util_altura = altura_pagina - 2 * margem

    colunas = max(int(area_util_largura // largura_carta), 1)
    linhas = max(int(area_util_altura // altura_carta), 1)
    por_pagina = colunas * linhas

    largura_grade = colunas * largura_carta
    altura_grade = linhas * altura_carta
    offset_x = (largura_pagina - largura_grade) / 2
    offset_y = (altura_pagina - altura_grade) / 2

    c = canvas.Canvas(caminho_saida, pagesize=tamanho_pagina)

    total = len(imagens)
    print("Cartas por pagina: %d (%d colunas x %d linhas)" % (por_pagina, colunas, linhas))
    print("Total de cartas: %d -> %d pagina(s)" % (total, -(-total // por_pagina)))

    for indice, caminho_imagem in enumerate(imagens):
        posicao_na_pagina = indice % por_pagina
        if posicao_na_pagina == 0 and indice != 0:
            if com_guias_corte:
                desenhar_guias_corte(c, offset_x, offset_y, colunas, linhas, largura_carta, altura_carta)
            c.showPage()

        col = posicao_na_pagina % colunas
        lin = posicao_na_pagina // colunas

        x = offset_x + col * largura_carta
        # eixo Y do PDF cresce pra cima, entao desenhamos de cima pra baixo
        y = altura_pagina - offset_y - (lin + 1) * altura_carta

        try:
            c.drawImage(
                caminho_imagem, x, y,
                width=largura_carta, height=altura_carta,
                preserveAspectRatio=False, mask="auto",
            )
        except Exception as e:
            print("  [ERRO] %s: %s" % (os.path.basename(caminho_imagem), e))

    if com_guias_corte:
        desenhar_guias_corte(c, offset_x, offset_y, colunas, linhas, largura_carta, altura_carta)

    c.showPage()
    c.save()


def desenhar_guias_corte(c, offset_x, offset_y, colunas, linhas, largura_carta, altura_carta, tamanho_mm=3):
    """Desenha marcas de corte finas nos cantos de cada carta."""
    tamanho = tamanho_mm * mm
    c.setLineWidth(0.25)
    c.setStrokeColorRGB(0.5, 0.5, 0.5)

    largura_grade = colunas * largura_carta
    altura_grade = linhas * altura_carta

    xs = [offset_x + i * largura_carta for i in range(colunas + 1)]
    ys = [offset_y + i * altura_carta for i in range(linhas + 1)]

    for x in xs:
        for y_base in ys:
            c.line(x, y_base - tamanho, x, y_base + tamanho)
    for y in ys:
        for x_base in xs:
            c.line(x_base - tamanho, y, x_base + tamanho, y)


def main():
    parser = argparse.ArgumentParser(description="Monta um PDF pronto pra grafica com as cartas ja redimensionadas.")
    parser.add_argument("--entrada", required=True, help="Pasta 'prontas' (ou uma subpasta especifica) com as imagens")
    parser.add_argument("--saida", default="cartas.pdf", help="Caminho do PDF de saida")
    parser.add_argument("--pagina", choices=["a4", "letter"], default="a4", help="Tamanho da pagina")
    parser.add_argument("--margem-mm", type=float, default=5.0, help="Margem da pagina em mm")
    parser.add_argument("--sem-guias-corte", action="store_true", help="Nao desenhar as marcas de corte")
    args = parser.parse_args()

    tamanho_pagina = A4 if args.pagina == "a4" else letter

    imagens = listar_imagens(args.entrada)
    if not imagens:
        print("Nenhuma imagem encontrada em %s" % args.entrada)
        return

    montar_pdf(
        imagens=imagens,
        caminho_saida=args.saida,
        tamanho_pagina=tamanho_pagina,
        com_guias_corte=not args.sem_guias_corte,
        margem_mm=args.margem_mm,
    )
    print("PDF gerado em: %s" % os.path.abspath(args.saida))


if __name__ == "__main__":
    main()