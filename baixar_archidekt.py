#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
baixar_archidekt.py

Baixa as imagens de todas as cartas de um deck PUBLICO do Archidekt,
separando os arquivos em tres pastas:

    <saida>/inDeck/       -> sempre baixado
    <saida>/sideboard/    -> opcional
    <saida>/maybeboard/   -> opcional

As imagens vem do Scryfall (fonte de imagens usada pelo Archidekt).

Uso:
    python baixar_archidekt.py --deck "https://archidekt.com/decks/123456/meu-deck"
    python baixar_archidekt.py --deck 123456 --sideboard --maybeboard
    python baixar_archidekt.py --deck 123456          (modo interativo pergunta o resto)

Requisitos:
    pip install requests
"""

import argparse
import json
import os
import re
import sys
import time
import unicodedata

import requests

ARCHIDEKT_API = "https://archidekt.com/api/decks/{deck_id}/"
SCRYFALL_BY_ID = "https://api.scryfall.com/cards/{scryfall_id}?format=image"
SCRYFALL_BY_SET = "https://api.scryfall.com/cards/{codigo_set}/{numero}?format=image"
SCRYFALL_BY_NAME = "https://api.scryfall.com/cards/named?exact={nome}&format=image"

# Scryfall pede um User-Agent identificavel e no maximo ~10 requisicoes/seg.
HEADERS_SCRYFALL = {
    "User-Agent": "ArchidektProxyDownloader/1.0 (uso pessoal)",
    "Accept": "*/*",
}
HEADERS_ARCHIDEKT = {
    "User-Agent": "ArchidektProxyDownloader/1.0 (uso pessoal)",
    "Accept": "application/json",
}

PAUSA_ENTRE_REQUISICOES = 0.12  # ~8 req/s, dentro do limite pedido pelo Scryfall


def extrair_deck_id(deck_url_ou_id: str) -> str:
    """Aceita tanto uma URL completa do Archidekt quanto apenas o ID numerico."""
    texto = deck_url_ou_id.strip()
    if texto.isdigit():
        return texto
    m = re.search(r"archidekt\.com/decks/(\d+)", texto)
    if m:
        return m.group(1)
    raise ValueError(
        "Nao consegui extrair o ID do deck a partir de: %r. "
        "Use algo como 'https://archidekt.com/decks/123456/nome-do-deck' ou apenas '123456'."
        % deck_url_ou_id
    )


def buscar_deck(deck_id: str) -> dict:
    url = ARCHIDEKT_API.format(deck_id=deck_id)
    resp = requests.get(url, headers=HEADERS_ARCHIDEKT, timeout=30)
    if resp.status_code == 404:
        raise RuntimeError(
            "Deck nao encontrado (404). Confira se o link e publico e se o ID esta correto."
        )
    resp.raise_for_status()
    return resp.json()


def sanitizar_nome_arquivo(nome: str) -> str:
    nome = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    nome = re.sub(r'[<>:"/\\|?*]', "", nome)
    nome = nome.strip().replace("  ", " ")
    return nome or "carta_sem_nome"


def classificar_categoria(entrada_carta: dict) -> str:
    """
    Decide se a carta pertence ao deck principal, sideboard ou maybeboard.
    O Archidekt guarda isso na lista 'categories' de cada carta (nomes como
    'Maybeboard' / 'Sideboard' aparecem ali quando a carta esta nessas zonas).
    Qualquer carta sem essas categorias e considerada parte do deck (inDeck).
    """
    categorias = entrada_carta.get("categories") or []
    categorias_lower = [str(c).lower() for c in categorias]

    if any("maybe" in c for c in categorias_lower):
        return "maybeboard"
    if any("side" in c for c in categorias_lower):
        return "sideboard"

    # fallback defensivo, caso a API exponha em outro formato em versoes futuras
    campo_extra = str(entrada_carta.get("category", "")).lower()
    if "maybe" in campo_extra:
        return "maybeboard"
    if "side" in campo_extra:
        return "sideboard"

    return "inDeck"


def extrair_info_carta(entrada_carta: dict):
    """Extrai nome, id do scryfall, codigo do set e numero de colecionador, com varios fallbacks."""
    card = entrada_carta.get("card", {}) or {}
    oracle = card.get("oracleCard", {}) or {}

    nome = (
        oracle.get("name")
        or card.get("name")
        or entrada_carta.get("name")
        or "Carta desconhecida"
    )

    scryfall_id = (
        card.get("uid")
        or card.get("scryfallId")
        or oracle.get("uid")
        or None
    )

    edition = card.get("edition", {}) or {}
    codigo_set = edition.get("editioncode") or edition.get("code")
    numero_colecionador = card.get("collectorNumber") or card.get("collector_number")

    quantidade = int(entrada_carta.get("quantity", 1) or 1)

    return {
        "nome": nome,
        "scryfall_id": scryfall_id,
        "codigo_set": codigo_set,
        "numero_colecionador": numero_colecionador,
        "quantidade": quantidade,
    }


def baixar_bytes_imagem(info_carta: dict) -> bytes:
    """Tenta baixar a imagem da carta no Scryfall, em ordem de confiabilidade."""
    tentativas = []

    if info_carta["scryfall_id"]:
        tentativas.append(SCRYFALL_BY_ID.format(scryfall_id=info_carta["scryfall_id"]))

    if info_carta["codigo_set"] and info_carta["numero_colecionador"]:
        tentativas.append(
            SCRYFALL_BY_SET.format(
                codigo_set=info_carta["codigo_set"].lower(),
                numero=info_carta["numero_colecionador"],
            )
        )

    tentativas.append(SCRYFALL_BY_NAME.format(nome=requests.utils.quote(info_carta["nome"])))

    ultimo_erro = None
    for url in tentativas:
        try:
            resp = requests.get(url, headers=HEADERS_SCRYFALL, timeout=30, allow_redirects=True)
            if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image"):
                return resp.content
            ultimo_erro = "HTTP %s em %s" % (resp.status_code, url)
        except requests.RequestException as e:
            ultimo_erro = str(e)
        time.sleep(PAUSA_ENTRE_REQUISICOES)

    raise RuntimeError("Nao foi possivel baixar imagem para '%s' (%s)" % (info_carta["nome"], ultimo_erro))


def baixar_deck(
    deck_url_ou_id: str,
    pasta_saida: str,
    incluir_sideboard: bool,
    incluir_maybeboard: bool,
    uma_copia_por_carta: bool = False,
):
    deck_id = extrair_deck_id(deck_url_ou_id)
    print("Buscando dados do deck %s no Archidekt..." % deck_id)
    deck = buscar_deck(deck_id)

    nome_deck = deck.get("name", "deck_%s" % deck_id)
    print("Deck encontrado: %s" % nome_deck)

    cartas = deck.get("cards") or []
    if not cartas:
        raise RuntimeError("O deck nao retornou nenhuma carta. Confira se o link e publico.")

    pastas = {
        "inDeck": os.path.join(pasta_saida, "inDeck"),
        "sideboard": os.path.join(pasta_saida, "sideboard"),
        "maybeboard": os.path.join(pasta_saida, "maybeboard"),
    }
    for caminho in pastas.values():
        os.makedirs(caminho, exist_ok=True)

    contadores = {"inDeck": 0, "sideboard": 0, "maybeboard": 0}
    falhas = []

    for entrada in cartas:
        categoria = classificar_categoria(entrada)

        if categoria == "sideboard" and not incluir_sideboard:
            continue
        if categoria == "maybeboard" and not incluir_maybeboard:
            continue

        info = extrair_info_carta(entrada)
        nome_arquivo_base = sanitizar_nome_arquivo(info["nome"])

        try:
            imagem_bytes = baixar_bytes_imagem(info)
        except RuntimeError as e:
            print("  [FALHA] %s" % e)
            falhas.append(info["nome"])
            continue

        copias = 1 if uma_copia_por_carta else max(info["quantidade"], 1)
        for i in range(1, copias + 1):
            sufixo = "" if copias == 1 else "_%d" % i
            caminho_arquivo = os.path.join(
                pastas[categoria], "%s%s.png" % (nome_arquivo_base, sufixo)
            )
            with open(caminho_arquivo, "wb") as f:
                f.write(imagem_bytes)

        contadores[categoria] += copias
        print("  [OK] (%s) %s x%d" % (categoria, info["nome"], copias))
        time.sleep(PAUSA_ENTRE_REQUISICOES)

    print("\nResumo:")
    for cat, qtd in contadores.items():
        print("  %s: %d imagem(ns)" % (cat, qtd))
    if falhas:
        print("  Falharam %d carta(s): %s" % (len(falhas), ", ".join(falhas)))

    return pastas, contadores


def perguntar_sim_nao(pergunta: str) -> bool:
    resposta = input("%s [s/N]: " % pergunta).strip().lower()
    return resposta in ("s", "sim", "y", "yes")


def main():
    parser = argparse.ArgumentParser(description="Baixa imagens de um deck publico do Archidekt.")
    parser.add_argument("--deck", required=True, help="URL do deck no Archidekt ou apenas o ID")
    parser.add_argument("--saida", default="./cartas_baixadas", help="Pasta onde salvar as imagens")
    parser.add_argument("--sideboard", action="store_true", help="Tambem baixar o sideboard")
    parser.add_argument("--maybeboard", action="store_true", help="Tambem baixar o maybeboard")
    parser.add_argument(
        "--uma-copia",
        action="store_true",
        help="Baixar apenas 1 copia de cada carta, mesmo que a quantidade no deck seja maior",
    )
    parser.add_argument(
        "--nao-interativo",
        action="store_true",
        help="Nao perguntar nada no terminal; usa exatamente as flags passadas",
    )
    args = parser.parse_args()

    incluir_sideboard = args.sideboard
    incluir_maybeboard = args.maybeboard

    if not args.nao_interativo and not args.sideboard:
        incluir_sideboard = perguntar_sim_nao("Baixar tambem o SIDEBOARD?")
    if not args.nao_interativo and not args.maybeboard:
        incluir_maybeboard = perguntar_sim_nao("Baixar tambem o MAYBEBOARD?")

    baixar_deck(
        deck_url_ou_id=args.deck,
        pasta_saida=args.saida,
        incluir_sideboard=incluir_sideboard,
        incluir_maybeboard=incluir_maybeboard,
        uma_copia_por_carta=args.uma_copia,
    )


if __name__ == "__main__":
    main()
