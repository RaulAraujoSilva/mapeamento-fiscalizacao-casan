"""Etapa 4a — pacote de evidências por processo organizacional do piloto, insumo para modelar o BPMN
canônico (típico + crítico + trilhas dos demais processos SEI do mesmo código).

Saída: saida/bpmn/evidencias_<Pxx>.md"""
from __future__ import annotations

from collections import Counter

import pandas as pd

from comum import ORGAO, SAIDA, SECRETARIA

HUB = SECRETARIA
DEST = SAIDA / "bpmn"


def main():
    DEST.mkdir(exist_ok=True)
    piloto = pd.read_csv(SAIDA / "piloto.csv")
    cls = pd.read_csv(SAIDA / "processos_classificados.csv")
    tarefas = pd.read_csv(SAIDA / "tarefas_piloto.csv")
    esf = pd.read_csv(SAIDA / "esforco_documentos.csv")
    est = pd.read_csv(SAIDA / "estadias.csv")
    posse = pd.read_csv(SAIDA / "posse.csv")
    for pid, g in piloto.groupby("processo_principal", sort=False):
        todos = cls[cls.processo_principal == pid]
        nativos = todos[todos.nativo_sei]
        md = [f"# Evidências — {pid} {g.nome_processo.iloc[0]}", "",
              f"Processos SEI na carteira com este código: {len(todos)} ({len(nativos)} nativos do SEI). "
              f"Casos do piloto: {', '.join(f'{r.numero} ({r.papel})' for r in g.itertuples())}.", ""]

        # trilhas de todos os processos do código
        e = est[est.numero.isin(todos.numero) & est.unidade.str.startswith(ORGAO, na=False)]
        part = (e[e.n_docs > 0].groupby("sigla").numero.nunique() / len(todos) * 100).sort_values(ascending=False)
        po = posse[posse.numero.isin(nativos.numero) & posse.unidade.str.startswith(ORGAO, na=False)]
        du = po.groupby("sigla").du.agg(["median", "sum"])
        md += ["## Participação das unidades (todos os processos do código)", "",
               "| Unidade | Processos em que juntou documento (%) | Posse mediana por passagem (du) | Posse total (du, nativos) |",
               "|---|---|---|---|"]
        for s, v in part.head(12).items():
            md.append(f"| {s} | {v:.0f} | {du['median'].get(s, float('nan')):.0f} | {du['sum'].get(s, 0):.0f} |")
        trans = Counter()
        for _, x in e[e.n_docs > 0].sort_values(["numero", "entrada"]).groupby("numero"):
            seq = [s for i, s in enumerate(x.sigla) if i == 0 or s != x.sigla.iloc[i - 1]]
            seq = [s for s in seq if s not in HUB]
            trans.update(zip(seq, seq[1:]))
        md += ["", "## Transições entre unidades ativas, sem a Secretaria (todos os processos)", "",
               "; ".join(f"{a} → {b}: {n}" for (a, b), n in trans.most_common(15)), "",
               f"Retornos a unidade já visitada (média): {todos.retornos_iteracao.mean():.1f}; ofícios por processo "
               f"(mediana): {todos.n_oficios.median():.0f}; vistas/razões finais (mediana): {todos.n_vista_razoes.median():.0f}; "
               f"aguardando terceiros (du, mediana): {todos.espera_externa_du.median():.0f}; lead time nativos (du, mediana): "
               f"{nativos.lead_du.median():.0f}; com deliberação: {100 * todos.tem_deliberacao.mean():.0f}%.", ""]

        # casos do piloto: tarefas em ordem
        for r in g.itertuples():
            t = tarefas[tarefas.numero == r.numero]
            md += [f"## Caso {r.papel}: {r.numero}", "", str(r.assunto), "",
                   "| # | Unidade | Tarefa (da ficha) | Natureza | du na passagem | Espera até 1ª juntada | Horas (teto) | Horas (piso) | Sinais de perda | Espera dominante |",
                   "|---|---|---|---|---|---|---|---|---|---|"]
            for i, x in enumerate(t.itertuples(), 1):
                md.append(f"| {i} | {x.sigla} | {x.tarefa} | {x.natureza} | {x.lead_du:.0f} | "
                          f"{'' if pd.isna(x.espera_1a_juntada_du) else f'{x.espera_1a_juntada_du:.0f}'} | "
                          f"{x.horas_modelo:.1f} | {x.horas_llm:.1f} | {x.sinais if isinstance(x.sinais, str) else ''} | "
                          f"{'sim' if x.espera_dominante_modelo else ''} |")
            d = esf[(esf.numero_processo == r.numero) & esf.tem_ficha & (esf.complexidade >= 3)]
            if len(d):
                md += ["", "Peças de maior complexidade: " + "; ".join(
                    f"{x.tipo} ({x.unidade.split('/')[-1]}, {x.laudas:.0f} laudas, complexidade {x.complexidade:.0f})"
                    for x in d.sort_values("horas_modelo", ascending=False).head(8).itertuples())]
            md.append("")
        (DEST / f"evidencias_{pid}.md").write_text("\n".join(md), encoding="utf-8")
        print(pid, "ok")


if __name__ == "__main__":
    main()
