"""Fase 2 — relatório do caso ao procedimento, montado só a partir das saídas (nenhum número digitado).

Entradas: saida/coorte_fase2.csv, saida/fase2/{procedimento_<Pxx>.json, auditoria_classificador.json,
avaliacao_classificador.json, comparacao_modelos_fichas.json, duplicados.csv, verificacao_classificacao.csv},
saida/fichas_trabalho.csv. Saída: docs/RESULTADOS_FASE2.md"""
from __future__ import annotations

import json

import pandas as pd

from comum import RAIZ, SAIDA

F2 = SAIDA / "fase2"
SIT = {"procedimento": "procedimento", "indicativo": "indicativo (com ressalva)", "estudo_de_caso": "estudo de caso"}


def _j(nome):
    arq = F2 / nome
    return json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else None


def _n(v) -> str:
    return f"{v:g}".replace(".", ",")


def _d(x, un="du"):
    return "—" if not x else f"{_n(x['mediana'])} {un} (q1 {_n(x['q1'])}–q3 {_n(x['q3'])}; n {x['n']})"


def _pct(x):
    return "—" if x is None else f"{100 * x:.0f}%"


def main():
    co = pd.read_csv(SAIDA / "coorte_fase2.csv")
    procs = {p.stem.split("_")[1]: json.loads(p.read_text(encoding="utf-8")) for p in sorted(F2.glob("procedimento_*.json"))}
    aud, aval, cmp_ = _j("auditoria_classificador.json"), _j("avaliacao_classificador.json"), _j("comparacao_modelos_fichas.json")
    fich = pd.read_csv(SAIDA / "fichas_trabalho.csv", usecols=["processo", "modelo"])
    dup = pd.read_csv(F2 / "duplicados.csv") if (F2 / "duplicados.csv").exists() else pd.DataFrame(columns=["numero"])
    md = ["# Resultados da Fase 2 — do caso ao procedimento", "",
          "Gerado por `scripts/resumo_fase2.py` a partir das saídas do pipeline. Tempos em dias úteis (du); horas são "
          "hipótese até a calibração com servidores.", "",
          "## Coorte", "",
          f"{len(co)} processos em {co.processo_principal.nunique()} códigos "
          f"({(co.trilha == 'nativa').sum()} com trilha nativa do SEI, {(co.trilha == 'migrada').sum()} migrados com "
          f"trilha parcial, {(co.trilha == 'sem').sum()} só com as peças, sem trâmite). {len(dup)} processos repetidos "
          "(cópia de processo físico migrado com número novo) foram retirados.", "",
          "| Código | Processo | Situação | Casos (nativa/migrada/sem) | Lead time dos nativos encerrados | "
          "Concordância na auditoria (peças substantivas) |", "|---|---|---|---|---|---|"]
    for cod, p in procs.items():
        t = p["trilha"]
        a = p.get("auditoria_classificador") or {}
        md.append(f"| {cod} | {p['nome']} | {SIT[p['situacao']]} | {p['casos']} ({t.get('nativa', 0)}/"
                  f"{t.get('migrada', 0)}/{t.get('sem', 0)}) | {_d(p['lead_nativos_encerrados'])} | "
                  f"{_pct(a.get('concordancia_substantivas'))} ({a.get('substantivas', 0)} peças) |")
    md += ["", "Situação: *procedimento* = 5 casos ou mais e concordância ≥ 85% na auditoria às cegas; *indicativo* = "
           "abaixo do critério, números com ressalva; *estudo de caso* = menos de 5 casos.", "",
           "## Controles de qualidade", ""]
    if aval and "_total" in aval:
        md.append(f"- Classificador de atividade contra os vínculos auditados do piloto: {_pct(aval['_total']['concordancia'])} "
                  f"em {aval['_total']['pecas_no_gabarito']} peças (otimista: as atividades foram descritas a partir "
                  "desses mesmos casos).")
    if aud:
        t = aud["resumo"]["_total"]
        md.append(f"- Auditoria às cegas fora do piloto: {t['pecas']} peças de {len(aud['resumo']) - 1} códigos; "
                  f"concordância {_pct(t['concordancia'])} no total e {_pct(t['concordancia_substantivas'])} nas "
                  f"{t['substantivas']} peças substantivas (critério {_pct(t['criterio'])}). Amostra de 14 substantivas "
                  "por código: o percentual por código tem margem larga.")
    md.append(f"- Fichas de trabalho: {len(fich)} peças; " + "; ".join(f"{m} {n}" for m, n in fich.modelo.value_counts().items())
              + ". As que faltavam quando o crédito do primeiro modelo acabou foram feitas com o segundo.")
    if cmp_:
        md.append(f"- Comparação dos dois modelos de ficha no mesmo documento ({cmp_['n']} peças): natureza igual em "
                  f"{_pct(cmp_['natureza_igual'])}, complexidade igual em {_pct(cmp_['complexidade_igual'])} "
                  f"(diferença de até 1 ponto em {_pct(cmp_['complexidade_dif_ate_1'])}); horas do segundo modelo = "
                  f"{_n(cmp_['razao_horas_b_sobre_a']['mediana'])}× as do primeiro (mediana). As horas-piso das peças "
                  "do segundo modelo tendem, portanto, a ser maiores.")
    md += ["", "## Procedimento por código", ""]
    for cod, p in procs.items():
        md += [f"### {cod} — {p['nome']} ({SIT[p['situacao']]})", "",
               f"{p['casos']} casos; {p['n_caminhos']} caminhos distintos (ordem da 1ª ocorrência de cada atividade). "
               f"Peças substantivas fora do modelo por caso: mediana {_n((p['fora_do_modelo_pct_substantivas'] or {}).get('mediana', 0))}%.", ""]
        if p["caminhos"] and p["caminhos"][0]["casos"] > 1:
            c = p["caminhos"][0]
            md += [f"Caminho mais frequente ({c['casos']} casos): {c['sequencia']}", ""]
        else:
            nucleo = [t for t, a in p["atividades"].items() if a["pct_casos"] >= 50]
            md += ["Nenhum caminho se repete entre os casos. Núcleo comum (atividades em metade dos casos ou mais, na "
                   "ordem do modelo): " + (" → ".join(nucleo) or "nenhuma"), ""]
        md += ["| Atividade | Casos | Com laço | Execução | Espera antes | Horas (piso) |", "|---|---|---|---|---|---|"]
        for t, a in p["atividades"].items():
            md.append(f"| {t} {a['nome']} | {a['pct_casos']}% | {a['casos_com_laco']} | {_d(a['execucao_du'])} | "
                      f"{_d(a['espera_antes_du'])} | {_d(a['horas_piso'], 'h')} |")
        md.append("")
    (RAIZ / "docs" / "RESULTADOS_FASE2.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("docs/RESULTADOS_FASE2.md:", len(md), "linhas")


if __name__ == "__main__":
    main()
