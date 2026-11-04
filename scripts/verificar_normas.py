"""Confere cada trecho de saida/fase3/normas_<cod>.json contra o texto integral da norma na base normativa
(BASE_NORMAS/TEXTOS_NORMAS do perfil).

Comparação literal depois de normalizar espaços, aspas, travessões e caixa. Trecho de fonte externa (fora da base) vai
para a lista de conferência manual, com a URL. Sai com código 1 se algum trecho da base não for achado."""
from __future__ import annotations

import json
import re
import sys
import unicodedata

from comum import BASE_NORMAS, CODIGOS_FASE3, SAIDA, TEXTOS_NORMAS

OUT = SAIDA / "fase3"
PASTA = TEXTOS_NORMAS  # raiz dos caminhos da coluna txt da base


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).lower()
    s = re.sub(r"[“”\"«»]", '"', s)
    s = re.sub(r"[‘’`´]", "'", s)
    s = re.sub(r"[–—−‐-]", "-", s)
    s = re.sub(r"\s*-\s*\n\s*", "", s)  # hifenização de quebra de linha
    return re.sub(r"\s+", " ", s).strip()


def verificar(cod: str) -> tuple[list, list]:
    d = json.loads((OUT / f"normas_{cod}.json").read_text(encoding="utf-8"))
    falhas, externas, cache = [], [], {}
    for n in d["normas"]:
        f = n.get("fonte") or {}
        if f.get("base") == "externa" or not f.get("txt"):
            externas.append((n["id"], f.get("url")))
            continue
        if f["txt"] not in cache:
            arq = PASTA / f["txt"]
            cache[f["txt"]] = norm(arq.read_text(encoding="utf-8", errors="replace")) if arq.exists() else None
        texto = cache[f["txt"]]
        if texto is None:
            falhas.append((n["id"], "texto não encontrado: " + f["txt"]))
        elif norm(n["trecho"]).strip(" .;\"'…") not in texto:
            falhas.append((n["id"], "trecho não achado no texto"))
    return falhas, externas


def main(codigos: list[str]) -> int:
    if not BASE_NORMAS.exists():
        print(f"aviso: sem base normativa ({BASE_NORMAS}); trechos NÃO conferidos")
        return 0
    erro = 0
    for cod in codigos:
        if not (OUT / f"normas_{cod}.json").exists():
            print(f"aviso: {cod} sem saida/fase3/normas_{cod}.json (curadoria); pulado")
            continue
        falhas, externas = verificar(cod)
        print(f"{cod}: {len(falhas)} trecho(s) sem correspondência; {len(externas)} de fonte externa")
        for i, m in falhas:
            print("  ✗", i, m)
        for i, u in externas:
            print("  ↗", i, u)
        erro |= bool(falhas)
    return int(erro)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or CODIGOS_FASE3))
