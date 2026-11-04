"""Insumo para a proposta de melhorias do TO-BE (fase 3): onde o tempo e as horas de cada caso nativo se concentram,
por atividade e por unidade, com os ids dos fatos citáveis, o que a conformidade aponta, as esperas protegidas por
prazo legal mínimo, as oportunidades da avaliação AS-IS e os casos de benchmarking da família do processo.

Saída: saida/fase3/insumo_tobe_<cod>.md"""
from __future__ import annotations

import json
import sys
from collections import defaultdict

import numpy as np

from comum import CODIGOS_FASE3, FAMILIA_BENCHMARK, SAIDA

F2, F3, BP = SAIDA / "fase2", SAIDA / "fase3", SAIDA / "bpmn"
SEM = "SEM UNIDADE"
FAMILIA = FAMILIA_BENCHMARK  # código → família de benchmarking (perfil)


def _j(p):
    return json.loads(p.read_text(encoding="utf-8"))


def num(v) -> str:
    return f"{v:.1f}".replace(".", ",")


def main(cod: str) -> None:
    casos = _j(F2 / f"casos_{cod}.json")["casos"]
    fatos = {f["id"] for f in _j(BP / f"fatos_{cod}.json")["fatos"]}
    modelo = _j(BP / f"modelo_{cod}.json")
    nomes = {e["id"]: (e["nome"], e.get("raia", "")) for e in modelo["elementos"] if e["tipo"] == "tarefa"}
    base = _j(F3 / f"linha_base_{cod}.json")
    n = len(casos)
    lead = np.mean([c["cauda_du"] + sum(o["espera_antes_du"] + o["execucao_du"] for o in c["ocorrencias"]) for c in casos])
    hor = np.mean([sum(o["horas_piso"] + o["horas_teto"] for o in c["ocorrencias"]) / 2 for c in casos])

    por = defaultdict(lambda: dict(oc=0, casos=set(), esp=0.0, exe=0.0, sem=0.0, rep_esp=0.0, horas=0.0, uni=defaultdict(float)))
    for i, c in enumerate(casos):
        vistos = set()
        for o in c["ocorrencias"]:
            d = por[o["atividade"]]
            d["oc"] += 1
            d["casos"].add(i)
            d["esp"] += o["espera_antes_du"]
            d["exe"] += o["execucao_du"]
            d["horas"] += (o["horas_piso"] + o["horas_teto"]) / 2
            for u, v in (o.get("espera_antes_por_unidade") or {}).items():
                d["uni"][u] += v
            d["sem"] += float((o.get("espera_antes_por_unidade") or {}).get(SEM, 0.0))
            if o["atividade"] in vistos:
                d["rep_esp"] += o["espera_antes_du"] + o["execucao_du"]
            vistos.add(o["atividade"])
    cauda = np.mean([c["cauda_du"] for c in casos])

    md = [f"# Insumo do TO-BE — {cod} ({base['nome']})", "",
          f"Casos nativos: {n}. Médias por caso nativo (a simulação usa todos os casos; o resultado é dado em mediana). "
          f"Lead médio {num(lead)} du; horas médias {num(hor)} h (média de piso e teto). Linha de base: lead mediano "
          f"{num(base['por_caso']['lead_du']['mediana'])} du; anual {base['anual']['processos']} processos/ano, "
          f"{base['anual']['horas']['piso']}–{base['anual']['horas']['teto']} h, {base['anual']['fte']['piso']}–"
          f"{base['anual']['fte']['teto']} FTE." if base.get("anual") else "", "",
          "## Onde está o tempo (média por caso nativo)", "",
          "| Atividade | Nome (raia) | Casos | Ocorr. | Espera antes (du) | % do lead | Sem unidade (du) | Espera por unidade (du) | Execução (du) | Laço: espera+exec. das repetidas (du) | Horas | Fatos |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for t, d in sorted(por.items(), key=lambda kv: -kv[1]["esp"]):
        uni = ", ".join(f"{u} {num(v / n)}" for u, v in sorted(d["uni"].items(), key=lambda kv: -kv[1]) if v / n >= 0.5)
        ids = [f"coorte.{t}.{s}" for s in ("espera_antes.mediana", "execucao.mediana", "casos_com_laco", "horas_piso.mediana")
               if f"coorte.{t}.{s}" in fatos]
        nm, raia = nomes.get(t, ("(fora do modelo)", ""))
        md.append(f"| {t} | {nm} ({raia}) | {len(d['casos'])} | {d['oc']} | {num(d['esp'] / n)} | {num(100 * d['esp'] / n / lead)} | "
                  f"{num(d['sem'] / n)} | {uni} | {num(d['exe'] / n)} | {num(d['rep_esp'] / n)} | {num(d['horas'] / n)} | {', '.join(ids)} |")
    md += ["", f"Cauda (depois da última atividade até o encerramento ou a data de corte): {num(cauda)} du por caso "
           f"({num(100 * cauda / lead)}% do lead).", ""]
    trans = sorted((f for f in fatos if f.startswith("coorte.transicao.") and not f.endswith(".pct")))
    md += ["Fatos de transição disponíveis (contagem; acrescente `.pct` para o %): " + ", ".join(trans), ""]
    md += ["Outros fatos de caso: " + ", ".join(sorted(f for f in fatos if f.startswith(("coorte.caso.", "coorte.posse.", "coorte.lead_")))), ""]

    arq_n = F3 / f"normas_{cod}.json"
    req = {r["id"]: r for r in _j(arq_n)["requisitos"]}
    conf = _j(F3 / f"conformidade_{cod}.json")["requisitos"]
    md += ["## Esperas protegidas por prazo legal mínimo (o validador barra reduzi-las)", ""]
    for r in req.values():
        if r["teste"]["tipo"] == "prazo_min":
            t = r["teste"]
            md.append(f"- {r['id']}: {t['de']} → {t['ate']}, mínimo {t['min']} {t['unidade']}. {r['exigencia']}")
    md += ["", "## Conformidade na coorte (requisitos computados)", "",
           "| Requisito | Exigência | Tipo | Conforme | Não conforme | Sem evidência | % conforme |", "|---|---|---|---|---|---|---|"]
    for i, c in conf.items():
        md.append(f"| {i} | {c['exigencia']} | {c['tipo']} | {c['conforme']} | {c['nao_conforme']} | {c['sem_evidencia']} | "
                  f"{'' if c['pct_conforme'] is None else num(c['pct_conforme'])} |")
    md += ["", "Requisitos manuais: " + "; ".join(f"{r['id']} ({r['exigencia']})" for r in req.values()
                                                  if r["teste"]["tipo"] == "manual"), ""]

    av = _j(BP / f"avaliacao_{cod}.json")
    md += ["## Oportunidades da avaliação AS-IS (ponto de partida, não obrigatórias)", ""]
    for o in av.get("oportunidades", []):
        md.append(f"- **{o['titulo']}** ({o.get('categoria', '')}; {', '.join(o.get('atividades', []))}): {o['descricao']}")
    md += ["", f"Gargalo: {av['gargalo'].get('onde', '')}", ""]

    md += ["## Benchmarking (família do processo e transversal)", ""]
    for fam in (FAMILIA.get(cod), "transversal"):
        if not (F3 / "benchmark" / f"{fam}.json").exists():
            print(f"aviso: {cod} sem benchmark/{fam}.json (FAMILIA_BENCHMARK do perfil); seção sem esses casos")
            continue
        for c in _j(F3 / "benchmark" / f"{fam}.json")["casos"]:
            md.append(f"- **{c['id']}** (fases {', '.join(map(str, c.get('fase_melhoria') or []))}; {c['fonte']['camada']}) "
                      f"{c['pratica']}. Resultado: {c['resultado_reportado']}"
                      + (f" Parâmetro: {c['parametro_ganho']}" if c.get("parametro_ganho") else "")
                      + (f" Aplicabilidade: {c['aplicabilidade']}" if c.get("aplicabilidade") else ""))
    md.append("")
    (F3 / f"insumo_tobe_{cod}.md").write_text("\n".join(md), encoding="utf-8")
    print(f"insumo_tobe_{cod}.md:", len(md), "linhas")


def insumos(cod: str) -> list:
    return [F2 / f"casos_{cod}.json", BP / f"fatos_{cod}.json", BP / f"modelo_{cod}.json", F3 / f"linha_base_{cod}.json",
            F3 / f"normas_{cod}.json", F3 / f"conformidade_{cod}.json", BP / f"avaliacao_{cod}.json"]


if __name__ == "__main__":
    for c in sys.argv[1:] or CODIGOS_FASE3:
        faltam = [a.name for a in insumos(c) if not a.exists()]
        if faltam:
            print(f"aviso: {c} sem {', '.join(faltam)}; insumo do TO-BE não gerado")
            continue
        main(c)
