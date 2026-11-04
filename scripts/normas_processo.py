"""Candidatos à base normativa de cada processo, para a curadoria da conformidade (fase 3).

Duas fontes de citação, normalizadas pelo mapa de dispositivos da base normativa (BASE_NORMAS do perfil; esquema em
docs/adaptacao/BASE_NORMATIVA.md):
- peças da coorte: `dispositivos_citados` da extração do relator, com a atividade a que a peça foi atribuída;
- deliberações do mesmo tipo em toda a agência (regra de VOLUME_REGRAS): `dispositivos_legais`.
Cada norma-raiz vem com o caminho do texto integral na base, quando existe, para o trecho literal ser lido e conferido.

Saída: saida/fase3/candidatos_normas_<cod>.json"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

from comum import BASE_NORMAS, CODIGOS_FASE3, DADOS, RUIDO_NORMA, SAIDA, TEXTOS_NORMAS, VOLUME_REGRAS

OUT = SAIDA / "fase3"
BASE_DIR = TEXTOS_NORMAS  # coluna txt da base: caminho relativo a esta pasta (perfil; padrão a pasta-avó do sqlite)


def so_digitos(s) -> str:
    return re.sub(r"\D", "", str(s))


def limpa(s: str) -> str:
    return re.sub(r"\s+", " ", str(s)).strip()


def id_texto(raiz: str) -> list[str]:
    """'IN:1/2007' → ['IN-001/2007', 'IN-1/2007']; 'LEI:5619/2009' → ['LEI-5619/2009']."""
    m = re.match(r"^([A-Z]+):(\d+)/(\d{4})$", raiz)
    if not m:
        return []
    tipo, num, ano = m.groups()
    return [f"{tipo}-{int(num):03d}/{ano}", f"{tipo}-{int(num)}/{ano}"]


def main(codigos: list[str]) -> None:
    faltam = [a for a in (BASE_NORMAS, SAIDA / "coorte_fase2.csv", DADOS / "relator" / "extractions.parquet")
              if not a.exists()]
    if faltam:
        print("aviso: candidatos a normas não gerados; falta", ", ".join(map(str, faltam)))
        return
    OUT.mkdir(exist_ok=True)
    con = sqlite3.connect(f"file:{BASE_NORMAS}?mode=ro", uri=True)
    mapa = dict(con.execute("select string_original, disp_id from dispositivo_map"))
    canon = {d: (r, t, p) for d, r, t, p in con.execute("select disp_id, rotulo, tipo, pai_id from dispositivos_canonicos")}
    textos = {}
    for tab in ("normativo", "legislacao_externa"):
        for i, tit, txt in con.execute(f"select id_canonico, titulo, txt from {tab}"):
            textos[i] = dict(titulo=tit, txt=Path(txt).as_posix() if txt else None, tabela=tab)
    delib = pd.read_sql("select numero, processo, tipo_decisao, tema, ementa_catalogo from deliberacoes", con)
    delib["texto"] = (delib.tema.fillna("") + " " + delib.ementa_catalogo.fillna("")).str.lower()
    disp_delib = pd.read_sql("select numero, dispositivo_legal from dispositivos_legais", con)
    contratos = pd.read_sql("select concessionaria_canonica, id_canonico, tipo, vigente from contratos_concessao", con)

    coorte = pd.read_csv(SAIDA / "coorte_fase2.csv")
    ext = pd.read_parquet(DADOS / "relator" / "extractions.parquet",
                          columns=["processo", "sei_doc_id", "extraction_json"])

    def raiz(disp_id: str) -> str:
        while disp_id in canon and canon[disp_id][2]:
            disp_id = canon[disp_id][2]
        return disp_id

    for cod in codigos:
        procs = set(coorte[coorte.processo_principal == cod].numero)
        if not (SAIDA / "fase2" / f"atribuicoes_{cod}.csv").exists():
            print(f"aviso: {cod} sem saida/fase2/atribuicoes_{cod}.csv (classificar_atividades.py); pulado")
            continue
        atrib = pd.read_csv(SAIDA / "fase2" / f"atribuicoes_{cod}.csv")
        ativ = dict(zip(atrib.ref, atrib.atividade))
        cit = defaultdict(lambda: dict(pecas=0, processos=set(), atividades=Counter(), variantes=Counter()))
        for p, s, j in zip(ext.processo, ext.sei_doc_id, ext.extraction_json):
            if p not in procs:
                continue
            for x in json.loads(j).get("dispositivos_citados") or []:
                x = limpa(x)
                if RUIDO_NORMA.search(x):
                    continue
                d = mapa.get(x) or f"BRUTO:{x[:120]}"
                c = cit[d]
                c["pecas"] += 1
                c["processos"].add(p)
                c["atividades"][ativ.get(f"{p}:{s}", "sem_atribuicao")] += 1
                c["variantes"][x] += 1
        tipos, rx = VOLUME_REGRAS.get(cod, ((), None))
        if rx:
            sel = delib[delib.tipo_decisao.isin(tipos) & delib.texto.str.contains(rx, regex=True)]
        else:  # sem regra de volume: deliberações dos próprios processos da coorte
            sel = delib[delib.processo.map(so_digitos).isin({so_digitos(p) for p in procs})]
        nd = Counter()
        for x in disp_delib[disp_delib.numero.isin(sel.numero)].dispositivo_legal:
            if RUIDO_NORMA.search(str(x)):
                continue
            nd[mapa.get(limpa(x)) or f"BRUTO:{limpa(x)[:120]}"] += 1

        raizes = defaultdict(lambda: dict(dispositivos=[], pecas=0, deliberacoes=0))
        for d in sorted(set(cit) | set(nd)):
            r = raiz(d) if not d.startswith("BRUTO:") else "BRUTO"
            c = cit.get(d)
            raizes[r]["pecas"] += c["pecas"] if c else 0
            raizes[r]["deliberacoes"] += nd.get(d, 0)
            raizes[r]["dispositivos"].append(dict(
                disp_id=d, rotulo=canon.get(d, (d,))[0], pecas=c["pecas"] if c else 0,
                processos=len(c["processos"]) if c else 0, deliberacoes_do_tipo=nd.get(d, 0),
                atividades=dict(sorted(c["atividades"].items(), key=lambda kv: (-kv[1], kv[0]))[:5]) if c else {},
                variante=min(c["variantes"].items(), key=lambda kv: (-kv[1], kv[0]))[0] if c and c["variantes"] else None))
        saida = []
        for r, v in sorted(raizes.items(), key=lambda kv: (-(kv[1]["pecas"] + kv[1]["deliberacoes"]), kv[0])):
            if r == "BRUTO" or RUIDO_NORMA.search(r):
                continue
            loc = next((textos[i] for i in id_texto(r) if i in textos), None)
            v["dispositivos"].sort(key=lambda x: (-(x["pecas"] + x["deliberacoes_do_tipo"]), x["disp_id"]))
            saida.append(dict(raiz=r, rotulo=canon.get(r, (r,))[0], tipo=canon.get(r, (None, None))[1],
                              pecas=v["pecas"], deliberacoes_do_tipo=v["deliberacoes"],
                              texto=loc, dispositivos=v["dispositivos"][:15]))
        brutos = sorted(((d[6:], c["pecas"], len(c["processos"])) for d, c in cit.items() if d.startswith("BRUTO:")),
                        key=lambda x: (-x[1], x[0]))[:40]
        ped = dict(codigo=cod, processos_coorte=len(procs), deliberacoes_do_tipo=int(sel.numero.nunique()),
                   nota="Candidatos por frequência de citação; a curadoria escolhe, lê o texto e transcreve o trecho.",
                   normas=saida[:40], citacoes_nao_mapeadas=[dict(texto=t, pecas=n, processos=k) for t, n, k in brutos],
                   contratos=contratos[contratos.vigente == 1].to_dict("records") if "vigente" in contratos else [])
        (OUT / f"candidatos_normas_{cod}.json").write_text(json.dumps(ped, ensure_ascii=False, indent=1), encoding="utf-8")
        print(cod, "normas-raiz", len(saida), "| deliberações do tipo", ped["deliberacoes_do_tipo"],
              "| com texto", sum(1 for n in saida[:40] if n["texto"]))


if __name__ == "__main__":
    main(sys.argv[1:] or CODIGOS_FASE3)
