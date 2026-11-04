"""Fase 2 — comparabilidade das fichas entre modelos: a rodada da coorte começou com Gemini (OpenRouter) e o crédito
acabou; as fichas que faltavam foram feitas com Claude Haiku 5.5. Mede, numa amostra estratificada por natureza
(até 5 por natureza, semente fixa) de fichas já feitas com Gemini, a concordância do Haiku no mesmo documento.

Cache das fichas Haiku da amostra em dados/fichas_comparacao/ (não entram em saida/fichas_trabalho.*).
Saída: saida/fase2/comparacao_modelos_fichas.json (+ .csv por documento)"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

import fichas_trabalho as F
from comum import DADOS, SAIDA

MODELO_B = "claude-haiku-5-5"
DIR = DADOS / "fichas_comparacao"
POR_NATUREZA = 5
SEMENTE = 7


def main():
    DIR.mkdir(parents=True, exist_ok=True)
    tar = {(t["processo"], t["sei_doc_id"]): t for t in F.montar_tarefas(None)}
    gem = {}
    for k in tar:
        a = F.CACHE / f"{k[0].replace('/', '_')}__{k[1]}.json"
        if a.exists():
            d = json.loads(a.read_text(encoding="utf-8"))
            if d.get("modelo", "").startswith("google/") and d.get("prompt_versao") == F.PROMPT_VERSAO:
                gem[k] = d["ficha"]
    df = pd.DataFrame([dict(k=k, nat=f.get("natureza_trabalho")) for k, f in gem.items()])
    amostra = pd.concat([g.sample(min(len(g), POR_NATUREZA), random_state=SEMENTE) for _, g in df.groupby("nat")])

    def um(k):
        arq = DIR / f"{k[0].replace('/', '_')}__{k[1]}.json"
        if arq.exists():
            return k, json.loads(arq.read_text(encoding="utf-8"))
        f, _ = F.chamar_anthropic(MODELO_B, tar[k]["usuario"])
        f = F.legado(F.ancorar(f, tar[k]["_texto"]))
        arq.write_text(json.dumps(f, ensure_ascii=False), encoding="utf-8")
        return k, f

    with ThreadPoolExecutor(8) as ex:
        hk = dict(ex.map(um, amostra.k))

    def n_anc(f):
        return (sum(len(f.get(c) or []) for c in ("insumos", "competencias", "sinais_perda"))
                + len(f.get("ferramentas") or []), len(f.get("nao_ancorados") or []))
    r = pd.DataFrame([dict(processo=k[0], sei_doc_id=k[1], categoria=tar[k]["categoria"],
                           natureza_a=gem[k].get("natureza_trabalho"), natureza_b=hk[k].get("natureza_trabalho"),
                           complexidade_a=gem[k].get("complexidade"), complexidade_b=hk[k].get("complexidade"),
                           horas_a=gem[k].get("horas_estimadas"), horas_b=hk[k].get("horas_estimadas"),
                           ancorados_a=n_anc(gem[k])[0], nao_ancorados_a=n_anc(gem[k])[1],
                           ancorados_b=n_anc(hk[k])[0], nao_ancorados_b=n_anc(hk[k])[1],
                           prazo_a=gem[k].get("prazo_concedido_dias"), prazo_b=hk[k].get("prazo_concedido_dias"))
                      for k in hk])
    dc = (pd.to_numeric(r.complexidade_a) - pd.to_numeric(r.complexidade_b)).abs()
    razao = pd.to_numeric(r.horas_b) / pd.to_numeric(r.horas_a)
    res = dict(modelo_a="google/gemini-3.6-flash", modelo_b=MODELO_B, n=len(r),
               natureza_igual=round(float((r.natureza_a == r.natureza_b).mean()), 3),
               complexidade_igual=round(float((dc == 0).mean()), 3),
               complexidade_dif_ate_1=round(float((dc <= 1).mean()), 3),
               complexidade_media=[round(float(pd.to_numeric(r.complexidade_a).mean()), 2),
                                   round(float(pd.to_numeric(r.complexidade_b).mean()), 2)],
               razao_horas_b_sobre_a=dict(mediana=round(float(razao.median()), 2), q1=round(float(razao.quantile(.25)), 2),
                                          q3=round(float(razao.quantile(.75)), 2)),
               itens_ancorados=[int(r.ancorados_a.sum()), int(r.ancorados_b.sum())],
               itens_nao_ancorados=[int(r.nao_ancorados_a.sum()), int(r.nao_ancorados_b.sum())],
               prazo_igual=round(float((r.prazo_a.fillna(-1) == r.prazo_b.fillna(-1)).mean()), 3))
    (SAIDA / "fase2").mkdir(parents=True, exist_ok=True)
    r.to_csv(SAIDA / "fase2" / "comparacao_modelos_fichas.csv", index=False, encoding="utf-8-sig")
    (SAIDA / "fase2" / "comparacao_modelos_fichas.json").write_text(json.dumps(res, ensure_ascii=False, indent=1),
                                                                     encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
