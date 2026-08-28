# Archidekt → Cartas prontas para gráfica

Baixa as imagens de um deck **público** do Archidekt e já deixa cada carta no
tamanho certo para impressão (com sangria, cantos arredondados e fundo preto),
seguindo exatamente o processo manual que você faz hoje no GIMP — e entrega
cada carta já em **PDF individual**, pronta pra gráfica.

## O que o projeto faz

1. **`baixar_archidekt.py`** — baixa as imagens (via Scryfall) de todas as
   cartas do deck, separando em três pastas:
   - `inDeck/` → **sempre baixado**
   - `sideboard/` → opcional
   - `maybeboard/` → opcional

2. **`redimensionar_gimp.py`** — script que roda **dentro do GIMP** e repete o
   processo manual:
   - Novo documento **69 mm × 93,98 mm**, 300 dpi (equivale à resolução
     4,16667 px/pt que você usa), fundo transparente.
   - Nova camada do mesmo tamanho, cantos arredondados, pintada de preto.
   - Insere a imagem da carta redimensionada para **63 mm × 88 mm** com
     interpolação **NoHalo**, centralizada.
   - Exporta como PNG (com transparência) para a pasta `prontas/`.

3. **`executar_tudo.py`** — faz o download, chama o GIMP, e depois **converte
   cada PNG em um PDF individual** (mesmo tamanho físico exato da carta,
   herdado automaticamente do DPI do PNG) e **apaga o PNG**, deixando só o
   PDF — tudo em um único comando.

4. **`gerar_pdf.py`** — opcional. Junta as cartas num único PDF com várias
   por página em folha A4/Letter, com marcas de corte (útil se a gráfica
   pedir um arquivo só em vez de um por carta). Veja a seção própria abaixo.

> **Sobre as medidas**: 69×93,98mm é a carta (63×88mm) + ~3mm de sangria em
> cada lado — o padrão para mandar para gráfica. Se ao abrir o GIMP você
> perceber que ficou "deitado" (largura e altura trocadas), edite as
> constantes `CANVAS_LARGURA_MM` / `CANVAS_ALTURA_MM` no topo do arquivo
> `redimensionar_gimp.py`.

## Requisitos

- **Python 3** + bibliotecas `requests` e `img2pdf`:
  ```bash
  pip install requests img2pdf
  ```
- **GIMP 2.10** instalado (com suporte a Python-Fu, que já vem por padrão nos
  instaladores oficiais do GIMP para Windows/Mac/Linux).
- `reportlab` só é necessário se for usar o `gerar_pdf.py` / `--pdf-grade`
  (PDF único com várias cartas por página):
  ```bash
  pip install reportlab
  ```


## Como usar

Rode tudo de uma vez (ele te pergunta se quer incluir sideboard/maybeboard):

```bash
python executar_tudo.py --deck "https://archidekt.com/decks/123456/meu-deck"
```

Ou já direto, sem perguntas:

```bash
python executar_tudo.py --deck 123456 --sideboard --maybeboard --nao-interativo
```

Se o GIMP não estiver no PATH do sistema, informe o caminho:

```bash
python executar_tudo.py --deck 123456 --gimp "C:\Program Files\GIMP 2\bin\gimp-console-2.10.exe"
```

### Rodar as etapas separadamente

Só baixar as imagens:
```bash
python baixar_archidekt.py --deck 123456 --saida ./cartas_archidekt/baixadas --sideboard
```

Depois, só redimensionar uma pasta já baixada:
```bash
python executar_tudo.py --pular-download --saida ./cartas_archidekt --gimp gimp
```

## Estrutura de pastas gerada

```
cartas_archidekt/
├── baixadas/
│   ├── inDeck/
│   ├── sideboard/
│   └── maybeboard/
└── prontas/
    ├── inDeck/
    ├── sideboard/
    └── maybeboard/
```

As imagens em `prontas/` são as que você manda para a gráfica — cada carta já
sai como `.png` **e** `.pdf` individual (o PDF já é gerado direto pelo GIMP,
sem etapa extra).

## PDF único com várias cartas por página (opcional)

Se a gráfica pedir um único arquivo em vez de um PDF por carta, use o
`gerar_pdf.py` (ou passe `--pdf-grade` para o `executar_tudo.py`):

```bash
pip install reportlab
python executar_tudo.py --deck "..." --gimp "..." --pdf-grade
```

Isso gera, além dos PDFs individuais, um `cartas_grade.pdf` com várias cartas
por página A4 (ou Letter, com `--pagina letter`), coladas lado a lado no
tamanho real, com marcas de corte nos cantos de cada carta.

Também dá pra rodar isso separadamente, a qualquer momento, sobre uma pasta
já processada:
```bash
python gerar_pdf.py --entrada cartas_archidekt/prontas --saida cartas_grade.pdf --modo grade
```

## Observações

- O link do Archidekt precisa ser **público** (sem login).
- Por padrão, cada carta é baixada em tantas cópias quanto a quantidade no
  deck (ex.: 4x Sol Ring vira 4 arquivos), pensando em impressão física. Use
  `--uma-copia` se quiser só uma imagem por carta única.
- As imagens vêm do Scryfall; o script respeita o limite de requisições
  pedido por eles (uma pequena pausa entre downloads).
- Use essas cartas apenas para fins pessoais (proxies para jogar/testar);
  respeite os direitos autorais da arte e do nome das cartas.