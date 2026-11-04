"""Parser da página de processo da Pesquisa Pública do SEI (md_pesq_processo_exibir.php).

Porte para Python do parser de referência do sistema SEI 2 (TypeScript/cheerio), com o que muda entre instalações
lido do perfil: rótulos da autuação, títulos e cabeçalhos das tabelas de protocolos e andamentos, formato de data,
padrão do link de documento e sinais de restrição.

Como acha as tabelas: pelo título (caption, atributo `summary` ou cabeçalho h1–h4 anterior) e, se não houver título
conhecido, pelos cabeçalhos das colunas. As colunas são localizadas pelo cabeçalho, nunca pela posição, porque a
ordem e a coluna de seleção (checkbox) variam entre versões do SEI."""
from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from coleta.perfil_sei import PerfilSEI
from coleta.util import chave, limpar


class PaginaInvalida(ValueError):
    """A página não é um processo da Pesquisa Pública (erro, captcha, página de busca...)."""


def sopa(html: bytes | str) -> BeautifulSoup:
    # bytes: o BeautifulSoup lê o charset do <meta> (o SEI costuma servir ISO-8859-1)
    return BeautifulSoup(html, "lxml")


# ------------------------------------------------------------------------------------------------ datas
def data_iso(texto: str, formatos) -> str | None:
    t = limpar(texto)
    for f in formatos:
        try:
            return datetime.strptime(t, f).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def data_hora_iso(texto: str, formatos) -> str | None:
    t = limpar(texto)
    for f in formatos:
        try:
            return datetime.strptime(t, f).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return None


# ------------------------------------------------------------------------------------------------ tabelas
def _linhas(tabela) -> list:
    """Linhas da própria tabela (ignora as de tabelas aninhadas)."""
    return [tr for tr in tabela.find_all("tr") if tr.find_parent("table") is tabela]


def _celulas(tr) -> list:
    return tr.find_all(["td", "th"], recursive=False)


def _titulo(tabela) -> str:
    partes = [tabela.get("summary", "")]
    cap = tabela.find("caption")
    if cap:
        partes.append(cap.get_text(" "))
    ant = tabela.find_previous(["h1", "h2", "h3", "h4", "caption"])
    if ant and ant.find_parent("table") is not tabela:
        partes.append(ant.get_text(" "))
    return " | ".join(chave(p) for p in partes if p)


def mapear_colunas(cabecalho: list[str], colunas: dict) -> dict:
    """Índice de cada coluna canônica: 1ª passada por igualdade, 2ª por 'contém'; cada índice usado uma vez."""
    cab = [chave(c) for c in cabecalho]
    usados, out = set(), {}
    for modo in ("exato", "contem"):
        for campo, rotulos in colunas.items():
            if campo in out:
                continue
            for r in rotulos:
                rk = chave(r)
                achou = [i for i, c in enumerate(cab) if i not in usados and c
                         and (c == rk if modo == "exato" else rk in c)]
                if achou:
                    out[campo] = achou[0]
                    usados.add(achou[0])
                    break
    return out


def _achar_tabela(s: BeautifulSoup, titulos, colunas: dict, obrigatorias: tuple):
    """(tabela, linha de cabeçalho, mapa de colunas) da primeira tabela que tem as colunas obrigatórias,
    preferindo as que têm um dos títulos esperados."""
    titulos_k = [chave(t) for t in titulos]
    candidatas = []
    for tb in s.find_all("table"):
        linhas = _linhas(tb)
        if not linhas:
            continue
        cab = next((tr for tr in linhas if tr.find("th", recursive=False)), linhas[0])
        mapa = mapear_colunas([c.get_text(" ") for c in _celulas(cab)], colunas)
        if not all(c in mapa for c in obrigatorias):
            continue
        tit = _titulo(tb)
        prioridade = next((i for i, t in enumerate(titulos_k) if t and t in tit), len(titulos_k))
        candidatas.append((prioridade, tb, cab, mapa))
    if not candidatas:
        return None, None, {}
    candidatas.sort(key=lambda x: x[0])
    return candidatas[0][1:]


# ------------------------------------------------------------------------------------------------ autuação
def _valor_rotulo(s: BeautifulSoup, rotulos: list[str]) -> str:
    """Texto da célula ao lado do primeiro rótulo encontrado. Várias linhas (<br>) viram '; '."""
    celulas = s.find_all(["td", "th", "dt", "label", "span", "b", "strong"])
    for r in rotulos:
        rk = chave(r)
        for c in celulas:
            if chave(c.get_text(" ")) != rk:
                continue
            viz = c.find_next_sibling(["td", "dd", "span", "div"])
            if viz is None and c.parent is not None and c.parent.name in ("td", "th"):  # <td><b>Tipo:</b></td><td>..
                viz = c.parent.find_next_sibling(["td", "dd"])
            if viz is not None:
                linhas = [limpar(x) for x in viz.get_text("\n").split("\n")]
                v = "; ".join(x for x in linhas if x)
                if v:
                    return v
    return ""


# ------------------------------------------------------------------------------------------------ página
def _link_documento(tr, celula, rx: re.Pattern, base: str) -> str | None:
    for escopo in (celula, tr):
        if escopo is None:
            continue
        for a in escopo.find_all("a"):
            m = rx.search(f"{a.get('href') or ''} {a.get('onclick') or ''}")
            if m:
                return urljoin(base, m.group(0).replace("&amp;", "&"))
    return None


def _restricao(tr, rx: re.Pattern) -> str | None:
    """Motivo declarado (title/alt) se a linha traz sinal de documento restrito ou sigiloso."""
    for el in tr.find_all(True):
        for attr in ("title", "alt", "aria-label"):
            v = limpar(el.get(attr))
            if v and rx.search(v):
                return v
    return "Documento restrito (sinal na lista de protocolos)" if rx.search(limpar(tr.get_text(" "))) else None


def analisar_pagina(html: bytes | str, perfil: PerfilSEI, url: str | None = None) -> dict:
    """Autuação, protocolos e andamentos de uma página de processo.

    Retorna {autuacao: {numero, tipo, data_geracao, interessado}, processo_restrito, protocolos: [...],
    andamentos: [...], avisos: [...]}. Datas em ISO; descrições de andamento já normalizadas para a frase canônica
    (a original fica em `descricao_original`)."""
    s = sopa(html)
    for el in s(["script", "style", "noscript"]):
        el.decompose()  # o texto de scripts não é conteúdo (e pode citar "captcha" do formulário de busca)
    texto = limpar(s.get_text(" "))
    if re.search(perfil.marca_bloqueio, texto, re.I) and not _valor_rotulo(s, perfil.rotulos_autuacao["numero"]):
        raise PaginaInvalida("a página pede verificação humana (captcha) ou bloqueou o acesso; o coletor não "
                             "contorna isso — salve a página à mão no navegador e use --html-salvo")
    avisos = []
    rot = perfil.rotulos_autuacao
    aut = dict(numero=_valor_rotulo(s, rot["numero"]), tipo=_valor_rotulo(s, rot["tipo"]),
               interessado=_valor_rotulo(s, rot["interessado"]) or None)
    aut["data_geracao"] = data_iso(_valor_rotulo(s, rot["data_geracao"]), perfil.formatos_data)
    # o número costuma vir como "SEI-220007/001234/2023"; descarta texto extra na mesma célula
    aut["numero"] = aut["numero"].split(";")[0].strip()
    if not aut["numero"]:
        raise PaginaInvalida("número do processo não encontrado: confira os rótulos da autuação no perfil")
    restrito = bool(re.search(perfil.marca_processo_restrito, texto, re.I))
    base = url or perfil.url_pesquisa

    # ---- protocolos
    protocolos = []
    rx_link, rx_restr = re.compile(perfil.padrao_link_documento, re.I), re.compile(perfil.marca_documento_restrito, re.I)
    tb, cab, mapa = _achar_tabela(s, perfil.titulos_protocolos, perfil.colunas_protocolos, ("numero", "tipo"))
    if tb is None:
        avisos.append("tabela de protocolos não encontrada")
    else:
        for tr in _linhas(tb):
            if tr is cab:
                continue
            cs = _celulas(tr)

            def cel(campo):
                i = mapa.get(campo)
                return cs[i] if i is not None and i < len(cs) else None

            def txt(campo):
                c = cel(campo)
                return limpar(c.get_text(" ")) if c is not None else ""

            numero, tipo = txt("numero"), txt("tipo")
            if not numero or not tipo:
                continue
            link = _link_documento(tr, cel("numero"), rx_link, base)
            motivo = _restricao(tr, rx_restr)
            if restrito and not motivo:
                motivo = "Acesso restrito no nível do processo"
            protocolos.append(dict(
                numero=numero, tipo=tipo,
                data=data_iso(txt("data"), perfil.formatos_data),
                data_inclusao=data_iso(txt("data_inclusao"), perfil.formatos_data),
                unidade=perfil.normalizar_unidade(txt("unidade")), link=link,
                restrito=bool(motivo) or (numero.isdigit() and link is None),
                motivo_restricao=motivo or (None if link or not numero.isdigit()
                                            else "Sem link na pesquisa pública (provável acesso restrito)")))

    # ---- andamentos
    andamentos = []
    tb, cab, mapa = _achar_tabela(s, perfil.titulos_andamentos, perfil.colunas_andamentos,
                                  ("data_hora", "unidade", "descricao"))
    if tb is None:
        avisos.append("tabela de andamentos não encontrada")
    else:
        sem_data = 0
        for tr in _linhas(tb):
            if tr is cab:
                continue
            cs = _celulas(tr)
            val = {k: (limpar(cs[i].get_text(" ")) if i < len(cs) else "") for k, i in mapa.items()}
            if not val.get("unidade") and not val.get("descricao"):
                continue
            dh = data_hora_iso(val.get("data_hora", ""), perfil.formatos_data_hora)
            sem_data += dh is None
            desc, regra = perfil.normalizar_andamento(val.get("descricao", ""))
            andamentos.append(dict(data_hora=dh, unidade=perfil.normalizar_unidade(val.get("unidade")),
                                   descricao=desc, descricao_original=val.get("descricao", ""), regra=regra))
        if sem_data:
            avisos.append(f"{sem_data} andamento(s) com data/hora fora dos formatos do perfil")
    return dict(autuacao=aut, processo_restrito=restrito, protocolos=protocolos, andamentos=andamentos,
                avisos=avisos)
