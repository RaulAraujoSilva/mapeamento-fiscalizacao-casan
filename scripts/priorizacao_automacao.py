"""Matriz de priorização da automação por tipo de processo, com modelo de custo e retorno (fase 4).

Pergunta: que tipo de processo serve de piloto para um sistema que automatize o processo inteiro? Procura alto volume,
trabalho de análise sobre dado estruturado e não estruturado, regras claras e padrões contra o que medir.

Cada critério sai de uma saída já verificada do método, e o peso e a régua 1 → 5 estão em comum.PRIORIZACAO_CRITERIOS:
- volume: volume_anual.json (piso de deliberações em toda a agência) ÷ (fração da carteira com deliberação × revocação
  da regra na coorte) = estimativa de processos por ano;
- análise, dados, regras, padrão: fichas de trabalho das peças da coorte (natureza, cálculos, insumos, testes,
  composição do texto) e caminho mais frequente do procedimento;
- completude: potencial de IA por atividade da avaliação AS-IS, ponderado pelas horas da atividade nos casos nativos.

Custo e retorno (3 cenários, parâmetros-hipótese em comum.py): retorno = volume × horas por caso × fração automatizável
× custo-hora do servidor; custo = capacidades de IA + configuração por atividade (com acréscimo pela variabilidade) +
validação por servidor; custo anual = manutenção + leitura pelo modelo.

Saídas: saida/fase4/matriz_automacao.csv/.json, capacidades_transversais.csv, Priorizacao_Automacao.xlsx,
matriz_automacao.png e docs/PRIORIZACAO_AUTOMACAO.md."""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from statistics import median

import pandas as pd

from comum import (CARGO_PADRAO, CASOS_VALIDACAO, CENARIOS_AUTOMACAO, CUSTO_HORA_BASE, CUSTO_HORA_DEV, FATOR_CUSTO_TOTAL,
                   FRACAO_AUTOMATIZAVEL, HORAS_CAPACIDADE, HORAS_CONFIG_ATIVIDADE, HORAS_PLATAFORMA, HORAS_VALIDACAO_CASO,
                   HORIZONTE_ANOS, MANUTENCAO_ANUAL, NATUREZAS_ANALISE, PORTOES_PILOTO, PRECO_LLM_MCHAR,
                   PRIORIZACAO_CRITERIOS, RAIZ, SAIDA, VARIABILIDADE_FATOR, horas_ano_fte)

OUT = SAIDA / "fase4"
BPMN, F2, F3 = SAIDA / "bpmn", SAIDA / "fase2", SAIDA / "fase3"
DOC = RAIZ / "docs" / "PRIORIZACAO_AUTOMACAO.md"
FATOR_CENARIO = dict(zip(CENARIOS_AUTOMACAO, ("piso", "esperado", "teto")))
NOMES_CRITERIO = {"volume": "Volume", "analise": "Foco em análise", "dados": "Dados estruturados e não estruturados",
                  "regras": "Regras claras", "padrao": "Padronização", "completude": "Completude da automação"}
PORTAO_TEXTO = {"volume_medido": "volume sem medida confiável", "nota_volume": "volume abaixo do portão",
                "nota_regras": "regras abaixo do portão", "casos_coorte": "coorte pequena"}
ESTRUTURADO = {"base_externa", "sistema_ou_base_interna"}
NAO_ESTRUTURADO = {"documento_da_regulada", "precedente_ou_jurisprudencia"}


def nota(valor, cortes) -> int | None:
    """Régua 1 → 5: nota 1 abaixo do 1º corte, +1 a cada corte atingido."""
    if valor is None:
        return None
    return 1 + sum(valor >= c for c in cortes)


def nota_composta(notas: dict) -> float | None:
    """0–100, como no diagnóstico organizacional: Σ peso × nota / 5. Critério sem nota zera (não se presume)."""
    if any(notas.get(c) is None for c in PRIORIZACAO_CRITERIOS):
        return None
    return round(sum(PRIORIZACAO_CRITERIOS[c][0] * notas[c] for c in PRIORIZACAO_CRITERIOS) / 5, 1)


def volume_estimado(piso, pct_delib, revocacao) -> float | None:
    """Piso de deliberações ÷ fração dos processos do tipo que chegam à deliberação e que a regra pega."""
    if not piso or not pct_delib or not revocacao:
        return None
    return round(piso / (pct_delib / 100 * revocacao), 1)


def fracao_automatizavel(horas_por_atividade: dict, potencial: dict, i: int) -> float:
    """Fração das horas que a automação tira no cenário i, ponderada pelas horas de cada atividade."""
    tot = sum(horas_por_atividade.values())
    if not tot:
        return 0.0
    return sum(h * FRACAO_AUTOMATIZAVEL[potencial.get(a, "baixo")][i] for a, h in horas_por_atividade.items()) / tot


def custo_construcao_h(capacidades: set, n_atividades: int, variabilidade: float, incremental: bool = False) -> float:
    """Horas de desenvolvimento. Isolado: plataforma + capacidades + configuração. Incremental: só a configuração
    (plataforma e capacidades já existem na carteira)."""
    config = n_atividades * HORAS_CONFIG_ATIVIDADE * (1 + VARIABILIDADE_FATOR * variabilidade)
    if incremental:
        return round(config, 1)
    return round(HORAS_PLATAFORMA + sum(HORAS_CAPACIDADE[c] for c in sorted(capacidades)) + config, 1)


def payback_anos(custo, retorno_ano, custo_ano) -> float | None:
    liquido = retorno_ano - custo_ano
    return round(custo / liquido, 1) if liquido > 0 else None


def horas_por_atividade(casos: list[dict]) -> dict:
    """Horas (média de piso e teto) de cada atividade, somadas nos casos nativos."""
    h = defaultdict(float)
    for c in casos:
        for o in c["ocorrencias"]:
            h[o["atividade"]] += (o["horas_piso"] + o["horas_teto"]) / 2
    return h


def insumos_especificacao(cod: str) -> dict:
    """O que o método já produziu para especificar o sistema do tipo (contagens; os arquivos são a especificação)."""
    modelo = json.loads((BPMN / f"modelo_{cod}.json").read_text(encoding="utf-8"))
    el = modelo["elementos"]
    out = dict(tarefas=sum(e["tipo"] == "tarefa" for e in el), decisoes=sum(e["tipo"] == "xor" for e in el),
               tarefas_com_gatilho_e_saida=sum(e["tipo"] == "tarefa" and bool(e.get("gatilho")) and bool(e.get("saida"))
                                               for e in el))
    if (F3 / f"normas_{cod}.json").exists():
        req = json.loads((F3 / f"normas_{cod}.json").read_text(encoding="utf-8"))["requisitos"]
        conf = json.loads((F3 / f"conformidade_{cod}.json").read_text(encoding="utf-8"))["requisitos"]
        pct = sorted(v["pct_conforme"] for v in conf.values() if v.get("pct_conforme") is not None)
        out.update(requisitos=len(req), requisitos_com_teste=sum(bool(r.get("teste")) for r in req),
                   requisitos_medidos=len(pct), conformidade_mediana=median(pct) if pct else None)
    if (F3 / f"melhorias_{cod}.json").exists():
        out["melhorias"] = len(json.loads((F3 / f"melhorias_{cod}.json").read_text(encoding="utf-8"))["melhorias"])
    if (F3 / f"controles_{cod}.json").exists():
        c = json.loads((F3 / f"controles_{cod}.json").read_text(encoding="utf-8"))
        out.update({k: len(c[k]) for k in ("indicadores", "controles_qualidade_ia", "auditoria_continua")})
    return out


def fatos_de(cod: str) -> dict:
    return {f["id"]: f["valor"] for f in json.loads((BPMN / f"fatos_{cod}.json").read_text(encoding="utf-8"))["fatos"]}


def fichas_por_codigo() -> dict[str, list[dict]]:
    coorte = pd.read_csv(SAIDA / "coorte_fase2.csv")
    cod_de = dict(zip(coorte.numero, coorte.processo_principal))
    por = defaultdict(list)
    with open(SAIDA / "fichas_trabalho.jsonl", encoding="utf-8") as fh:
        for linha in fh:
            r = json.loads(linha)
            if r["processo"] in cod_de and r.get("ficha"):
                por[cod_de[r["processo"]]].append(r)
    return por


def sinais_fichas(fichas: list[dict]) -> dict:
    """Análise, dados, regras e padronização a partir das fichas das peças do tipo."""
    h_tot = h_an = h_padrao = 0.0
    an = []
    chars = defaultdict(float)
    for r in sorted(fichas, key=lambda r: (r["processo"], str(r["sei_doc_id"]))):
        f = r["ficha"]
        h = float(f.get("horas_estimadas") or 0)
        ct = f.get("composicao_texto") or {}
        h_tot += h
        h_padrao += h * ((ct.get("pct_padrao") or 0) + (ct.get("pct_transcricao") or 0)) / 100
        chars[r["processo"]] += float(r.get("n_chars") or 0)
        if f.get("natureza_trabalho") in NATUREZAS_ANALISE:
            h_an += h
            tipos = {i.get("tipo") for i in f.get("insumos") or []}
            an.append(dict(estruturado=bool(f.get("calculos")) or bool(tipos & ESTRUTURADO),
                           nao_estruturado=bool(tipos & NAO_ESTRUTURADO) or (f.get("n_documentos_analisados") or 0) > 0,
                           norma="norma_ou_contrato" in tipos, teste=bool(f.get("testes_auditoria"))))
    frac = (lambda k: round(sum(x[k] for x in an) / len(an), 3)) if an else (lambda k: None)
    return dict(pecas=len(fichas), pecas_analise=len(an), horas_fichas=round(h_tot, 1),
                frac_horas_analise=round(h_an / h_tot, 3) if h_tot else None,
                frac_estruturado=frac("estruturado"), frac_nao_estruturado=frac("nao_estruturado"),
                frac_norma=frac("norma"), frac_teste=frac("teste"),
                frac_texto_padrao=round(h_padrao / h_tot, 3) if h_tot else None,
                mchar_por_caso=round(median(chars.values()) / 1e6, 4) if chars else None)


def media(*v):
    v = [x for x in v if x is not None]
    return round(sum(v) / len(v), 3) if v else None


def avaliar_codigo(cod: str, fichas: list[dict], vol: dict) -> dict:
    fat = fatos_de(cod)
    proc = json.loads((F2 / f"procedimento_{cod}.json").read_text(encoding="utf-8"))
    casos = json.loads((F2 / f"casos_{cod}.json").read_text(encoding="utf-8"))["casos"]
    av = json.loads((BPMN / f"avaliacao_{cod}.json").read_text(encoding="utf-8"))
    potencial = {a: v.get("potencial_ia", "baixo") for a, v in av["atividades"].items()}
    horas_ativ = horas_por_atividade(casos)
    automatizaveis = sorted(a for a, p in potencial.items() if p in ("alto", "médio"))
    capacidades = {t for a in automatizaveis for t in av["atividades"][a].get("tipos_ia") or []}
    h_ativ_tot = sum(horas_ativ.values())
    s = sinais_fichas(fichas)

    v = vol["codigos"].get(cod) or {}
    pct_delib = fat.get("carteira.com_deliberacao_pct")
    rev = v.get("revocacao_coorte")
    confiavel = bool(rev is not None and rev >= PORTOES_PILOTO["revocacao_volume"])
    volume = volume_estimado(v.get("media_anual"), pct_delib, rev) if confiavel else None
    casos_coorte = fat.get("coorte.casos") or proc["casos"]
    caminho_freq = (fat.get("coorte.caminho_mais_frequente.casos") or 0) / casos_coorte if casos_coorte else None
    variabilidade = round(proc["n_caminhos"] / casos_coorte, 3) if casos_coorte else 1.0
    metricas = dict(
        volume=volume, analise=s["frac_horas_analise"],
        dados=media(s["frac_estruturado"], s["frac_nao_estruturado"]),
        regras=media(s["frac_norma"], s["frac_teste"]),
        padrao=media(s["frac_texto_padrao"], round(caminho_freq, 3) if caminho_freq is not None else None),
        completude=round(sum(h for a, h in horas_ativ.items() if potencial.get(a) == "alto") / h_ativ_tot, 3)
        if h_ativ_tot else None)
    notas = {c: nota(metricas[c], PRIORIZACAO_CRITERIOS[c][1]) for c in PRIORIZACAO_CRITERIOS}

    ch = CUSTO_HORA_BASE[CARGO_PADRAO]
    hp, ht = fat.get("coorte.caso.horas_piso.mediana"), fat.get("coorte.caso.horas_teto.mediana")
    horas_caso = dict(zip(CENARIOS_AUTOMACAO, (hp, (hp + ht) / 2 if hp is not None and ht is not None else None, ht)))
    h_isolado = custo_construcao_h(capacidades, len(automatizaveis), variabilidade)
    h_incr = custo_construcao_h(capacidades, len(automatizaveis), variabilidade, incremental=True)
    cen = {}
    for i, k in enumerate(CENARIOS_AUTOMACAO):
        fa = fracao_automatizavel(horas_ativ, potencial, i)
        validacao = CASOS_VALIDACAO * HORAS_VALIDACAO_CASO * ch * FATOR_CUSTO_TOTAL[FATOR_CENARIO[k]]
        construcao = h_isolado * CUSTO_HORA_DEV[i] + validacao
        incremental = h_incr * CUSTO_HORA_DEV[i] + validacao
        r = dict(fracao_automatizavel=round(fa, 3), custo_construcao=round(construcao), custo_incremental=round(incremental))
        if volume is not None and horas_caso[k] is not None:
            horas_ano = volume * horas_caso[k] * fa
            retorno = horas_ano * ch * FATOR_CUSTO_TOTAL[FATOR_CENARIO[k]]
            llm = volume * (s["mchar_por_caso"] or 0) * PRECO_LLM_MCHAR[i]
            custo_ano = MANUTENCAO_ANUAL * construcao + llm
            custo_ano_incr = MANUTENCAO_ANUAL * incremental + llm
            r.update(horas_liberadas_ano=round(horas_ano, 1), fte_liberado=round(horas_ano / horas_ano_fte(), 2),
                     retorno_ano=round(retorno), custo_ano=round(custo_ano), custo_llm_ano=round(llm),
                     liquido_ano=round(retorno - custo_ano), liquido_incremental_ano=round(retorno - custo_ano_incr),
                     payback_anos=payback_anos(construcao, retorno, custo_ano),
                     payback_incremental_anos=payback_anos(incremental, retorno, custo_ano_incr),
                     saldo_horizonte=round(HORIZONTE_ANOS * (retorno - custo_ano) - construcao))
        cen[k] = r

    portoes = dict(volume_medido=volume is not None,
                   nota_volume=(notas["volume"] or 0) >= PORTOES_PILOTO["nota_volume"],
                   nota_regras=(notas["regras"] or 0) >= PORTOES_PILOTO["nota_regras"],
                   casos_coorte=casos_coorte >= PORTOES_PILOTO["casos_coorte"])
    lead, espera = fat.get("coorte.caso.lead.mediana"), fat.get("coorte.caso.espera_entre_atividades.mediana")
    return dict(codigo=cod, nome=proc["nome"], situacao=proc["situacao"], casos_coorte=casos_coorte,
                casos_nativos=len(casos), concordancia_classificador=(proc.get("auditoria_classificador") or {}).get(
                    "concordancia_substantivas"),
                volume=dict(piso_deliberacoes=v.get("media_anual"), pct_com_deliberacao=pct_delib, revocacao=rev,
                            coorte_com_deliberacao=v.get("coorte_com_deliberacao"), estimado=volume),
                sinais=s, caminho_mais_frequente=round(caminho_freq, 3) if caminho_freq is not None else None,
                variabilidade=variabilidade, metricas=metricas, notas=notas, nota_composta=nota_composta(notas),
                atividades=len(potencial), atividades_automatizaveis=len(automatizaveis),
                atividades_alto=sum(p == "alto" for p in potencial.values()), capacidades=sorted(capacidades),
                horas_dev=dict(isolado=h_isolado, incremental=h_incr), horas_caso=horas_caso,
                espera_no_lead=round(espera / lead, 3) if lead and espera is not None else None,
                cenarios=cen, portoes=portoes, especificacao=insumos_especificacao(cod))


def classificar(linhas: list[dict]) -> None:
    """Piloto = passa todos os portões, maior nota composta; empate pelo saldo esperado no horizonte."""
    for r in linhas:
        p = r["portoes"]
        if not p["volume_medido"] or not p["casos_coorte"]:
            r["prioridade"] = "reavaliar com dados"
        elif all(p.values()):
            r["prioridade"] = "candidato a piloto"
        elif (r["nota_composta"] or 0) >= 60:
            r["prioridade"] = "próxima onda"
        else:
            r["prioridade"] = "não priorizar agora"
    cand = sorted((r for r in linhas if r["prioridade"] == "candidato a piloto"),
                  key=lambda r: (-(r["nota_composta"] or 0), -r["cenarios"]["esperado"].get("saldo_horizonte", 0),
                                 r["codigo"]))
    if cand:
        cand[0]["prioridade"] = "piloto"


def capacidades_transversais(linhas: list[dict]) -> pd.DataFrame:
    """Cada capacidade de IA na carteira: em quantos tipos e atividades aparece e quantas horas por ano alcança."""
    agg = defaultdict(lambda: dict(tipos=set(), atividades=0, horas_ano=0.0))
    for r in linhas:
        av = json.loads((BPMN / f"avaliacao_{r['codigo']}.json").read_text(encoding="utf-8"))["atividades"]
        casos = json.loads((F2 / f"casos_{r['codigo']}.json").read_text(encoding="utf-8"))["casos"]
        h = horas_por_atividade(casos)
        tot = sum(h.values()) or 1
        base = (r["volume"]["estimado"] or 0) * (r["horas_caso"]["esperado"] or 0)
        for a, v in sorted(av.items()):
            if v.get("potencial_ia") not in ("alto", "médio"):
                continue
            for t in v.get("tipos_ia") or []:
                g = agg[t]
                g["tipos"].add(r["codigo"])
                g["atividades"] += 1
                g["horas_ano"] += base * h.get(a, 0) / tot
    return pd.DataFrame([dict(capacidade=t, tipos_de_processo=len(g["tipos"]), codigos=", ".join(sorted(g["tipos"])),
                              atividades=g["atividades"], horas_ano_alcancadas=round(g["horas_ano"], 1),
                              horas_construcao=HORAS_CAPACIDADE[t],
                              horas_ano_por_hora_construcao=round(g["horas_ano"] / HORAS_CAPACIDADE[t], 2))
                         for t, g in agg.items()]).sort_values(["horas_ano_alcancadas", "capacidade"],
                                                               ascending=[False, True]).reset_index(drop=True)


def tabela(linhas: list[dict]) -> pd.DataFrame:
    out = []
    for r in linhas:
        e = r["cenarios"]["esperado"]
        out.append({"codigo": r["codigo"], "processo": r["nome"], "prioridade": r["prioridade"],
                    "nota_composta": r["nota_composta"], **{f"nota_{c}": r["notas"][c] for c in PRIORIZACAO_CRITERIOS},
                    **{f"metrica_{c}": r["metricas"][c] for c in PRIORIZACAO_CRITERIOS},
                    "casos_coorte": r["casos_coorte"], "situacao_procedimento": r["situacao"],
                    "piso_deliberacoes_ano": r["volume"]["piso_deliberacoes"], "revocacao_volume": r["volume"]["revocacao"],
                    "atividades": r["atividades"], "atividades_automatizaveis": r["atividades_automatizaveis"],
                    "capacidades": len(r["capacidades"]), "espera_no_lead": r["espera_no_lead"],
                    "fracao_automatizavel_esperada": e["fracao_automatizavel"],
                    "horas_liberadas_ano": e.get("horas_liberadas_ano"), "retorno_ano_esperado": e.get("retorno_ano"),
                    "custo_construcao_esperado": e["custo_construcao"], "custo_incremental_esperado": e["custo_incremental"],
                    "custo_ano_esperado": e.get("custo_ano"), "liquido_ano_esperado": e.get("liquido_ano"),
                    "liquido_incremental_ano_esperado": e.get("liquido_incremental_ano"),
                    "payback_anos_esperado": e.get("payback_anos"),
                    "payback_incremental_anos_esperado": e.get("payback_incremental_anos"),
                    f"saldo_{HORIZONTE_ANOS}_anos_esperado": e.get("saldo_horizonte")})
    ordem = {"piloto": 0, "candidato a piloto": 1, "próxima onda": 2, "não priorizar agora": 3, "reavaliar com dados": 4}
    return pd.DataFrame(out).sort_values(["prioridade", "nota_composta", "codigo"], key=lambda s: s.map(ordem)
                                         if s.name == "prioridade" else (-s.fillna(-1) if s.name == "nota_composta" else s)
                                         ).reset_index(drop=True)


def grafico(df: pd.DataFrame) -> None:
    """Custo de construção × retorno líquido anual (retorno − manutenção − leitura pelo modelo), cenário esperado.
    Círculo cheio = construção isolada; círculo vazado = só a configuração, com a plataforma já construída."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    d = df.dropna(subset=["retorno_ano_esperado"])
    if d.empty:  # nenhum tipo com volume medido (ex.: estudo de caso de um processo): sem retorno, sem gráfico
        print("aviso: nenhum tipo com retorno medido; gráfico custo × retorno não gerado")
        return
    cores = {"piloto": "#1b6e3a", "candidato a piloto": "#4f9d69", "próxima onda": "#c48a1b",
             "não priorizar agora": "#8a8a8a", "reavaliar com dados": "#b0b0b0"}
    fig, ax = plt.subplots(figsize=(9, 6), dpi=150)
    xmax = d.custo_construcao_esperado.max() / 1e3 * 1.12
    ys = list(d.liquido_ano_esperado / 1e3) + list(d.liquido_incremental_ano_esperado / 1e3)
    ymin, ymax = min(ys + [0]) * 1.15 - 2, max(ys) * 1.2 + 2
    for anos in (2, 5, 10):
        ax.plot([0, xmax], [0, xmax / anos], ":", color="#777", linewidth=0.8)
        x_rot = min(xmax, ymax * anos) * 0.97
        ax.annotate(f"payback de {anos} anos", (x_rot, x_rot / anos), fontsize=7, color="#555", ha="right", va="bottom")
    ax.axhline(0, color="#333", linewidth=0.8)
    rotulos = []  # (x, y) já rotulados: desloca o rótulo de pontos colados
    for _, r in d.sort_values(["liquido_ano_esperado", "codigo"]).iterrows():
        c = cores[r.prioridade]
        x1, y1 = r.custo_construcao_esperado / 1e3, r.liquido_ano_esperado / 1e3
        x0, y0 = r.custo_incremental_esperado / 1e3, r.liquido_incremental_ano_esperado / 1e3
        ax.plot([x0, x1], [y0, y1], color=c, linewidth=0.8, alpha=0.6)
        ax.scatter(x0, y0, s=30, facecolor="white", edgecolor=c, linewidth=1.2, zorder=3)
        ax.scatter(x1, y1, s=40 + 6 * r.nota_composta, color=c, alpha=0.9, edgecolor="white", linewidth=1, zorder=3)
        perto = sum(abs(x1 - x) < xmax * 0.06 and abs(y1 - y) < (ymax - ymin) * 0.05 for x, y in rotulos)
        rotulos.append((x1, y1))
        ax.annotate(f"{r.codigo} · {r.nota_composta:.0f}", (x1, y1), xytext=(8, -3 + 11 * perto), textcoords="offset points",
                    fontsize=8, zorder=5, bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.8))
    ax.set_xlim(0, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_xlabel("Custo de construção, cenário esperado (R$ mil, hipótese)")
    ax.set_ylabel("Retorno líquido anual, cenário esperado (R$ mil/ano)")
    ax.set_title("Custo × retorno da automação por tipo de processo\n(cheio: construção isolada · vazado: sobre a "
                 "plataforma já construída · rótulo: nota composta)", fontsize=9)
    for k, c in cores.items():
        if k in set(d.prioridade):
            ax.scatter([], [], color=c, label=k)
    ax.legend(fontsize=8, loc="upper left", frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "matriz_automacao.png")
    plt.close(fig)


def planilha(df: pd.DataFrame, cap: pd.DataFrame, param: dict) -> None:
    from openpyxl.styles import Alignment, Font, PatternFill
    with pd.ExcelWriter(OUT / "Priorizacao_Automacao.xlsx", engine="openpyxl") as xw:
        df.to_excel(xw, sheet_name="Matriz", index=False)
        cap.to_excel(xw, sheet_name="Capacidades transversais", index=False)
        pd.DataFrame([dict(criterio=NOMES_CRITERIO[c], chave=c, peso_pct=p, cortes_notas_2_a_5=", ".join(map(str, cortes)))
                      for c, (p, cortes) in PRIORIZACAO_CRITERIOS.items()]).to_excel(xw, sheet_name="Critérios", index=False)
        pd.DataFrame([dict(parametro=k, valor=json.dumps(v, ensure_ascii=False)) for k, v in param.items()]).to_excel(
            xw, sheet_name="Premissas (hipótese)", index=False)
        for ws in xw.book.worksheets:
            for c in ws[1]:
                c.font = Font(bold=True, color="FFFFFF")
                c.fill = PatternFill("solid", fgColor="404040")
                c.alignment = Alignment(wrap_text=True, vertical="top")
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = min(45, max(10, max(len(str(x.value or "")) for x in col) + 2))
            ws.freeze_panes = "B2"


def br(x, casas=0) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "—"
    s = f"{x:,.{casas}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def documento(linhas: list[dict], df: pd.DataFrame, cap: pd.DataFrame) -> str:
    por = {r["codigo"]: r for r in linhas}
    pil = [r for r in linhas if r["prioridade"] == "piloto"]
    cand = [r for r in linhas if r["prioridade"] in ("piloto", "candidato a piloto")]
    sem_vol = [r["codigo"] for r in linhas if not r["portoes"]["volume_medido"]]
    corte_alto = PRIORIZACAO_CRITERIOS["volume"][1][2]
    altos = sorted((r for r in linhas if (r["volume"]["estimado"] or 0) >= corte_alto), key=lambda r: -r["volume"]["estimado"])
    medidos = [r for r in linhas if r["volume"]["estimado"]]
    esperas = [r["espera_no_lead"] for r in linhas if r["espera_no_lead"] is not None]
    freq = [r["caminho_mais_frequente"] for r in linhas if r["caminho_mais_frequente"] is not None]
    an = [r for r in linhas if r["sinais"]["frac_estruturado"] is not None]
    L = ["# Priorização da automação: matriz de critérios e custo × retorno", "",
         "Gerado por `scripts/priorizacao_automacao.py`. Os números vêm das saídas verificadas do mapeamento; as premissas "
         "de custo e de fração automatizável são **hipótese até a medição no piloto** e estão na aba “Premissas” da planilha "
         "`saida/fase4/Priorizacao_Automacao.xlsx`. Horas de trabalho são hipótese até a calibração com os servidores.", "",
         "## 1. O que o mapeamento ensinou para a automação", ""]
    L += [f"- **O volume por tipo de processo é baixo.** Estimado a partir das deliberações de toda a agência, "
          f"{len(altos)} de {len(medidos)} tipos com volume medido chegam a {corte_alto} processos por ano "
          f"({', '.join(f'{r['codigo']}: {br(r['volume']['estimado'], 1)}' for r in altos) or 'nenhum'}); "
          f"{', '.join(sem_vol) or 'nenhum'} ficam sem volume medido. Automação do processo inteiro só se paga onde há "
          "repetição; nos demais tipos, o retorno vem de capacidades compartilhadas (seção 4).",
          f"- **A espera pesa tanto quanto o trabalho.** A soma das esperas entre atividades vai de "
          f"{br(min(esperas) * 100)}% a {br(max(esperas) * 100)}% do lead time mediano dos casos nativos, conforme o tipo. "
          "Automatizar a redação e a análise reduz horas; o prazo só cai se o sistema também vigiar posse, prazos e "
          "pendências.",
          f"- **Nenhum fluxo é padronizado.** O caminho mais frequente cobre de {br(min(freq) * 100)}% a "
          f"{br(max(freq) * 100)}% dos casos da coorte. O sistema deve automatizar por atividade, disparado pelo gatilho "
          "de cada tarefa do modelo, e não impor uma sequência fixa.",
          "- **A IA julga melhor quando a regra está escrita.** As etapas que passaram nos portões tinham especificação "
          "prévia, saída em formato fixo e conferência automática ou às cegas; o mesmo vale para o sistema: cada atividade "
          "automatizada precisa de uma regra computável e de um conjunto de casos de referência.",
          "- **Tempo de terceiros e prazo legal não são ganho.** A espera pela regulada e o prazo mínimo da norma ficam "
          "fora do retorno; o sistema pode cobrar prazos vencidos, não encurtar o que a lei concede.",
          f"- **A análise mistura texto e dado.** Nas peças de análise, a fração com dado não estruturado vai de "
          f"{br(min(r['sinais']['frac_nao_estruturado'] for r in an) * 100)}% a "
          f"{br(max(r['sinais']['frac_nao_estruturado'] for r in an) * 100)}% e a com dado estruturado, de "
          f"{br(min(r['sinais']['frac_estruturado'] for r in an) * 100)}% a "
          f"{br(max(r['sinais']['frac_estruturado'] for r in an) * 100)}%, conforme o tipo. O sistema precisa extrair "
          "do texto e conferir contra a regra e o cálculo.", ""]
    L += ["## 2. Critérios e régua", "",
          "| Critério | Peso | O que mede | Cortes para as notas 2, 3, 4 e 5 |", "|---|---|---|---|"]
    desc = {"volume": "Processos por ano na agência: piso de deliberações ÷ (fração com deliberação × revocação da regra)",
            "analise": "Fração das horas do tipo em peças de análise (jurídica, técnica, econômica, conferência, relatoria)",
            "dados": "Peças de análise com dado estruturado (cálculo, base, sistema) e com não estruturado (documento da "
                     "regulada, precedente, documentos examinados): média das duas frações",
            "regras": "Peças de análise ancoradas em norma ou contrato e com teste contra um padrão: média das duas frações",
            "padrao": "Texto padronizado ou transcrito (ponderado por horas) e fração dos casos no caminho mais frequente",
            "completude": "Fração das horas dos casos em atividades com potencial de IA alto na avaliação AS-IS"}
    for c, (p, cortes) in PRIORIZACAO_CRITERIOS.items():
        L.append(f"| {NOMES_CRITERIO[c]} | {p}% | {desc[c]} | {' · '.join(br(x, 2) if x < 1 else br(x) for x in cortes)} |")
    L += ["", f"Nota composta = Σ peso × nota ÷ 5 (0 a 100). Portões do piloto de automação completa: volume medido com "
          f"revocação ≥ {br(PORTOES_PILOTO['revocacao_volume'] * 100)}%, nota de volume ≥ {PORTOES_PILOTO['nota_volume']}, "
          f"nota de regras ≥ {PORTOES_PILOTO['nota_regras']} e ao menos {PORTOES_PILOTO['casos_coorte']} casos na coorte.", "",
          "## 3. Matriz", "", "![Matriz custo × retorno](../saida/fase4/matriz_automacao.png)", "",
          "| Código | Processo | Prioridade | Nota | V | A | D | R | P | C | Volume/ano | Retorno/ano (R$) | "
          "Construção (R$) | Payback isolado (anos) | Payback com plataforma (anos) |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for _, r in df.iterrows():
        n = [r[f"nota_{c}"] for c in PRIORIZACAO_CRITERIOS]
        L.append(f"| {r.codigo} | {r.processo} | {r.prioridade} | {br(r.nota_composta, 1)} | "
                 + " | ".join("—" if pd.isna(x) else str(int(x)) for x in n)
                 + f" | {br(r.metrica_volume, 1)} | {br(r.retorno_ano_esperado)} | {br(r.custo_construcao_esperado)} | "
                   f"{br(r.payback_anos_esperado, 1)} | {br(r.payback_incremental_anos_esperado, 1)} |")
    L += ["", "V volume · A foco em análise · D dados estruturados e não estruturados · R regras claras · P padronização · "
          "C completude da automação. Valores monetários no cenário esperado; os três cenários estão em "
          "`saida/fase4/matriz_automacao.json`. Payback com plataforma = só a configuração das atividades, com a "
          "plataforma e as capacidades de IA já construídas para outro tipo. Payback vazio = o retorno anual não cobre "
          "o custo anual.", ""]
    L += ["## 4. Capacidades transversais", "",
          "Uma capacidade de IA construída uma vez serve a vários tipos de processo. A tabela soma, por capacidade, as "
          "atividades de potencial alto ou médio que a usam e as horas por ano que elas alcançam (só tipos com volume "
          "medido).", "", "| Capacidade | Tipos | Atividades | Horas/ano alcançadas | Horas de construção |",
          "|---|---|---|---|---|"]
    for _, c in cap.iterrows():
        L.append(f"| {c.capacidade} | {c.tipos_de_processo} | {c.atividades} | {br(c.horas_ano_alcancadas, 1)} | "
                 f"{c.horas_construcao} |")
    L += ["", "## 5. Recomendação", ""]
    if pil:
        p = pil[0]
        e = p["cenarios"]["esperado"]
        L += [f"**Piloto: {p['codigo']} — {p['nome']}.** É o tipo com maior nota composta ({br(p['nota_composta'], 1)}) "
              f"entre os que passam em todos os portões: volume estimado de {br(p['volume']['estimado'], 1)} processos por "
              f"ano, {p['atividades_automatizaveis']} de {p['atividades']} atividades com potencial de IA alto ou médio e "
              f"{len(p['capacidades'])} capacidades de IA. No cenário esperado, libera {br(e.get('horas_liberadas_ano'), 1)} "
              f"horas por ano ({br(e.get('retorno_ano'))} reais) para uma construção de {br(e['custo_construcao'])} reais, "
              f"payback de {br(e.get('payback_anos'), 1)} anos isolado e {br(e.get('payback_incremental_anos'), 1)} anos "
              "se a plataforma e as capacidades já existirem."]
        c, o = p["cenarios"]["conservador"], p["cenarios"]["otimista"]
        L += [f"Nos extremos, o payback isolado vai de {br(o.get('payback_anos'), 1)} anos (otimista) a "
              + (f"{br(c.get('payback_anos'), 1)} anos" if c.get("payback_anos") else "nunca")
              + " (conservador): o conservador soma horas no piso, fração automatizável baixa e desenvolvimento caro. "
              "A medição no piloto decide entre eles.", ""]
    outros = [r for r in cand if r not in pil]
    if outros:
        L += ["Também passam nos portões: " + "; ".join(
            f"{r['codigo']} ({r['nome']}, nota {br(r['nota_composta'], 1)}; payback esperado de "
            f"{br(r['cenarios']['esperado'].get('payback_anos'), 1)} anos isolado e "
            f"{br(r['cenarios']['esperado'].get('payback_incremental_anos'), 1)} anos sobre a plataforma do piloto)"
            for r in outros) + ". É a segunda onda natural: reaproveita a plataforma e as capacidades.", ""]
    onda = [r for r in linhas if r["prioridade"] == "próxima onda"]
    if onda:
        L += ["Próxima onda (nota ≥ 60, falha num portão): " + "; ".join(
            f"{r['codigo']} ({', '.join(PORTAO_TEXTO[k] for k, ok in r['portoes'].items() if not ok)})"
            for r in onda) + ".", ""]
    if pil:
        p = pil[0]
        e = p["especificacao"]
        L += ["## 6. O que o método já entrega para especificar o sistema do piloto", "",
              "| Insumo | Quantidade | Onde está |", "|---|---|---|",
              f"| Tarefas do modelo, com gatilho e saída | {e['tarefas_com_gatilho_e_saida']} de {e['tarefas']} | "
              f"`saida/bpmn/modelo_{p['codigo']}.json` |",
              f"| Pontos de decisão | {e['decisoes']} | idem |",
              f"| Atividades com potencial de IA alto ou médio, com tipos de IA | {p['atividades_automatizaveis']} de "
              f"{p['atividades']} | `saida/bpmn/avaliacao_{p['codigo']}.json` |",
              f"| Casos nativos para o conjunto de referência | {p['casos_nativos']} | `saida/fase2/casos_{p['codigo']}.json` |",
              f"| Peças com ficha de trabalho (insumos, testes, cálculos) | {p['sinais']['pecas']} | "
              "`saida/fichas_trabalho.jsonl` |"]
        if "requisitos" in e:
            L += [f"| Requisitos normativos com teste computável | {e['requisitos_com_teste']} de {e['requisitos']} | "
                  f"`saida/fase3/normas_{p['codigo']}.json` |",
                  f"| Requisitos medidos na coorte (conformidade mediana de {br(e['conformidade_mediana'], 1)}%) | "
                  f"{e['requisitos_medidos']} | `saida/fase3/conformidade_{p['codigo']}.json` |"]
        if "indicadores" in e:
            L += [f"| Melhorias do TO-BE simuladas | {e.get('melhorias', '—')} | `saida/fase3/melhorias_{p['codigo']}.json` |",
                  f"| Indicadores, controles de qualidade da IA e testes de auditoria contínua | {e['indicadores']}, "
                  f"{e['controles_qualidade_ia']} e {e['auditoria_continua']} | `saida/fase3/controles_{p['codigo']}.json` |"]
        L += ["", "Cada tarefa vira um caso de uso (gatilho → entrada → regra → saída); cada requisito com teste vira uma "
              "verificação automática; os casos nativos, rotulados por servidor, formam o conjunto de aceite; os "
              "indicadores e controles medem o sistema em produção.", ""]
    L += ["O retorno em horas é só parte do valor: prazo, conformidade e rastreabilidade não estão monetizados. O "
          "piloto deve medir, antes e depois, a fração automatizável real por atividade e o custo efetivo de construção, "
          "e com isso substituir as premissas desta matriz.", "",
          "## 7. Limites", "",
          "- O volume é estimado a partir de deliberações; tipos que raramente chegam à deliberação ficam sem medida.",
          "- A fração automatizável por potencial de IA, as horas de construção e o custo-hora de desenvolvimento são "
          "hipóteses; o retorno escala linearmente com elas.",
          "- As horas por caso vêm das fichas por peça (estimativa, piso e teto) e são hipótese até a calibração.",
          "- Coortes pequenas dão medianas instáveis: a coluna de casos na coorte diz quanto confiar."]
    fora = sorted(set(pd.read_csv(SAIDA / "coorte_fase2.csv").processo_principal) - set(por))
    if fora:
        L.append(f"- Ficam fora da matriz, por não terem avaliação AS-IS: {', '.join(fora)}. Tipos que quase não chegam "
                 "ao Conselho, como o atendimento de manifestações, podem ter volume real bem maior do que a base do "
                 "gabinete mostra; medir com outra fonte (sistema da Ouvidoria) antes de descartá-los.")
    return "\n".join(L) + "\n"


def main() -> None:
    OUT.mkdir(exist_ok=True)
    if (F3 / "volume_anual.json").exists():
        vol = json.loads((F3 / "volume_anual.json").read_text(encoding="utf-8"))
    else:  # órgão novo sem base de deliberações: todos os tipos saem "reavaliar com dados"
        print("aviso: sem saida/fase3/volume_anual.json — volume não medido em nenhum tipo")
        vol = dict(codigos={})
    codigos = sorted(p.stem.split("_")[1] for p in F2.glob("procedimento_*.json")
                     if (BPMN / f"avaliacao_{p.stem.split('_')[1]}.json").exists())
    fichas = fichas_por_codigo()
    linhas = [avaliar_codigo(c, fichas.get(c, []), vol) for c in codigos]
    classificar(linhas)
    df, cap = tabela(linhas), capacidades_transversais(linhas)
    param = dict(criterios=PRIORIZACAO_CRITERIOS, naturezas_analise=sorted(NATUREZAS_ANALISE), portoes=PORTOES_PILOTO,
                 fracao_automatizavel=FRACAO_AUTOMATIZAVEL, horas_capacidade=HORAS_CAPACIDADE,
                 horas_plataforma=HORAS_PLATAFORMA, horas_config_atividade=HORAS_CONFIG_ATIVIDADE,
                 variabilidade_fator=VARIABILIDADE_FATOR, casos_validacao=CASOS_VALIDACAO,
                 horas_validacao_caso=HORAS_VALIDACAO_CASO, custo_hora_dev=CUSTO_HORA_DEV, preco_llm_mchar=PRECO_LLM_MCHAR,
                 manutencao_anual=MANUTENCAO_ANUAL, horizonte_anos=HORIZONTE_ANOS, cenarios=CENARIOS_AUTOMACAO,
                 custo_hora_servidor=CUSTO_HORA_BASE[CARGO_PADRAO], fator_custo_total=FATOR_CUSTO_TOTAL)
    corpo = dict(nota="Priorização da automação por tipo de processo. Premissas de custo e de fração automatizável "
                      "são hipótese até a medição no piloto.", parametros=param, codigos=linhas)
    corpo["carimbo"] = hashlib.sha256(json.dumps(corpo, sort_keys=True, ensure_ascii=False, default=list).encode()).hexdigest()
    (OUT / "matriz_automacao.json").write_text(json.dumps(corpo, ensure_ascii=False, indent=1, default=list),
                                               encoding="utf-8")
    df.to_csv(OUT / "matriz_automacao.csv", index=False)
    cap.to_csv(OUT / "capacidades_transversais.csv", index=False)
    planilha(df, cap, param)
    grafico(df)
    DOC.write_text(documento(linhas, df, cap), encoding="utf-8")
    for _, r in df.iterrows():
        print(f"{r.codigo:4} {r.prioridade:22} nota={r.nota_composta} vol={r.metrica_volume} "
              f"retorno={r.retorno_ano_esperado} custo={r.custo_construcao_esperado} payback={r.payback_anos_esperado}")


if __name__ == "__main__":
    main()
