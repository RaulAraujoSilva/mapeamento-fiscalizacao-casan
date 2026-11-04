"""Importa as respostas dos agentes de leitura (dados/agentes/lote_*/saida) para os caches do repositório, no mesmo
formato que coleta/extrair.py e scripts/fichas_trabalho.py gravariam. Depois disso os dois scripts rodam normalmente
e reaproveitam o cache (peça sem resposta válida cai para a API, com o mesmo modelo).

  python ferramentas_caso/importar_lotes.py analise   # antes de: python -m coleta.extrair --provedor openrouter --modelo anthropic/claude-haiku-5.5
  python ferramentas_caso/importar_lotes.py ficha     # antes de: python fichas_trabalho.py --modelo anthropic/claude-haiku-5.5
Validação: análise pelo validador do esquema (extrair.validar_extracao); ficha pela ancoragem literal (fichas_trabalho.ancorar)."""
import hashlib, json, sys
from pathlib import Path
import pandas as pd
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(RAIZ / "scripts"))
from coleta import extrair as EX
from coleta.util import EXTRACOES, slug
MODELO = "anthropic/claude-haiku-5.5"
AG = RAIZ / "dados" / "agentes"


def respostas(sufixo):
    for arq in sorted(AG.glob(f"lote_*/saida/*__{sufixo}.json")):
        try:
            yield arq.name.split("__")[0], arq.parent.parent.name, json.loads(arq.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as e:
            print("JSON inválido", arq, e); yield arq.name.split("__")[0], arq.parent.parent.name, None


def analise():
    docs = pd.read_parquet(RAIZ / "dados/relator/documentos.parquet"); txt = pd.read_parquet(RAIZ / "dados/relator/doc_text_piloto.parquet")
    m = {str(r.sei_doc_id): r for r in docs.merge(txt, on=["processo", "sei_doc_id"]).itertuples()}
    ok = ruim = 0
    for sid, lote, resp in respostas("analise"):
        r = m[sid]; texto = r.texto
        prob = EX.validar_extracao(resp) if resp is not None else ["json"]
        if prob:
            ruim += 1; print("fora do esquema", sid, prob[:3]); continue
        h = hashlib.sha256(f"{texto}\n##{EX.PROMPT_VERSION}##{MODELO}".encode()).hexdigest()
        x = dict(resp, sei_doc_id=sid, model_id=MODELO, fonte_texto_hash=h, texto_truncado=len(texto) > EX.MAX_CHARS)
        x["data"] = x.get("data") or EX._iso(r.data)
        x["posicao_cronologica"] = EX._iso(x["data"]) or EX._iso(r.data) or EX._iso(r.data_inclusao)
        arq = EXTRACOES / slug(r.processo) / f"{sid}.json"; arq.parent.mkdir(parents=True, exist_ok=True)
        arq.write_text(json.dumps(dict(prompt_version=EX.PROMPT_VERSION, modelo=MODELO, provedor="agente-claude-code",
                                       hash=h, analise=x, uso={"lote": lote}), ensure_ascii=False, indent=1), encoding="utf-8")
        ok += 1
    print(f"análises importadas: {ok}; rejeitadas: {ruim}")


def ficha():
    import fichas_trabalho as FT
    tarefas = {t["sei_doc_id"]: t for t in FT.montar_tarefas(None)}
    FT.CACHE.mkdir(parents=True, exist_ok=True)
    ok = ruim = 0; anc = tot = 0
    for sid, lote, resp in respostas("ficha"):
        t = tarefas.get(sid)
        if t is None or not isinstance(resp, dict):
            ruim += 1; print("sem tarefa ou JSON inválido", sid); continue
        f = FT.legado(FT.ancorar(resp, t["_texto"]))
        def conta(x):
            global anc, tot
        dado = {k: v for k, v in t.items() if k != "usuario" and not k.startswith("_")} | {
            "ficha": f, "modelo": MODELO, "prompt_versao": FT.PROMPT_VERSAO, "origem": f"agente-claude-code/{lote}"}
        (FT.CACHE / f"{t['processo'].replace('/', '_')}__{sid}.json").write_text(
            json.dumps(dado, ensure_ascii=False, indent=1), encoding="utf-8")
        ok += 1
    falta = sorted(set(tarefas) - {s for s, _, _ in respostas("ficha")})
    print(f"fichas importadas: {ok}; rejeitadas: {ruim}; tarefas sem resposta: {falta}")


if __name__ == "__main__":
    {"analise": analise, "ficha": ficha}[sys.argv[1]]()
