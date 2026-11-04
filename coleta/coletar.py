"""Coleta da trilha dos processos na Pesquisa Pública do SEI → tabelas canônicas em dados/sei2_dump/.

Entradas (podem ser combinadas):
  URLs da pesquisa pública (md_pesq_processo_exibir.php?...), na linha de comando ou em --lista arquivo.txt;
  números de processo, se houver --mapa-urls (CSV numero,url) ou `modelo_url_processo` no perfil — a busca por
  número da pesquisa pública tem captcha, que o coletor NÃO automatiza: copie o link do processo no navegador;
  --html-salvo PASTA: páginas de processo salvas à mão (Ctrl+S no navegador), para quem não tem acesso automatizado.

Cada página baixada fica em dados/bruto/processos/ (cache: não baixa de novo sem --atualizar). Saídas:
  <destino>/processos.tsv, andamentos.tsv, protocolos.tsv, observacoes.tsv  (esquema de scripts/comum.py::carregar)
  dados/coleta/indice_documentos.csv   link público e restrição de cada documento (entrada de coleta/documentos.py)
  dados/coleta/andamentos_original.csv frase original × canônica de cada andamento (auditoria do perfil)
  dados/coleta/fontes.csv              de onde veio cada processo (URL ou arquivo) e quando

Uso:
  python -m coleta.coletar --perfil RJ "https://sei.rj.gov.br/sei/modulos/pesquisa/md_pesq_processo_exibir.php?..."
  python -m coleta.coletar --perfil RJ --lista processos.txt --intervalo 3
  python -m coleta.coletar --perfil meu_estado.json --html-salvo paginas_salvas/
Depois: python -m coleta.validar_coleta --perfil RJ"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import datetime
from pathlib import Path

if __package__ in (None, ""):  # permite `python coleta/coletar.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from coleta.parser import PaginaInvalida, analisar_pagina
from coleta.perfil_sei import PerfilSEI, carregar_perfil
from coleta.util import (BRUTO, DUMP, TRABALHO, ClienteHTTP, escrever_tsv, hash_curto, id_processo, ler_tsv,
                         sem_credencial)

RE_URL = re.compile(r"^https?://", re.I)
COLS_INDICE = ["processo", "processo_id", "sei_doc_id", "tipo", "data", "data_inclusao", "unidade", "link",
               "restrito", "motivo_restricao", "processo_restrito"]
COLS_ORIGINAL = ["processo_id", "processo", "data_hora", "unidade", "descricao_original", "descricao", "regra"]
COLS_FONTES = ["processo", "processo_id", "origem", "arquivo_bruto", "coletado_em", "perfil", "avisos"]


# ------------------------------------------------------------------------------------------------ montagem
def tabelas(pagina: dict) -> dict:
    """Linhas canônicas (processo, andamentos, protocolos) e auxiliares de uma página já analisada."""
    aut = pagina["autuacao"]
    pid = id_processo(aut["numero"])
    ands = pagina["andamentos"]
    datados = [a for a in ands if a["data_hora"]]
    ultimo = max(datados, key=lambda a: a["data_hora"]) if datados else None
    proc = dict(id=pid, numero=aut["numero"], tipo=aut["tipo"] or None, interessado=aut["interessado"],
                data_geracao=aut["data_geracao"], ultima_unidade=ultimo["unidade"] if ultimo else None,
                data_ultimo_andamento=ultimo["data_hora"] if ultimo else None)
    # assunto, tipo_custom, natureza, concessionaria, status: campos do controle interno do gabinete no projeto
    # original; a pesquisa pública não os tem (ficam NULL)
    andamentos = [dict(processo_id=pid, data_hora=a["data_hora"], unidade=a["unidade"], descricao=a["descricao"])
                  for a in ands]
    originais = [dict(processo_id=pid, processo=aut["numero"], data_hora=a["data_hora"], unidade=a["unidade"],
                      descricao_original=a["descricao_original"], descricao=a["descricao"], regra=a["regra"] or "")
                 for a in ands]
    protocolos = [dict(processo_id=pid, numero=d["numero"], tipo=d["tipo"], data=d["data"],
                       data_inclusao=d["data_inclusao"], unidade=d["unidade"], descricao=None)
                  for d in pagina["protocolos"]]
    indice = [dict(processo=aut["numero"], processo_id=pid, sei_doc_id=d["numero"], tipo=d["tipo"], data=d["data"],
                   data_inclusao=d["data_inclusao"], unidade=d["unidade"], link=d["link"] or "",
                   restrito=d["restrito"], motivo_restricao=d["motivo_restricao"] or "",
                   processo_restrito=pagina["processo_restrito"])
              for d in pagina["protocolos"]]
    return dict(processo=proc, andamentos=andamentos, protocolos=protocolos, originais=originais, indice=indice)


def _ler_csv(arq: Path) -> list[dict]:
    if not arq.exists():
        return []
    with open(arq, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _escrever_csv(linhas: list[dict], arq: Path, cols: list[str]):
    arq.parent.mkdir(parents=True, exist_ok=True)
    with open(arq, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(linhas)


def gravar(resultados: list[dict], destino: Path, trabalho: Path, acrescentar: bool = False) -> dict:
    """Grava as TSVs canônicas e os auxiliares. Com `acrescentar`, mantém os processos já gravados que não estão
    nesta coleta (os que estão são substituídos)."""
    novos = {r["processo"]["id"] for r in resultados}
    # processo repetido na mesma coleta (duas URLs do mesmo número): vale a última
    por_id = {r["processo"]["id"]: r for r in resultados}
    res = list(por_id.values())

    def juntar(antigas, novas, chave_id):
        mantidas = [x for x in antigas if x.get(chave_id) not in novos] if acrescentar else []
        return mantidas + novas

    procs = juntar(ler_tsv(destino / "processos.tsv"), [r["processo"] for r in res], "id")
    ands = juntar(ler_tsv(destino / "andamentos.tsv"), [a for r in res for a in r["andamentos"]], "processo_id")
    prots = juntar(ler_tsv(destino / "protocolos.tsv"), [p for r in res for p in r["protocolos"]], "processo_id")
    obs = juntar(ler_tsv(destino / "observacoes.tsv"), [], "processo_id")
    escrever_tsv(procs, destino, "processos.tsv")
    escrever_tsv(ands, destino, "andamentos.tsv")
    escrever_tsv(prots, destino, "protocolos.tsv")
    escrever_tsv(obs, destino, "observacoes.tsv")  # notas internas do gabinete: a pesquisa pública não tem

    _escrever_csv(juntar(_ler_csv(trabalho / "indice_documentos.csv"), [i for r in res for i in r["indice"]],
                         "processo_id"), trabalho / "indice_documentos.csv", COLS_INDICE)
    _escrever_csv(juntar(_ler_csv(trabalho / "andamentos_original.csv"), [o for r in res for o in r["originais"]],
                         "processo_id"), trabalho / "andamentos_original.csv", COLS_ORIGINAL)
    _escrever_csv(juntar(_ler_csv(trabalho / "fontes.csv"), [r["fonte"] for r in res if "fonte" in r],
                         "processo_id"), trabalho / "fontes.csv", COLS_FONTES)
    return dict(processos=len(procs), andamentos=len(ands), protocolos=len(prots))


# ------------------------------------------------------------------------------------------------ entradas
def ler_entradas(args) -> list[str]:
    itens = list(args.entradas or [])
    if args.lista:
        for ln in Path(args.lista).read_text(encoding="utf-8-sig").splitlines():
            ln = ln.split("#", 1)[0].strip()
            if ln:
                itens.append(ln)
    return itens


def resolver_url(item: str, perfil: PerfilSEI, mapa: dict) -> str | None:
    if RE_URL.match(item):
        return item
    if item in mapa:
        return mapa[item]
    if perfil.modelo_url_processo:
        return perfil.modelo_url_processo.format(numero=item)
    return None


def baixar_pagina(url: str, cliente: ClienteHTTP | None, pasta: Path, atualizar: bool) -> Path:
    arq = pasta / f"{hash_curto(url)}.html"
    if arq.exists() and not atualizar:
        return arq
    if cliente is None:
        raise RuntimeError("página fora do cache e coleta sem rede (--sem-rede)")
    r = cliente.obter(url)
    pasta.mkdir(parents=True, exist_ok=True)
    arq.write_bytes(r.conteudo)
    with open(pasta / "indice_urls.tsv", "a", encoding="utf-8") as f:
        f.write(f"{arq.name}\t{url}\n")
    return arq


def processar_arquivo(arq: Path, perfil: PerfilSEI, origem: str, url: str | None = None) -> dict:
    pagina = analisar_pagina(arq.read_bytes(), perfil, url=url)
    t = tabelas(pagina)
    t["fonte"] = dict(processo=t["processo"]["numero"], processo_id=t["processo"]["id"], origem=origem,
                      arquivo_bruto=str(arq), coletado_em=datetime.now().isoformat(timespec="seconds"),
                      perfil=perfil.uf, avisos="; ".join(pagina["avisos"]))
    t["avisos"] = pagina["avisos"]
    return t


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("entradas", nargs="*", help="URLs da pesquisa pública ou números de processo")
    ap.add_argument("--perfil", default="RJ", help="sigla em coleta/perfil_sei.py::PERFIS ou arquivo .json")
    ap.add_argument("--lista", help="arquivo com uma URL ou número por linha (# comenta)")
    ap.add_argument("--mapa-urls", help="CSV com colunas numero,url (para entradas por número)")
    ap.add_argument("--html-salvo", help="pasta com páginas de processo salvas à mão (.html/.htm)")
    ap.add_argument("--destino", type=Path, default=DUMP, help="pasta das TSVs (padrão dados/sei2_dump)")
    ap.add_argument("--trabalho", type=Path, default=TRABALHO, help="pasta dos índices auxiliares (dados/coleta)")
    ap.add_argument("--acrescentar", action="store_true", help="mantém os processos já gravados no destino")
    ap.add_argument("--atualizar", action="store_true", help="baixa de novo mesmo com a página no cache")
    ap.add_argument("--sem-rede", action="store_true", help="só usa o cache e o HTML salvo")
    ap.add_argument("--intervalo", type=float, default=2.0, help="segundos mínimos entre requisições (padrão 2)")
    ap.add_argument("--timeout", type=float, default=30.0)
    ap.add_argument("--tentativas", type=int, default=3, help="novas tentativas em erro temporário (429/5xx/rede)")
    ap.add_argument("--contato", help="e-mail para o User-Agent (ou variável COLETA_CONTATO)")
    args = ap.parse_args(argv)

    perfil = carregar_perfil(args.perfil)
    mapa = {}
    if args.mapa_urls:
        mapa = {r["numero"].strip(): r["url"].strip() for r in _ler_csv(Path(args.mapa_urls))}
    cliente = None if args.sem_rede else ClienteHTTP(args.intervalo, args.timeout, args.tentativas,
                                                     contato=args.contato)
    if cliente and cliente.usa_proxy:
        print("proxy: ativo (COLETA_PROXY)")

    resultados, erros = [], []
    for item in ler_entradas(args):
        url = resolver_url(item, perfil, mapa)
        if url is None:
            erros.append(f"{item}: número sem URL — copie o link do processo na pesquisa pública (a busca por "
                         "número tem captcha) ou informe --mapa-urls")
            continue
        try:
            arq = baixar_pagina(url, cliente, BRUTO / "processos", args.atualizar)
            resultados.append(processar_arquivo(arq, perfil, url, url=url))
        except (PaginaInvalida, RuntimeError) as e:
            erros.append(f"{item[:90]}: {sem_credencial(e)}")
            if "captcha" in str(e):
                print("PARADO: o servidor pediu verificação humana. Não insista; use páginas salvas à mão.")
                break
    if args.html_salvo:
        for arq in sorted(p for p in Path(args.html_salvo).iterdir() if p.suffix.lower() in (".html", ".htm")):
            try:
                resultados.append(processar_arquivo(arq, perfil, f"arquivo:{arq.name}"))
            except PaginaInvalida as e:
                erros.append(f"{arq.name}: {e}")

    for r in resultados:
        for a in r["avisos"]:
            print(f"AVISO {r['processo']['numero']}: {a}")
    for e in erros:
        print("ERRO", e)
    if not resultados:
        raise SystemExit("nenhum processo coletado")
    n = gravar(resultados, args.destino, args.trabalho, args.acrescentar)
    print(f"{len(resultados)} página(s) lida(s) → {n['processos']} processos, {n['andamentos']} andamentos, "
          f"{n['protocolos']} protocolos em {args.destino}")
    print("próximo passo: python -m coleta.validar_coleta --perfil", args.perfil)


if __name__ == "__main__":
    main()
