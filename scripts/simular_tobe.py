"""Simulação do TO-BE (fase 3): reaplica cada caso nativo da coorte com as melhorias de cada fase.

Entrada: saida/fase3/melhorias_<cod>.json (formato e tipos de efeito em saida/fase3/ESPECIFICACAO_TOBE.md),
saida/fase2/casos_<cod>.json (linha do tempo de cada caso nativo) e saida/fase3/linha_base_<cod>.json (volume, custo).
Fase 0 = caso sem mudança, recalculado pela mesma regra; as fases são cumulativas (fase f aplica as melhorias de
fase ≤ f). Lead time = cauda + Σ (espera antes + execução) das ocorrências. A parte da espera que é tempo de resposta
de terceiro (ofício com prazo, `espera_antes_terceiros_du`) não é cortada por teto nem por redução de espera.

Saída: saida/fase3/resultado_tobe_<cod>.json"""
from __future__ import annotations

import copy
import json
import sys

import numpy as np

import pandas as pd

from comum import CARGO_PADRAO, CODIGOS_FASE3, CUSTO_HORA_BASE, FATOR_CUSTO_TOTAL, SAIDA, somar_du
from conformidade import avaliar

F2, OUT = SAIDA / "fase2", SAIDA / "fase3"
CENARIOS = ("conservador", "esperado", "otimista")
SEM = "SEM UNIDADE"


def aplicar(caso: dict, efeito: dict, valor: float) -> None:
    """Aplica um efeito (tipo + parâmetros) com o valor do cenário, no lugar."""
    t, ativ = efeito["tipo"], set(efeito.get("atividades") or [])
    oc = caso["ocorrencias"]
    if t == "reduz_cauda_pct":  # só no encerrado: no aberto a cauda vai até a data de corte, não até o encerramento
        if caso.get("encerrado"):
            caso["cauda_du"] *= 1 - valor / 100
        return
    vistos = set()
    for k, o in enumerate(oc):
        repetida = o["atividade"] in vistos
        vistos.add(o["atividade"])
        if t == "paralelo":
            if k and oc[k - 1]["atividade"] == efeito["a"] and o["atividade"] == efeito["b"]:
                o["espera_antes_du"] = 0.0
            continue
        if o["atividade"] not in ativ:
            continue
        terc = min(float(o.get("espera_antes_terceiros_du", 0.0)), o["espera_antes_du"])  # resposta de terceiro: intocável
        if t == "teto_espera":
            if efeito.get("parte") == "sem_unidade":
                su = float((o.get("espera_antes_por_unidade") or {}).get(SEM, 0.0))
                corte = min(max(0.0, su - valor), o["espera_antes_du"] - terc)
                o["espera_antes_du"] -= corte
                if corte:
                    o["espera_antes_por_unidade"] = {**o["espera_antes_por_unidade"], SEM: su - corte}
            else:
                o["espera_antes_du"] = terc + min(o["espera_antes_du"] - terc, valor)
        elif t == "reduz_espera_pct":
            o["espera_antes_du"] = terc + (o["espera_antes_du"] - terc) * (1 - valor / 100)
        elif t == "reduz_execucao_pct":
            o["execucao_du"] *= 1 - valor / 100
        elif t == "reduz_horas_pct":
            o["horas_piso"] *= 1 - valor / 100
            o["horas_teto"] *= 1 - valor / 100
        elif t == "elimina_laco_pct":
            if repetida:
                for c in ("espera_antes_du", "execucao_du", "horas_piso", "horas_teto"):
                    o[c] *= 1 - valor / 100
        else:
            raise ValueError(f"tipo de efeito desconhecido: {t}")


# testes que o TO-BE quer melhorar e que a mudança de tempo altera. prazo_min fica de fora: o validador já impede corte
# da espera que ele protege, e em dias corridos a mesma espera em du muda de valor só pelo calendário (±1 caso)
TEMPORAIS = ("prazo_max", "duracao_max")


def eventos(caso: dict) -> list[dict]:
    """Linha do tempo refeita a partir das esperas e execuções (simuladas): um evento no início e outro no fim de cada
    ocorrência, em datas reais de calendário a partir da data de início da primeira ocorrência."""
    oc = caso["ocorrencias"]
    if not oc:
        return []
    ancora, x0, x, ev = pd.Timestamp(oc[0]["inicio"]), oc[0]["espera_antes_du"], 0.0, []
    for o in oc:
        ini = x + o["espera_antes_du"]
        x = ini + o["execucao_du"]
        for v in (ini, x):
            ev.append(dict(atividade=o["atividade"], data=somar_du(ancora, round(v - x0)), prazo=None))
    return ev


def medir(caso: dict, requisitos: list[dict] | None = None) -> dict:
    oc = caso["ocorrencias"]
    m = dict(lead=caso["cauda_du"] + sum(o["espera_antes_du"] + o["execucao_du"] for o in oc),
             horas_piso=sum(o["horas_piso"] for o in oc), horas_teto=sum(o["horas_teto"] for o in oc))
    if requisitos:
        ev = eventos(caso)
        m["conformidade"] = {r["id"]: avaliar(r["teste"], ev)[0] for r in requisitos}
    return m


def simular(casos: list[dict], melhorias: list[dict], fase: int, cenario: str,
            requisitos: list[dict] | None = None) -> list[dict]:
    out = []
    for c in casos:
        c = copy.deepcopy(c)
        for m in sorted((m for m in melhorias if m["fase"] <= fase), key=lambda m: (m["fase"], m["id"])):
            aplicar(c, m["efeito"], float(m["efeito"]["cenarios"][cenario]))
        out.append(medir(c, requisitos))
    return out


def pct_conforme(medidas: list[dict]) -> dict:
    """% conforme por requisito temporal, entre os casos em que ele se aplica (conforme + não conforme)."""
    out = {}
    for r in medidas[0].get("conformidade", {}) if medidas else {}:
        v = [m["conformidade"][r] for m in medidas]
        ap = sum(x in ("conforme", "nao_conforme") for x in v)
        out[r] = round(100 * v.count("conforme") / ap, 1) if ap else None
    return out


def dist(v):
    q1, md, q3 = np.percentile(v, [25, 50, 75])
    return dict(media=round(float(np.mean(v)), 1), mediana=round(float(md), 1), q1=round(float(q1), 1), q3=round(float(q3), 1))


def anual(medidas: list[dict], base: dict) -> dict | None:
    if not base.get("anual"):
        return None
    n, hfte = base["anual"]["processos"], base["parametros"]["horas_ano_fte"]
    ch = CUSTO_HORA_BASE[CARGO_PADRAO]
    hp = n * float(np.mean([m["horas_piso"] for m in medidas]))
    ht = n * float(np.mean([m["horas_teto"] for m in medidas]))
    return dict(horas=dict(piso=round(hp, 1), teto=round(ht, 1)), fte=dict(piso=round(hp / hfte, 2), teto=round(ht / hfte, 2)),
                custo_reais=dict(piso=round(hp * ch * FATOR_CUSTO_TOTAL["piso"]),
                                 esperado=round((hp + ht) / 2 * ch * FATOR_CUSTO_TOTAL["esperado"]),
                                 teto=round(ht * ch * FATOR_CUSTO_TOTAL["teto"])))


def sensibilidade(casos: list[dict], mel: list[dict]) -> dict:
    """Na última fase, cenário esperado: quanto pioram o lead (mediana, média) e as horas médias sem cada melhoria."""
    f = max(m["fase"] for m in mel)
    def resumo(ms):
        return (float(np.median([m["lead"] for m in ms])), float(np.mean([m["lead"] for m in ms])),
                float(np.mean([(m["horas_piso"] + m["horas_teto"]) / 2 for m in ms])))
    todos = resumo(simular(casos, mel, f, "esperado"))
    out = []
    for m in mel:
        sem = resumo(simular(casos, [x for x in mel if x is not m], f, "esperado"))
        out.append(dict(melhoria=m["id"], fase=m["fase"], lead_mediano_du=round(sem[0] - todos[0], 1),
                        lead_medio_du=round(sem[1] - todos[1], 1), horas_medias=round(sem[2] - todos[2], 2)))
    return dict(fase=f, cenario="esperado", sem_cada_melhoria=sorted(out, key=lambda d: -d["lead_medio_du"]))


def main(codigos: list[str]) -> None:
    for cod in codigos:
        arq = OUT / f"melhorias_{cod}.json"
        if not arq.exists():
            print(f"aviso: {cod} sem melhorias_{cod}.json; TO-BE não simulado")
            continue
        mel = json.loads(arq.read_text(encoding="utf-8"))["melhorias"]
        casos = json.loads((F2 / f"casos_{cod}.json").read_text(encoding="utf-8"))["casos"]
        base = json.loads((OUT / f"linha_base_{cod}.json").read_text(encoding="utf-8"))
        arq_n = OUT / f"normas_{cod}.json"
        req = [r for r in json.loads(arq_n.read_text(encoding="utf-8"))["requisitos"]
               if r["teste"]["tipo"] in TEMPORAIS] if arq_n.exists() else []
        b0 = simular(casos, [], 0, "esperado", req)
        res = dict(codigo=cod, casos_nativos=len(casos), carimbo_linha_base=base["carimbo"],
                   linha_base=dict(lead=dist([m["lead"] for m in b0]), horas_piso=dist([m["horas_piso"] for m in b0]),
                                   horas_teto=dist([m["horas_teto"] for m in b0]), anual=anual(b0, base),
                                   conformidade_temporal=pct_conforme(b0)),
                   fases={})
        for f in sorted({m["fase"] for m in mel}):
            res["fases"][str(f)] = {}
            for cen in CENARIOS:
                ms = simular(casos, mel, f, cen, req)
                lead = dist([m["lead"] for m in ms])
                r = dict(lead=lead, horas_piso=dist([m["horas_piso"] for m in ms]),
                         horas_teto=dist([m["horas_teto"] for m in ms]), anual=anual(ms, base),
                         conformidade_temporal=pct_conforme(ms),
                         ganho_lead_mediano_pct=round(100 * (1 - lead["mediana"] / res["linha_base"]["lead"]["mediana"]), 1),
                         ganho_horas_media_pct=round(100 * (1 - np.mean([m["horas_piso"] + m["horas_teto"] for m in ms]) /
                                                          np.mean([m["horas_piso"] + m["horas_teto"] for m in b0])), 1))
                res["fases"][str(f)][cen] = r
        res["sensibilidade"] = sensibilidade(casos, mel)
        (OUT / f"resultado_tobe_{cod}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        for f, v in res["fases"].items():
            print(cod, "fase", f, {c: (v[c]["lead"]["mediana"], v[c]["ganho_lead_mediano_pct"], v[c]["ganho_horas_media_pct"])
                                  for c in CENARIOS})


if __name__ == "__main__":
    main(sys.argv[1:] or CODIGOS_FASE3)
