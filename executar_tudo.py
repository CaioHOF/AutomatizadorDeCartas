#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
executar_tudo.py

Faz o processo completo em um unico comando:
  1) Baixa as imagens do deck do Archidekt (inDeck obrigatorio,
     sideboard/maybeboard opcionais).
  2) Chama o GIMP em modo batch (headless) para redimensionar cada
     carta seguindo o processo manual descrito em redimensionar_gimp.py.
  3) Salva o resultado final em "<saida>/prontas/...".
  4) Monta automaticamente um PDF pronto pra grafica em "<saida>/cartas.pdf"
     (pode ser desativado com --sem-pdf).

Uso basico:
    python executar_tudo.py --deck "https://archidekt.com/decks/123456/meu-deck"

Opcoes:
    --saida PASTA        pasta base de trabalho (padrao: ./cartas_archidekt)
    --sideboard           tambem baixa/processa o sideboard
    --maybeboard           tambem baixa/processa o maybeboard
    --uma-copia            baixa so 1 copia por carta (ignora quantidade do deck)
    --gimp CAMINHO         caminho do executavel do GIMP, se nao estiver no PATH
    --pular-download       so roda o GIMP em cima de uma pasta ja baixada antes
    --nao-interativo        nao pergunta nada no terminal
    --sem-pdf               nao gera o PDF final automaticamente
    --pdf-saida CAMINHO     caminho do PDF final (padrao: <saida>/cartas.pdf)
    --pagina a4|letter      tamanho de pagina do PDF (padrao: a4)
    --margem-mm N           margem da pagina do PDF em mm (padrao: 5)
    --sem-guias-corte       nao desenha marcas de corte no PDF

Requisitos:
    - Python 3 com "requests" e "reportlab" instalados
      (pip install requests reportlab)
    - GIMP 2.10 instalado com suporte a Python-Fu (vem por padrao na
      instalacao normal do GIMP no Windows/Mac/Linux)
"""

import argparse
import json
import os
import shutil
import subprocess
import sys

import baixar_archidekt
import gerar_pdf


CAMINHOS_GIMP_COMUNS = [
    "gimp",
    "gimp-console",
    "gimp-2.10",
    "gimp-console-2.10",
    r"C:\Program Files\GIMP 2\bin\gimp-console-2.10.exe",
    r"C:\Program Files\GIMP 2\bin\gimp-2.10.exe",
    "/Applications/GIMP-2.10.app/Contents/MacOS/gimp",
    "/usr/bin/gimp",
]


def localizar_gimp(caminho_informado):
    if caminho_informado:
        return caminho_informado
    for candidato in CAMINHOS_GIMP_COMUNS:
        if os.path.isabs(candidato):
            if os.path.isfile(candidato):
                return candidato
        else:
            encontrado = shutil.which(candidato)
            if encontrado:
                return encontrado
    return None


def montar_script_combinado(base_entrada, base_saida, incluir_side, incluir_maybe):
    """Junta o conteudo de redimensionar_gimp.py com uma chamada final,
    gerando um unico arquivo .py que o GIMP vai executar via execfile()."""
    pasta_atual = os.path.dirname(os.path.abspath(__file__))
    caminho_modulo = os.path.join(pasta_atual, "redimensionar_gimp.py")
    with open(caminho_modulo, "r", encoding="utf-8") as f:
        conteudo = f.read()

    chamada = (
        "\n\nprocessar_tudo(%r, %r, %r, %r)\n"
        % (base_entrada, base_saida, incluir_side, incluir_maybe)
    )

    caminho_temp = os.path.join(pasta_atual, "_temp_gimp_batch.py")
    with open(caminho_temp, "w", encoding="utf-8") as f:
        f.write(conteudo + chamada)

    return caminho_temp


def rodar_gimp(caminho_gimp, caminho_script_py):
    """Chama o GIMP em modo batch (sem interface) para executar o script py."""
    codigo_python = "execfile(%s)" % json.dumps(caminho_script_py)
    # escapa para virar uma string valida dentro do Script-Fu (Scheme)
    codigo_escapado = codigo_python.replace("\\", "\\\\").replace('"', '\\"')
    comando_scheme = '(python-fu-eval RUN-NONINTERACTIVE "%s")' % codigo_escapado

    args = [
        caminho_gimp,
        "-i",  # sem interface grafica
        "-d",  # sem carregar fontes/paletas extras (mais rapido)
        "-f",  # sem carregar plugins de fonte
        "-b", comando_scheme,
        "-b", "(gimp-quit 0)",
    ]

    print("Chamando o GIMP em modo batch...")
    resultado = subprocess.run(args, capture_output=True, text=True)
    print(resultado.stdout)
    if resultado.returncode != 0:
        print(resultado.stderr, file=sys.stderr)
        raise RuntimeError(
            "O GIMP terminou com erro (codigo %d). Veja a mensagem acima." % resultado.returncode
        )


def main():
    parser = argparse.ArgumentParser(description="Baixa um deck do Archidekt e prepara as cartas para impressao usando o GIMP.")
    parser.add_argument("--deck", required=not "--pular-download" in sys.argv, help="URL do deck no Archidekt ou apenas o ID")
    parser.add_argument("--saida", default="./cartas_archidekt", help="Pasta base de trabalho")
    parser.add_argument("--sideboard", action="store_true", help="Tambem baixar/processar o sideboard")
    parser.add_argument("--maybeboard", action="store_true", help="Tambem baixar/processar o maybeboard")
    parser.add_argument("--uma-copia", action="store_true", help="Baixar so 1 copia de cada carta")
    parser.add_argument("--gimp", default=None, help="Caminho do executavel do GIMP, se nao estiver no PATH")
    parser.add_argument("--pular-download", action="store_true", help="Nao baixa nada, so processa uma pasta ja existente")
    parser.add_argument("--nao-interativo", action="store_true", help="Nao pergunta nada no terminal")
    parser.add_argument("--sem-pdf", action="store_true", help="Nao gerar o PDF final automaticamente")
    parser.add_argument("--pdf-saida", default=None, help="Caminho do PDF final (padrao: <saida>/cartas.pdf)")
    parser.add_argument("--pagina", choices=["a4", "letter"], default="a4", help="Tamanho de pagina do PDF")
    parser.add_argument("--margem-mm", type=float, default=5.0, help="Margem da pagina do PDF em mm")
    parser.add_argument("--sem-guias-corte", action="store_true", help="Nao desenhar marcas de corte no PDF")
    args = parser.parse_args()

    pasta_baixadas = os.path.join(args.saida, "baixadas")
    pasta_prontas = os.path.join(args.saida, "prontas")

    incluir_sideboard = args.sideboard
    incluir_maybeboard = args.maybeboard

    if not args.pular_download:
        if not args.nao_interativo and not args.sideboard:
            incluir_sideboard = baixar_archidekt.perguntar_sim_nao("Baixar tambem o SIDEBOARD?")
        if not args.nao_interativo and not args.maybeboard:
            incluir_maybeboard = baixar_archidekt.perguntar_sim_nao("Baixar tambem o MAYBEBOARD?")

        baixar_archidekt.baixar_deck(
            deck_url_ou_id=args.deck,
            pasta_saida=pasta_baixadas,
            incluir_sideboard=incluir_sideboard,
            incluir_maybeboard=incluir_maybeboard,
            uma_copia_por_carta=args.uma_copia,
        )
    else:
        # assume que as pastas inDeck/sideboard/maybeboard ja existem em pasta_baixadas
        incluir_sideboard = incluir_sideboard or os.path.isdir(os.path.join(pasta_baixadas, "sideboard"))
        incluir_maybeboard = incluir_maybeboard or os.path.isdir(os.path.join(pasta_baixadas, "maybeboard"))

    caminho_gimp = localizar_gimp(args.gimp)
    if not caminho_gimp:
        print(
            "\nNao encontrei o GIMP instalado automaticamente.\n"
            "As imagens ja foram baixadas em: %s\n"
            "Rode novamente com --gimp \"CAMINHO_DO_GIMP\" apontando para o executavel,\n"
            "por exemplo no Windows: --gimp \"C:\\Program Files\\GIMP 2\\bin\\gimp-console-2.10.exe\""
            % pasta_baixadas
        )
        sys.exit(1)

    script_combinado = montar_script_combinado(
        os.path.abspath(pasta_baixadas),
        os.path.abspath(pasta_prontas),
        incluir_sideboard,
        incluir_maybeboard,
    )

    try:
        rodar_gimp(caminho_gimp, script_combinado)
    finally:
        if os.path.exists(script_combinado):
            os.remove(script_combinado)

    print("\nPronto! Cartas redimensionadas salvas em: %s" % os.path.abspath(pasta_prontas))

    if not args.sem_pdf:
        caminho_pdf = args.pdf_saida or os.path.join(args.saida, "cartas.pdf")
        imagens = gerar_pdf.listar_imagens(pasta_prontas)
        if not imagens:
            print("\nNenhuma imagem encontrada em %s, PDF nao foi gerado." % pasta_prontas)
        else:
            tamanho_pagina = gerar_pdf.A4 if args.pagina == "a4" else gerar_pdf.letter
            print("\nMontando o PDF final...")
            gerar_pdf.montar_pdf(
                imagens=imagens,
                caminho_saida=caminho_pdf,
                tamanho_pagina=tamanho_pagina,
                com_guias_corte=not args.sem_guias_corte,
                margem_mm=args.margem_mm,
            )
            print("PDF gerado em: %s" % os.path.abspath(caminho_pdf))


if __name__ == "__main__":
    main()