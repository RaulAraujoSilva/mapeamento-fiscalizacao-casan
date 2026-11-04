"""Análise de cada peça por LLM → dados/relator/extractions.parquet (no lugar da análise "map-v3" do relator).

Por que existe: no projeto original, um sistema externo (o relator de voto) já tinha lido cada peça e gravado uma
análise estruturada. O pipeline usa dela: a data escrita na peça (`data`), os pedidos e a ação processual
(`pedidos_e_determinacoes`, `acao_processual` — prorrogação de prazo, classificação das atividades), os resumos
(`resumo_dos_fatos_relevantes`, `resumo_detalhado`), a base normativa (`dispositivos_citados`) e o número de
documentos referenciados (`entidades.documentos_referenciados`). Este módulo refaz essa análise com o mesmo formato.

Entradas: dados/relator/documentos.parquet e doc_text_piloto.parquet (de coleta/documentos.py).
Saída: extractions.parquet com processo, sei_doc_id, model_id, prompt_version, extraction_json (texto JSON).
Peças sem texto (restritas, escaneadas, não baixadas) recebem uma análise "stub" sem chamar o LLM, como no original.

Provedores: Anthropic (SDK oficial, padrão; modelo claude-haiku-5-5; chave ANTHROPIC_API_KEY) ou OpenRouter
(OPENROUTER_API_KEY). Saída JSON validada por esquema (structured outputs) e de novo localmente; cache por documento
em dados/extracoes/ (só chama de novo se mudar texto, modelo ou versão do prompt); a versão do prompt vai em cada linha.

Uso:
  python -m coleta.extrair                                  # Anthropic, claude-haiku-5-5, esforço medium
  python -m coleta.extrair --provedor openrouter --modelo google/gemini-3.6-flash
  python -m coleta.extrair --sem-llm                        # só stubs e cache (não chama API)"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from coleta.util import EXTRACOES, RELATOR, slug

PROMPT_VERSION = "map-v3-coleta-1"
MAX_CHARS = 100_000   # acima disso o texto é cortado e a análise marca texto_truncado=true
MIN_CHARS = 60        # peça mais curta que isso não tem o que analisar
PAPEIS = ["peticao", "parecer", "ata", "nota_tecnica", "deliberacao", "oficio", "relatorio_tecnico", "manifestacao",
          "razoes_finais", "consulta_publica", "despacho", "comprovante", "outro"]

SISTEMA = """Você é analista de processos de uma agência reguladora brasileira. Recebe o TEXTO de UMA peça \
(documento) de um processo administrativo do SEI, com seus metadados. Extraia os fatos da peça de forma factual e \
impessoal, em português do Brasil com acentuação correta. NÃO invente dados e NÃO opine: se um campo não consta do \
documento, use null, "" ou lista vazia.

Campos:
- instrumento: nome e número do instrumento, se houver ("Ofício nº 33/2024/ORGAO/UNIDADE", "Parecer nº 12/2024", \
"Nota Técnica ...", "Deliberação nº ...") ou "".
- ator_orgao: quem produziu ou assina — a sigla da unidade do órgão (ex.: "PROC", "SECEX", "Câmara técnica"), \
"Regulada/Concessionária", "Externo" ou "".
- papel_no_processo: o tipo funcional da peça (um dos valores do esquema).
- acao_processual: o verbo do movimento (requereu, solicitou, aprovou, opinou, homologou, encaminhou, esclareceu, \
determinou, recomendou, instaurou, deliberou, notificou...) ou "".
- data: data escrita no documento, em AAAA-MM-DD, ou null.
- data_por_extenso: a data como aparece por extenso ("03 de junho de 2024") ou null.
- resumo_dos_fatos_relevantes: 1 a 4 frases com o que a peça pede, decide ou conclui e por quê; inclua números \
(%, R$, prazos) quando forem o objeto.
- resumo_detalhado: análise completa, de 1 parágrafo (peça curta ou rotineira) a 8 (peça técnica ou decisória \
longa), na ordem do texto: contexto e motivação; todos os pedidos, determinações, conclusões e encaminhamentos; \
fundamentos técnicos e jurídicos; todos os números substantivos com contexto; ressalvas e condicionantes; \
providências e destinatários. Só o que consta do texto.
- pontos_chave: 3 a 12 frases curtas, cada uma com um fato, decisão ou pedido central.
- pedidos_e_determinacoes: cada pedido, requerimento, determinação ou recomendação expressa, um por item, com o \
destinatário quando houver (inclusive pedido de prorrogação de prazo). [] se não houver.
- prazos_e_eventos: objetos {evento, data} com data em AAAA-MM-DD ou o texto do prazo ("10 dias úteis").
- dispositivos_citados: leis, decretos, resoluções, deliberações, cláusulas contratuais e decisões anteriores \
citados, como aparecem no texto.
- citacoes_verbatim: 0 a 10 trechos copiados LITERALMENTE (metodologia, parâmetros, fundamentos, conclusões).
- numeros_substantivos: objetos {rotulo, valor} (ex.: {"rotulo": "reajuste pedido", "valor": "4,5%"}).
- entidades: {clausulas_contratuais: [...], documentos_referenciados: [...]} — documentos citados pela peça \
(ofícios, pareceres, processos, números SEI).
- tier_relevancia: 1 = marco processual (pedido inicial, parecer, nota técnica, relatório de fiscalização, \
manifestação de mérito, decisão, deliberação, recurso), mesmo se curto; 2 = secundário; 3 = só tramita \
(encaminhamento, ciência, acuse de recebimento, pedido de prorrogação, comprovante de envio); 0 = ruído (capa, \
recibo eletrônico, etiqueta).
- relevancia_para_relatorio: número de 0 a 1.
- requer_revisao: true se o texto é ambíguo ou ilegível e a extração é incerta.
- confianca: número de 0 a 1 com a sua confiança na extração."""


def _lista_str():
    return {"type": "array", "items": {"type": "string"}}


def _opcional_str():
    return {"anyOf": [{"type": "string"}, {"type": "null"}]}


ESQUEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "instrumento": {"type": "string"}, "ator_orgao": {"type": "string"},
        "papel_no_processo": {"type": "string", "enum": PAPEIS}, "acao_processual": {"type": "string"},
        "data": _opcional_str(), "data_por_extenso": _opcional_str(),
        "resumo_dos_fatos_relevantes": {"type": "string"}, "resumo_detalhado": {"type": "string"},
        "pontos_chave": _lista_str(), "pedidos_e_determinacoes": _lista_str(),
        "prazos_e_eventos": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["evento", "data"],
            "properties": {"evento": {"type": "string"}, "data": {"type": "string"}}}},
        "dispositivos_citados": _lista_str(), "citacoes_verbatim": _lista_str(),
        "numeros_substantivos": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["rotulo", "valor"],
            "properties": {"rotulo": {"type": "string"}, "valor": {"type": "string"}}}},
        "entidades": {"type": "object", "additionalProperties": False,
                      "required": ["clausulas_contratuais", "documentos_referenciados"],
                      "properties": {"clausulas_contratuais": _lista_str(), "documentos_referenciados": _lista_str()}},
        "tier_relevancia": {"type": "integer", "enum": [0, 1, 2, 3]},
        "relevancia_para_relatorio": {"type": "number"}, "requer_revisao": {"type": "boolean"},
        "confianca": {"type": "number"},
    },
}
ESQUEMA["required"] = list(ESQUEMA["properties"])


# ------------------------------------------------------------------------------------------------ validação
def validar_extracao(x) -> list[str]:
    """Problemas de uma resposta do LLM frente ao esquema (vazio = válida). Confere também o que o esquema da API
    não garante: faixas numéricas e o formato da data."""
    if not isinstance(x, dict):
        return ["resposta não é um objeto JSON"]
    p = []
    props = ESQUEMA["properties"]
    for k in ESQUEMA["required"]:
        if k not in x:
            p.append(f"falta '{k}'")
    for k in set(x) - set(props):
        p.append(f"campo inesperado '{k}'")
    tipos = {"string": str, "boolean": bool, "array": list, "object": dict}
    for k, sch in props.items():
        if k not in x:
            continue
        v = x[k]
        t = sch.get("type")
        if "anyOf" in sch:
            if v is not None and not isinstance(v, str):
                p.append(f"'{k}' deve ser texto ou null")
        elif t == "integer":
            if not isinstance(v, int) or isinstance(v, bool) or ("enum" in sch and v not in sch["enum"]):
                p.append(f"'{k}' fora de {sch.get('enum')}")
        elif t == "number":
            if not isinstance(v, (int, float)) or isinstance(v, bool) or not 0 <= v <= 1:
                p.append(f"'{k}' deve ser número entre 0 e 1")
        elif not isinstance(v, tipos[t]):
            p.append(f"'{k}' deve ser {t}")
        elif "enum" in sch and v not in sch["enum"]:
            p.append(f"'{k}' fora da lista de valores")
        elif t == "array" and sch["items"].get("type") == "string" and not all(isinstance(i, str) for i in v):
            p.append(f"'{k}' deve ser lista de textos")
        elif t == "array" and sch["items"].get("type") == "object":
            req = sch["items"]["required"]
            if not all(isinstance(i, dict) and all(isinstance(i.get(r), str) for r in req) for i in v):
                p.append(f"'{k}' deve ser lista de objetos com {req}")
    if isinstance(x.get("data"), str) and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", x["data"]):
        p.append("'data' deve estar em AAAA-MM-DD ou ser null")
    ent = x.get("entidades")
    if isinstance(ent, dict):
        for r in ("clausulas_contratuais", "documentos_referenciados"):
            if not isinstance(ent.get(r), list):
                p.append(f"'entidades.{r}' deve ser lista")
    return p


# ------------------------------------------------------------------------------------------------ provedores
def _json_da_resposta(texto: str) -> dict:
    t = texto.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    return json.loads(t)


def chamar_anthropic(modelo: str, usuario: str, esforco: str = "medium") -> tuple[dict, dict]:
    """Uma chamada com saída restrita ao ESQUEMA (structured outputs). Devolve (resposta, uso)."""
    import anthropic
    cliente = _cliente_anthropic()
    try:
        r = cliente.messages.create(
            model=modelo, max_tokens=16000, system=SISTEMA,
            messages=[{"role": "user", "content": usuario}],
            output_config={"effort": esforco, "format": {"type": "json_schema", "schema": ESQUEMA}})
    except anthropic.RateLimitError as e:
        raise RuntimeError("limite de requisições da API (o SDK já tentou de novo)") from e
    except anthropic.APIStatusError as e:
        raise RuntimeError(f"API respondeu {e.status_code}") from e
    except anthropic.APIConnectionError as e:
        raise RuntimeError("sem conexão com a API") from e
    if r.stop_reason != "end_turn":
        raise RuntimeError(f"resposta interrompida (stop_reason={r.stop_reason})")
    texto = next(b.text for b in r.content if b.type == "text")
    return json.loads(texto), r.usage.model_dump()


_CLIENTE = None


def _cliente_anthropic():
    global _CLIENTE
    if _CLIENTE is None:
        import anthropic
        _CLIENTE = anthropic.Anthropic(max_retries=4)  # credencial: ANTHROPIC_API_KEY ou perfil do `ant auth login`
    return _CLIENTE


def chamar_openrouter(modelo: str, usuario: str, esforco: str = "medium") -> tuple[dict, dict]:
    import time
    import requests
    chave = os.environ.get("OPENROUTER_API_KEY")
    if not chave:
        raise RuntimeError("OPENROUTER_API_KEY não definida")
    corpo = dict(model=modelo, temperature=0.1, max_tokens=16000,
                 messages=[{"role": "system", "content": SISTEMA}, {"role": "user", "content": usuario}],
                 response_format={"type": "json_schema",
                                  "json_schema": {"name": "analise_peca", "strict": True, "schema": ESQUEMA}})
    for tentativa in range(5):
        r = requests.post("https://openrouter.ai/api/v1/chat/completions", json=corpo, timeout=180,
                          headers={"Authorization": f"Bearer {chave}"})
        if r.status_code in (429, 500, 502, 503) and tentativa < 4:
            time.sleep(4 * (tentativa + 1))
            continue
        if r.status_code >= 400:
            raise RuntimeError(f"OpenRouter respondeu {r.status_code}")
        dado = r.json()
        return _json_da_resposta(dado["choices"][0]["message"]["content"] or ""), dado.get("usage", {})
    raise RuntimeError("OpenRouter sem resposta")


PROVEDORES = {"anthropic": chamar_anthropic, "openrouter": chamar_openrouter}
MODELO_PADRAO = {"anthropic": "claude-haiku-5-5", "openrouter": "google/gemini-3.6-flash"}


# ------------------------------------------------------------------------------------------------ análise
def _iso(s) -> str | None:
    if not s:
        return None
    s = str(s)
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", s)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return s[:10] if re.match(r"\d{4}-\d{2}-\d{2}", s) else None


def stub(sei_doc_id: str, tipo: str, motivo: str) -> dict:
    """Análise sem LLM para peça sem texto útil (mesmos campos, listas vazias, tier 0)."""
    return dict(sei_doc_id=sei_doc_id, instrumento=tipo or "", ator_orgao="", papel_no_processo="outro",
                acao_processual="", data=None, data_por_extenso=None, resumo_dos_fatos_relevantes=motivo,
                resumo_detalhado="", pontos_chave=[], pedidos_e_determinacoes=[], prazos_e_eventos=[],
                dispositivos_citados=[], texto_truncado=False, citacoes_verbatim=[], numeros_substantivos=[],
                entidades={"clausulas_contratuais": [], "documentos_referenciados": []}, tier_relevancia=0,
                relevancia_para_relatorio=0.0, requer_revisao=False, posicao_cronologica=None, confianca=0.0,
                fonte_texto_hash="", model_id="stub")


def mensagem_usuario(doc: dict, texto: str) -> str:
    return (f"Documento SEI nº {doc['sei_doc_id']}\nTipo (lista): {doc.get('tipo') or ''}\n"
            f"Unidade: {doc.get('unidade') or ''}\nData (lista): {doc.get('data') or ''}\n\n"
            f"=== TEXTO DO DOCUMENTO ===\n{texto[:MAX_CHARS]}")


def analisar(doc: dict, texto: str, provedor: str, modelo: str, esforco: str, cache: Path, chamar=None,
             usar_llm: bool = True) -> dict | None:
    """Análise de uma peça com texto: do cache se texto, modelo e versão do prompt forem os mesmos; senão chama o
    LLM (até 2 tentativas se a resposta não passar na validação). None = fora do cache e `usar_llm` falso."""
    h = hashlib.sha256(f"{texto}\n##{PROMPT_VERSION}##{modelo}".encode()).hexdigest()
    arq = cache / slug(doc["processo"]) / f"{doc['sei_doc_id']}.json"
    if arq.exists():
        c = json.loads(arq.read_text(encoding="utf-8"))
        if c.get("prompt_version") == PROMPT_VERSION and c.get("modelo") == modelo and c.get("hash") == h:
            return c["analise"]
    if not usar_llm:
        return None
    chamar = chamar or PROVEDORES[provedor]
    usuario = mensagem_usuario(doc, texto)
    problemas = []
    for _ in range(2):
        resp, uso = chamar(modelo, usuario, esforco)
        problemas = validar_extracao(resp)
        if not problemas:
            break
    else:
        raise RuntimeError("resposta fora do esquema: " + "; ".join(problemas[:4]))
    x = dict(resp, sei_doc_id=doc["sei_doc_id"], model_id=modelo, fonte_texto_hash=h,
             texto_truncado=len(texto) > MAX_CHARS)
    x["data"] = x.get("data") or _iso(doc.get("data"))
    x["posicao_cronologica"] = _iso(x["data"]) or _iso(doc.get("data")) or _iso(doc.get("data_inclusao"))
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(dict(prompt_version=PROMPT_VERSION, modelo=modelo, provedor=provedor, hash=h,
                                   analise=x, uso=uso), ensure_ascii=False, indent=1), encoding="utf-8")
    return x


def extrair_todos(docs: list[dict], textos: dict, provedor: str, modelo: str, esforco: str = "medium",
                  cache: Path = EXTRACOES, workers: int = 4, chamar=None, usar_llm: bool = True,
                  limite: int | None = None) -> tuple[list[dict], list[str]]:
    """Linhas de extractions.parquet e lista de erros. `textos` = {(processo, sei_doc_id): texto}."""
    linhas, erros, tarefas = [], [], []

    def linha(doc, x, mid):
        return dict(processo=doc["processo"], sei_doc_id=str(doc["sei_doc_id"]), model_id=mid,
                    prompt_version=PROMPT_VERSION, extraction_json=json.dumps(x, ensure_ascii=False))

    for d in docs:
        sid = str(d["sei_doc_id"])
        t = (textos.get((d["processo"], sid)) or "").strip()
        if d.get("restrito") or d.get("download_status") == "restricted":
            linhas.append(linha(d, stub(sid, d.get("tipo"), "Documento de acesso restrito."), "stub"))
        elif len(t) < MIN_CHARS:
            motivo = f"Sem texto útil ({d['mime']})." if d.get("mime") else "Sem texto útil."
            linhas.append(linha(d, stub(sid, d.get("tipo"), motivo), "stub"))
        else:
            tarefas.append((d, t))
    if limite is not None:
        tarefas = tarefas[:limite]
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        fut = {ex.submit(analisar, dict(d, sei_doc_id=str(d["sei_doc_id"])), t, provedor, modelo, esforco, cache,
                         chamar, usar_llm): d for d, t in tarefas}
        for f in as_completed(fut):
            d = fut[f]
            try:
                x = f.result()
            except Exception as e:  # noqa: BLE001 — um documento com erro não para os demais
                erros.append(f"{d['processo']}:{d['sei_doc_id']}: {e}")
                continue
            if x is not None:
                linhas.append(linha(d, x, modelo))
    linhas.sort(key=lambda r: (r["processo"], r["sei_doc_id"]))
    return linhas, erros


def main(argv=None):
    import pandas as pd
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--provedor", choices=sorted(PROVEDORES), default="anthropic")
    ap.add_argument("--modelo", help="padrão: claude-haiku-5-5 (anthropic) ou google/gemini-3.6-flash (openrouter)")
    ap.add_argument("--esforco", default="medium", choices=["low", "medium", "high"],
                    help="esforço de raciocínio (só Anthropic)")
    ap.add_argument("--relator", type=Path, default=RELATOR, help="pasta dos parquets de entrada e saída")
    ap.add_argument("--processos", type=Path, help="CSV com coluna 'numero': só esses processos")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limite", type=int, help="no máximo N chamadas ao LLM (teste de custo)")
    ap.add_argument("--sem-llm", action="store_true", help="não chama a API: grava stubs e o que houver no cache")
    args = ap.parse_args(argv)
    modelo = args.modelo or MODELO_PADRAO[args.provedor]
    docs = pd.read_parquet(args.relator / "documentos.parquet")
    txt = pd.read_parquet(args.relator / "doc_text_piloto.parquet")
    if args.processos:
        alvo = set(pd.read_csv(args.processos)["numero"].astype(str))
        docs = docs[docs.processo.isin(alvo)]
    textos = {(p, str(s)): t for p, s, t in zip(txt.processo, txt.sei_doc_id, txt.texto)}
    registros = [{k: (None if pd.isna(v) else v) if not isinstance(v, (list, dict)) else v for k, v in r.items()}
                 for r in docs.to_dict("records")]
    linhas, erros = extrair_todos(registros, textos, args.provedor, modelo, args.esforco, workers=args.workers,
                                  usar_llm=not args.sem_llm, limite=args.limite)
    out = pd.DataFrame(linhas, columns=["processo", "sei_doc_id", "model_id", "prompt_version", "extraction_json"])
    out.to_parquet(args.relator / "extractions.parquet", index=False)
    n_stub = int((out.model_id == "stub").sum())
    print(f"extractions={len(out)} (stub={n_stub}, {modelo}={len(out) - n_stub})  prompt={PROMPT_VERSION}")
    for e in erros[:20]:
        print("ERRO", e)
    if erros:
        raise SystemExit(f"{len(erros)} documento(s) com erro; rode de novo (o cache guarda os que deram certo)")


if __name__ == "__main__":
    main()
