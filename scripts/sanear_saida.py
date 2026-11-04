"""Tira dados pessoais de terceiros das saídas versionadas (saida/ e docs/) antes de publicar.

As saídas citam trechos das peças do SEI: nome de usuário reclamante, endereço, CPF, e-mail e telefone podem vir
junto. Este script aplica `limpar_pessoais` (fichas_atividades.py) a cada TEXTO, sem quebrar a estrutura:
CSV célula a célula, JSON e JSONL valor a valor, Markdown e HTML no texto corrido. Planilhas .xlsx são só
conferidas (regere-as a partir dos CSV se acusarem algo).

    python scripts/sanear_saida.py              # aplica e mostra o que mudou
    python scripts/sanear_saida.py --verificar  # só confere; sai com 1 se restar algo (é o que o CI roda)
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fichas_atividades import PESSOAIS, limpar_pessoais  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
PASTAS = ("saida", "docs")
TEXTO = {".csv", ".json", ".jsonl", ".md", ".html", ".bpmn", ".txt"}
# Endereços de exemplo da documentação (seu.email@exemplo.edu.br) não são dado pessoal.
EXEMPLO = re.compile(r"@(?:[\w-]+\.)*exemplo\b|\[e-mail\]|\[nome\]|\[endereço\]|\[CPF\]|\[telefone\]")
csv.field_size_limit(2**31 - 1)


def achados(texto: str) -> list[str]:
    """Trechos que o limpador ainda trocaria (ignora exemplos da documentação)."""
    out = []
    for rx, rep in PESSOAIS:
        for m in rx.finditer(texto):
            trocado = rx.sub(rep, m.group(0))
            if trocado != m.group(0) and not EXEMPLO.search(m.group(0)):
                out.append(m.group(0))
    return out


def _folhas(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, list):
        for x in obj:
            yield from _folhas(x)
    elif isinstance(obj, dict):
        for x in obj.values():
            yield from _folhas(x)


def achados_arquivo(texto: str, sufixo: str) -> list[str]:
    """Confere célula a célula (CSV) e valor a valor (JSON): o separador do CSV não vira parte de um endereço."""
    if sufixo == ".csv":
        partes = [c for ln in csv.reader(io.StringIO(texto, newline="")) for c in ln]
    elif sufixo == ".jsonl":
        partes = [s for ln in texto.splitlines() if ln.strip() for s in _folhas(json.loads(ln))]
    elif sufixo == ".json":
        partes = list(_folhas(json.loads(texto)))
    else:
        partes = [texto]
    return [x for s in partes for x in achados(s)]


def _ler(p: Path) -> tuple[str, str]:
    bruto = p.read_bytes()
    cod = "utf-8-sig" if bruto.startswith(b"\xef\xbb\xbf") else "utf-8"
    return bruto.decode(cod), cod


def _csv(texto: str) -> str:
    linhas = list(csv.reader(io.StringIO(texto, newline="")))
    buf = io.StringIO(newline="")
    fim = "\r\n" if "\r\n" in texto[:5000] else "\n"
    csv.writer(buf, lineterminator=fim).writerows([[limpar_pessoais(c) for c in ln] for ln in linhas])
    return buf.getvalue()


def _jsonl(texto: str) -> str:
    out = []
    for ln in texto.splitlines(keepends=True):
        corpo = ln.rstrip("\r\n")
        out.append(json.dumps(limpar_pessoais(json.loads(corpo)), ensure_ascii=False) + ln[len(corpo):]
                   if corpo.strip() else ln)
    return "".join(out)


def _json(texto: str) -> str:
    recuo = 1
    m = re.match(r"[\[{]\r?\n( +)", texto)
    if m:
        recuo = len(m.group(1))
    elif "\n" not in texto.strip():
        recuo = None
    fim = "\n" if texto.endswith("\n") else ""
    return json.dumps(limpar_pessoais(json.loads(texto)), ensure_ascii=False, indent=recuo) + fim


def _texto(texto: str) -> str:
    def troca(m):
        return m.group(0) if EXEMPLO.search(m.group(0)) else limpar_pessoais(m.group(0))
    for rx, _ in PESSOAIS:
        texto = rx.sub(troca, texto)
    return texto


def arquivos():
    for pasta in PASTAS:
        for p in sorted((RAIZ / pasta).rglob("*")):
            if p.is_file() and (p.suffix in TEXTO or p.suffix == ".xlsx"):
                yield p


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--verificar", action="store_true", help="só confere, não altera")
    a = ap.parse_args()
    restos, mudados = {}, 0
    for p in arquivos():
        rel = p.relative_to(RAIZ).as_posix()
        if p.suffix == ".xlsx":
            with zipfile.ZipFile(p) as z:
                xml = " ".join(z.read(n).decode("utf-8", "ignore") for n in z.namelist() if n.endswith(".xml"))
            if achados(re.sub(r"<[^>]+>", " ", xml)):
                restos[rel] = achados(re.sub(r"<[^>]+>", " ", xml))
            continue
        texto, cod = _ler(p)
        if not achados_arquivo(texto, p.suffix):
            continue
        if a.verificar:
            restos[rel] = achados_arquivo(texto, p.suffix)
            continue
        f = {".csv": _csv, ".jsonl": _jsonl, ".json": _json}.get(p.suffix, _texto)
        novo = f(texto)
        if novo != texto:
            p.write_bytes(novo.encode(cod))
            mudados += 1
            print(f"limpo: {rel} ({len(achados_arquivo(texto, p.suffix))} trechos)")
        if achados_arquivo(novo, p.suffix):
            restos[rel] = achados_arquivo(novo, p.suffix)
    for rel, v in restos.items():
        print(f"RESTA em {rel}: {len(v)} trecho(s), ex.: {v[0][:60]!r}")
    if not a.verificar:
        print(f"{mudados} arquivo(s) limpo(s)")
    return 1 if restos else 0


if __name__ == "__main__":
    sys.exit(main())
