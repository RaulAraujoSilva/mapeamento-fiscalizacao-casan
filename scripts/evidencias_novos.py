"""Fase 2 — pacote de evidências por tipo novo (lote 2 da coorte), insumo para modelar o procedimento canônico.

Diferente do piloto (2 casos), parte da coorte inteira do código:
  - participação das unidades e transições entre unidades ativas (processos com trilha);
  - frequência dos tipos de peça próprias e das tarefas das fichas (todos, inclusive os sem trilha);
  - sequência completa de peças próprias (data, unidade, tipo, tarefa e natureza da ficha) de até 4 casos de
    referência: com trilha nativa e encerrados primeiro, depois os de mais peças com ficha.
Saída: saida/bpmn/evidencias_<cod>.md e saida/fase2/referencias.csv (casos de referência por código)."""
from __future__ import annotations

from collections import Counter

import pandas as pd

from comum import ORGAO, SAIDA, SECRETARIA, documentos

HUB = SECRETARIA
DEST = SAIDA / "bpmn"
N_REF = 4


def referencias(g: pd.DataFrame, esf: pd.DataFrame) -> list[str]:
    fich = esf[esf.tem_ficha].groupby("numero_processo").size()
    g = g.assign(fichas=g.numero.map(fich).fillna(0),
                 prio=g.trilha.map({"nativa": 0, "migrada": 1, "sem": 2}) - g.encerrado.fillna(False).astype(int))
    g = g[g.fichas >= 3].sort_values(["prio", "fichas"], ascending=[True, False])
    return g.numero.head(N_REF).tolist()


def main():
    co = pd.read_csv(SAIDA / "coorte_fase2.csv")
    co = co[co.lote == 2]
    esf = pd.read_csv(SAIDA / "esforco_documentos.csv", dtype={"numero": str})
    est = pd.read_csv(SAIDA / "estadias.csv")
    docs = documentos()
    fm = pd.read_csv(SAIDA / "fichas_trabalho.csv", usecols=["processo", "modelo"])
    refs_out = []
    for cod, g in co.groupby("processo_principal"):
        nome = g.nome_processo.iloc[0]
        trilha = g[g.trilha != "sem"]
        md = [f"# Evidências — {cod} {nome}", "",
              f"Processos na coorte: {len(g)} ({(g.trilha == 'nativa').sum()} com trilha nativa do SEI, "
              f"{(g.trilha == 'migrada').sum()} migrados com trilha parcial, {(g.trilha == 'sem').sum()} só com as peças "
              f"do banco do relator, sem andamentos). Encerrados: {int(g.encerrado.fillna(False).sum())}.", ""]
        e = est[est.numero.isin(trilha.numero) & est.unidade.str.startswith(ORGAO, na=False)]
        if len(e):
            part = (e[e.n_docs > 0].groupby("sigla").numero.nunique() / len(trilha) * 100).sort_values(ascending=False)
            md += ["## Participação das unidades (processos com trilha)", "",
                   "| Unidade | Processos em que juntou peça (%) |", "|---|---|"]
            md += [f"| {s} | {v:.0f} |" for s, v in part.head(12).items()]
            trans = Counter()
            for _, x in e[e.n_docs > 0].sort_values(["numero", "entrada"]).groupby("numero"):
                seq = [s for i, s in enumerate(x.sigla) if i == 0 or s != x.sigla.iloc[i - 1]]
                seq = [s for s in seq if s not in HUB]
                trans.update(zip(seq, seq[1:]))
            md += ["", "## Transições entre unidades ativas, sem a Secretaria", "",
                   "; ".join(f"{a} → {b}: {n}" for (a, b), n in trans.most_common(15)) or "(nenhuma)", ""]
        p = docs[docs.numero_processo.isin(g.numero) & docs.unidade.str.startswith(ORGAO, na=False)
                 & (docs.categoria != "processo_relacionado")]
        uni = (p.groupby(p.unidade.str.split("/").str[-1]).numero_processo.nunique() / len(g) * 100)
        md += ["## Unidades que produzem peças (todos os processos)", "",
               "; ".join(f"{u} {v:.0f}%" for u, v in uni.sort_values(ascending=False).head(12).items()), "",
               "## Tipos de peça própria mais frequentes (processos em que aparece)", "",
               "; ".join(f"{t} ({n})" for t, n in p.groupby("tipo").numero_processo.nunique()
                         .sort_values(ascending=False).head(20).items()), ""]
        f = esf[esf.numero_processo.isin(g.numero) & esf.tem_ficha]
        md += ["## Naturezas de trabalho nas fichas", "",
               "Fichas por modelo: " + "; ".join(f"{k} ({v})" for k, v in fm[fm.processo.isin(g.numero)].modelo
                                                 .value_counts().items()), "",
               "; ".join(f"{k} ({v})" for k, v in f.natureza_ficha.value_counts().items()), ""]
        for n in referencias(g, esf):
            r = g[g.numero == n].iloc[0]
            refs_out.append(dict(codigo=cod, numero=n, trilha=r.trilha))
            x = esf[(esf.numero_processo == n) & (esf.autoria == "agenersa")].sort_values("data_inclusao")
            md += [f"## Caso de referência {n} (trilha {r.trilha}{', encerrado' if r.encerrado is True else ''})", "",
                   "| Data | Unidade | Tipo | Tarefa (ficha) | Natureza | Laudas | Complexidade |", "|---|---|---|---|---|---|---|"]
            for y in x.itertuples():
                md.append(f"| {str(y.data_inclusao)[:10]} | {str(y.unidade).split('/')[-1]} | {y.tipo} | "
                          f"{'' if pd.isna(y.tarefa) else y.tarefa} | {'' if pd.isna(y.natureza_ficha) else y.natureza_ficha} | "
                          f"{y.laudas:.1f} | {'' if pd.isna(y.complexidade) else int(y.complexidade)} |")
            md.append("")
        (DEST / f"evidencias_{cod}.md").write_text("\n".join(md), encoding="utf-8")
        print(cod, "ok")
    pd.DataFrame(refs_out).to_csv(SAIDA / "fase2" / "referencias.csv", index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
