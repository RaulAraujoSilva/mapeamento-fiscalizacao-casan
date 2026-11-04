"""Prepara lotes de leitura para agentes (Claude Code, Haiku): para cada peça com texto, a mensagem da análise por
peça (coleta/extrair.py, map-v3-coleta-1) e, se for peça da agência com ficha, a mensagem da ficha de trabalho
(scripts/fichas_trabalho.py, ficha-v2). Os prompts de sistema são copiados literalmente dos módulos do repositório.
Saída em dados/agentes/ (fora do git: tem texto integral das peças)."""
import json, sys
from pathlib import Path
import pandas as pd
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(RAIZ / "scripts"))
from coleta import extrair as EX
import fichas_trabalho as FT
from comum import categoria_documento, ORGAO

N_LOTES = int(sys.argv[1]) if len(sys.argv) > 1 else 15
REL = RAIZ / "dados" / "relator"; OUT = RAIZ / "dados" / "agentes"
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "SISTEMA_ANALISE.md").write_text(EX.SISTEMA + "\n\nEsquema JSON obrigatório (todos os campos, sem campos extras):\n"
    + json.dumps(EX.ESQUEMA, ensure_ascii=False, indent=1), encoding="utf-8")
(OUT / "SISTEMA_FICHA.md").write_text(FT.SISTEMA, encoding="utf-8")
docs = pd.read_parquet(REL / "documentos.parquet"); txt = pd.read_parquet(REL / "doc_text_piloto.parquet")
m = docs.merge(txt, on=["processo", "sei_doc_id"], how="inner")
m = m[m.texto.str.strip().str.len() >= EX.MIN_CHARS].sort_values("sei_doc_id", key=lambda s: s.astype(int))
cat = json.loads((RAIZ / "saida" / "catalogo_processos.json").read_text(encoding="utf-8")) if (RAIZ / "saida" / "catalogo_processos.json").exists() else []
nome_p06 = next((c["nome"] for c in cat if c["id"] == "P06"), "Fiscalização")
itens = []
for r in m.to_dict("records"):
    d = {k: (None if not isinstance(v, (list, dict)) and pd.isna(v) else v) for k, v in r.items()}
    categoria = categoria_documento(d["tipo"], str(d["sei_doc_id"]))[0]
    com_ficha = categoria in FT.CATEGORIAS_COM_FICHA and str(d["unidade"]).startswith(ORGAO) and len(d["texto"].strip()) > 50
    item = dict(sei_doc_id=str(d["sei_doc_id"]), tipo=d["tipo"], categoria=categoria, com_ficha=com_ficha,
                msg_analise=EX.mensagem_usuario(dict(d, sei_doc_id=str(d["sei_doc_id"])), d["texto"]))
    if com_ficha:
        item["msg_ficha"] = (f"Processo SEI {d['processo']} — assunto: (não informado na pesquisa pública)\n"
                             f"Processo organizacional: P06 {nome_p06}\n"
                             f"Documento SEI {d['sei_doc_id']} · tipo: {d['tipo']} · unidade autora: {d['unidade']} · incluído em "
                             f"{str(d['data_inclusao'])[:10]} · {len(d['texto'])} caracteres\n\n=== TEXTO ===\n{FT._texto(d['texto'])}")
    itens.append(item)
# lotes balanceados por tamanho
itens.sort(key=lambda x: -len(x["msg_analise"]))
lotes = [[] for _ in range(N_LOTES)]; tam = [0] * N_LOTES
for it in itens:
    i = tam.index(min(tam)); lotes[i].append(it); tam[i] += len(it["msg_analise"]) * (2 if it["com_ficha"] else 1)
for i, l in enumerate(lotes, 1):
    p = OUT / f"lote_{i:02d}"; (p / "entrada").mkdir(parents=True, exist_ok=True); (p / "saida").mkdir(exist_ok=True)
    for it in l:
        (p / "entrada" / f"{it['sei_doc_id']}__analise.txt").write_text(it["msg_analise"], encoding="utf-8")
        if it["com_ficha"]:
            (p / "entrada" / f"{it['sei_doc_id']}__ficha.txt").write_text(it["msg_ficha"], encoding="utf-8")
print(len(itens), "peças;", sum(i["com_ficha"] for i in itens), "com ficha;", [len(l) for l in lotes])
print(pd.Series([i["categoria"] for i in itens]).value_counts().to_dict())
