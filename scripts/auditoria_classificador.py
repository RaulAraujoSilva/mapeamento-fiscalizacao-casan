"""Fase 2 — auditoria independente do classificador de atividade fora do piloto.

A avaliação contra os vínculos do piloto é otimista (gatilho e saída das atividades vêm dos mesmos casos). Aqui a
amostra sai de processos da coorte que NÃO estão no piloto: por código, até 14 peças próprias substantivas e 6 de
expediente com atividade candidata, semente fixa. Um auditor (revisão por agente, sem ver os rótulos do
classificador) recebe o mesmo retrato do processo, com só as peças da amostra marcadas ROTULAR, e pode ler o
texto integral da peça. Critério da fase 2: concordância ≥ 85% nas peças substantivas.

  --preparar  → dados/auditoria_classificador/pacote_<Pxx>.md e amostra.csv (contém nomes: fica fora do git)
  (auditor)   → dados/auditoria_classificador/rotulos_<Pxx>.json  {"<ref>": {"atividade": "t3", "motivo": "..."}}
  --comparar  → saida/fase2/auditoria_classificador.json (concordância por código e divergências)"""
from __future__ import annotations

import argparse
import json

import pandas as pd

from classificar_atividades import DIR, FORA, carregar_contexto, montar
from comum import DADOS, SAIDA
from fichas_atividades import limpar_pessoais
from selecionar_piloto import SUBSTANTIVAS

AUD = DADOS / "auditoria_classificador"
N_SUB, N_EXP, SEMENTE = 14, 6, 11


def preparar(codigos):
    AUD.mkdir(parents=True, exist_ok=True)
    docs, fichas, rel = carregar_contexto()
    cat = dict(zip(docs.numero_processo + ":" + docs.numero.astype(str), docs.categoria))
    co = pd.read_csv(SAIDA / "coorte_fase2.csv")
    linhas = []
    for cod in codigos:
        atr = pd.read_csv(SAIDA / "fase2" / f"atribuicoes_{cod}.csv")
        fora_piloto = set(co[(co.processo_principal == cod) & ~co.no_piloto].numero)
        a = atr[atr.processo.isin(fora_piloto) & (atr.atividade != "fora_da_raia")].copy()
        a["substantiva"] = a.ref.map(cat).isin(SUBSTANTIVAS)
        am = pd.concat([a[a.substantiva].sample(min(N_SUB, int(a.substantiva.sum())), random_state=SEMENTE),
                        a[~a.substantiva].sample(min(N_EXP, int((~a.substantiva).sum())), random_state=SEMENTE)])
        alvo = set(am.ref)
        md = [f"# Auditoria do classificador — {cod}", "",
              "Para cada peça marcada ROTULAR, diga qual atividade do modelo ela executa (só entre as candidatas "
              "da peça) ou fora_do_modelo. As demais peças são contexto.", ""]
        for n in sorted(am.processo.unique()):
            usuario, pecas, _ = montar(cod, n, docs, fichas, rel)
            for p in pecas:  # só a amostra fica marcada para rotular
                if p["cand"] and p["ref"] not in alvo:
                    usuario = usuario.replace(f"[{p['i']}] ", f"[{p['i']}] (contexto) ", 1)
            usuario = "\n".join(ln if "(contexto)" not in ln else ln.replace("ROTULAR — candidatas", "candidatas")
                                for ln in usuario.split("\n"))
            refs = {p["i"]: p["ref"] for p in pecas if p["ref"] in alvo}
            md += [f"## Processo {n}", "", "Peças a rotular (índice → ref): "
                   + "; ".join(f"[{i}] {r}" for i, r in refs.items()), "", "```", usuario, "```", ""]
        (AUD / f"pacote_{cod}.md").write_text("\n".join(md), encoding="utf-8")
        linhas.append(am.assign(codigo=cod)[["codigo", "processo", "ref", "tipo", "substantiva"]])
        print(cod, len(am), "peças em", am.processo.nunique(), "processos")
    nova = pd.concat(linhas)
    if (AUD / "amostra.csv").exists():  # preparar outros códigos não apaga a amostra já auditada
        velha = pd.read_csv(AUD / "amostra.csv")
        nova = pd.concat([velha[~velha.codigo.isin(codigos)], nova])
    nova.to_csv(AUD / "amostra.csv", index=False, encoding="utf-8-sig")


def comparar():
    am = pd.read_csv(AUD / "amostra.csv")
    res, div = {}, []
    for cod, g in am.groupby("codigo"):
        arq = AUD / f"rotulos_{cod}.json"
        if not arq.exists():
            continue
        aud = json.loads(arq.read_text(encoding="utf-8"))
        atr = pd.read_csv(SAIDA / "fase2" / f"atribuicoes_{cod}.csv").set_index("ref")
        g = g[g.ref.isin(aud)].assign(classificador=lambda x: x.ref.map(atr.atividade),
                                      auditor=lambda x: x.ref.map(lambda r: aud[r]["atividade"]))
        ok = g.classificador == g.auditor
        res[cod] = dict(pecas=len(g), concordancia=round(float(ok.mean()), 3),
                        substantivas=int(g.substantiva.sum()),
                        concordancia_substantivas=round(float(ok[g.substantiva].mean()), 3) if g.substantiva.any() else None,
                        auditor_fora_do_modelo=int((g.auditor == FORA).sum()))
        div += [dict(codigo=cod, ref=r.ref, tipo=r.tipo, substantiva=bool(r.substantiva), classificador=r.classificador,
                     auditor=r.auditor, motivo_auditor=limpar_pessoais(aud[r.ref].get("motivo", "")))
                for r in g[~ok].itertuples()]
    tot = pd.DataFrame([dict(c=k, **v) for k, v in res.items()])
    if len(tot):
        sub = sum((v["concordancia_substantivas"] or 0) * v["substantivas"] for v in res.values())
        res["_total"] = dict(pecas=int(tot.pecas.sum()),
                             concordancia=round(float((tot.concordancia * tot.pecas).sum() / tot.pecas.sum()), 3),
                             substantivas=int(tot.substantivas.sum()),
                             concordancia_substantivas=round(sub / tot.substantivas.sum(), 3), criterio=0.85)
    (SAIDA / "fase2" / "auditoria_classificador.json").write_text(
        json.dumps(dict(resumo=res, divergencias=div), ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preparar", nargs="*", help="códigos (padrão: todos com atribuições)")
    ap.add_argument("--comparar", action="store_true")
    args = ap.parse_args()
    if args.preparar is not None:
        cods = args.preparar or sorted(p.stem.split("_")[1] for p in (SAIDA / "fase2").glob("atribuicoes_*.csv"))
        preparar([c for c in cods if (DIR / f"modelo_{c}.json").exists()])
    if args.comparar:
        comparar()


if __name__ == "__main__":
    main()
