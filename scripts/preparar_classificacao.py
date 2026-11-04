"""Etapa 2a — monta o insumo de classificação: um registro por processo com metadados, trilha e
títulos das peças substantivas, mais uma sugestão por regras (palavras-chave) do processo
organizacional do catálogo do perfil (catalogo/dados_processos.py; na AGENERSA, P01–P36).

Saídas: saida/insumo_classificacao.jsonl e saida/catalogo_processos.json"""
from __future__ import annotations

import json
import re

import pandas as pd

from comum import DUMP, REGRAS_SUGESTAO, SAIDA, carregar
from dados_processos import MACROS, P  # catálogo do perfil (comum põe CATALOGO no sys.path)

# sugestão por palavras-chave (regex sobre tipo + natureza + assunto, código do processo), do perfil:
# primeira que casar vence
_REGRAS = [(re.compile(rx, re.I), c) for rx, c in REGRAS_SUGESTAO]

SUBSTANTIVAS = {"parecer", "relatorio", "relatorio_fiscalizacao", "nota_tecnica", "voto", "deliberacao",
                "decisao", "despacho_decisorio", "notificacao_autuacao", "ato_normativo", "informacao",
                "manifestacao_pge", "ata"}


def sugerir(texto: str) -> str | None:
    for rx, c in _REGRAS:
        if rx.search(texto):
            return c
    return None


def main():
    p, _, _ = carregar()
    ind = pd.read_csv(SAIDA / "processos_indicadores.csv")
    docs = pd.read_csv(SAIDA / "documentos.csv", low_memory=False)
    obs = pd.read_csv(DUMP / "observacoes.tsv",
                      sep="\t", quoting=3, na_values="NULL")
    obs = obs.merge(p[["id", "numero"]], left_on="processo_id", right_on="id")

    catalogo = [dict(id=x["id"], macro=x["macro"], macroprocesso=MACROS[x["macro"]][1], nome=x["nome"],
                     escopo=x["escopo"], unidades=x["unidades"]) for x in P]
    (SAIDA / "catalogo_processos.json").write_text(json.dumps(catalogo, ensure_ascii=False, indent=1),
                                                    encoding="utf-8")

    with open(SAIDA / "insumo_classificacao.jsonl", "w", encoding="utf-8") as f:
        for r in ind.itertuples():
            d = docs[docs.numero_processo == r.numero]
            subst = d[d.categoria.isin(SUBSTANTIVAS)]
            titulos = [f"{t} [{u.split('/')[-1] if isinstance(u, str) else '?'}]"
                       for t, u in zip(subst["tipo"], subst["unidade"])]
            relacionados = d.loc[d.categoria == "processo_relacionado", "tipo"].dropna().unique().tolist()
            notas = obs.loc[obs.numero == r.numero, "texto"].dropna().str.slice(0, 200).tolist()
            texto = " ".join(str(x) for x in [r.tipo, r.natureza, r.assunto] if pd.notna(x))
            f.write(json.dumps(dict(
                numero=r.numero, tipo=r.tipo, natureza=None if pd.isna(r.natureza) else r.natureza,
                assunto=None if pd.isna(r.assunto) else r.assunto,
                interessado=None if pd.isna(r.interessado) else r.interessado,
                data_geracao=str(r.data_geracao)[:10], sequencia_ativa=r.sequencia_ativa,
                tem_voto=bool(r.tem_voto), tem_deliberacao=bool(r.tem_deliberacao),
                pecas_substantivas=titulos[:40], processos_relacionados=relacionados[:15],
                observacoes_gabinete=notas[:5], sugestao_regra=sugerir(texto),
            ), ensure_ascii=False) + "\n")
    print("insumo gerado:", len(ind), "processos;", "com sugestão por regra:",
          sum(1 for x in ind.itertuples()
              if sugerir(" ".join(str(v) for v in [x.tipo, x.natureza, x.assunto] if pd.notna(v)))))


if __name__ == "__main__":
    main()
