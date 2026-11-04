"""Fase 2 — tipos de processo além dos já mapeados: classifica no inventário P01–P36 os processos que só existem
no banco do relator (texto e análise por peça, sem trilha no SEI 2) e aponta demandas sem processo no inventário.

Entrada por processo: tipos e unidades das peças, período e o resumo da análise do relator das primeiras peças e
das peças decisórias (parecer, voto, deliberação, relatório). Saída validada por esquema: código principal e
secundário, confiança e, quando LACUNA, o tipo de demanda (usar um dos já sugeridos se couber).
Modelo: Claude Haiku 5.5 com esforço alto. Cache por processo em dados/classificador_novos/.

Saída: saida/fase2/classificacao_relator.csv"""
from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

import anthropic
import pandas as pd

from comum import DADOS, DESCRICAO_ORGAO, SAIDA, SETORES_ORGAO
from fichas_atividades import limpar_pessoais

MODELO = "claude-haiku-5-5"
ESFORCO = "high"
VERSAO = "tipo-v1"
CACHE = DADOS / "classificador_novos"
OUT = SAIDA / "fase2"
DECISORIAS = ("parecer", "voto", "delibera", "relat", "nota técnica", "decis")

SISTEMA = """Você classifica processos SEI de uma agência reguladora (""" + f"{DESCRICAO_ORGAO}: {SETORES_ORGAO}" + """) no
inventário de processos organizacionais da agência. Recebe o inventário (código, nome, escopo) e o retrato de UM
processo: tipos de peça, unidades, período e resumos das peças iniciais e decisórias.

Regras:
- principal = o processo organizacional que o processo SEI executa (o motivo de existir, não um passo de passagem).
- secundario = outro processo que ele também executa de forma relevante, ou "nenhum".
- LACUNA = a demanda não corresponde a nenhum processo do inventário. Nesse caso, nomeie o tipo de demanda em
  tipo_novo (curto, genérico, reutilizável por outros processos do mesmo tipo); se couber num tipo já sugerido,
  use exatamente esse nome. Fora de LACUNA, tipo_novo fica vazio.
- confiança: alta = escopo inequívoco; media = cabe em mais de um; baixa = informação insuficiente.
- Baseie-se só no que está nos resumos. justificativa: até duas frases."""


def catalogo() -> tuple[str, list[str], list[str]]:
    cat = json.loads((SAIDA / "catalogo_processos.json").read_text(encoding="utf-8"))
    cls = pd.read_csv(SAIDA / "processos_classificados.csv")
    lac = sorted(cls.lacuna_sugerida.dropna().unique())
    txt = "\n".join(f"- {c['id']} {c['nome']}: {c['escopo']}" for c in cat)
    txt += "\n\nTipos de demanda já sugeridos como LACUNA:\n" + "\n".join(f"- {x}" for x in lac)
    return txt, [c["id"] for c in cat] + ["LACUNA"], lac


def retrato(numero: str, docs: pd.DataFrame, ext: dict) -> str:
    d = docs[docs.processo == numero].copy()
    d["data_inclusao"] = d.data_inclusao.astype(str)
    d = d.sort_values(["data_inclusao", "sei_doc_id"])
    tipos = d.tipo.fillna("?").value_counts().head(15)
    unid = d.unidade.fillna("?").str.split("/").str[-1].value_counts().head(10)

    def res(r):
        x = ext.get((numero, str(r.sei_doc_id))) or {}
        t = x.get("resumo_dos_fatos_relevantes") or x.get("resumo_detalhado") or ""
        return f"[{str(r.data_inclusao)[:10]} · {r.tipo} · {str(r.unidade).split('/')[-1]}] {str(t)[:500]}"
    ini = [res(r) for r in d.head(5).itertuples()]
    dec = [res(r) for r in d[d.tipo.fillna("").str.lower().str.contains("|".join(DECISORIAS))].tail(4).itertuples()]
    return (f"Processo {numero} · {len(d)} peças · {str(d.data_inclusao.min())[:10]} a {str(d.data_inclusao.max())[:10]}\n"
            f"Tipos de peça: " + "; ".join(f"{k} ({v})" for k, v in tipos.items()) + "\n"
            f"Unidades: " + "; ".join(f"{k} ({v})" for k, v in unid.items()) + "\n\n"
            "Peças iniciais:\n" + "\n".join(ini) + "\n\nPeças decisórias:\n" + ("\n".join(dec) or "(nenhuma)"))


def esquema(ids):
    return {"type": "object", "additionalProperties": False,
            "required": ["principal", "secundario", "confianca", "tipo_novo", "justificativa"],
            "properties": {"principal": {"type": "string", "enum": ids},
                           "secundario": {"type": "string", "enum": ids + ["nenhum"]},
                           "confianca": {"type": "string", "enum": ["alta", "media", "baixa"]},
                           "tipo_novo": {"type": "string"}, "justificativa": {"type": "string"}}}


def classificar(cliente, numero, docs, ext, cat_txt, ids) -> dict:
    usuario = f"Inventário:\n{cat_txt}\n\n=== PROCESSO ===\n{retrato(numero, docs, ext)}"
    arq = CACHE / f"{numero.replace('/', '_')}.json"
    if arq.exists() and (c := json.loads(arq.read_text(encoding="utf-8"))).get("versao") == VERSAO \
            and c.get("usuario") == usuario:
        return dict(numero=numero, **c["resposta"])
    r = cliente.messages.create(model=MODELO, max_tokens=16000, system=SISTEMA,
                                messages=[{"role": "user", "content": usuario}],
                                output_config={"effort": ESFORCO,
                                               "format": {"type": "json_schema", "schema": esquema(ids)}})
    if r.stop_reason != "end_turn":
        raise RuntimeError(f"{numero}: stop_reason {r.stop_reason}")
    resp = json.loads(next(b.text for b in r.content if b.type == "text"))
    arq.write_text(json.dumps(dict(versao=VERSAO, modelo=MODELO, esforco=ESFORCO, usuario=usuario, resposta=resp,
                                   uso=r.usage.model_dump()), ensure_ascii=False, indent=1), encoding="utf-8")
    return dict(numero=numero, **resp)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    docs = pd.read_parquet(DADOS / "relator" / "documentos.parquet")
    cls = pd.read_csv(SAIDA / "processos_classificados.csv")
    alvo = sorted(set(docs.processo) - set(cls.numero))
    e = pd.read_parquet(DADOS / "relator" / "extractions.parquet", columns=["processo", "sei_doc_id",
                                                                                  "extraction_json"])
    e = e[e.processo.isin(alvo)]
    ext = {(p, str(s)): json.loads(j) for p, s, j in zip(e.processo, e.sei_doc_id, e.extraction_json)}
    cat_txt, ids, _ = catalogo()
    cliente = anthropic.Anthropic()
    res, erros = [], []
    with ThreadPoolExecutor(args.workers) as ex:
        fut = {ex.submit(classificar, cliente, n, docs, ext, cat_txt, ids): n for n in alvo}
        for f in as_completed(fut):
            try:
                res.append(f.result())
            except Exception as err:  # noqa: BLE001
                erros.append(f"{fut[f]}: {err}")
    for x in erros:
        print("ERRO", x)
    t = pd.DataFrame(res)
    t["justificativa"] = t.justificativa.map(limpar_pessoais)  # vai para o git: sem dados de terceiros
    n_docs = docs.groupby("processo").size()
    t["n_docs"] = t.numero.map(n_docs)
    t.sort_values(["principal", "numero"]).to_csv(OUT / "classificacao_relator.csv", index=False, encoding="utf-8-sig")
    print(t.principal.value_counts().to_string())
    print(t[t.principal == "LACUNA"].tipo_novo.value_counts().to_string())


if __name__ == "__main__":
    main()
