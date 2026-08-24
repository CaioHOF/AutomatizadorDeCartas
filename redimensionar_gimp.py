# -*- coding: utf-8 -*-
"""
redimensionar_gimp.py

Este arquivo NAO deve ser rodado com "python redimensionar_gimp.py".
Ele contem funcoes escritas para a API Python-Fu do GIMP (gimpfu) e
so funciona executado DENTRO do GIMP (o script executar_tudo.py faz
isso automaticamente, chamando o GIMP em modo batch).

Reproduz o processo manual descrito:
  1) Novo documento: 69mm x 93,98mm, resolucao 300dpi (=4,16667 px/pt),
     preenchido com transparencia.
     -> 69mm largura / 93,98mm altura = a carta (63x88mm) + ~3mm de
        sangria em cada lado. Se no seu GIMP a orientacao ficar
        "deitada", troque CANVAS_LARGURA_MM e CANVAS_ALTURA_MM abaixo.
  2) Nova camada do mesmo tamanho, cantos arredondados, pintada de preto.
  3) A imagem da carta e inserida, redimensionada para 63mm x 88mm com
     interpolacao NoHalo, e centralizada.
  4) Resultado exportado em PNG (com transparencia) para a pasta "prontas".
"""

from gimpfu import *
import os

# ---------------------- Configuracoes ----------------------
DPI = 300.0                  # 4,16667 px/pt = 300 / 72 = 300 dpi
CANVAS_LARGURA_MM = 69.0     # largura do canvas final (carta + sangria)
CANVAS_ALTURA_MM = 93.98     # altura do canvas final (carta + sangria)
CARTA_LARGURA_MM = 63.0      # largura da carta
CARTA_ALTURA_MM = 88.0       # altura da carta
RAIO_CANTO_MM = 3.0          # raio dos cantos arredondados da camada preta
RAIO_CANTO_CARTA_MM = 4.0    # raio dos cantos arredondados da propria carta (remove rebarbas)

EXTENSOES_VALIDAS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")


def mm_para_px(mm, dpi=DPI):
    return int(round((mm / 25.4) * dpi))


def processar_uma_carta(caminho_entrada, caminho_saida):
    largura_canvas = mm_para_px(CANVAS_LARGURA_MM)
    altura_canvas = mm_para_px(CANVAS_ALTURA_MM)
    largura_carta = mm_para_px(CARTA_LARGURA_MM)
    altura_carta = mm_para_px(CARTA_ALTURA_MM)
    raio = mm_para_px(RAIO_CANTO_MM)

    # 1) novo documento transparente -----------------------------------
    imagem = gimp.Image(largura_canvas, altura_canvas, RGB)
    pdb.gimp_image_set_resolution(imagem, DPI, DPI)

    fundo = gimp.Layer(
        imagem, "fundo", largura_canvas, altura_canvas, RGBA_IMAGE, 100, LAYER_MODE_NORMAL
    )
    imagem.insert_layer(fundo)
    pdb.gimp_drawable_fill(fundo, FILL_TRANSPARENT)

    # 2) camada preta com cantos arredondados ---------------------------
    preto = gimp.Layer(
        imagem, "preto", largura_canvas, altura_canvas, RGBA_IMAGE, 100, LAYER_MODE_NORMAL
    )
    imagem.insert_layer(preto, position=0)
    pdb.gimp_drawable_fill(preto, FILL_TRANSPARENT)

    pdb.gimp_context_set_foreground((0, 0, 0))
    pdb.gimp_image_select_rectangle(imagem, CHANNEL_OP_REPLACE, 0, 0, largura_canvas, altura_canvas)
    pdb.gimp_edit_fill(preto, FILL_FOREGROUND)
    pdb.gimp_selection_none(imagem)

    # recorta os cantos arredondados (fora do arredondado vira transparente)
    pdb.gimp_image_select_round_rectangle(
        imagem, CHANNEL_OP_REPLACE, 0, 0, largura_canvas, altura_canvas, raio, raio
    )
    pdb.gimp_selection_invert(imagem)
    pdb.gimp_edit_clear(preto)
    pdb.gimp_selection_none(imagem)

    # 3) insere a imagem da carta, redimensiona (NoHalo) e centraliza ---
    imagem_carta = pdb.gimp_file_load(caminho_entrada, os.path.basename(caminho_entrada))
    camada_carta = pdb.gimp_layer_new_from_drawable(imagem_carta.active_drawable, imagem)
    imagem.insert_layer(camada_carta, position=0)
    camada_carta.name = "carta"

    # garante canal alfa: sem isso, "limpar" pixels preenche com BRANCO
    # (cor de fundo) em vez de ficar transparente
    if not pdb.gimp_drawable_has_alpha(camada_carta):
        pdb.gimp_image_set_active_layer(imagem, camada_carta)
        pdb.gimp_layer_add_alpha(camada_carta)

    pdb.gimp_context_set_interpolation(INTERPOLATION_NOHALO)
    pdb.gimp_layer_scale(camada_carta, largura_carta, altura_carta, False)

    # forca cada pixel a ficar 100% opaco ou 100% transparente, eliminando
    # qualquer franja/penumbra semi-transparente que a imagem original ou a
    # propria interpolacao do redimensionamento possa ter deixado na borda
    pdb.gimp_levels(camada_carta, HISTOGRAM_ALPHA, 128, 255, 1.0, 0, 255)

    offset_x = (largura_canvas - largura_carta) // 2
    offset_y = (altura_canvas - altura_carta) // 2
    pdb.gimp_layer_set_offsets(camada_carta, offset_x, offset_y)

    pdb.gimp_image_delete(imagem_carta)

    # corta a propria camada da carta com cantos limpos, removendo qualquer
    # "rebarba"/franja branca residual da anti-serrilhagem da imagem original
    raio_carta = mm_para_px(RAIO_CANTO_CARTA_MM)
    pdb.gimp_image_select_round_rectangle(
        imagem, CHANNEL_OP_REPLACE, offset_x, offset_y, largura_carta, altura_carta, raio_carta, raio_carta
    )
    pdb.gimp_selection_invert(imagem)
    pdb.gimp_edit_clear(camada_carta)
    pdb.gimp_selection_none(imagem)

    # 4) achata (mantendo alpha) e exporta em PNG ------------------------
    camada_final = pdb.gimp_image_merge_visible_layers(imagem, CLIP_TO_IMAGE)
    pdb.file_png_save(
        imagem, camada_final, caminho_saida, caminho_saida, 0, 9, 1, 1, 1, 1, 1
    )
    pdb.gimp_image_delete(imagem)


def processar_pasta(pasta_entrada, pasta_saida):
    if not os.path.isdir(pasta_entrada):
        print("Pasta nao encontrada, pulando: %s" % pasta_entrada)
        return
    if not os.path.isdir(pasta_saida):
        os.makedirs(pasta_saida)

    for nome in sorted(os.listdir(pasta_entrada)):
        if not nome.lower().endswith(EXTENSOES_VALIDAS):
            continue
        origem = os.path.join(pasta_entrada, nome)
        nome_saida = os.path.splitext(nome)[0] + ".png"
        destino = os.path.join(pasta_saida, nome_saida)
        try:
            processar_uma_carta(origem, destino)
            print("OK: %s" % nome)
        except Exception as e:
            print("ERRO em %s: %s" % (nome, e))


def processar_tudo(base_entrada, base_saida, incluir_side, incluir_maybe):
    processar_pasta(os.path.join(base_entrada, "inDeck"), os.path.join(base_saida, "inDeck"))
    if incluir_side:
        processar_pasta(os.path.join(base_entrada, "sideboard"), os.path.join(base_saida, "sideboard"))
    if incluir_maybe:
        processar_pasta(os.path.join(base_entrada, "maybeboard"), os.path.join(base_saida, "maybeboard"))
    print("Processamento no GIMP concluido.")