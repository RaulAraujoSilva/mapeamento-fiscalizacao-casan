"""Auditoria automática de acurácia — checagens determinísticas sobre todas as camadas.

A. Trilha: posse particiona o tempo; SEI 2 × banco do relator (unidade e data das peças).
B. Fichas de trabalho: números, percentuais, valores e referências de documento/norma ancorados no texto.
D. Modelos × vínculos × fichas: frequência de casos, dias úteis e horas coerentes.
E. Vínculos: unidade da peça × raia; ordem das datas × ordem do fluxo.
F. Avaliações: números citados ancorados nas fontes (texto das peças, fichas, trilha).

Saída: saida/auditoria/auditoria_automatica.json + resumo no terminal."""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict

import pandas as pd

from comum import DADOS, RAIA_ALIAS, RAIZ, SAIDA

sys.path.insert(0, str(RAIZ / "scripts"))
from gerar_bpmn import diagramar  # noqa: E402

DIR = SAIDA / "bpmn"
AUD = SAIDA / "auditoria"
CAMPOS_FICHA = ["tarefa", "entregavel", "calculos", "testes_auditoria", "insumos", "fontes_externas", "sinais_perda",
                "encaminha_para"]
# números "informativos": decimais, percentuais, valores, números com 3+ dígitos (ofícios, pareceres, normas, anos)
RE_NUM = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+,\d+|\d{3,}")


def norm(s: str) -> str:
    """Remove espaços e separadores (ponto e vírgula decimal/milhar) para comparar 28,0 com 28.0."""
    return re.sub(r"[\s.,]", "", str(s or "")).lower()


def numeros(texto: str) -> set[str]:
    return {n for n in RE_NUM.findall(str(texto or "")) if not re.fullmatch(r"0+", n)}


def canon(n: str) -> str:
    """Valor canônico: tira separador de milhar, vírgula decimal vira ponto, zeros à direita somem."""
    n = str(n)
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", n):
        n = n.replace(".", "")
    n = n.replace(",", ".")
    if "." in n:
        n = n.rstrip("0").rstrip(".")
    return n.lstrip("0") or "0"


def conjunto(texto: str) -> set[str]:
    """Números presentes na fonte (inclui decimais com ponto, como em JSON)."""
    t = str(texto or "")
    return {canon(x) for x in RE_NUM.findall(t)} | {canon(x) for x in re.findall(r"\d+\.\d+", t)}


def ancorado(n: str, fonte: set[str]) -> bool:
    return canon(n) in fonte


def texto_ficha(f: dict, campo: str) -> str:
    v = f.get(campo)
    if isinstance(v, list):
        return " | ".join(json.dumps(x, ensure_ascii=False) if isinstance(x, dict) else str(x) for x in v)
    return str(v or "")


def main():
    AUD.mkdir(exist_ok=True)
    out = {}

    # ---------------- A. trilha
    posse = pd.read_csv(SAIDA / "posse.csv", parse_dates=["inicio", "fim"])
    proc = pd.read_csv(SAIDA / "processos_indicadores.csv", parse_dates=["inicio", "ultimo_andamento"])
    sob = []
    for n, g in posse.sort_values(["numero", "inicio"]).groupby("numero"):
        buracos = (g.inicio.iloc[1:].values != g.fim.iloc[:-1].values).sum()
        sob.append(buracos)
    docs = pd.read_csv(SAIDA / "documentos.csv", low_memory=False, dtype={"numero": str})
    rel = pd.read_parquet(DADOS / "relator" / "documentos.parquet")
    m = docs.merge(rel, left_on=["numero_processo", "numero"], right_on=["processo", "sei_doc_id"], suffixes=("", "_rel"))
    d_sei = pd.to_datetime(m.data_inclusao, errors="coerce").dt.date
    d_rel = pd.to_datetime(m.data_inclusao_rel, errors="coerce", dayfirst=True).dt.date
    out["A_trilha"] = dict(
        processos_com_posse=int(posse.numero.nunique()),
        posse_com_lacuna_ou_sobreposicao=int(sum(1 for b in sob if b)),
        docs_cruzados_sei2_relator=len(m),
        unidade_diverge=int((m.unidade.fillna("") != m.unidade_rel.fillna("")).sum()),
        tipo_diverge=int((m.tipo.fillna("").str.strip() != m.tipo_rel.fillna("").str.strip()).sum()),
        data_diverge=int(((d_sei != d_rel) & d_rel.notna()).sum()),
        docs_fora_da_estadia_pct=round(100 * (docs.atribuicao != "dentro").mean(), 1),
    )

    # ---------------- B. fichas: ancoragem de números
    txt = pd.read_parquet(DADOS / "relator" / "doc_text_piloto.parquet")
    texto = {f"{p}:{s}": t for p, s, t in zip(txt.processo, txt.sei_doc_id, txt.texto)}
    por_campo = defaultdict(lambda: [0, 0])
    exemplos = []
    n_fichas = 0
    with open(SAIDA / "fichas_trabalho.jsonl", encoding="utf-8") as f:
        for ln in f:
            d = json.loads(ln)
            ref = f"{d['processo']}:{d['sei_doc_id']}"
            if not texto.get(ref):
                continue
            fonte = conjunto(texto[ref])
            n_fichas += 1
            for campo in CAMPOS_FICHA:
                for n in numeros(texto_ficha(d["ficha"], campo)):
                    por_campo[campo][0] += 1
                    if not ancorado(n, fonte):
                        por_campo[campo][1] += 1
                        if len(exemplos) < 60:
                            exemplos.append(dict(ref=ref, campo=campo, numero=n,
                                                 contexto=texto_ficha(d["ficha"], campo)[:200]))
    tot = sum(v[0] for v in por_campo.values())
    falta = sum(v[1] for v in por_campo.values())
    out["B_fichas"] = dict(fichas_com_texto=n_fichas, numeros_citados=tot, numeros_sem_ancora=falta,
                           pct_sem_ancora=round(100 * falta / max(tot, 1), 1),
                           por_campo={k: dict(citados=v[0], sem_ancora=v[1]) for k, v in por_campo.items()},
                           exemplos=exemplos)

    # ---------------- D/E. modelos × vínculos × fichas
    esf = pd.read_csv(SAIDA / "esforco_documentos.csv", dtype={"numero": str})
    esf["ref"] = esf.numero_processo + ":" + esf.numero
    esf = esf.set_index("ref")
    consist = []
    cron = []
    for arq in sorted(DIR.glob("modelo_*.json")):
        mod = json.loads(arq.read_text(encoding="utf-8"))
        cod = mod["codigo"]
        if not (DIR / f"vinculos_{cod}.json").exists():  # tipo novo da fase 2: auditado por auditoria_classificador
            continue
        fic = json.loads((DIR / f"fichas_{cod}.json").read_text(encoding="utf-8"))
        vin = json.loads((DIR / f"vinculos_{cod}.json").read_text(encoding="utf-8"))
        raias = {r["id"]: r["nome"] for r in mod["raias"]}
        D = diagramar(mod)
        n_casos = len(fic["processo"]["casos"])
        datas_por_caso = defaultdict(list)
        for e in mod["elementos"]:
            if e["tipo"] != "tarefa":
                continue
            a = fic["atividades"][e["id"]]
            fq = re.match(r"(\d+)/(\d+)", str(e.get("freq") or ""))
            refs = [r for r in vin["atividades"].get(e["id"], {}).get("docs", []) if r in esf.index]
            unidades = {esf.loc[r, "unidade"].split("/")[-1] for r in refs}
            raia_txt = (e["raia"] + " " + raias.get(e["raia"], "")).upper()
            fora_raia = sorted(u for u in unidades if u not in raia_txt and not (u in RAIA_ALIAS and RAIA_ALIAS[u] in raia_txt))
            consist.append(dict(
                codigo=cod, tarefa=e["id"], nome=e["nome"],
                freq_modelo=e.get("freq"), casos_com_pecas=a["casos_com_evidencia"],
                freq_diverge=bool(fq and int(fq.group(1)) != a["casos_com_evidencia"] and a["n_docs"] > 0),
                du_modelo=e.get("du"), espera_antes_fichas=a["espera_du"]["antes"],
                horas_modelo=e.get("horas"), horas_fichas=f"{a['trabalho_h']['piso']} / {a['trabalho_h']['teto']}",
                unidades_das_pecas=sorted(unidades), pecas_fora_da_raia=fora_raia,
            ))
            for r in refs:
                datas_por_caso[esf.loc[r, "numero_processo"]].append((D["col"][e["id"]], esf.loc[r, "data_inclusao"], e["id"]))
        for caso, xs in datas_por_caso.items():
            # mediana da data por tarefa; inversões entre pares de tarefas em colunas diferentes
            med = pd.DataFrame(xs, columns=["col", "data", "t"]).assign(data=lambda x: pd.to_datetime(x.data))
            med = med.groupby(["t", "col"]).data.median().reset_index()
            pares = inv = 0
            for i in range(len(med)):
                for j in range(len(med)):
                    if med.col[i] < med.col[j]:
                        pares += 1
                        inv += med.data[i] > med.data[j]
            cron.append(dict(codigo=cod, caso=caso, pares=pares, inversoes=int(inv),
                             pct=round(100 * inv / max(pares, 1), 1)))
    cdf = pd.DataFrame(consist)
    out["D_modelos"] = dict(tarefas=len(cdf), freq_diverge=int(cdf.freq_diverge.sum()),
                            tarefas_com_peca_fora_da_raia=int((cdf.pecas_fora_da_raia.str.len() > 0).sum()),
                            divergencias=cdf[cdf.freq_diverge | (cdf.pecas_fora_da_raia.str.len() > 0)].to_dict("records"))
    out["E_cronologia"] = cron

    # ---------------- F. avaliações: números ancorados nas fontes
    aval = {}
    for arq in sorted(DIR.glob("avaliacao_*.json")):
        av = json.loads(arq.read_text(encoding="utf-8"))
        cod = av["codigo"]
        casos = pd.read_csv(SAIDA / "piloto.csv").query("processo_principal == @cod").numero.tolist()
        # tipo sem caso-piloto não tem fichas, vínculos nem docs: no lugar, o procedimento da coorte
        arqs = [DIR / f"fatos_{cod}.json", DIR / f"fichas_{cod}.json", DIR / f"modelo_{cod}.json",
                DIR / f"evidencias_{cod}.md", DIR / f"vinculos_{cod}.json", DIR / f"docs_{cod}.csv",
                SAIDA / "fase2" / f"procedimento_{cod}.json"]
        fontes = [a.read_text(encoding="utf-8-sig") for a in arqs if a.exists()]
        # só as camadas estruturadas de que a avaliação foi feita: somar os textos integrais de ~100 peças
        # tornaria qualquer número de 3 dígitos "ancorado" por acaso
        fonte_norm = conjunto(" ".join(fontes))
        textos = []

        def coleta(o, cam=""):
            if isinstance(o, dict):
                for k, v in o.items():
                    coleta(v, f"{cam}.{k}" if cam else k)
            elif isinstance(o, list):
                for i, v in enumerate(o):
                    coleta(v, f"{cam}[{i}]")
            elif isinstance(o, str):
                textos.append((cam, o))

        coleta(av)
        nums, falta = 0, []
        for cam, t in textos:
            for n in numeros(t):
                nums += 1
                if not ancorado(n, fonte_norm):
                    falta.append(dict(campo=cam, numero=n, trecho=t[max(0, t.find(n) - 80): t.find(n) + 40]))
        aval[cod] = dict(numeros_citados=nums, sem_ancora=len(falta), exemplos=falta[:25])
    out["F_avaliacoes"] = aval

    (AUD / "auditoria_automatica.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str),
                                                    encoding="utf-8")
    print("A trilha:", {k: v for k, v in out["A_trilha"].items()})
    b = out["B_fichas"]
    print(f"B fichas: {b['numeros_citados']} números, {b['numeros_sem_ancora']} sem âncora ({b['pct_sem_ancora']}%)",
          {k: v for k, v in b["por_campo"].items()})
    d = out["D_modelos"]
    print(f"D modelos: {d['tarefas']} tarefas; freq diverge {d['freq_diverge']}; tarefas com peça de trâmite de outra unidade "
          f"{d['tarefas_com_peca_fora_da_raia']} (fora do cálculo de tempo e horas)")
    print("E cronologia (inversões %):", [(c["codigo"], c["caso"][-9:], c["pct"]) for c in cron])
    print("F avaliações (números sem âncora):", {k: f"{v['sem_ancora']}/{v['numeros_citados']}" for k, v in aval.items()})


if __name__ == "__main__":
    main()
