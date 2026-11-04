"""Etapa 3a — exporta do Postgres do relator (Railway) o que o mapeamento precisa por documento:
metadados (tipo, unidade, MIME, nº de caracteres, restrição), a análise map-v3 já feita por IA e,
para os processos-piloto, o texto integral.

ESPECÍFICO DA AGENERSA: lê o banco de um sistema da própria agência (relator de voto), que já baixou do SEI-RJ as
peças dos processos do gabinete e as analisou. Outros Estados não têm esse banco: usam o coletor em coleta/, que
produz os mesmos arquivos em dados/ a partir do SEI do órgão.

A conexão vem da variável DATABASE_URL (URL pública do Postgres do relator) ou de um arquivo .env indicado em
--env-file (que define DATABASE_URL). A URL nunca é impressa.

Uso:
  python exportar_relator.py                      # metadados + análises de todos os processos
  python exportar_relator.py --texto-piloto       # idem + texto integral dos processos de saida/piloto.csv
  python exportar_relator.py --texto-piloto --processos saida/coorte_fase2.csv
                                                  # idem + texto da coorte (CSV com coluna "numero")
Saídas: dados/relator/documentos.parquet, extractions.parquet, [doc_text_piloto.parquet — texto do piloto e da
coorte —, cobertura_texto.csv — por processo, fração das peças substantivas com texto não vazio]"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd

from comum import DADOS, SAIDA
from selecionar_piloto import COBERTURA_MIN, SUBSTANTIVAS

DESTINO = DADOS / "relator"


def conectar(env_file: Path | None):
    import psycopg
    if not os.environ.get("DATABASE_URL") and env_file and env_file.exists():
        from dotenv import load_dotenv
        load_dotenv(env_file)
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise SystemExit("DATABASE_URL não definida (nem no ambiente, nem em --env-file).")
    if ".railway.internal" in dsn:
        raise SystemExit("DATABASE_URL aponta para a rede interna do Railway; use a URL pública (proxy).")
    return psycopg.connect(dsn, connect_timeout=20)


def cobertura(docs: pd.DataFrame, txt: pd.DataFrame, alvo: list) -> pd.DataFrame:
    """Por processo: peças, peças substantivas e fração delas com texto não vazio (restritas não têm texto:
    afirmação sobre elas se apoia no tipo e em peças posteriores que as relatam)."""
    from comum import categoria_documento
    d = docs[docs.processo.isin(alvo)].copy()
    d["categoria"] = [categoria_documento(t, str(n))[0] for t, n in zip(d.tipo.fillna(""), d.sei_doc_id)]
    com = set(zip(txt.processo, txt.sei_doc_id.astype(str))) - {
        (p, str(s)) for p, s, t in zip(txt.processo, txt.sei_doc_id, txt.texto) if not str(t or "").strip()}
    d["tem_texto"] = [(p, str(s)) in com for p, s in zip(d.processo, d.sei_doc_id)]
    d["subst"] = d.categoria.isin(SUBSTANTIVAS)
    g = d.groupby("processo").apply(lambda x: pd.Series(dict(
        pecas=len(x), com_texto=int(x.tem_texto.sum()), restritas=int(x.restrito.fillna(False).astype(bool).sum()),
        substantivas=int(x.subst.sum()),
        cobertura_substantivas=round(x[x.subst].tem_texto.mean(), 3) if x.subst.any() else 0.0)),
        include_groups=False).reset_index()
    faltam = sorted(set(alvo) - set(g.processo))
    return pd.concat([g, pd.DataFrame({"processo": faltam, "pecas": 0, "cobertura_substantivas": 0.0})],
                     ignore_index=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env-file", type=Path, help=".env que define DATABASE_URL (se a variável não estiver no ambiente)")
    ap.add_argument("--texto-piloto", action="store_true")
    ap.add_argument("--processos", type=Path, help="CSV com coluna 'numero': processos além do piloto")
    args = ap.parse_args()
    DESTINO.mkdir(parents=True, exist_ok=True)
    with conectar(args.env_file) as con:
        docs = pd.read_sql("""SELECT processo, sei_doc_id, tipo, data, data_inclusao, unidade, download_status,
                                     mime, n_chars, restrito, motivo_restricao, origem_apenso
                              FROM documentos""", con)
        ext = pd.read_sql("""SELECT processo, sei_doc_id, model_id, prompt_version, extraction_json::text AS extraction_json
                             FROM extractions""", con)
        docs.to_parquet(DESTINO / "documentos.parquet", index=False)
        ext.to_parquet(DESTINO / "extractions.parquet", index=False)
        print(f"documentos={len(docs)} ({docs.processo.nunique()} processos)  extractions={len(ext)}")
        if args.texto_piloto:
            alvo = pd.read_csv(SAIDA / "piloto.csv")["numero"].tolist()
            if args.processos:
                alvo = sorted(set(alvo) | set(pd.read_csv(args.processos)["numero"]))
            txt = pd.read_sql("SELECT processo, sei_doc_id, texto FROM doc_text WHERE processo = ANY(%(p)s)",
                              con, params={"p": alvo})
            txt.to_parquet(DESTINO / "doc_text_piloto.parquet", index=False)
            print(f"doc_text={len(txt)} documentos de {txt.processo.nunique()} processos")
            cob = cobertura(docs, txt, alvo)
            cob.to_csv(DESTINO / "cobertura_texto.csv", index=False, encoding="utf-8-sig")
            baixa = cob[cob.cobertura_substantivas < COBERTURA_MIN]
            print(f"cobertura < {COBERTURA_MIN:.0%} das peças substantivas: {len(baixa)} de {len(cob)} processos"
                  + (" — " + ", ".join(baixa.processo) if len(baixa) else ""))


if __name__ == "__main__":
    main()
