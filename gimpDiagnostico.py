#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diagnosticar_gimp.py

Testa a comunicacao com o GIMP em modo batch exatamente do mesmo jeito
que o executar_tudo.py faz, mas mostrando TUDO (stdout, stderr e o
codigo de saida), para descobrir onde esta travando.

Uso:
    python diagnosticar_gimp.py --gimp "C:\\Users\\caioh\\AppData\\Local\\Programs\\GIMP 2\\bin\\gimp-console-2.10.exe"
"""

import argparse
import json
import subprocess
import sys


def rodar_teste(caminho_gimp, codigo_python, descricao):
    codigo_escapado = codigo_python.replace("\\", "\\\\").replace('"', '\\"')
    comando_scheme = '(python-fu-eval RUN-NONINTERACTIVE "%s")' % codigo_escapado

    args = [
        caminho_gimp,
        "-i", "-d", "-f",
        "-b", comando_scheme,
        "-b", "(gimp-quit 0)",
    ]

    print("=" * 70)
    print("TESTE: %s" % descricao)
    print("Codigo Python enviado: %r" % codigo_python)
    print("-" * 70)

    resultado = subprocess.run(args, capture_output=True, text=True)

    print("Codigo de saida: %s" % resultado.returncode)
    print("--- STDOUT ---")
    print(resultado.stdout if resultado.stdout else "(vazio)")
    print("--- STDERR ---")
    print(resultado.stderr if resultado.stderr else "(vazio)")
    print()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gimp", required=True, help="Caminho do gimp-console-2.10.exe")
    args = parser.parse_args()

    rodar_teste(args.gimp, "print(2+2)", "print simples")
    rodar_teste(args.gimp, "import sys; print(sys.version)", "versao do Python usada pelo GIMP")
    rodar_teste(args.gimp, "print('ola mundo')", "print com aspas simples")

    # testa se execfile existe (Python 2) ou nao (Python 3)
    rodar_teste(
        args.gimp,
        "print('execfile existe' if 'execfile' in dir(__builtins__) else 'execfile NAO existe')",
        "checagem de execfile",
    )


if __name__ == "__main__":
    main()