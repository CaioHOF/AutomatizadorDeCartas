#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
executar_tudo.py

Faz o processo completo em um unico comando:
  1) Baixa as imagens do deck do Archidekt (inDeck obrigatorio,
     sideboard/maybeboard opcionais).
  2) Chama o GIMP em modo batch (headless) para redimensionar cada carta
     seguindo o processo manual descrito em redimensionar_gimp.py.
  3) O GIMP salva cada carta como PNG (com transparencia). Em seguida,
     este script converte cada PNG em um PDF individual (pagina no
     tamanho fisico exato da carta) e apaga o PNG, deixando so o PDF em
     "<saida>/prontas/...".

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
    --pdf-grade             (opcional) alem dos PDFs individuais, tambem monta
                             um unico PDF com varias cartas por pagina (requer
                             "pip install reportlab"). OBS: essa opcao le
                             arquivos .png/.jpg em "prontas/", que nao sao mais
                             gerados por padrao -- so use --pdf-grade se voce
                             tambem gerar essas imagens por outro meio.
    --pagina a4|letter      [--pdf-grade] tamanho de pagina
    --margem-mm N           [--pdf-grade] margem da pagina em mm (padrao: 5)
    --sem-guias-corte       [--pdf-grade] nao desenha marcas de corte

Requisitos:
    - Python 3 com "requests" e "img2pdf" instalados
      (pip install requests img2pdf)
    - GIMP 2.10 instalado com suporte a Python-Fu (vem por padrao na
      instalacao normal do GIMP no Windows/Mac/Linux)
    - reportlab so e necessario se usar --pdf-grade (pip install reportlab)
"""

import argparse
import json
import os
import shutil
import subprocess
import sys

import baixar_archidekt


def converter_pngs_para_pdf_e_apagar(pasta_prontas):
    """Converte cada PNG dentro de inDeck/sideboard/maybeboard em um PDF de
    mesmo nome (pagina no tamanho fisico exato, preservado a partir do DPI
    do PNG) e apaga o PNG, deixando so o PDF."""
    import img2pdf

    subpastas = ("inDeck", "sideboard", "maybeboard")
    convertidos = 0
    falhas = []

    pastas_existentes = [
        os.path.join(pasta_prontas, s) for s in subpastas
        if os.path.isdir(os.path.join(pasta_prontas, s))
    ] or [pasta_prontas]

    for pasta in pastas_existentes:
        for nome in sorted(os.listdir(pasta)):
            if not nome.lower().endswith(".png"):
                continue
            caminho_png = os.path.join(pasta, nome)
            caminho_pdf = os.path.join(pasta, os.path.splitext(nome)[0] + ".pdf")
            try:
                with open(caminho_pdf, "wb") as f:
                    f.write(img2pdf.convert(caminho_png))
                os.remove(caminho_png)
                convertidos += 1
            except Exception as e:
                print("  [ERRO ao converter] %s: %s" % (nome, e))
                falhas.append(nome)

    print("PNG -> PDF convertidos: %d" % convertidos)
    if falhas:
        print("Falharam: %d arquivo(s)" % len(falhas))


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
    parser.add_argument("--pdf-grade", action="store_true",
                         help="Alem dos PDFs individuais, monta tambem um unico PDF em grade (requer reportlab)")
    parser.add_argument("--pdf-grade-saida", default=None, help="Caminho do PDF em grade (padrao: <saida>/cartas_grade.pdf)")
    parser.add_argument("--pagina", choices=["a4", "letter"], default="a4", help="[--pdf-grade] Tamanho de pagina")
    parser.add_argument("--margem-mm", type=float, default=5.0, help="[--pdf-grade] Margem da pagina em mm")
    parser.add_argument("--sem-guias-corte", action="store_true", help="[--pdf-grade] Nao desenhar marcas de corte")
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

    print("\nConvertendo PNG -> PDF (um arquivo por carta)...")
    converter_pngs_para_pdf_e_apagar(pasta_prontas)

    print("\nPronto! Cada carta ja foi salva como PDF individual dentro de: %s" % os.path.abspath(pasta_prontas))

    if args.pdf_grade:
        import gerar_pdf  # import tardio: so exige reportlab se essa opcao for usada
        caminho_pdf = args.pdf_grade_saida or os.path.join(args.saida, "cartas_grade.pdf")
        imagens = gerar_pdf.listar_imagens(pasta_prontas)
        if not imagens:
            print("\nNenhuma imagem encontrada em %s, PDF em grade nao foi gerado." % pasta_prontas)
        else:
            tamanho_pagina = gerar_pdf.A4 if args.pagina == "a4" else gerar_pdf.letter
            print("\nMontando o PDF em grade...")
            gerar_pdf.montar_pdf(
                imagens=imagens,
                caminho_saida=caminho_pdf,
                tamanho_pagina=tamanho_pagina,
                com_guias_corte=not args.sem_guias_corte,
                margem_mm=args.margem_mm,
            )
            print("PDF em grade gerado em: %s" % os.path.abspath(caminho_pdf))


if __name__ == "__main__":
    main()