"""Etapa 5a — insumo para vincular cada atividade do BPMN canônico aos documentos reais dos casos-piloto.

Saída: saida/bpmn/docs_<Pxx>.csv (documentos dos casos-piloto do código, em ordem, com unidade, tipo,
autoria, tarefa e entregável da ficha e horas)."""
from __future__ import annotations

import json

import pandas as pd

from comum import SAIDA

DIR = SAIDA / "bpmn"


def main():
    piloto = pd.read_csv(SAIDA / "piloto.csv")
    esf = pd.read_csv(SAIDA / "esforco_documentos.csv", dtype={"numero": str})
    entreg = {}
    with open(SAIDA / "fichas_trabalho.jsonl", encoding="utf-8") as f:
        for ln in f:
            d = json.loads(ln)
            entreg[(d["processo"], str(d["sei_doc_id"]))] = d["ficha"].get("entregavel")
    for pid, g in piloto.groupby("processo_principal"):
        d = esf[esf.numero_processo.isin(g.numero)].copy()
        d["papel_caso"] = d.numero_processo.map(dict(zip(g.numero, g.papel)))
        d["entregavel"] = [entreg.get((p, n)) for p, n in zip(d.numero_processo, d.numero)]
        d["ref"] = d.numero_processo + ":" + d.numero
        d = d.sort_values(["numero_processo", "data_inclusao"])
        cols = ["ref", "papel_caso", "data_inclusao", "unidade", "tipo", "categoria", "autoria", "tarefa",
                "natureza_ficha", "entregavel", "horas_llm", "horas_modelo", "sinais_txt"]
        d[cols].to_csv(DIR / f"docs_{pid}.csv", index=False, encoding="utf-8-sig")
        print(pid, len(d), "documentos")


if __name__ == "__main__":
    main()
