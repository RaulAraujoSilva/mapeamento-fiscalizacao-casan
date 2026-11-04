"""Coletor do SEI (coleta/) em páginas sintéticas: parse da Pesquisa Pública do SEI-RJ e de um "outro Estado" com
rótulos e redação diferentes, normalização dos andamentos para as frases que o pipeline reconhece, esquema das TSVs
lido por scripts/comum.py, HTML salvo à mão, documentos (texto, PDF, restrição), análise por LLM (com provedor falso:
nenhum teste chama API) e o portão de qualidade. Nenhum teste acessa a rede."""
import ast
import json
import re
import sys
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

import comum  # noqa: E402  (só leitura das regras do pipeline)
from coleta import coletar, documentos, extrair, validar_coleta  # noqa: E402
from coleta.parser import PaginaInvalida, analisar_pagina, mapear_colunas  # noqa: E402
from coleta.perfil_sei import MODELO, PERFIS, RJ, RegraAndamento, perfil_de_dict  # noqa: E402
from coleta.util import COLUNAS, ClienteHTTP, Resposta, id_processo, sem_credencial  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "sei"
ARSX = replace(MODELO, uf="XX", orgao="ARSX", url_pesquisa="https://sei.arsx.exemplo.gov.br/sei/modulos/pesquisa/")
# o aluno que só ajustou rótulos e cabeçalhos, sem as regras de andamento do seu Estado
ARSX_SEM_REGRAS = replace(ARSX, regras_andamento=RJ.regras_andamento)


def _pagina(nome, perfil=RJ):
    return analisar_pagina((FIX / nome).read_bytes(), perfil)


def _gravar(tmp_path, paginas, acrescentar=False):
    res = [coletar.tabelas(p) for p in paginas]
    coletar.gravar(res, tmp_path / "dump", tmp_path / "coleta", acrescentar=acrescentar)
    return validar_coleta.carregar_dump(tmp_path / "dump")


# ================================================================== parse da pesquisa pública (RJ)

def test_autuacao_rj():
    p = _pagina("rj_processo.html")
    a = p["autuacao"]
    assert a["numero"] == "SEI-999001/000123/2024"
    assert a["tipo"] == "Agenersa: Saneamento"
    assert a["data_geracao"] == "2024-02-05"
    assert a["interessado"] == "Empresa Fictícia de Saneamento S.A.; Associação Exemplo de Usuários"
    assert not p["processo_restrito"] and p["avisos"] == []


def test_protocolos_rj_link_restricao_e_processo_relacionado():
    prot = {d["numero"]: d for d in _pagina("rj_processo.html")["protocolos"]}
    assert len(prot) == 6
    of = prot["1000001"]
    assert (of["tipo"], of["data"], of["data_inclusao"], of["unidade"]) == \
        ("Ofício 15", "2024-02-05", "2024-02-05", "AGENERSA/SCEXEC")
    assert of["link"] == ("https://sei.rj.gov.br/sei/modulos/pesquisa/md_pesq_documento_consulta_externa.php"
                          "?eSEI_doc=AAA111&id=1000001")
    assert not of["restrito"]
    par = prot["1000003"]
    assert par["restrito"] and par["link"] is None and "Informação Pessoal" in par["motivo_restricao"]
    rel = prot["SEI-999001/000999/2023"]  # protocolo que é outro processo: sem link de documento, não restrito
    assert rel["link"] is None and not rel["restrito"]


def test_andamentos_rj_datas_e_frases():
    ands = _pagina("rj_processo.html")["andamentos"]
    assert len(ands) == 12
    assert ands[-1] == dict(data_hora="2024-02-05 09:12:00", unidade="AGENERSA/SCEXEC",
                            descricao="Processo público gerado", descricao_original="Processo público gerado",
                            regra=None)
    eventos = [comum.tipo_andamento(a["descricao"])[0] for a in ands]
    assert eventos.count("remetido") == 3 and eventos.count("recebido") == 3
    assert {"conclusao", "reabertura", "gerado", "acesso_externo", "anexacao"} <= set(eventos)


def test_pagina_em_iso_8859_1():
    """O SEI costuma servir ISO-8859-1: os bytes são decodificados pelo charset do <meta>."""
    txt = (FIX / "rj_processo.html").read_text(encoding="utf-8").replace("charset=utf-8", "charset=iso-8859-1")
    p = analisar_pagina(txt.encode("latin-1"), RJ)
    assert p["autuacao"]["interessado"].startswith("Empresa Fictícia")
    assert any(d["tipo"] == "Relatório de Fiscalização 3" for d in p["protocolos"])
    assert any(a["descricao"] == "Conclusão do processo na unidade" for a in p["andamentos"])


def test_processo_restrito_registra_tudo_sem_link():
    p = _pagina("rj_processo_restrito.html")
    assert p["processo_restrito"]
    assert all(d["restrito"] and d["link"] is None for d in p["protocolos"])
    assert p["protocolos"][0]["motivo_restricao"] == "Acesso restrito no nível do processo"
    # "Processo restrito gerado" é andamento de geração, não sinal de página restrita
    assert comum.tipo_andamento(p["andamentos"][-1]["descricao"])[0] == "gerado"


def test_pagina_que_nao_e_processo():
    with pytest.raises(PaginaInvalida, match="captcha"):
        analisar_pagina(b"<html><body><p>Digite o captcha</p></body></html>", RJ)
    with pytest.raises(PaginaInvalida, match="número do processo"):
        analisar_pagina(b"<html><body><p>Erro interno</p></body></html>", RJ)


def test_colunas_pelo_cabecalho_nao_pela_posicao():
    cab = ["", "Unidade", "Data de Inclusão", "Tipo", "Data", "Processo / Documento"]
    m = mapear_colunas(cab, RJ.colunas_protocolos)
    assert m == {"numero": 5, "tipo": 3, "data": 4, "data_inclusao": 2, "unidade": 1}


# ================================================================== outro Estado

def test_outro_estado_rotulos_cabecalhos_e_formato_de_data():
    p = _pagina("outro_estado_processo.html", ARSX)
    a = p["autuacao"]
    assert (a["numero"], a["tipo"], a["data_geracao"]) == \
        ("ARSX.2024.00000077-1", "Fiscalização: Distribuição de Gás", "2024-03-12")
    prot = {d["numero"]: d for d in p["protocolos"]}
    assert prot["2000002"]["data_inclusao"] == "2024-04-03"
    assert prot["2000001"]["unidade"] == "ARSX/DIFIS"  # prefixo do órgão completado
    assert prot["2000002"]["link"].startswith("https://sei.arsx.exemplo.gov.br/sei/modulos/pesquisa/")
    assert p["andamentos"][0]["data_hora"] == "2024-04-22 15:00:00"  # "22/04/2024 às 15:00"


def test_outro_estado_normaliza_andamentos_e_guarda_original():
    ands = _pagina("outro_estado_processo.html", ARSX)["andamentos"]
    remessa = ands[2]
    assert remessa["descricao_original"] == "Processo enviado pela unidade PROTOCOLO"
    assert remessa["descricao"] == "Processo remetido pela unidade ARSX/PROTOCOLO"
    assert comum.tipo_andamento(remessa["descricao"]) == ("remetido", "ARSX/PROTOCOLO")
    assert [comum.tipo_andamento(a["descricao"])[0] for a in ands] == \
        ["conclusao", "recebido", "remetido", "reabertura", "conclusao", "recebido", "remetido", "gerado"]


def test_sem_regras_locais_as_frases_nao_sao_reconhecidas():
    ands = _pagina("outro_estado_processo.html", ARSX_SEM_REGRAS)["andamentos"]
    assert all(comum.tipo_andamento(a["descricao"])[0] == "outro" for a in ands)


@pytest.mark.parametrize("nome", sorted(PERFIS))
def test_exemplo_de_cada_regra_e_reconhecido_pelo_pipeline(nome):
    perfil = PERFIS[nome]
    for r in perfil.regras_andamento:
        assert r.exemplo, f"regra sem exemplo: {r.padrao}"
        canon, evento = perfil.normalizar_andamento(r.exemplo)
        assert evento == r.evento
        tipo, origem = comum.tipo_andamento(canon)
        assert tipo == r.evento, f"{nome}: '{r.exemplo}' → '{canon}' virou '{tipo}'"
        if tipo == "remetido":
            assert origem.startswith(perfil.orgao + "/") or "/" in r.exemplo


def test_regra_com_grupo_inexistente_avisa():
    p = replace(RJ, regras_andamento=(RegraAndamento("recebido", r"^Chegou", "Processo recebido {setor}", "Chegou"),))
    with pytest.raises(ValueError, match="grupo"):
        p.normalizar_andamento("Chegou")


def test_perfil_em_json(tmp_path):
    d = json.loads(json.dumps(ARSX.para_json()))
    p = perfil_de_dict(d)
    assert p == ARSX
    with pytest.raises(ValueError, match="desconhecidos"):
        perfil_de_dict(dict(d, campo_inventado=1))


# ================================================================== TSVs canônicas

def test_tsv_tem_o_esquema_e_e_lida_por_comum_carregar(tmp_path):
    p, a, d = _gravar(tmp_path, [_pagina("rj_processo.html"), _pagina("rj_processo_restrito.html")])
    for nome, cols in COLUNAS.items():
        assert (tmp_path / "dump" / nome).read_text(encoding="utf-8").split("\n")[0].split("\t") == cols
    assert list(p.columns) == COLUNAS["processos.tsv"]
    assert len(p) == 2 and len(a) == 15 and len(d) == 8
    for col, df in (("data_geracao", p), ("data_ultimo_andamento", p), ("data_hora", a), ("data", d),
                    ("data_inclusao", d)):
        assert pd.api.types.is_datetime64_any_dtype(df[col]), col
    proc = p.set_index("numero").loc["SEI-999001/000123/2024"]
    assert proc.id == id_processo("SEI-999001/000123/2024") == id_processo(" sei-999001/000123/2024 ")
    assert proc.ultima_unidade == "AGENERSA/SCEXEC"
    assert proc.data_ultimo_andamento == pd.Timestamp("2024-03-25 17:40")
    assert p.assunto.isna().all() and p.status.isna().all()  # campos internos do gabinete: NULL
    assert set(d.processo_id) <= set(p.id) and set(a.processo_id) <= set(p.id)
    assert (d.numero == "SEI-999001/000999/2023").sum() == 1
    assert comum.categoria_documento("Processo", "SEI-999001/000999/2023")[0] == "processo_relacionado"


def test_tsv_escapa_tabulacao_e_quebra_de_linha(tmp_path):
    pag = _pagina("rj_processo.html")
    pag["autuacao"]["tipo"] = "Tipo\tcom tab"
    pag["andamentos"][0]["descricao"] = "linha 1\nlinha 2"
    p, a, _ = _gravar(tmp_path, [pag])
    assert p.tipo.iloc[0] == "Tipo com tab"
    assert len(a) == 12  # a quebra não parte a linha da TSV
    # convenção do dump original: quebra gravada como "\n" literal (barra + n); comum.carregar mantém assim
    assert "linha 1\\nlinha 2" in set(a.descricao)


def test_trilha_do_pipeline_monta_estadias(tmp_path):
    """As TSVs do coletor alimentam a reconstrução de estadias de scripts/trilhas.py sem adaptação."""
    import trilhas
    _, a, _ = _gravar(tmp_path, [_pagina("rj_processo.html")])
    est = trilhas.montar_estadias(a, a.data_hora.max())
    seq = [(e["unidade"], e["motivo_entrada"], e["motivo_saida"]) for e in est]
    assert seq[:4] == [("AGENERSA/SCEXEC", "geracao", "remessa"), ("AGENERSA/CASAN", "remessa", "remessa"),
                       ("AGENERSA/PROC", "remessa", "remessa"), ("AGENERSA/SCEXEC", "remessa", "conclusao")]
    assert seq[4] == ("AGENERSA/SCEXEC", "reabertura", "conclusao")


def test_acrescentar_mantem_outros_processos_e_substitui_o_mesmo(tmp_path):
    _gravar(tmp_path, [_pagina("rj_processo.html")])
    p, a, _ = _gravar(tmp_path, [_pagina("rj_processo_restrito.html")], acrescentar=True)
    assert len(p) == 2
    p, a, _ = _gravar(tmp_path, [_pagina("rj_processo_restrito.html")], acrescentar=True)
    assert len(p) == 2 and len(a) == 15  # mesmo processo de novo: substitui, não duplica
    p, _, _ = _gravar(tmp_path, [_pagina("rj_processo_restrito.html")])
    assert len(p) == 1  # sem --acrescentar a coleta é a fotografia desta execução


def test_html_salvo_a_mao_pela_linha_de_comando(tmp_path):
    coletar.main(["--perfil", "RJ", "--sem-rede", "--html-salvo", str(FIX / "salvo_a_mao"),
                  "--destino", str(tmp_path / "dump"), "--trabalho", str(tmp_path / "coleta")])
    p, a, d = validar_coleta.carregar_dump(tmp_path / "dump")
    assert list(p.numero) == ["SEI-999001/000789/2024"]
    assert a.data_hora.iloc[0] == pd.Timestamp("2024-05-02 10:15")  # &nbsp; entre data e hora
    assert a.descricao.iloc[0] == "Processo público gerado"  # espaços e quebra normalizados
    ind = pd.read_csv(tmp_path / "coleta" / "indice_documentos.csv", dtype=str)
    assert ind.link.iloc[0].startswith("https://sei.rj.gov.br/sei/modulos/pesquisa/md_pesq_documento_consulta")
    orig = pd.read_csv(tmp_path / "coleta" / "andamentos_original.csv", dtype=str)
    assert "descricao_original" in orig.columns
    fontes = pd.read_csv(tmp_path / "coleta" / "fontes.csv", dtype=str)
    assert fontes.origem.iloc[0] == "arquivo:processo_salvo.html"


def test_numero_sem_url_nao_e_buscado(tmp_path):
    assert coletar.resolver_url("SEI-999001/000123/2024", RJ, {}) is None  # busca por número tem captcha
    assert coletar.resolver_url("X", RJ, {"X": "https://a/b"}) == "https://a/b"
    p = replace(RJ, modelo_url_processo="https://sei.exemplo/pesq?n={numero}")
    assert coletar.resolver_url("123", p, {}) == "https://sei.exemplo/pesq?n=123"


# ================================================================== HTTP educado

class _Sessao:
    def __init__(self, respostas):
        self.respostas, self.headers, self.proxies, self.chamadas = list(respostas), {}, {}, 0

    def get(self, url, timeout):
        self.chamadas += 1
        r = self.respostas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


class _R:
    def __init__(self, status, conteudo=b"ok", headers=None):
        self.status_code, self.content, self.headers, self.url = status, conteudo, headers or {}, "u"


def test_cliente_tenta_de_novo_so_em_erro_temporario():
    s = _Sessao([_R(503), _R(429, headers={"Retry-After": "0"}), _R(200, b"<html/>", {"Content-Type": "text/html"})])
    c = ClienteHTTP(intervalo=0, espera_base=0, tentativas=3, sessao=s, contato="aluno@exemplo.edu")
    r = c.obter("https://sei.exemplo/x")
    assert r.conteudo == b"<html/>" and s.chamadas == 3
    assert "processos-sei-regulacao-coletor" in s.headers["User-Agent"] and "aluno@exemplo.edu" in s.headers[
        "User-Agent"]
    s = _Sessao([_R(404), _R(200)])
    with pytest.raises(RuntimeError, match="404"):
        ClienteHTTP(intervalo=0, espera_base=0, sessao=s).obter("u")
    assert s.chamadas == 1  # 404 não é repetido


def test_cache_da_pagina_nao_baixa_de_novo(tmp_path):
    s = _Sessao([_R(200, (FIX / "rj_processo.html").read_bytes())])
    c = ClienteHTTP(intervalo=0, espera_base=0, sessao=s)
    url = "https://sei.rj.gov.br/sei/modulos/pesquisa/md_pesq_processo_exibir.php?IJ=sintetico"
    a1 = coletar.baixar_pagina(url, c, tmp_path, atualizar=False)
    a2 = coletar.baixar_pagina(url, c, tmp_path, atualizar=False)
    assert a1 == a2 and s.chamadas == 1
    assert coletar.processar_arquivo(a1, RJ, url, url)["processo"]["numero"] == "SEI-999001/000123/2024"


def test_credencial_do_proxy_nunca_aparece(monkeypatch, capsys):
    assert sem_credencial("ProxyError http://usuario:senha123@p.exemplo:80/") == "ProxyError http://***@p.exemplo:80/"
    monkeypatch.setenv("COLETA_PROXY", "http://usuario:senha123@p.exemplo:80")
    import requests
    s = _Sessao([requests.ConnectionError("falhou via http://usuario:senha123@p.exemplo:80")] * 2)
    c = ClienteHTTP(intervalo=0, espera_base=0, tentativas=1, sessao=s)
    with pytest.raises(RuntimeError) as e:
        c.obter("https://sei.exemplo/x")
    assert "senha123" not in str(e.value) and c.usa_proxy


# ================================================================== documentos

def _pdf(texto: str | None) -> bytes:
    """PDF mínimo de 1 página: com camada de texto (Helvetica) ou só com um traço (como um escaneado)."""
    conteudo = (f"BT /F1 12 Tf 72 720 Td ({texto}) Tj ET" if texto else "0 0 m 200 200 l S").encode()
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
            b"/Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n" % len(conteudo) + conteudo + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, pos = bytearray(b"%PDF-1.4\n"), []
    for i, o in enumerate(objs, 1):
        pos.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % p for p in pos)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)


class _Servidor:
    """Cliente HTTP falso: devolve um arquivo por id do documento no link e conta os pedidos."""

    def __init__(self, arquivos: dict):
        self.arquivos, self.pedidos = arquivos, []

    def obter(self, url):
        sid = re.search(r"id=(\d+)", url).group(1)
        self.pedidos.append(sid)
        if sid not in self.arquivos:
            raise RuntimeError("falha ao baixar (HTTP 500)")
        conteudo, ct = self.arquivos[sid]
        return Resposta(conteudo, ct, 200, url)


def _indice(tmp_path):
    res = [coletar.tabelas(_pagina("rj_processo.html")), coletar.tabelas(_pagina("rj_processo_restrito.html"))]
    coletar.gravar(res, tmp_path / "dump", tmp_path / "coleta")
    return documentos.ler_indice(tmp_path / "coleta" / "indice_documentos.csv")


ARQUIVOS = {
    "1000001": ((FIX / "documentos" / "documento_sei.html").read_bytes(), "text/html; charset=utf-8"),
    "1000002": (_pdf("Relatorio de Fiscalizacao 3 de 2024: vazamento constatado na rede"), "application/pdf"),
    "1000004": (_pdf(None), "application/octet-stream"),  # PDF escaneado (sem camada de texto)
    "1000005": (b"\xff\xd8\xff\xe0JFIF", "image/jpeg"),
}


def test_documentos_texto_pdf_restricao_e_esquema(tmp_path):
    srv = _Servidor(ARQUIVOS)
    docs, textos = documentos.coletar_documentos(_indice(tmp_path), RJ, srv, cache=tmp_path / "bruto")
    st = {d["sei_doc_id"]: d["download_status"] for d in docs}
    assert st == {"1000001": "ok", "1000002": "ok", "1000003": "restricted", "1000004": "sem_texto",
                  "1000005": "sem_texto", "3000001": "restricted", "3000002": "restricted"}
    assert "1000003" not in srv.pedidos and "3000001" not in srv.pedidos  # restrito: nunca se tenta baixar
    texto = {t["sei_doc_id"]: t["texto"] for t in textos}
    assert "10 (dez) dias úteis" in texto["1000001"] and "vazamento constatado" in texto["1000002"]
    r = documentos.gravar(docs, textos, tmp_path / "relator", sorted({d["processo"] for d in docs}))
    assert r["com_texto"] == 2
    dp = pd.read_parquet(tmp_path / "relator" / "documentos.parquet")
    assert list(dp.columns) == documentos.COLUNAS_DOCUMENTOS
    assert dp.n_chars.dtype == "int64" and dp.restrito.dtype == bool
    linha = dp.set_index("sei_doc_id").loc["1000002"]
    assert (linha.data, linha.data_inclusao, linha.mime) == ("14/02/2024", "15/02/2024", "application/pdf")
    assert dp.set_index("sei_doc_id").loc["1000004"].mime == "application/pdf"  # tipo pelo conteúdo
    tp = pd.read_parquet(tmp_path / "relator" / "doc_text_piloto.parquet")
    assert list(tp.columns) == ["processo", "sei_doc_id", "texto"]
    cob = pd.read_csv(tmp_path / "relator" / "cobertura_texto.csv").set_index("processo")
    assert list(cob.columns) == ["pecas", "com_texto", "restritas", "substantivas", "cobertura_substantivas"]
    # substantivas do processo: relatório de fiscalização (com texto) e parecer (restrito) → 50%
    assert cob.loc["SEI-999001/000123/2024"].tolist() == [5, 2, 1, 2, 0.5]
    assert cob.loc["SEI-999001/000456/2024"].restritas == 2


def test_documentos_cache_pasta_salva_e_sem_rede(tmp_path):
    ind = _indice(tmp_path)
    srv = _Servidor(ARQUIVOS)
    documentos.coletar_documentos(ind, RJ, srv, cache=tmp_path / "bruto")
    n = len(srv.pedidos)
    docs, _ = documentos.coletar_documentos(ind, RJ, srv, cache=tmp_path / "bruto")
    assert len(srv.pedidos) == n  # segunda passada vem do cache
    salvos = tmp_path / "salvos"
    salvos.mkdir()
    (salvos / "1000001.html").write_bytes(ARQUIVOS["1000001"][0])
    docs, textos = documentos.coletar_documentos(ind, RJ, None, cache=tmp_path / "vazio", pasta_docs=salvos)
    st = {d["sei_doc_id"]: d["download_status"] for d in docs}
    assert st["1000001"] == "ok" and st["1000002"] == "pending"  # sem rede e fora da pasta: fica pendente


def test_documentos_pagina_restrita_falha_e_captcha(tmp_path):
    ind = _indice(tmp_path)
    arq = dict(ARQUIVOS)
    arq["1000001"] = ((FIX / "documentos" / "documento_restrito.html").read_bytes(), "text/html")
    del arq["1000002"]  # erro do servidor
    docs, _ = documentos.coletar_documentos(ind, RJ, _Servidor(arq), cache=tmp_path / "b1")
    st = {d["sei_doc_id"]: d for d in docs}
    assert st["1000001"]["download_status"] == "restricted" and st["1000001"]["restrito"]
    assert st["1000002"]["download_status"] == "failed"
    arq["1000001"] = (b"<html><body>Confirme o captcha para continuar</body></html>", "text/html")
    srv = _Servidor(arq)
    docs, _ = documentos.coletar_documentos(ind, RJ, srv, cache=tmp_path / "b2")
    assert srv.pedidos == ["1000001"]  # parou no primeiro bloqueio
    assert {d["download_status"] for d in docs if d["sei_doc_id"] != "1000003"} <= {"pending", "restricted"}


def test_documentos_so_baixa_os_processos_alvo(tmp_path):
    srv = _Servidor(ARQUIVOS)
    docs, _ = documentos.coletar_documentos(_indice(tmp_path), RJ, srv, cache=tmp_path / "b", alvo={"outro"})
    assert srv.pedidos == [] and {d["download_status"] for d in docs} == {"pending", "restricted"}


def test_substantivas_igual_a_do_pipeline():
    arv = ast.parse((RAIZ / "scripts" / "selecionar_piloto.py").read_text(encoding="utf-8"))
    valor = next(n.value for n in arv.body if isinstance(n, ast.Assign)
                 and any(getattr(t, "id", "") == "SUBSTANTIVAS" for t in n.targets))
    assert ast.literal_eval(valor) == documentos.SUBSTANTIVAS


def test_colunas_de_documentos_iguais_as_do_banco_do_relator():
    src = (RAIZ / "scripts" / "exportar_relator.py").read_text(encoding="utf-8")
    sel = re.search(r"SELECT (.*?)\s+FROM documentos", src, re.S).group(1)
    assert [c.strip() for c in sel.split(",")] == documentos.COLUNAS_DOCUMENTOS


# ================================================================== análise por LLM (provedor falso)

def _resposta_valida(**kw):
    x = dict(instrumento="Ofício nº 15/2024", ator_orgao="SCEXEC", papel_no_processo="oficio",
             acao_processual="solicitou", data="2024-02-05", data_por_extenso="05 de fevereiro de 2024",
             resumo_dos_fatos_relevantes="Solicita manifestação em 10 dias úteis.",
             resumo_detalhado="O ofício solicita manifestação.", pontos_chave=["Prazo de 10 dias úteis."],
             pedidos_e_determinacoes=["Solicita à concessionária manifestação."],
             prazos_e_eventos=[{"evento": "manifestação", "data": "10 dias úteis"}],
             dispositivos_citados=["Cláusula décima do contrato de concessão"], citacoes_verbatim=[],
             numeros_substantivos=[{"rotulo": "prazo", "valor": "10 dias úteis"}],
             entidades={"clausulas_contratuais": ["Cláusula décima"],
                        "documentos_referenciados": ["Relatório de Fiscalização nº 3/2024"]},
             tier_relevancia=1, relevancia_para_relatorio=0.8, requer_revisao=False, confianca=0.9)
    x.update(kw)
    return x


def _docs_e_textos(tmp_path):
    docs, textos = documentos.coletar_documentos(_indice(tmp_path), RJ, _Servidor(ARQUIVOS), cache=tmp_path / "b")
    return docs, {(t["processo"], t["sei_doc_id"]): t["texto"] for t in textos}


def test_extracao_formato_cache_e_stubs(tmp_path):
    docs, textos = _docs_e_textos(tmp_path)
    chamadas = []

    def falso(modelo, usuario, esforco):
        chamadas.append(usuario)
        return _resposta_valida(data=None), {"input_tokens": 1}

    linhas, erros = extrair.extrair_todos(docs, textos, "anthropic", "claude-haiku-5-5", cache=tmp_path / "ext",
                                          chamar=falso, workers=2)
    assert erros == [] and len(chamadas) == 2 and len(linhas) == len(docs)
    assert "=== TEXTO DO DOCUMENTO ===" in chamadas[0]
    por = {r["sei_doc_id"]: r for r in linhas}
    assert {r["prompt_version"] for r in linhas} == {extrair.PROMPT_VERSION}
    assert por["1000003"]["model_id"] == "stub" and por["1000004"]["model_id"] == "stub"
    x = json.loads(por["1000001"]["extraction_json"])
    assert por["1000001"]["model_id"] == "claude-haiku-5-5"
    # campos que os scripts leem
    for k in ("data", "pedidos_e_determinacoes", "acao_processual", "dispositivos_citados",
              "resumo_dos_fatos_relevantes", "resumo_detalhado", "entidades"):
        assert k in x
    assert x["entidades"]["documentos_referenciados"] and x["sei_doc_id"] == "1000001"
    assert x["data"] == "2024-02-05"  # sem data no texto: cai na data da lista
    import trilhas
    assert trilhas.data_da_peca(x["data"]) == pd.Timestamp("2024-02-05")
    stub = json.loads(por["1000003"]["extraction_json"])
    assert stub["resumo_dos_fatos_relevantes"] == "Documento de acesso restrito." and stub["tier_relevancia"] == 0
    assert set(stub) == set(x)  # stub e análise têm os mesmos campos
    extrair.extrair_todos(docs, textos, "anthropic", "claude-haiku-5-5", cache=tmp_path / "ext", chamar=falso)
    assert len(chamadas) == 2  # cache por documento
    extrair.extrair_todos(docs, textos, "anthropic", "outro-modelo", cache=tmp_path / "ext", chamar=falso)
    assert len(chamadas) == 4  # outro modelo: analisa de novo
    sem, _ = extrair.extrair_todos(docs, textos, "anthropic", "modelo-novo", cache=tmp_path / "ext", chamar=falso,
                                   usar_llm=False)
    assert all(r["model_id"] == "stub" for r in sem)  # --sem-llm: só stubs e cache


def test_extracao_fora_do_esquema_vira_erro(tmp_path):
    docs, textos = _docs_e_textos(tmp_path)
    n = []

    def ruim(modelo, usuario, esforco):
        n.append(1)
        return _resposta_valida(data="05/02/2024", tier_relevancia=7), {}

    linhas, erros = extrair.extrair_todos(docs, textos, "anthropic", "m", cache=tmp_path / "ext", chamar=ruim)
    assert len(erros) == 2 and len(n) == 4  # 2 documentos × 2 tentativas
    assert all(r["model_id"] == "stub" for r in linhas)
    assert not list((tmp_path / "ext").rglob("*.json"))  # resposta inválida não entra no cache


def test_validar_extracao():
    assert extrair.validar_extracao(_resposta_valida()) == []
    p = extrair.validar_extracao(_resposta_valida(relevancia_para_relatorio=3, pontos_chave="x", extra=1))
    assert any("relevancia" in x for x in p) and any("pontos_chave" in x for x in p) and any("extra" in x for x in p)
    sem = _resposta_valida()
    del sem["entidades"]
    assert "falta 'entidades'" in extrair.validar_extracao(sem)
    assert extrair.ESQUEMA["required"] == list(extrair.ESQUEMA["properties"])


# ================================================================== portão de qualidade

def test_validador_aprova_coleta_rj(tmp_path):
    _gravar(tmp_path, [_pagina("rj_processo.html"), _pagina("rj_processo_restrito.html")])
    ch = {c.nome: c for c in validar_coleta.validar(tmp_path / "dump", None, RJ, {"min_andamentos_essenciais": 1})}
    assert all(c.ok for c in ch.values()), [(c.nome, c.valor, c.detalhe) for c in ch.values() if not c.ok]
    assert ch["andamentos_nao_reconhecidos"].valor == 0.0
    assert "gerado=2" in ch["eventos_essenciais"].valor


def test_validador_aponta_perfil_sem_regras_de_andamento(tmp_path):
    _gravar(tmp_path, [_pagina("outro_estado_processo.html", ARSX_SEM_REGRAS)])
    ch = {c.nome: c for c in validar_coleta.validar(tmp_path / "dump", None, ARSX_SEM_REGRAS,
                                                    {"min_andamentos_essenciais": 1})}
    assert not ch["andamentos_nao_reconhecidos"].ok and ch["andamentos_nao_reconhecidos"].valor == 1.0
    assert any("Processo enviado pela unidade <UNIDADE>" in x or "Processo enviado pela unidade" in x
               for x in ch["andamentos_nao_reconhecidos"].detalhe)
    assert not ch["eventos_essenciais"].ok
    # com as regras do Estado, a mesma página passa
    _gravar(tmp_path, [_pagina("outro_estado_processo.html", ARSX)])
    assert all(c.ok for c in validar_coleta.validar(tmp_path / "dump", None, ARSX, {"min_andamentos_essenciais": 1}))


def test_validador_datas_unidades_e_cobertura(tmp_path):
    pag = _pagina("rj_processo.html")
    pag["andamentos"][0]["data_hora"] = None
    pag["andamentos"][1]["data_hora"] = "2023-01-01 10:00:00"  # antes da geração
    pag["andamentos"][2]["unidade"] = "SCEXEC"  # sem prefixo
    for d in pag["protocolos"][:2]:
        d["unidade"] = None
    _gravar(tmp_path, [pag])
    rel = tmp_path / "relator"
    rel.mkdir()
    pd.DataFrame(dict(processo=["SEI-999001/000123/2024"], pecas=[5], com_texto=[0], restritas=[1],
                      substantivas=[2], cobertura_substantivas=[0.0])).to_csv(rel / "cobertura_texto.csv", index=False)
    ch = {c.nome: c for c in validar_coleta.validar(tmp_path / "dump", rel, RJ, {"min_andamentos_essenciais": 1})}
    assert not ch["datas_fora_de_ordem"].ok
    assert not ch["unidades_sem_prefixo"].ok and "SCEXEC (1)" in ch["unidades_sem_prefixo"].detalhe
    assert not ch["documentos_sem_unidade"].ok
    assert not ch["cobertura_texto"].ok


def test_validador_esquema_e_codigo_de_saida(tmp_path, capsys):
    (tmp_path / "vazio").mkdir()
    ch = validar_coleta.validar(tmp_path / "vazio", None, RJ)
    assert len(ch) == 1 and ch[0].nome == "esquema" and not ch[0].ok
    with pytest.raises(SystemExit) as e:
        validar_coleta.main(["--perfil", "RJ", "--destino", str(tmp_path / "vazio"), "--relator", str(tmp_path)])
    assert e.value.code == 1
    _gravar(tmp_path, [_pagina("rj_processo.html")])
    validar_coleta.main(["--perfil", "RJ", "--destino", str(tmp_path / "dump"), "--relator", str(tmp_path / "nada"),
                         "--min-andamentos-essenciais", "1", "--json", str(tmp_path / "v.json")])
    assert "aprovado" in capsys.readouterr().out
    assert json.loads((tmp_path / "v.json").read_text(encoding="utf-8"))[0]["nome"] == "esquema"
