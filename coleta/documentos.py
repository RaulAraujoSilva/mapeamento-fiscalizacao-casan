"""Conteúdo das peças: baixa os documentos públicos listados pela coleta e grava, em dados/relator/, os arquivos que os
scripts leem no lugar do banco do relator do projeto original.

Entrada: dados/coleta/indice_documentos.csv (gerado por coleta/coletar.py: link público e restrição de cada peça).
Saídas (mesmo esquema de scripts/exportar_relator.py):
  documentos.parquet      processo, sei_doc_id, tipo, data, data_inclusao, unidade, download_status, mime, n_chars,
                          restrito, motivo_restricao, origem_apenso — uma linha por documento do índice
  doc_text_piloto.parquet processo, sei_doc_id, texto — só documentos com texto extraído
  cobertura_texto.csv     processo, pecas, com_texto, restritas, substantivas, cobertura_substantivas

download_status: ok (texto extraído) · sem_texto (baixado, mas sem camada de texto: PDF escaneado, imagem, planilha,
zip) · restricted (restrito/sigiloso ou sem link público: registrado sem texto, NUNCA se tenta contornar) · failed
(erro de rede/servidor) · pending (não baixado nesta execução: fora de --processos ou --sem-rede sem cache) ·
bloqueado (o servidor pediu captcha: a coleta para na hora).

Também aceita documentos salvos à mão: --pasta-docs com arquivos nomeados pelo número SEI (12345678.pdf, .html...).

Uso:
  python -m coleta.documentos --perfil RJ
  python -m coleta.documentos --perfil RJ --processos saida/piloto.csv --intervalo 3
  python -m coleta.documentos --perfil RJ --pasta-docs documentos_salvos/ --sem-rede"""
from __future__ import annotations

import argparse
import csv
import html as html_lib
import io
import json
import mimetypes
import re
import sys
import zipfile
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from coleta.perfil_sei import PerfilSEI, carregar_perfil
from coleta.util import BRUTO, RELATOR, TRABALHO, ClienteHTTP, comum, limpar, sem_credencial, slug

# Mesmo conjunto de scripts/selecionar_piloto.py::SUBSTANTIVAS (copiado porque aquele módulo importa o catálogo da
# AGENERSA por caminho absoluto; tests/test_coleta.py confere que os dois continuam iguais).
SUBSTANTIVAS = {"parecer", "relatorio", "relatorio_fiscalizacao", "nota_tecnica", "voto", "deliberacao",
                "decisao", "despacho_decisorio", "notificacao_autuacao", "informacao", "manifestacao_pge", "ata"}
COLUNAS_DOCUMENTOS = ["processo", "sei_doc_id", "tipo", "data", "data_inclusao", "unidade", "download_status", "mime",
                      "n_chars", "restrito", "motivo_restricao", "origem_apenso"]
MIN_CARACTERES = 20  # abaixo disso (sem espaços) o "texto" de um PDF é ruído de imagem escaneada
# página de documento que só avisa restrição (curta) — documento longo que CITA "acesso restrito" não conta
RE_PAGINA_RESTRITA = re.compile(r"(documento|processo)[^.]{0,40}(restrito|sigiloso)|n[ãa]o (?:est[áa]|[ée]) "
                                r"dispon[íi]vel para (?:consulta|acesso)", re.I)


# ------------------------------------------------------------------------------------------------ texto
def tipo_mime(conteudo: bytes, content_type: str) -> str:
    ct = (content_type or "").split(";")[0].strip().lower()
    if conteudo[:5] == b"%PDF-":
        return "application/pdf"
    if conteudo[:2] == b"PK" and b"word/" in conteudo[:4000]:
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if not ct or ct == "application/octet-stream":
        cab = conteudo[:400].lower()
        if b"<html" in cab or b"<!doctype html" in cab or b"<body" in cab:
            return "text/html"
    return ct or "application/octet-stream"


def texto_html(conteudo: bytes) -> str:
    from bs4 import BeautifulSoup
    s = BeautifulSoup(conteudo, "lxml")
    for el in s(["script", "style", "noscript", "head"]):
        el.decompose()
    linhas = [limpar(x) for x in s.get_text("\n").split("\n")]
    return "\n".join(x for x in linhas if x)


def texto_pdf(conteudo: bytes) -> str:
    from pypdf import PdfReader
    leitor = PdfReader(io.BytesIO(conteudo))
    return "\n".join((p.extract_text() or "").strip() for p in leitor.pages).strip()


def texto_docx(conteudo: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
        xml = z.read("word/document.xml").decode("utf-8", "ignore")
    xml = re.sub(r"</w:p>", "\n", xml)
    return "\n".join(limpar(html_lib.unescape(x)) for x in re.sub(r"<[^>]+>", "", xml).split("\n") if limpar(x))


def extrair(conteudo: bytes, content_type: str, perfil: PerfilSEI) -> tuple[str, str, str, str | None]:
    """(download_status, mime, texto, motivo_restricao) de um arquivo baixado."""
    mime = tipo_mime(conteudo, content_type)
    try:
        if "html" in mime:
            texto = texto_html(conteudo)
            if re.search(perfil.marca_bloqueio, texto, re.I) and len(texto) < 3000:
                return "bloqueado", mime, "", None
            if len(texto) < 1500 and RE_PAGINA_RESTRITA.search(texto):
                return "restricted", mime, "", "Documento restrito (aviso na página do documento)"
        elif mime == "application/pdf":
            texto = texto_pdf(conteudo)
        elif "wordprocessingml" in mime:
            texto = texto_docx(conteudo)
        elif mime.startswith("text/"):
            texto = conteudo.decode("utf-8", "replace").strip()
        else:
            return "sem_texto", mime, "", None  # imagem, planilha, zip: sem extração de texto
    except Exception:  # noqa: BLE001 — arquivo corrompido não pode parar a coleta
        return "sem_texto", mime, "", None
    if len(re.sub(r"\s", "", texto)) < MIN_CARACTERES:
        return "sem_texto", mime, "", None
    return "ok", mime, texto, None


# ------------------------------------------------------------------------------------------------ obtenção
def _br(iso: str | None) -> str | None:
    """'2024-03-05' → '05/03/2024' (formato do banco do relator; scripts/pecas_relator.py lê os dois)."""
    if not iso:
        return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", iso)
    return f"{m.group(3)}/{m.group(2)}/{m.group(1)}" if m else iso


def _verdade(v) -> bool:
    return str(v).strip().lower() in ("true", "1", "sim", "s", "yes")


def obter_arquivo(doc: dict, cliente, cache: Path, pasta_docs: Path | None) -> tuple[bytes, str] | None:
    """Conteúdo e content-type: da pasta de documentos salvos, do cache ou baixado (e posto no cache)."""
    sid = doc["sei_doc_id"]
    if pasta_docs:
        for arq in pasta_docs.glob(f"{sid}.*"):
            return arq.read_bytes(), mimetypes.guess_type(arq.name)[0] or ""
    pasta = cache / slug(doc["processo"])
    bruto, meta = pasta / f"{sid}.bin", pasta / f"{sid}.json"
    if bruto.exists() and meta.exists():
        return bruto.read_bytes(), json.loads(meta.read_text(encoding="utf-8")).get("content_type", "")
    if cliente is None:
        return None
    r = cliente.obter(doc["link"])
    pasta.mkdir(parents=True, exist_ok=True)
    bruto.write_bytes(r.conteudo)
    meta.write_text(json.dumps(dict(content_type=r.content_type, status_http=r.status), ensure_ascii=False),
                    encoding="utf-8")
    return r.conteudo, r.content_type


def coletar_documentos(indice: list[dict], perfil: PerfilSEI, cliente, cache: Path = BRUTO / "documentos",
                       pasta_docs: Path | None = None, alvo: set | None = None) -> tuple[list[dict], list[dict]]:
    """Linhas de documentos.parquet e de doc_text_piloto.parquet. `alvo` limita os processos com download."""
    docs, textos = [], []
    parado = False
    for d in indice:
        sid = str(d["sei_doc_id"]).strip()
        if not sid.isdigit():
            continue  # protocolo que é outro processo (anexado/relacionado): não é peça
        base = dict(processo=d["processo"], sei_doc_id=sid, tipo=d.get("tipo") or None, data=_br(d.get("data")),
                    data_inclusao=_br(d.get("data_inclusao")), unidade=d.get("unidade") or None, mime=None,
                    n_chars=0, restrito=False, motivo_restricao=None, origem_apenso=None)
        restrito = _verdade(d.get("restrito")) or _verdade(d.get("processo_restrito"))
        if restrito or not d.get("link"):
            docs.append(base | dict(download_status="restricted", restrito=True,
                                    motivo_restricao=d.get("motivo_restricao") or "Sem link na pesquisa pública"))
            continue
        if parado or (alvo is not None and d["processo"] not in alvo):
            docs.append(base | dict(download_status="pending"))
            continue
        try:
            got = obter_arquivo(dict(d, sei_doc_id=sid), cliente, cache, pasta_docs)
        except RuntimeError as e:
            docs.append(base | dict(download_status="failed", mime=f"erro: {sem_credencial(e)[:80]}"))
            continue
        if got is None:
            docs.append(base | dict(download_status="pending"))
            continue
        status, mime, texto, motivo = extrair(got[0], got[1], perfil)
        if status == "bloqueado":
            print("PARADO: o servidor pediu verificação humana (captcha). Não insista; salve os documentos à mão "
                  "e use --pasta-docs.")
            parado = True
            docs.append(base | dict(download_status="pending"))
            continue
        docs.append(base | dict(download_status=status, mime=mime, n_chars=len(texto),
                                restrito=status == "restricted", motivo_restricao=motivo))
        if status == "ok":
            textos.append(dict(processo=d["processo"], sei_doc_id=sid, texto=texto))
    return docs, textos


# ------------------------------------------------------------------------------------------------ cobertura
def cobertura(docs, txt, alvo: list):
    """Mesma regra de scripts/exportar_relator.py::cobertura: por processo, peças, peças substantivas e fração delas
    com texto não vazio."""
    import pandas as pd
    categoria_documento = comum().categoria_documento
    d = docs[docs.processo.isin(alvo)].copy()
    d["categoria"] = [categoria_documento(t, str(n))[0] for t, n in zip(d.tipo.fillna(""), d.sei_doc_id)]
    com = {(p, str(s)) for p, s, t in zip(txt.processo, txt.sei_doc_id, txt.texto) if str(t or "").strip()}
    d["tem_texto"] = [(p, str(s)) in com for p, s in zip(d.processo, d.sei_doc_id)]
    d["subst"] = d.categoria.isin(SUBSTANTIVAS)
    linhas = []
    for p, x in d.groupby("processo"):
        linhas.append(dict(processo=p, pecas=len(x), com_texto=int(x.tem_texto.sum()),
                           restritas=int(x.restrito.fillna(False).astype(bool).sum()), substantivas=int(x.subst.sum()),
                           cobertura_substantivas=round(x[x.subst].tem_texto.mean(), 3) if x.subst.any() else 0.0))
    faltam = sorted(set(alvo) - {r["processo"] for r in linhas})
    linhas += [dict(processo=p, pecas=0, com_texto=0, restritas=0, substantivas=0, cobertura_substantivas=0.0)
               for p in faltam]
    return pd.DataFrame(linhas, columns=["processo", "pecas", "com_texto", "restritas", "substantivas",
                                         "cobertura_substantivas"])


def gravar(docs: list[dict], textos: list[dict], saida: Path, alvo: list) -> dict:
    import pandas as pd
    saida.mkdir(parents=True, exist_ok=True)
    d = pd.DataFrame(docs, columns=COLUNAS_DOCUMENTOS)
    d["n_chars"] = d.n_chars.fillna(0).astype("int64")
    d["restrito"] = d.restrito.fillna(False).astype(bool)
    d["origem_apenso"] = d.origem_apenso.astype(object)
    t = pd.DataFrame(textos, columns=["processo", "sei_doc_id", "texto"])
    d.to_parquet(saida / "documentos.parquet", index=False)
    t.to_parquet(saida / "doc_text_piloto.parquet", index=False)
    cob = cobertura(d, t, alvo)
    cob.to_csv(saida / "cobertura_texto.csv", index=False, encoding="utf-8-sig")
    return dict(documentos=len(d), com_texto=len(t), status=d.download_status.value_counts().to_dict())


def ler_indice(arq: Path) -> list[dict]:
    if not arq.exists():
        raise SystemExit(f"{arq} não existe: rode antes python -m coleta.coletar")
    with open(arq, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--perfil", default="RJ")
    ap.add_argument("--indice", type=Path, default=TRABALHO / "indice_documentos.csv")
    ap.add_argument("--processos", type=Path, help="CSV com coluna 'numero': só esses processos têm download")
    ap.add_argument("--pasta-docs", type=Path, help="documentos salvos à mão, nomeados pelo número SEI")
    ap.add_argument("--saida", type=Path, default=RELATOR)
    ap.add_argument("--sem-rede", action="store_true", help="só cache e --pasta-docs")
    ap.add_argument("--intervalo", type=float, default=2.0)
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--tentativas", type=int, default=3)
    ap.add_argument("--contato")
    args = ap.parse_args(argv)
    perfil = carregar_perfil(args.perfil)
    indice = ler_indice(args.indice)
    alvo = None
    if args.processos:
        import pandas as pd
        alvo = set(pd.read_csv(args.processos)["numero"].astype(str))
    cliente = None if args.sem_rede else ClienteHTTP(args.intervalo, args.timeout, args.tentativas,
                                                     contato=args.contato)
    docs, textos = coletar_documentos(indice, perfil, cliente, pasta_docs=args.pasta_docs, alvo=alvo)
    processos = sorted(alvo) if alvo is not None else sorted({d["processo"] for d in indice})
    r = gravar(docs, textos, args.saida, processos)
    print(f"documentos={r['documentos']}  com texto={r['com_texto']}  situação={r['status']}")
    print(f"saídas em {args.saida}: documentos.parquet, doc_text_piloto.parquet, cobertura_texto.csv")


if __name__ == "__main__":
    main()
