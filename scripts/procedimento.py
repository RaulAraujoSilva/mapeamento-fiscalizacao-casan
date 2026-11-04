"""Fase 2 — do caso ao procedimento: agrega a coorte de cada código por atividade do modelo canônico.

Entrada: atribuições peça → atividade (saida/fase2/atribuicoes_<cod>.csv, do classificador), linha do tempo de cada
processo (mesma regra do piloto: fatos.linha_do_tempo), fichas de trabalho e trilha.
Por código:
  - casos (com trilha nativa, migrada, sem trilha), lead time dos nativos encerrados (mediana, quartis, n);
  - variantes: sequência de atividades (ocorrências consecutivas iguais fundidas) com frequência; como quase todo
    caso tem laços próprios, também o caminho (atividades na ordem da 1ª ocorrência, sem repetição);
  - conformidade: atividades do modelo ausentes por caso, fração das peças próprias SUBSTANTIVAS (parecer, voto,
    relatório, nota técnica...) "fora do modelo" — expediente (encaminhamento, ofício, anexo) fica fora do modelo
    por regra e é contado à parte;
  - transições entre atividades (probabilidade de cada saída) — base das decisões do BPMN revisado;
  - por atividade: em quantos casos ocorre, laço (casos com 2+ ocorrências), execução, espera antes e horas
    (mediana, quartis, n), ferramentas, insumos e competências mais frequentes (% dos casos em que aparecem).
Fichas de dois modelos (Gemini e, onde o crédito acabou, Haiku 5.5): a saída conta as fichas por modelo e por
atividade, porque as horas-piso do Haiku tendem a ser maiores (saida/fase2/comparacao_modelos_fichas.json).
Situação de cada código (campo situacao), pela auditoria às cegas do classificador fora do piloto
(saida/fase2/auditoria_classificador.json) e pelo número de casos:
  procedimento  = ≥ MIN_CASOS casos e concordância nas peças substantivas ≥ CRITERIO;
  indicativo    = ≥ MIN_CASOS casos, mas concordância abaixo do critério (ou sem auditoria): números com ressalva;
  estudo_de_caso = menos de MIN_CASOS casos.
  - por caso nativo (trilha do SEI): soma das esperas entre atividades, das execuções e das horas das ocorrências,
    lead time, espera de terceiros, ofícios, retornos e unidades ativas (distribuições) e posse por unidade.
Regras: espera antes da 1ª ocorrência só conta em processo com trilha (sem trilha, o início é desconhecido);
espera entre ocorrências vale para todos (datas de juntada das peças). Nenhum número é digitado: tudo sai daqui.

Saída: saida/fase2/procedimento_<cod>.json e casos_<cod>.json (linha do tempo de cada caso nativo: ocorrências com
espera antes, execução, espera por unidade e horas; base da simulação do TO-BE na fase 3)."""
from __future__ import annotations

import json
from collections import Counter, defaultdict

import numpy as np
import pandas as pd

from comum import SAIDA, dias_uteis, documentos, somar_du
from fatos import linha_do_tempo
from selecionar_piloto import SUBSTANTIVAS

DIR = SAIDA / "bpmn"
OUT = SAIDA / "fase2"
MIN_CASOS, CRITERIO = 5, 0.85


def situacao(casos: int, aud: dict | None) -> str:
    if casos < MIN_CASOS:
        return "estudo_de_caso"
    if aud and (aud.get("concordancia_substantivas") or 0) >= CRITERIO:
        return "procedimento"
    return "indicativo"


def dist(vals) -> dict | None:
    v = [float(x) for x in vals if x is not None and not pd.isna(x)]
    if not v:
        return None
    q1, md, q3 = np.percentile(v, [25, 50, 75])
    return dict(n=len(v), mediana=round(md, 1), q1=round(q1, 1), q3=round(q3, 1), max=round(max(v), 1))


def fichas_por_ref() -> dict:
    out = {}
    for ln in open(SAIDA / "fichas_trabalho.jsonl", encoding="utf-8"):
        d = json.loads(ln)
        out[f"{d['processo']}:{d['sei_doc_id']}"] = d["ficha"] | {"_modelo": d.get("modelo")}
    return out


def janelas_terceiros() -> dict:
    """Por processo, os intervalos em que a espera é tempo de resposta de terceiro (ofício com prazo, até a resposta ou
    o prazo + 5 du, a mesma regra de trilhas.janelas_espera_externa)."""
    j = pd.read_csv(SAIDA / "janelas_terceiros.csv", parse_dates=["oficio_data", "resposta_data"])
    j = j[j.situacao.str.startswith("terceiros")]
    out = defaultdict(list)
    for r in j.itertuples():
        out[r.numero_processo].append((r.oficio_data, min(r.resposta_data, somar_du(r.oficio_data, r.prazo_dias + 5))))
    return out


def terceiros_no_intervalo(janelas: list, ini, fim) -> float:
    """Dias úteis de [ini, fim] cobertos pelas janelas de terceiros (unidas)."""
    ints = sorted((max(a, ini), min(b, fim)) for a, b in janelas if min(b, fim) > max(a, ini))
    tot, cur = 0.0, None
    for a, b in ints:
        if cur and a <= cur[1]:
            cur = (cur[0], max(cur[1], b))
        else:
            tot += dias_uteis(*cur) if cur else 0.0
            cur = (a, b)
    return tot + (dias_uteis(*cur) if cur else 0.0)


def main():
    terc = janelas_terceiros()
    co = pd.read_csv(SAIDA / "coorte_fase2.csv").set_index("numero")
    ind = pd.read_csv(SAIDA / "processos_indicadores.csv", parse_dates=["inicio", "ultimo_andamento"]).set_index("numero")
    esf = pd.read_csv(SAIDA / "esforco_documentos.csv", dtype={"numero": str}, parse_dates=["data_inclusao"])
    esf["ref"] = esf.numero_processo + ":" + esf.numero
    esf = esf.set_index("ref")
    posse = pd.read_csv(SAIDA / "posse.csv", parse_dates=["inicio", "fim"])
    fichas = fichas_por_ref()
    arq_aud = OUT / "auditoria_classificador.json"
    auditoria = json.loads(arq_aud.read_text(encoding="utf-8"))["resumo"] if arq_aud.exists() else {}
    dd = documentos()
    categoria = dict(zip(dd.numero_processo + ":" + dd.numero.astype(str), dd.categoria))
    for arq in sorted(OUT.glob("atribuicoes_*.csv")):
        cod = arq.stem.split("_")[1]
        atr = pd.read_csv(arq)
        mod = json.loads((DIR / f"modelo_{cod}.json").read_text(encoding="utf-8"))
        raias = {r["id"]: (r["id"] + " " + r["nome"]).upper() for r in mod["raias"]}
        tarefas = {e["id"]: e for e in mod["elementos"] if e["tipo"] == "tarefa"}
        ordem = {e["id"]: k for k, e in enumerate(mod["elementos"])}
        casos = sorted(atr.processo.unique())
        por_ativ = defaultdict(lambda: defaultdict(list))
        variantes, caminhos, trans, ausentes, fora, fora_exp = Counter(), Counter(), Counter(), Counter(), [], []
        por_caso, posse_un, casos_nat = defaultdict(list), defaultdict(list), []
        for n in casos:
            trilha = co.loc[n, "trilha"] if n in co.index else "nativa"
            a = atr[atr.processo == n]
            sub = a.ref.map(categoria).isin(SUBSTANTIVAS)
            if sub.any():
                fora.append(float((a[sub].atividade == "fora_do_modelo").mean()))
            if (~sub).any():
                fora_exp.append(float((a[~sub].atividade == "fora_do_modelo").mean()))
            atrib = [(t, r) for t, r in zip(a.atividade, a.ref) if t in tarefas]
            if n in ind.index:
                pi, po = ind.loc[n], posse[posse.numero == n]
            else:  # sem trilha: início e fim = primeira e última peça do processo
                d = esf[esf.numero_processo == n].data_inclusao
                pi, po = pd.Series(dict(inicio=d.min(), ultimo_andamento=d.max())), posse.iloc[0:0]
            oc = linha_do_tempo(n, atrib, tarefas, ordem, raias, esf, pi, po)
            seq = [o["atividade"] for o in oc]
            variantes[" → ".join(seq)] += 1
            caminhos[" → ".join(dict.fromkeys(seq))] += 1
            trans.update(zip(["início"] + seq, seq + ["fim"]))
            ausentes.update(set(tarefas) - set(seq))
            cont = Counter(seq)
            if trilha == "nativa" and oc:  # totais por caso: só com trilha nativa (início e posse conhecidos)
                por_caso["espera_entre_atividades"].append(sum(o["espera_antes_du"] for o in oc))
                por_caso["execucao_atividades"].append(sum(o["execucao_du"] for o in oc))
                por_caso["horas_piso"].append(sum(o["horas_piso"] for o in oc))
                por_caso["horas_teto"].append(sum(o["horas_teto"] for o in oc))
                por_caso["lead"].append(float(pi.lead_du))
                for col, nome in (("espera_externa_du", "terceiros"), ("espera_indeterminada_du", "indeterminado"),
                                  ("n_oficios", "oficios"), ("retornos_iteracao", "retornos"),
                                  ("n_unidades_ativas", "unidades_ativas")):
                    por_caso[nome].append(float(pi[col]))
                for u, v in po.groupby("sigla").du.sum().items():
                    posse_un[u].append(float(v))
                soma = sum(o["espera_antes_du"] + o["execucao_du"] for o in oc)
                casos_nat.append(dict(
                    numero=n, encerrado=bool(co.loc[n, "encerrado"]) if n in co.index else None,
                    lead_du=float(pi.lead_du), terceiros_du=float(pi.espera_externa_du),
                    indeterminado_du=float(pi.espera_indeterminada_du), cauda_du=round(float(pi.lead_du) - soma, 1),
                    posse_du={u: float(v) for u, v in po.groupby("sigla").du.sum().items()},
                    ocorrencias=[dict(atividade=o["atividade"], inicio=o["inicio"], fim=o["fim"],
                                      espera_antes_du=o["espera_antes_du"], execucao_du=o["execucao_du"],
                                      espera_antes_por_unidade=o["espera_antes_por_unidade"],
                                      espera_antes_terceiros_du=min(o["espera_antes_du"], terceiros_no_intervalo(
                                          terc[n], pd.Timestamp(oc[k - 1]["fim"] if k else pi.inicio),
                                          pd.Timestamp(o["inicio"]))),
                                      horas_piso=round(o["horas_piso"], 2), horas_teto=round(o["horas_teto"], 2))
                                 for k, o in enumerate(oc)]))
            for k, o in enumerate(oc):
                t = o["atividade"]
                x = por_ativ[t]
                x["execucao"].append(o["execucao_du"])
                if k > 0 or trilha != "sem":
                    x["espera"].append(o["espera_antes_du"])
                x["horas_piso"].append(o["horas_piso"])
                x["horas_teto"].append(o["horas_teto"])
            for t, c_ in cont.items():
                x = por_ativ[t]
                x["casos"].append(n)
                x["ocorrencias"].append(c_)
                ft, ins, comp, perda = set(), set(), set(), set()
                for r in a[a.atividade == t].ref:
                    f = fichas.get(r) or {}
                    if f:
                        x["modelos"].append(f["_modelo"])
                    ft |= {s.strip().lower() for s in f.get("ferramentas") or [] if s}
                    ins |= {(i.get("descricao") or "").strip() for i in f.get("insumos") or [] if i.get("tipo") in
                            ("norma_ou_contrato", "base_externa", "sistema_ou_base_interna",
                                                                         "precedente_ou_jurisprudencia")}
                    comp |= {f"{c.get('area')} ({c.get('nivel')})" for c in f.get("competencias") or [] if c.get("area")}
                    perda |= {s_.get("tipo") for s_ in f.get("sinais_perda") or [] if s_.get("tipo")}  # só ancorados
                x["ferramentas"].append(ft)
                x["insumos"].append(ins)
                x["competencias"].append(comp)
                x["perda"].append(perda)
        nc = len(casos)

        def freq(conjs, top=8):
            c_ = Counter(s for cj in conjs for s in cj if s)
            ordem = sorted(c_.items(), key=lambda kv: (-kv[1], kv[0]))[:top]  # empate pelo nome: saída reproduzível
            return [dict(item=k, casos=v, pct=round(100 * v / nc)) for k, v in ordem]
        saidas = defaultdict(Counter)
        for (a_, b_), v in trans.items():
            saidas[a_][b_] += v
        nat = co[(co.processo_principal == cod) & (co.trilha == "nativa") & (co.encerrado == True)]  # noqa: E712
        res = dict(
            codigo=cod, nome=mod["nome"], casos=nc, situacao=situacao(nc, auditoria.get(cod)),
            auditoria_classificador=auditoria.get(cod),
            trilha={k: int(v) for k, v in co[co.index.isin(casos)].trilha.value_counts().items()},
            lead_nativos_encerrados=dist(ind.loc[ind.index.intersection(nat.index)].lead_du),
            por_caso_nativo={k: dist(v) for k, v in por_caso.items()},
            posse_por_unidade_nativos={u: dist(v) for u, v in
                                       sorted(posse_un.items(), key=lambda kv: -np.median(kv[1]))[:8]},
            fora_do_modelo_pct_substantivas=dist([100 * f for f in fora]),
            fora_do_modelo_pct_expediente=dist([100 * f for f in fora_exp]),
            variantes=[dict(sequencia=k, casos=v, pct=round(100 * v / nc)) for k, v in variantes.most_common(10)],
            n_variantes=len(variantes),
            caminhos=[dict(sequencia=k, casos=v, pct=round(100 * v / nc)) for k, v in caminhos.most_common(10)],
            n_caminhos=len(caminhos),
            transicoes={a_: [dict(para=b_, n=v, pct=round(100 * v / sum(c_.values()))) for b_, v in c_.most_common()]
                        for a_, c_ in saidas.items()},
            atividades={t: dict(
                nome=tarefas[t]["nome"], casos=len(por_ativ[t]["casos"]),
                pct_casos=round(100 * len(por_ativ[t]["casos"]) / nc),
                casos_com_laco=sum(1 for c_ in por_ativ[t]["ocorrencias"] if c_ > 1),
                execucao_du=dist(por_ativ[t]["execucao"]), espera_antes_du=dist(por_ativ[t]["espera"]),
                horas_piso=dist(por_ativ[t]["horas_piso"]), horas_teto=dist(por_ativ[t]["horas_teto"]),
                ferramentas=freq(por_ativ[t]["ferramentas"]), insumos=freq(por_ativ[t]["insumos"], 6),
                competencias=freq(por_ativ[t]["competencias"], 6),
                sinais_perda=freq(por_ativ[t]["perda"], 8),
                fichas_por_modelo=dict(Counter(por_ativ[t]["modelos"])),
                ausente_em=ausentes.get(t, 0)) for t in tarefas},
            fichas_por_modelo=dict(Counter(m for t in tarefas for m in por_ativ[t]["modelos"])),
        )
        (OUT / f"casos_{cod}.json").write_text(json.dumps(dict(codigo=cod, casos=casos_nat), ensure_ascii=False,
                                                          indent=1, default=str), encoding="utf-8")
        (OUT / f"procedimento_{cod}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str),
                                                     encoding="utf-8")
        print(cod, res["situacao"], nc, "casos;", len(variantes), "variantes;", len(caminhos), "caminhos; substantivas fora do modelo (mediana %):",
              (res["fora_do_modelo_pct_substantivas"] or {}).get("mediana"))


if __name__ == "__main__":
    main()
