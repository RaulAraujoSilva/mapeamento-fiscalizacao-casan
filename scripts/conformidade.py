"""Testes de conformidade legal na coorte (fase 3).

Cada requisito de saida/fase3/normas_<cod>.json traz um teste computável (formato em
saida/fase3/ESPECIFICACAO_CONFORMIDADE.md). Cada caso da coorte vira uma lista de eventos (atividade, data da peça,
prazo concedido) a partir das atribuições do classificador, das datas das peças e das fichas de trabalho.

Saídas: saida/fase3/conformidade_<cod>.csv (caso × requisito) e conformidade_<cod>.json (% por requisito)."""
from __future__ import annotations

import json
import sys

import pandas as pd

from comum import CODIGOS_FASE3, SAIDA, dias_uteis

OUT = SAIDA / "fase3"
RESULTADOS = ("conforme", "nao_conforme", "sem_evidencia", "nao_aplicavel")


def intervalo(ini, fim, unidade: str) -> float:
    if unidade == "du":
        return dias_uteis(ini, fim)
    if unidade == "anos":
        return (fim - ini).days / 365.25
    return float((fim - ini).days)


def avaliar(teste: dict, eventos: list[dict]) -> tuple[str, str]:
    """Resultado de um teste num caso. eventos: dicts com atividade, data (Timestamp) e prazo (dias ou None)."""
    ev = sorted(eventos, key=lambda e: e["data"])
    datas = lambda a: [e["data"] for e in ev if e["atividade"] == a]  # noqa: E731
    t = teste["tipo"]
    if t == "manual":
        return "nao_aplicavel", "teste manual"
    if t == "precede":
        b = datas(teste["b"])
        if not b:
            return "nao_aplicavel", f"{teste['b']} não ocorre"
        a = [d for d in datas(teste["a"]) if d <= b[0]]
        return ("conforme", f"{teste['a']} em {a[0]:%d/%m/%Y}") if a else ("nao_conforme", f"{teste['b']} sem {teste['a']} antes")
    if t == "exige":
        se = [a for a in teste["se"] if datas(a)]
        if not se:
            return "nao_aplicavel", "condição não ocorre"
        ok = [a for a in teste["entao"] if datas(a)]
        return ("conforme", ", ".join(ok)) if ok else ("nao_conforme", f"{', '.join(se)} sem {'/'.join(teste['entao'])}")
    if t in ("prazo_max", "prazo_min"):
        de, ate = datas(teste["de"]), datas(teste["ate"])
        if not de or not ate:
            return "nao_aplicavel", "atividade ausente"
        antes = [d for d in de if d <= ate[0]]
        if not antes:
            return "nao_aplicavel", f"{teste['de']} só depois de {teste['ate']}"
        if t == "prazo_max":  # conta da 1ª ocorrência de `de`, ou da última antes de `ate` se o prazo reabre a cada rodada
            ini = antes[-1] if teste.get("de_ocorrencia") == "ultima" else antes[0]
            v = intervalo(ini, ate[0], teste["unidade"])
            return ("conforme" if v <= teste["max"] else "nao_conforme"), f"{v:g} {teste['unidade']} (máx. {teste['max']})"
        v = intervalo(antes[-1], ate[0], teste["unidade"])
        return ("conforme" if v >= teste["min"] else "nao_conforme"), f"{v:g} {teste['unidade']} (mín. {teste['min']})"
    if t == "prazo_concedido_min":
        ps = [e["prazo"] for e in ev if e["atividade"] == teste["atividade"]]
        if not ps:
            return "nao_aplicavel", "atividade ausente"
        lidos = [p for p in ps if p is not None]
        if not lidos:
            return "sem_evidencia", "prazo não lido nas peças"
        menor = min(lidos)
        return ("conforme" if menor >= teste["min"] else "nao_conforme"), f"menor prazo {menor:g} dias (mín. {teste['min']})"
    if t == "duracao_max":
        ate = datas(teste["ate"])
        if not ate:
            return "nao_aplicavel", f"{teste['ate']} não ocorre"
        ini = datas(teste["de"])[0] if teste.get("de") and datas(teste["de"]) else ev[0]["data"]
        v = intervalo(ini, ate[0], teste["unidade"])
        return ("conforme" if v <= teste["max"] else "nao_conforme"), f"{v:.1f} {teste['unidade']} (máx. {teste['max']})"
    raise ValueError(f"tipo de teste desconhecido: {t}")


def eventos_por_caso(cod: str) -> dict[str, list[dict]]:
    atr = pd.read_csv(SAIDA / "fase2" / f"atribuicoes_{cod}.csv")
    esf = pd.read_csv(SAIDA / "esforco_documentos.csv", dtype={"numero": str}, parse_dates=["data_inclusao"])
    data = dict(zip(esf.numero_processo + ":" + esf.numero, esf.data_inclusao))
    prazo = {}
    for ln in open(SAIDA / "fichas_trabalho.jsonl", encoding="utf-8"):
        d = json.loads(ln)
        prazo[f"{d['processo']}:{d['sei_doc_id']}"] = (d["ficha"] or {}).get("prazo_concedido_dias")
    out = {}
    for p, g in atr.groupby("processo"):
        out[p] = [dict(atividade=a, data=data[r], prazo=prazo.get(r), ref=r)
                  for a, r in zip(g.atividade, g.ref) if a != "fora_do_modelo" and r in data and pd.notna(data[r])]
    return out


def main(codigos: list[str]) -> None:
    for cod in codigos:
        arq = OUT / f"normas_{cod}.json"
        if not arq.exists():
            print(f"aviso: {cod} sem normas_{cod}.json; conformidade não medida")
            continue
        req = json.loads(arq.read_text(encoding="utf-8"))["requisitos"]
        casos = eventos_por_caso(cod)
        linhas = [dict(caso=c, requisito=r["id"], resultado=res, detalhe=det)
                  for c, ev in casos.items() for r in req for res, det in [avaliar(r["teste"], ev)]]
        df = pd.DataFrame(linhas)
        df.to_csv(OUT / f"conformidade_{cod}.csv", index=False)
        resumo = {}
        for r in req:
            x = df[df.requisito == r["id"]].resultado.value_counts().to_dict()
            ap = x.get("conforme", 0) + x.get("nao_conforme", 0)
            resumo[r["id"]] = dict(exigencia=r["exigencia"], criticidade=r.get("criticidade"), tipo=r["teste"]["tipo"],
                                   **{k: int(x.get(k, 0)) for k in RESULTADOS},
                                   pct_conforme=round(100 * x.get("conforme", 0) / ap, 1) if ap else None)
        (OUT / f"conformidade_{cod}.json").write_text(json.dumps(dict(codigo=cod, casos=len(casos), requisitos=resumo),
                                                                 ensure_ascii=False, indent=1), encoding="utf-8")
        print(cod, len(casos), "casos,", len(req), "requisitos")


if __name__ == "__main__":
    main(sys.argv[1:] or CODIGOS_FASE3)
