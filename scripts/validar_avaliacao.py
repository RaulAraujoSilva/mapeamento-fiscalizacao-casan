"""Trava de ancoragem das avaliações: barra número que não venha da tabela de fatos ou das fichas.

Regras, por bloco da avaliação (sintese, leitura_metricas, gargalo, variabilidade, desperdicios[i],
oportunidades[i], atividades[tN]):
  - todo bloco com número precisa de "fatos_usados" com ids existentes em fatos_<Pxx>.json;
  - número seguido de "du" tem que ser o valor de um fato citado (dias úteis não se recalculam);
  - demais números: valor de fato citado ou número presente na ficha do processo (fichas_<Pxx>.json; tipo sem
    caso-piloto: procedimento da coorte, saida/fase2/procedimento_<Pxx>.json);
  - toda tarefa do modelo tem entrada em "atividades" e nenhuma entrada é de tarefa inexistente;
  - ficam de fora: identificadores de peça e norma (Parecer 83, NA 149, Lei 8.987/1995, art. 67), datas,
    ordinais e anos.

Uso: python validar_avaliacao.py [P01 P06 ...]   (sem argumentos: todos)"""
from __future__ import annotations

import hashlib
import json
import re
import sys

import pandas as pd

from comum import DADOS, SAIDA

DIR = SAIDA / "bpmn"
RE_ID = re.compile(r"(?:Parecer|Pareceres|Of[ií]cio|NA|Delibera[cç][aã]o|Deliberações|Voto|Relat[oó]rio|Lei|Decreto|IN|"
                   r"Instru[cç][aã]o Normativa|art\.?|arts\.?|Resolu[cç][aã]o|Carta|GEREG|Processo|SEI|n[ºo°.]|Nota Técnica|"
                   r"Termo de Notifica[cç][aã]o|TN|Despacho|Contrato|Cl[aá]usula|Ata|Bloco|RI|Reuni[aã]o)\s*[\w./-]*\d[\w./-]*",
                   re.I)
RE_SIGLA = re.compile(r"\b[A-Za-zÀ-ú]+[-/]\d[\w/-]*|\b[A-Z]{2,}\d+\b")
RE_DATA = re.compile(r"\d{1,2}/\d{1,2}/\d{2,4}|\d{1,2}/\d{4}|\b(?:19|20)\d{2}\b|\d+\s*[ºª°]")
RE_NUM = re.compile(r"\d+(?:[.,]\d+)*")


def canon(n: str) -> str:
    n = str(n)
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", n):
        n = n.replace(".", "")
    n = n.replace(",", ".")
    if "." in n:
        n = n.rstrip("0").rstrip(".")
    return n.lstrip("0") or "0"


def numeros_ficha(obj) -> set[str]:
    return {canon(x) for x in RE_NUM.findall(json.dumps(obj, ensure_ascii=False))}


def blocos(av: dict):
    for k in ("sintese", "leitura_metricas", "variabilidade"):
        if av.get(k):
            yield k, av[k], av.get(f"fatos_{k}", []) if isinstance(av.get(f"fatos_{k}"), list) else av.get("fatos_usados_gerais", [])
    g = av.get("gargalo") or {}
    yield "gargalo", f"{g.get('onde', '')} {g.get('evidencia', '')}", g.get("fatos_usados", [])
    for i, w in enumerate(av.get("desperdicios", [])):
        yield f"desperdicios[{i}]", w.get("evidencia", ""), w.get("fatos_usados", [])
    for i, o in enumerate(av.get("oportunidades", [])):
        yield f"oportunidades[{i}]", f"{o.get('descricao', '')} {o.get('ganho_esperado', '')}", o.get("fatos_usados", [])
    for t, a in (av.get("atividades") or {}).items():
        yield f"atividades.{t}", f"{a.get('aplicacao_ia', '')} {a.get('ganho_esperado', '')} {a.get('justificativa_valor', '')}", a.get("fatos_usados", [])


RE_DATA_COMPLETA = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
RE_DU_TEXTO = re.compile(r"\d+\s*(?:du\b|dias úteis)")
MESES = {m: i for i, m in enumerate(["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
                                      "setembro", "outubro", "novembro", "dezembro"], 1)}
RE_DATA_EXTENSO = re.compile(r"\b(\d{1,2})º?\s+de\s+(" + "|".join(MESES) + r")\s+de\s+(\d{4})", re.I)


def datas_conhecidas(cod: str) -> set[str]:
    """Datas (AAAA-MM-DD) que uma afirmação pode citar: fatos do código, datas de juntada das peças dos casos e
    datas escritas no texto das peças dos casos."""
    fat = json.loads((DIR / f"fatos_{cod}.json").read_text(encoding="utf-8"))
    casos = {f["caso"] for f in fat["fatos"] if f.get("caso")}
    out = {str(f["valor"]) for f in fat["fatos"] if f.get("unidade") == "data"}
    docs = pd.read_csv(SAIDA / "documentos.csv", low_memory=False, usecols=["numero_processo", "data", "data_inclusao"])
    docs = docs[docs.numero_processo.isin(casos)]
    out |= set(docs.data.dropna().astype(str).str[:10]) | set(docs.data_inclusao.dropna().astype(str).str[:10])
    rel = DADOS / "relator"
    if (rel / "doc_text_piloto.parquet").exists():
        t = pd.read_parquet(rel / "doc_text_piloto.parquet")
        for texto in t[t.processo.isin(casos)].texto.dropna():
            for d, m, y in RE_DATA_COMPLETA.findall(texto):
                out.add(f"{y}-{int(m):02d}-{int(d):02d}")
            for d, mes, y in RE_DATA_EXTENSO.findall(texto):
                out.add(f"{y}-{MESES[mes.lower()]:02d}-{int(d):02d}")
    if (rel / "extractions.parquet").exists():  # datas que a análise do relator leu nas peças (inclui apensos)
        e = pd.read_parquet(rel / "extractions.parquet", columns=["processo", "extraction_json"])
        for j in e[e.processo.isin(casos)].extraction_json:
            out |= set(re.findall(r"\d{4}-\d{2}-\d{2}", j))
            for d, mes, y in RE_DATA_EXTENSO.findall(j):
                out.add(f"{y}-{MESES[mes.lower()]:02d}-{int(d):02d}")
            for d, m, y in RE_DATA_COMPLETA.findall(j):
                out.add(f"{y}-{int(m):02d}-{int(d):02d}")
    return out


def sha_fatos(cod: str) -> str:
    """Impressão digital dos VALORES da tabela de fatos (muda quando um fato muda)."""
    fat = json.loads((DIR / f"fatos_{cod}.json").read_text(encoding="utf-8"))
    base = json.dumps(sorted((f["id"], str(f["valor"])) for f in fat["fatos"]), ensure_ascii=False)
    return hashlib.sha256(base.encode()).hexdigest()[:16]


def validar(cod: str, exigir_carimbo: bool = False) -> list[str]:
    av = json.loads((DIR / f"avaliacao_{cod}.json").read_text(encoding="utf-8"))
    fatos = {f["id"]: f for f in json.loads((DIR / f"fatos_{cod}.json").read_text(encoding="utf-8"))["fatos"]}
    arq_ficha = DIR / f"fichas_{cod}.json"  # tipo sem caso-piloto: contagens vêm do procedimento da coorte
    if not arq_ficha.exists():
        arq_ficha = SAIDA / "fase2" / f"procedimento_{cod}.json"
    ficha_nums = numeros_ficha(json.loads(arq_ficha.read_text(encoding="utf-8")))
    datas = datas_conhecidas(cod)
    erros = []
    for nome, texto, usados in blocos(av):
        usados = usados or []
        inexistentes = [u for u in usados if u not in fatos]
        if inexistentes:
            erros.append(f"{cod} {nome}: fatos inexistentes {inexistentes}")
        valores = {canon(str(fatos[u]["valor"])) for u in usados if u in fatos}
        # datas completas têm que existir nos fatos, na juntada ou no texto das peças do caso
        for d, m, y in RE_DATA_COMPLETA.findall(texto):
            iso = f"{y}-{int(m):02d}-{int(d):02d}"
            if iso not in datas:
                erros.append(f"{cod} {nome}: data {d}/{m}/{y} não aparece nos fatos nem nas peças dos casos")
        # mediana da carteira tem que dizer de quais processos
        for frase in re.split(r"(?<=[.;])\s+", texto):
            if re.search(r"mediana", frase, re.I) and not re.search(r"nativ|todos|considerando|migrad", frase, re.I):
                erros.append(f"{cod} {nome}: mediana sem dizer se é dos nativos ou de todos: {frase[:80]}")
        limpo = RE_DATA.sub(" ", RE_SIGLA.sub(" ", RE_ID.sub(" ", texto)))
        for m_ in re.finditer(r"(\d+(?:[.,]\d+)*)\s*(du\b|dias úteis)?", limpo):
            n, du = m_.group(1), m_.group(2)
            if not usados and RE_NUM.fullmatch(n):
                erros.append(f"{cod} {nome}: número {n} sem fatos_usados")
                break
            c = canon(n)
            if du and c not in valores:
                erros.append(f"{cod} {nome}: {n} du não é valor de fato citado")
            elif not du and c not in valores and c not in ficha_nums:
                erros.append(f"{cod} {nome}: {n} não está nos fatos citados nem na ficha")
    # toda tarefa do modelo tem entrada em atividades (regra 1 da especificação)
    mod = json.loads((DIR / f"modelo_{cod}.json").read_text(encoding="utf-8"))
    faltam = [e["id"] for e in mod["elementos"] if e["tipo"] == "tarefa" and e["id"] not in (av.get("atividades") or {})]
    if faltam:
        erros.append(f"{cod}: tarefas do modelo sem entrada em atividades: {faltam}")
    extras = sorted(set(av.get("atividades") or {}) - {e["id"] for e in mod["elementos"] if e["tipo"] == "tarefa"})
    if extras:
        erros.append(f"{cod}: atividades que não existem no modelo: {extras}")
    # vínculos: descritivo, gatilho, saída e observações sem tempos medidos e sem datas sem lastro
    arq_v = DIR / f"vinculos_{cod}.json"
    vin = json.loads(arq_v.read_text(encoding="utf-8")) if arq_v.exists() else {}
    for t, a in vin.get("atividades", {}).items():
        for campo in ("descritivo", "gatilho", "saida"):
            texto = a.get(campo) or ""
            # prazo citado na peça (está na ficha) pode; tempo medido não — tempos vêm da linha do tempo
            for m_ in RE_DU_TEXTO.finditer(texto):
                if canon(re.match(r"\d+", m_.group(0)).group(0)) not in ficha_nums:
                    erros.append(f"{cod} vinculos.{t}.{campo}: '{m_.group(0)}' não é prazo de peça (tempos vêm da linha do tempo)")
            for d, m, y in RE_DATA_COMPLETA.findall(texto):
                if f"{y}-{int(m):02d}-{int(d):02d}" not in datas:
                    erros.append(f"{cod} vinculos.{t}.{campo}: data {d}/{m}/{y} sem lastro")
    # carimbo: a avaliação foi validada contra esta versão dos fatos?
    if exigir_carimbo and (av.get("validado_contra") or {}).get("fatos_sha") != sha_fatos(cod):
        erros.append(f"{cod}: avaliação não carimbada contra a versão atual dos fatos (rode com --carimbar após validar)")
    return erros


def carimbar(cod: str):
    p = DIR / f"avaliacao_{cod}.json"
    av = json.loads(p.read_text(encoding="utf-8"))
    av["validado_contra"] = {"fatos_sha": sha_fatos(cod), "data": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")}
    p.write_text(json.dumps(av, ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    cods = args or sorted(p.stem.split("_")[1] for p in DIR.glob("avaliacao_*.json"))
    exigir = "--exigir-carimbo" in sys.argv
    total = 0
    for cod in cods:
        e = validar(cod, exigir)
        total += len(e)
        print(f"{cod}: {len(e)} problema(s)")
        for x in e[:40]:
            print("  ", x)
        if not e and "--carimbar" in sys.argv:
            carimbar(cod)
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
