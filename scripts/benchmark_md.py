"""Relatório do benchmarking (fase 3) a partir de saida/fase3/benchmark/*.json, já com a verificação independente
das citações aplicada. Saída: docs/BENCHMARKING.md"""
from __future__ import annotations

import json
from collections import Counter

from comum import FAMILIAS_BENCHMARK, ORGAO, RAIZ, SAIDA

DIR = SAIDA / "fase3" / "benchmark"
FAMILIAS = FAMILIAS_BENCHMARK  # família → título (perfil)
FASES = {1: "Ajuste do fluxo", 2: "Automação de regras e dados", 3: "Automação com IA", 4: "Controles, indicadores e metas"}
CAMADA = {"cientifica": "científica", "oficial": "oficial"}
NIVEL = {"avaliacao_quantitativa": "avaliação quantitativa", "quase_experimental": "quase-experimental",
         "estudo_de_caso": "estudo de caso", "revisao_sistematica": "revisão sistemática", "relato_oficial": "relato oficial"}


def ref(f: dict) -> str:
    doi = f" https://doi.org/{f['doi']}" if f.get("doi") else (f" {f['url']}" if f.get("url") else "")
    return f"{f.get('autores', '')} ({f.get('ano', '')}). {f.get('titulo', '')}. *{f.get('veiculo', '')}*.{doi}"


def main() -> None:
    if not (DIR / "verificacao.json").exists():
        print(f"aviso: sem {DIR / 'verificacao.json'} (benchmarking verificado); relatório não gerado")
        return
    ver = json.loads((DIR / "verificacao.json").read_text(encoding="utf-8"))
    md = ["# Benchmarking dos processos-piloto da fase 3", "",
          "Casos de estado da arte, no Brasil e no exterior, que orientam a melhoria de P01 (reajuste tarifário), "
          "P06 (fiscalização técnica de campo) e P21 (apuração de ocorrência de usuário). Inclusão: prática aplicada por "
          "órgão identificado, com resultado medido ou avaliado. Duas camadas, nunca misturadas: **científica** (revisada "
          "por pares, tese ou dissertação, com DOI ou handle conferido) e **oficial** (documento de regulador ou organismo). "
          "Cada caso traz um trecho literal da fonte, conferido de forma independente; o resultado e o parâmetro de ganho "
          "foram revistos para não dizer mais do que a fonte sustenta.", "",
          f"Conferência independente de {sum(ver['resumo'].values())} casos: {ver['resumo'].get('ok', 0)} sem ressalva, "
          f"{ver['resumo'].get('corrigir', 0)} corrigidos, {ver['resumo'].get('excluir', 0)} excluídos.", ""]
    tot = Counter()
    blocos = []
    for fam, nome in FAMILIAS.items():
        if not (DIR / f"{fam}.json").exists():
            print(f"aviso: família {fam} sem {fam}.json; fora do relatório")
            continue
        d = json.loads((DIR / f"{fam}.json").read_text(encoding="utf-8"))
        cs = d["casos"]
        cam = Counter(c["fonte"]["camada"] for c in cs)
        fases = Counter(f for c in cs for f in c.get("fase_melhoria") or [])
        tot.update(cam)
        md.append(f"- **{nome}** ({', '.join(d['processos'])}): {len(cs)} casos, {cam['cientifica']} científicos e "
                  f"{cam['oficial']} oficiais; por fase: " + "; ".join(f"{FASES[k]} {fases[k]}" for k in sorted(fases)))
        b = [f"## {nome}", "", d.get("pergunta", ""), "",
             "| Caso | Prática | Contexto | Resultado | Evidência | Fases |", "|---|---|---|---|---|---|"]
        for c in cs:
            ctx = c.get("contexto") or {}
            b.append(f"| {c['id']} | {c['pratica']} | {ctx.get('orgao', '')} ({ctx.get('pais', '')}, {ctx.get('periodo', '')}) | "
                     f"{c['resultado_reportado']} | {NIVEL.get(c.get('nivel_evidencia'), c.get('nivel_evidencia'))}, "
                     f"{CAMADA.get(c['fonte']['camada'], c['fonte']['camada'])} | {', '.join(map(str, c.get('fase_melhoria') or []))} |")
        b += ["", f"### Aplicação à {ORGAO}", ""]
        b += [f"- **{c['id']}** — {c['aplicabilidade']}" + (f" Parâmetro: {c['parametro_ganho']}" if c.get("parametro_ganho") else "")
              for c in cs]
        b += ["", "### Lacunas", ""] + [f"- {x}" for x in d.get("lacunas") or []]
        b += ["", "### Fontes", ""] + [f"- {c['id']}: {ref(c['fonte'])} Trecho: “{c['fonte']['trecho']}”" for c in cs] + [""]
        blocos += b
    md.insert(len(md), "")
    md.append(f"Total: {tot['cientifica'] + tot['oficial']} casos ({tot['cientifica']} científicos, {tot['oficial']} oficiais). "
              "Algumas fontes aparecem em mais de uma família; a contagem não é de estudos independentes.")
    md.append("")
    (RAIZ / "docs" / "BENCHMARKING.md").write_text("\n".join(md + blocos), encoding="utf-8")
    print("docs/BENCHMARKING.md:", len(md + blocos), "linhas")


if __name__ == "__main__":
    main()
