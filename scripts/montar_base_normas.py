"""Monta a base normativa mínima (sqlite) que a fase 3 lê — para órgão que não tem uma base pronta.

Na AGENERSA a base é a do Especialista AGENERSA (milhares de normas, deliberações e dispositivos já mapeados). Este
script não reproduz aquele pipeline: monta só o que `volume_anual.py`, `normas_processo.py` e `verificar_normas.py`
leem, a partir de
  --textos        pasta com o texto integral das normas (.txt; .pdf com pypdf e .html/.htm opcionais), um arquivo por
                  norma. O nome identifica a norma (LEI-5619-2009.txt, DEC_48209_2022.pdf, IN-001-2007.html...) ou
                  vem do índice --normas;
  --deliberacoes  planilha (.csv ou .xlsx) com as deliberações/decisões do órgão: numero, data ou ano, processo,
                  tipo_decisao, tema, ementa e, opcional, dispositivos (citações separadas por ";");
  --normas        (opcional) índice .csv: arquivo, tipo, numero, ano, titulo, tabela (normativo | legislacao_externa),
                  url — para nomes de arquivo fora do padrão, título e URL;
  --citacoes      (opcional) citações livres para o mapa de dispositivos: extractions.parquet do relator/coletor
                  (campo dispositivos_citados), .csv (1ª coluna) ou .txt (uma por linha);
  --contratos     (opcional) .csv com concessionaria_canonica, id_canonico, tipo, vigente (contratos de concessão).
Os textos são copiados (PDF/HTML convertidos) para <pasta do sqlite>/txt/, e a coluna txt guarda o caminho relativo à
pasta-avó do sqlite — a mesma convenção da base do Especialista (TEXTOS_NORMAS em comum.py).
Esquema e exemplos: docs/adaptacao/BASE_NORMATIVA.md.

Uso:
  python montar_base_normas.py --textos ../dados/normas/brutos --deliberacoes ../dados/normas/deliberacoes.csv
  python montar_base_normas.py ... --saida ../dados/normas/base_normas.sqlite   (padrão: BASE_NORMAS do perfil)"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sqlite3
from pathlib import Path

import pandas as pd

from comum import BASE_NORMAS

# sigla do disp_id → (nome por extenso no rótulo, tipo canônico, regex que reconhece a citação)
# a ordem importa: "lei complementar" antes de "lei", "instrução normativa" antes de qualquer outra
TIPOS = [
    ("LC", "Lei Complementar", "lei", r"lei\s+complementar"),
    ("LEI", "Lei", "lei", r"lei"),
    ("DEC", "Decreto", "decreto", r"decreto"),
    ("IN", "Instrução Normativa", "instrucao_normativa", r"instru[çc][ãa]o\s+normativa"),
    ("RES", "Resolução", "resolucao", r"resolu[çc][ãa]o"),
    ("DELIB", "Deliberação", "deliberacao", r"delibera[çc][ãa]o"),
    ("PORT", "Portaria", "portaria", r"portaria"),
]
NOME = {s: (n, t) for s, n, t, _ in TIPOS}
_NUM = r"n?[º°o.]*\s*(\d{1,3}(?:\.\d{3})+|\d+)"  # 5.619 | 5619 | 001
_ANO = r"(?:/|,?\s+de\s+(?:\d{1,2}(?:º|°)?\s+de\s+\w+\s+de\s+)?)(\d{4}|\d{2})\b"  # /2009 | , de 22 de dezembro de 2009
RX_CITACAO = [(s, re.compile(rf"\b{rx}\b[^0-9;]{{0,80}}?{_NUM}\s*{_ANO}", re.I)) for s, _, _, rx in TIPOS]
RX_ARTIGO = re.compile(r"\bart(?:igo)?s?\.?\s*(\d+)", re.I)
RX_ARQUIVO = re.compile(r"^(LC|LEI|DEC|IN|RES|DELIB|PORT)[-_ ]?(\d+)[-_ ](\d{4})", re.I)
RX_ART_TEXTO = re.compile(r"^\s*Art(?:igo)?\.?\s*(\d+)", re.I | re.M)


def limpa(s) -> str:
    """Mesma limpeza de normas_processo.py: o mapa é consultado com a citação limpa."""
    return re.sub(r"\s+", " ", str(s)).strip()


def _ano(a: str) -> int:
    a = int(a)
    return a if a >= 100 else (2000 + a if a <= 30 else 1900 + a)


def raiz(sig: str, num, ano) -> str:
    return f"{sig}:{int(str(num).replace('.', ''))}/{int(ano)}"


def rotulo(disp_id: str) -> str:
    """'LEI:5619/2009' → 'Lei nº 5.619/2009'; 'LEI:5619/2009:art5' → 'Lei nº 5.619/2009, art. 5º'."""
    partes = disp_id.split(":")
    sig, (num, ano) = partes[0], partes[1].split("/")
    r = f"{NOME[sig][0]} nº {int(num):,}".replace(",", ".") + f"/{ano}"
    if len(partes) > 2:
        n = int(partes[2][3:])
        r += f", art. {n}{'º' if n < 10 else ''}"
    return r


def normalizar(citacao: str) -> str | None:
    """Citação livre → disp_id ('LEI:5619/2009' ou 'LEI:5619/2009:art5'); None se não reconhecer a norma.
    O artigo só conta se vier antes da norma ("art. 5º da Lei nº 5.619/2009" ou "art. 5º, Lei 5.619/2009")."""
    s = limpa(citacao)
    achados = [(m.start(), sig, m) for sig, rx in RX_CITACAO for m in rx.finditer(s)]
    if not achados:
        return None
    ini, sig, m = min(achados, key=lambda x: (x[0], [t[0] for t in TIPOS].index(x[1])))
    d = raiz(sig, m.group(1), _ano(m.group(2)))
    art = RX_ARTIGO.search(s[:ini]) or RX_ARTIGO.search(s[m.end():m.end() + 12])
    return f"{d}:art{int(art.group(1))}" if art else d


def ler_texto(arq: Path) -> str:
    suf = arq.suffix.lower()
    if suf == ".txt":
        return arq.read_text(encoding="utf-8", errors="replace")
    if suf == ".pdf":
        from pypdf import PdfReader  # opcional: só para PDF
        return "\n".join(p.extract_text() or "" for p in PdfReader(arq).pages)
    if suf in (".html", ".htm"):
        t = arq.read_text(encoding="utf-8", errors="replace")
        t = re.sub(r"(?is)<(script|style).*?</\1>", " ", t)
        t = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</tr>|</h\d>", "\n", t)
        return html.unescape(re.sub(r"<[^>]+>", " ", t))
    raise ValueError(f"formato não suportado: {arq.name}")


def ler_planilha(arq: Path) -> pd.DataFrame:
    if arq.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(arq, dtype=str)
    return pd.read_csv(arq, dtype=str, sep=None, engine="python", encoding="utf-8-sig")


def citacoes_livres(arq: Path) -> list[str]:
    if arq.suffix.lower() == ".parquet":
        ext = pd.read_parquet(arq, columns=["extraction_json"])
        return [x for j in ext.extraction_json for x in (json.loads(j).get("dispositivos_citados") or [])]
    if arq.suffix.lower() == ".csv":
        return pd.read_csv(arq, dtype=str).iloc[:, 0].dropna().tolist()
    return [x for x in arq.read_text(encoding="utf-8").splitlines() if x.strip()]


ESQUEMA = """
create table normativo (id_canonico text primary key, titulo text, tipo text, numero_norma text, ano integer,
                        txt text, url_documento text);
create table legislacao_externa (id_canonico text primary key, titulo text, tipo text, numero_norma text,
                                 ano integer, txt text, url_documento text, disp_id text);
create table dispositivos_canonicos (disp_id text primary key, rotulo text, tipo text, pai_id text, nivel integer);
create table dispositivo_map (string_original text primary key, disp_id text, metodo text);
create table deliberacoes (numero text, data text, ano integer, processo text, tema text,
                           tipo_decisao text, ementa_catalogo text);
create table dispositivos_legais (numero text, dispositivo_legal text);
create table contratos_concessao (concessionaria_canonica text, id_canonico text, tipo text, vigente integer);
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--textos", type=Path, required=True)
    ap.add_argument("--deliberacoes", type=Path, required=True)
    ap.add_argument("--normas", type=Path)
    ap.add_argument("--citacoes", type=Path, action="append", default=[])
    ap.add_argument("--contratos", type=Path)
    ap.add_argument("--saida", type=Path, default=BASE_NORMAS)
    args = ap.parse_args()
    saida = args.saida.resolve()
    pasta_txt, raiz_textos = saida.parent / "txt", saida.parents[1]
    pasta_txt.mkdir(parents=True, exist_ok=True)
    if saida.exists():
        saida.unlink()  # a base é sempre remontada do zero a partir dos insumos
    con = sqlite3.connect(saida)
    con.executescript(ESQUEMA)

    # ---- normas com texto integral
    indice = {}
    if args.normas:
        for r in ler_planilha(args.normas).fillna("").to_dict("records"):
            indice[r["arquivo"]] = r
    canon = {}  # disp_id → (rótulo, tipo, pai, nível)

    def registrar(d: str) -> None:
        partes = d.split(":")
        r = ":".join(partes[:2])
        canon.setdefault(r, (rotulo(r), NOME[partes[0]][1], None, 0))
        if len(partes) > 2:
            canon.setdefault(d, (rotulo(d), NOME[partes[0]][1], r, 1))

    sem_id = []
    for arq in sorted(p for p in args.textos.rglob("*") if p.suffix.lower() in (".txt", ".pdf", ".html", ".htm")):
        meta = indice.get(arq.name, {})
        m = RX_ARQUIVO.match(arq.stem)
        sig, num, ano = ((meta["tipo"].upper(), meta["numero"], meta["ano"]) if meta.get("tipo")
                         else (m.group(1).upper(), m.group(2), m.group(3)) if m else (None, None, None))
        if sig not in NOME:
            sem_id.append(arq.name)
            continue
        d = raiz(sig, num, ano)
        destino = pasta_txt / f"{sig}-{int(num)}-{int(ano)}.txt"
        texto = ler_texto(arq)
        destino.write_text(texto, encoding="utf-8")
        tab = meta.get("tabela") or "normativo"
        id_c = f"{sig}-{int(num):03d}/{int(ano)}"  # normas_processo procura 'IN-001/2007' e 'IN-1/2007'
        cols = dict(id_canonico=id_c, titulo=meta.get("titulo") or rotulo(d), tipo=NOME[sig][1],
                    numero_norma=f"{int(num)}/{int(ano)}", ano=int(ano),
                    txt=Path(os.path.relpath(destino, raiz_textos)).as_posix(), url_documento=meta.get("url") or None)
        if tab == "legislacao_externa":
            cols["disp_id"] = d
        con.execute(f"insert or replace into {tab} ({', '.join(cols)}) values ({', '.join('?' * len(cols))})",
                    list(cols.values()))
        registrar(d)
        for n in sorted({int(a) for a in RX_ART_TEXTO.findall(texto)}):
            registrar(f"{d}:art{n}")

    # ---- deliberações e dispositivos citados nelas
    dl = ler_planilha(args.deliberacoes)
    if "ementa_catalogo" not in dl and "ementa" in dl:
        dl = dl.rename(columns={"ementa": "ementa_catalogo"})
    faltam = {"numero", "processo", "tipo_decisao"} - set(dl.columns)
    if faltam:
        raise SystemExit(f"planilha de deliberações sem as colunas: {sorted(faltam)}")
    if "ano" not in dl:
        if "data" not in dl:
            raise SystemExit("planilha de deliberações sem 'ano' nem 'data'")
        dl["ano"] = pd.to_datetime(dl.data, errors="coerce", dayfirst=True).dt.year
    for c in ("data", "tema", "ementa_catalogo"):
        dl[c] = dl[c] if c in dl else None
    dl["tipo_decisao"] = dl.tipo_decisao.str.strip().str.lower()
    dl["ano"] = pd.to_numeric(dl.ano, errors="coerce").astype("Int64")
    dl[["numero", "data", "ano", "processo", "tema", "tipo_decisao", "ementa_catalogo"]].to_sql(
        "deliberacoes", con, if_exists="append", index=False)
    pares = []
    if "dispositivos" in dl:
        for n, s in zip(dl.numero, dl.dispositivos.fillna("")):
            pares += [(n, limpa(x)) for x in re.split(r"[;|]", s) if limpa(x)]
    con.executemany("insert into dispositivos_legais values (?, ?)", pares)

    # ---- mapa citação livre → dispositivo
    livres = [x for _, x in pares]
    for arq in args.citacoes:
        livres += citacoes_livres(arq)
    mapa, sem_mapa = {}, 0
    for x in map(limpa, livres):
        if not x or x in mapa:
            continue
        d = normalizar(x)
        if d:
            mapa[x] = d
            registrar(d)
        else:
            sem_mapa += 1
    con.executemany("insert into dispositivo_map values (?, ?, 'regex')", sorted(mapa.items()))
    con.executemany("insert into dispositivos_canonicos values (?, ?, ?, ?, ?)",
                    [(d, *v) for d, v in sorted(canon.items())])

    if args.contratos:
        ct = ler_planilha(args.contratos)
        ct["vigente"] = pd.to_numeric(ct.get("vigente"), errors="coerce").fillna(0).astype(int)
        ct[["concessionaria_canonica", "id_canonico", "tipo", "vigente"]].to_sql(
            "contratos_concessao", con, if_exists="append", index=False)
    con.commit()
    n = {t: con.execute(f"select count(*) from {t}").fetchone()[0] for t in
         ("normativo", "legislacao_externa", "dispositivos_canonicos", "dispositivo_map", "deliberacoes",
          "dispositivos_legais", "contratos_concessao")}
    con.close()
    print(f"base: {saida}")
    print(" ".join(f"{k}={v}" for k, v in n.items()))
    print(f"citações sem norma reconhecida: {sem_mapa} (ficam como BRUTO nos candidatos)")
    if sem_id:
        print(f"{len(sem_id)} arquivo(s) sem identificação (use --normas):", ", ".join(sem_id[:10]))


if __name__ == "__main__":
    main()
