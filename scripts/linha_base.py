"""Linha de base AS-IS congelada por código (fase 3): referência de todo cálculo de resultado do TO-BE.

Junta o procedimento da coorte (casos nativos), o volume anual (deliberações de toda a agência) e o custo-hora, e grava
um carimbo (sha-256 das entradas). Médias por caso multiplicam o volume (total anual); medianas e quartis descrevem o
caso típico. Horas e custo são hipótese até a calibração (TASK-011) e os dados do RH (TASK-019).

Saída: saida/fase3/linha_base_<cod>.json"""
from __future__ import annotations

import hashlib
import json
import sys

import numpy as np

from comum import (CARGO_PADRAO, CODIGOS_FASE3, CUSTO_HORA_BASE, FATOR_CUSTO_TOTAL, SAIDA, VENCIMENTO_BASE_2022, horas_ano_fte)

F2, OUT = SAIDA / "fase2", SAIDA / "fase3"


def dist(v):
    v = [float(x) for x in v]
    if not v:
        return None
    q1, md, q3 = np.percentile(v, [25, 50, 75])
    return dict(n=len(v), media=round(float(np.mean(v)), 1), mediana=round(float(md), 1), q1=round(float(q1), 1),
                q3=round(float(q3), 1), max=round(max(v), 1))


def main(codigos: list[str]) -> None:
    arq_v = OUT / "volume_anual.json"
    if not arq_v.exists():
        print("aviso: sem volume_anual.json (base normativa ausente?); linha de base sem volume nem custo anual")
    vol = json.loads(arq_v.read_text(encoding="utf-8")) if arq_v.exists() else {"codigos": {}}
    hfte = horas_ano_fte()
    for cod in codigos:
        faltam = [f"{k}_{cod}.json" for k in ("procedimento", "casos") if not (F2 / f"{k}_{cod}.json").exists()]
        if faltam:
            print(f"aviso: {cod} sem saida/fase2/{', '.join(faltam)} (procedimento.py); pulado")
            continue
        bruto = {k: (F2 / f"{k}_{cod}.json").read_text(encoding="utf-8") for k in ("procedimento", "casos")}
        proc, casos = json.loads(bruto["procedimento"]), json.loads(bruto["casos"])["casos"]
        v = vol["codigos"].get(cod)
        param = dict(custo_hora_base=CUSTO_HORA_BASE, cargo_padrao=CARGO_PADRAO, fator_custo_total=FATOR_CUSTO_TOTAL,
                     vencimento_base_2022=VENCIMENTO_BASE_2022, horas_ano_fte=hfte)
        hp = [sum(o["horas_piso"] for o in c["ocorrencias"]) for c in casos]
        ht = [sum(o["horas_teto"] for o in c["ocorrencias"]) for c in casos]
        sem = [c["posse_du"].get("SEM UNIDADE", 0.0) for c in casos]
        caso = dict(lead_du=dist([c["lead_du"] for c in casos]),
                    lead_encerrados_du=dist([c["lead_du"] for c in casos if c["encerrado"]]),
                    espera_entre_atividades_du=dist([sum(o["espera_antes_du"] for o in c["ocorrencias"]) for c in casos]),
                    execucao_du=dist([sum(o["execucao_du"] for o in c["ocorrencias"]) for c in casos]),
                    terceiros_du=dist([c["terceiros_du"] for c in casos]),
                    sem_unidade_du=dist(sem), horas_piso=dist(hp), horas_teto=dist(ht),
                    ocorrencias=dist([len(c["ocorrencias"]) for c in casos]))
        anual = None
        if v and hp:
            n = v["media_anual"]
            h = dict(piso=round(n * float(np.mean(hp)), 1), teto=round(n * float(np.mean(ht)), 1))
            ch = CUSTO_HORA_BASE[CARGO_PADRAO]
            anual = dict(processos=n, horas=h, fte=dict(piso=round(h["piso"] / hfte, 2), teto=round(h["teto"] / hfte, 2)),
                         custo_reais=dict(piso=round(h["piso"] * ch * FATOR_CUSTO_TOTAL["piso"]),
                                          esperado=round((h["piso"] + h["teto"]) / 2 * ch * FATOR_CUSTO_TOTAL["esperado"]),
                                          teto=round(h["teto"] * ch * FATOR_CUSTO_TOTAL["teto"])))
        carimbo = hashlib.sha256(json.dumps([bruto, v, param], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        res = dict(codigo=cod, nome=proc["nome"], situacao=proc["situacao"], casos_coorte=proc["casos"],
                   casos_nativos=len(casos), auditoria_classificador=proc.get("auditoria_classificador"),
                   por_caso=caso, posse_por_unidade=proc["posse_por_unidade_nativos"], anual=anual, volume=v,
                   parametros=param, carimbo=carimbo,
                   ressalvas=["Horas por peça são estimativa (hipótese até a calibração com servidores).",
                              "Volume anual é piso: só processos que chegaram a deliberação.",
                              "Custo-hora parte do vencimento base inicial de 2022; o fator de custo total é hipótese."])
        (OUT / f"linha_base_{cod}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        print(cod, "nativos", len(casos), "| lead mediano", caso["lead_du"] and caso["lead_du"]["mediana"],
              "| horas/ano", anual and anual["horas"], "| FTE", anual and anual["fte"], "| carimbo", carimbo[:10])


if __name__ == "__main__":
    main(sys.argv[1:] or CODIGOS_FASE3)
