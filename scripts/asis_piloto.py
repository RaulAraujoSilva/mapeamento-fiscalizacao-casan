"""Etapa 3c — esforço por conteúdo e AS-IS dos processos-piloto.

Junta trilhas (estadias, posse), documentos e fichas de trabalho; recalcula o esforço por laudas e
complexidade; refaz a separação trabalho × espera com esse esforço; e gera, por processo organizacional,
o fluxo AS-IS (Mermaid), competências, insumos, ferramentas e sinais de perda.

Saídas: saida/esforco_documentos.csv, tarefas_piloto.csv, resumo_piloto.csv, Mapeamento_SEI_Piloto.xlsx
        docs/ASIS_PILOTO.md"""
from __future__ import annotations

import json
import re
from collections import Counter

import pandas as pd

from comum import CARACTERES_LAUDA, DADOS, RAIZ, SAIDA, documentos, horas_modelo, sigla

HORAS_DIA = 6.0
PDF_INTERNO = {"relatorio", "relatorio_fiscalizacao", "nota_tecnica", "notificacao_autuacao"}
HORAS_JUNTADA = 0.1
# sem MIME (peça restrita ou não baixada): decide pela categoria do tipo SEI
SEM_MIME_EXTERNA = {"peca_externa", "anexo", "registro_entrada", "publicacao"}
NIVEL = {"basico": 1, "intermediario": 2, "especialista": 3}
ROTULO_AREA = {
    "juridico_regulatoria": "Jurídico-regulatória", "economico_financeira_tarifaria": "Econômico-financeira e tarifária",
    "engenharia_saneamento": "Engenharia de saneamento", "engenharia_gas_seguranca": "Engenharia de gás e segurança",
    "auditoria_controle": "Auditoria e controle", "dados_estatistica": "Dados e estatística",
    "redacao_oficial": "Redação oficial", "gestao_processual": "Gestão processual",
    "atendimento_usuario": "Atendimento ao usuário", "ambiental": "Ambiental", "contabil": "Contábil",
}
ROTULO_NAT = {
    "encaminhamento": "Encaminhamento", "comunicacao": "Comunicação", "instrucao_processual": "Instrução processual",
    "analise_juridica": "Análise jurídica", "analise_tecnica_engenharia": "Análise técnica de engenharia",
    "analise_economico_financeira": "Análise econômico-financeira", "fiscalizacao_campo": "Fiscalização de campo",
    "auditoria_conferencia": "Auditoria e conferência", "relatoria_decisao": "Relatoria e decisão",
    "publicacao_registro": "Publicação e registro",
}
ROTULO_SINAL = {
    "pedido_complementacao": "pedido de complementação", "devolucao_por_vicio": "devolução por vício",
    "refazimento": "refazimento", "diligencia_externa": "diligência externa", "prazo_concedido": "prazo concedido",
    "reiteracao": "reiteração", "aguardando_outra_unidade": "aguardando outra unidade", "sobrestamento": "sobrestamento",
}


def carregar_fichas() -> pd.DataFrame:
    linhas = []
    with open(SAIDA / "fichas_trabalho.jsonl", encoding="utf-8") as f:
        for ln in f:
            d = json.loads(ln)
            fi = d["ficha"]
            linhas.append(dict(
                processo=d["processo"], sei_doc_id=str(d["sei_doc_id"]), natureza_ficha=fi.get("natureza_trabalho"),
                tarefa=fi.get("tarefa"), entregavel=fi.get("entregavel"), complexidade=fi.get("complexidade"),
                fracao_autoral=fi.get("fracao_autoral"), horas_llm=fi.get("horas_estimadas"),
                n_analisados=fi.get("n_documentos_analisados"), fontes=fi.get("fontes_externas") or [],
                insumos=fi.get("insumos") or [], ferramentas=fi.get("ferramentas") or [],
                calculos=fi.get("calculos") or [], testes=fi.get("testes_auditoria") or [],
                competencias=fi.get("competencias") or [], sinais=fi.get("sinais_perda") or [],
                prazo=fi.get("prazo_concedido_dias")))
    return pd.DataFrame(linhas)


def _limpa(s: str, n: int = 60) -> str:
    s = re.sub(r'["\[\]{}()<>|#;]', " ", str(s or "")).strip()
    return (s[: n - 1] + "…") if len(s) > n else s


def mermaid(passos: pd.DataFrame) -> str:
    out = ["```mermaid", "flowchart LR"]
    ids = []
    for i, r in enumerate(passos.itertuples()):
        nid = f"t{i}"
        ids.append(nid)
        rotulo = f"{r.sigla}<br/>{_limpa(r.tarefa)}<br/>{r.horas_modelo:.1f} h · {r.lead_du:.0f} du"
        out.append(f'  {nid}["{rotulo}"]')
        if r.espera_dominante_modelo:
            out.append(f"  class {nid} espera")
        elif r.sinais:
            out.append(f"  class {nid} perda")
    for a, b in zip(ids, ids[1:]):
        out.append(f"  {a} --> {b}")
    out += ["  classDef espera fill:#f8d7da,stroke:#b02a37", "  classDef perda fill:#fff3cd,stroke:#b58105", "```"]
    return "\n".join(out)


def main():
    piloto = pd.read_csv(SAIDA / "piloto.csv")
    cls = pd.read_csv(SAIDA / "processos_classificados.csv").set_index("numero")
    docs = documentos()
    # esforço por peça: piloto e coorte da fase 2 (o AS-IS abaixo continua só do piloto)
    from fichas_trabalho import universo
    docs = docs[docs.numero_processo.isin(universo()) & (docs.categoria != "processo_relacionado")].copy()
    txt = pd.read_parquet(DADOS / "relator" / "doc_text_piloto.parquet")
    txt["n_chars"] = txt.texto.str.len()
    docs = docs.merge(txt[["processo", "sei_doc_id", "n_chars"]], left_on=["numero_processo", "numero"],
                      right_on=["processo", "sei_doc_id"], how="left").drop(columns=["processo", "sei_doc_id"])
    mime = pd.read_parquet(DADOS / "relator" / "documentos.parquet", columns=["processo", "sei_doc_id", "mime"])
    docs = docs.merge(mime, left_on=["numero_processo", "numero"], right_on=["processo", "sei_doc_id"],
                      how="left").drop(columns=["processo", "sei_doc_id"])
    # autoria: o editor do SEI gera HTML; PDF é peça de fora juntada, salvo relatórios técnicos que as câmaras sobem em PDF
    docs["autoria"] = "agenersa"
    externa = ((docs.mime.notna() & ~docs.mime.str.contains("html", na=False) & ~docs.categoria.isin(PDF_INTERNO))
               | (docs.mime.isna() & docs.categoria.isin(SEM_MIME_EXTERNA)))
    docs.loc[externa, "autoria"] = "externa"
    docs.loc[externa, "horas_base"] = HORAS_JUNTADA
    fi = carregar_fichas()
    docs = docs.merge(fi, left_on=["numero_processo", "numero"], right_on=["processo", "sei_doc_id"], how="left")
    docs["tem_ficha"] = docs.tarefa.notna() & docs.autoria.eq("agenersa")
    docs["laudas"] = (docs.n_chars.fillna(0) / CARACTERES_LAUDA).round(2)
    docs["horas_proxy"] = docs.horas_base
    docs["horas_modelo"] = [
        horas_modelo(r.horas_base, r.n_chars, r.fracao_autoral, r.complexidade, r.n_analisados,
                     len(r.fontes) if isinstance(r.fontes, list) else 0) if r.tem_ficha else r.horas_base
        for r in docs.itertuples()]
    docs["horas_llm"] = docs.horas_llm.where(docs.tem_ficha, docs.horas_base).astype(float)
    docs["sinais_txt"] = docs.sinais.apply(lambda s: "; ".join(x.get("tipo", "") for x in s) if isinstance(s, list) else "")
    cols_doc = ["numero_processo", "numero", "tipo", "categoria", "unidade", "data_inclusao", "estadia_idx", "autoria", "laudas",
                "tem_ficha", "natureza_ficha", "tarefa", "complexidade", "fracao_autoral", "n_analisados",
                "horas_proxy", "horas_modelo", "horas_llm", "sinais_txt"]
    docs[cols_doc].to_csv(SAIDA / "esforco_documentos.csv", index=False, encoding="utf-8-sig")

    est = pd.read_csv(SAIDA / "estadias.csv", parse_dates=["entrada", "saida"])
    est = est[est.numero.isin(piloto.numero)]
    posse = pd.read_csv(SAIDA / "posse.csv", parse_dates=["inicio", "fim"])
    posse = posse[posse.numero.isin(piloto.numero)].copy()
    docs = docs[docs.numero_processo.isin(piloto.numero)].copy()
    docs["data_inclusao"] = pd.to_datetime(docs.data_inclusao)

    # posse recalculada com o esforço por conteúdo
    hp = []
    for r in posse.itertuples():
        dj = docs[(docs.numero_processo == r.numero) & (docs.unidade == r.unidade)
                  & (docs.data_inclusao >= r.inicio.normalize()) & (docs.data_inclusao <= r.fim.normalize())]
        hp.append(dj.horas_modelo.sum())
    posse["horas_modelo"] = hp
    posse["espera_dominante_modelo"] = (posse.du >= 20) & (posse.horas_modelo / (posse.du.clip(lower=1) * HORAS_DIA) < 0.05)

    # tarefas = estadias ativas, com a tarefa principal da ficha mais pesada
    tarefas = []
    for r in est[est.n_docs > 0].sort_values(["numero", "entrada"]).itertuples():
        ds = docs[(docs.numero_processo == r.numero) & (docs.estadia_idx == r.idx)]
        if ds.empty:
            continue
        com = ds[ds.tem_ficha].sort_values("horas_modelo", ascending=False)
        princ = com.iloc[0] if len(com) else None
        h = ds.horas_modelo.sum()
        sinais = sorted({x.get("tipo", "") for s in ds.sinais.dropna() for x in s})
        tarefas.append(dict(
            numero=r.numero, sigla=r.sigla, entrada=r.entrada, saida=r.saida, lead_du=r.lead_du,
            espera_1a_juntada_du=r.espera_1a_juntada_du, n_docs=len(ds), n_fichas=len(com),
            tarefa=(princ.tarefa if princ is not None else
                    ("Juntar " if ds.autoria.eq("externa").any() else "") + str(ds.tipo.iloc[0])),
            natureza=(princ.natureza_ficha if princ is not None else ds.natureza_trabalho.iloc[0]),
            documentos="; ".join(ds.tipo.astype(str)), horas_proxy=ds.horas_proxy.sum(), horas_modelo=round(h, 2),
            horas_llm=round(ds.horas_llm.sum(), 2), sinais="; ".join(sinais),
            espera_dominante_modelo=bool(r.lead_du >= 20 and h / (max(r.lead_du, 1) * HORAS_DIA) < 0.05
                                         and not r.acompanhamento)))
    tarefas = pd.DataFrame(tarefas)
    tarefas.to_csv(SAIDA / "tarefas_piloto.csv", index=False, encoding="utf-8-sig")

    # resumo por processo SEI
    resumo = []
    for p in piloto.itertuples():
        d = docs[docs.numero_processo == p.numero]
        po = posse[posse.numero == p.numero]
        f = d[d.tem_ficha]
        tot = po.du.sum() or 1
        n_ins = f.insumos.apply(lambda l: {i.get("tipo") for i in l})
        resumo.append(dict(
            numero=p.numero, processo_principal=p.processo_principal, nome_processo=p.nome_processo, papel=p.papel,
            lead_du=p.lead_du, docs=len(d), fichas=len(f), laudas_produzidas=round(f.laudas.sum(), 1),
            horas_proxy=round(d.horas_proxy.sum(), 1), horas_modelo=round(d.horas_modelo.sum(), 1),
            horas_llm=round(d.horas_llm.sum(), 1),
            eficiencia_ciclo_modelo_pct=round(100 * d.horas_modelo.sum() / (max(p.lead_du, 1) * HORAS_DIA), 2),
            pct_tempo_espera_dominante_modelo=round(100 * po.loc[po.espera_dominante_modelo, "du"].sum() / tot, 1),
            pct_pecas_com_base_externa=round(100 * n_ins.apply(lambda s: "base_externa" in s).mean(), 1) if len(f) else 0,
            pct_pecas_com_calculo=round(100 * f.calculos.apply(bool).mean(), 1) if len(f) else 0,
            pct_pecas_com_teste=round(100 * f.testes.apply(bool).mean(), 1) if len(f) else 0,
            **{f"sinal_{k}": int(sum(1 for s in f.sinais for x in s if x.get("tipo") == k)) for k in ROTULO_SINAL},
        ))
    resumo = pd.DataFrame(resumo)
    resumo.to_csv(SAIDA / "resumo_piloto.csv", index=False, encoding="utf-8-sig")

    # competências: área × processo organizacional (horas do modelo nas peças que exigem a área)
    comp = []
    for r in docs[docs.tem_ficha].itertuples():
        pid = cls.loc[r.numero_processo, "processo_principal"]
        for c in r.competencias:
            comp.append(dict(processo_principal=pid, unidade=sigla(r.unidade), area=c.get("area"),
                             nivel=NIVEL.get(c.get("nivel"), 1), horas=r.horas_modelo))
    comp = pd.DataFrame(comp)
    matriz_proc = comp.pivot_table(index="area", columns="processo_principal", values="horas", aggfunc="sum",
                                   fill_value=0).round(0)
    matriz_unid = comp.pivot_table(index="area", columns="unidade", values="horas", aggfunc="sum", fill_value=0).round(0)
    nivel_max = comp.pivot_table(index="area", columns="unidade", values="nivel", aggfunc="max", fill_value=0)
    for m in (matriz_proc, matriz_unid, nivel_max):
        m.index = m.index.map(lambda a: ROTULO_AREA.get(a, a))

    with pd.ExcelWriter(SAIDA / "Mapeamento_SEI_Piloto.xlsx", engine="openpyxl") as xw:
        resumo.to_excel(xw, sheet_name="Resumo por processo", index=False)
        tarefas.to_excel(xw, sheet_name="Tarefas (estadias ativas)", index=False)
        docs[cols_doc].to_excel(xw, sheet_name="Esforço por documento", index=False)
        matriz_proc.to_excel(xw, sheet_name="Competências × processo")
        matriz_unid.to_excel(xw, sheet_name="Competências × unidade (h)")
        nivel_max.replace({1: "básico", 2: "intermediário", 3: "especialista", 0: ""}).to_excel(
            xw, sheet_name="Nível exigido × unidade")
        for ws in xw.sheets.values():
            ws.freeze_panes = "B2"

    # documento AS-IS
    md = ["# AS-IS dos processos-piloto (reconstruído do SEI)", "",
          "Gerado por `scripts/asis_piloto.py`. Horas = modelo por conteúdo (laudas autorais × complexidade + leitura "
          "de insumos + fontes externas), hipótese a calibrar. du = dias úteis. Nos fluxos, cada caixa é uma passagem "
          "em que a unidade juntou documento; vermelho = espera dominante (≥ 20 du com trabalho < 5% da capacidade); "
          "amarelo = a peça registra sinal de perda (complementação, diligência, prazo, reiteração).", ""]
    for pid, g in piloto.groupby("processo_principal", sort=False):
        md += [f"## {pid} — {g.nome_processo.iloc[0]}", ""]
        rs = resumo[resumo.processo_principal == pid]
        md += ["| Processo SEI | Caso | Lead time (du) | Documentos | Laudas produzidas | Horas (modelo) | Eficiência do ciclo | Tempo em espera dominante |",
               "|---|---|---|---|---|---|---|---|"]
        for r in rs.itertuples():
            md.append(f"| {r.numero} | {r.papel} | {r.lead_du:.0f} | {r.docs} | {r.laudas_produzidas:.0f} | "
                      f"{r.horas_modelo:.0f} | {r.eficiencia_ciclo_modelo_pct:.1f}% | {r.pct_tempo_espera_dominante_modelo:.0f}% |")
        md.append("")
        fp = docs[docs.tem_ficha & docs.numero_processo.isin(g.numero)]
        horas_nat = fp.groupby("natureza_ficha").horas_modelo.sum().sort_values(ascending=False)
        tot = horas_nat.sum() or 1
        md.append("**Onde está o trabalho:** " + "; ".join(
            f"{ROTULO_NAT.get(k, k)} {100 * v / tot:.0f}%" for k, v in horas_nat.head(5).items()) + ".")
        cp = comp[comp.processo_principal == pid].groupby("area").agg(h=("horas", "sum"), n=("nivel", "max"))
        cp = cp.sort_values("h", ascending=False).head(6)
        md.append("**Competências exigidas (por horas):** " + "; ".join(
            f"{ROTULO_AREA.get(a, a)} ({['', 'básico', 'intermediário', 'especialista'][int(r.n)]})"
            for a, r in cp.iterrows()) + ".")
        ins = Counter(i.get("tipo") for l in fp.insumos for i in l)
        md.append("**Insumos:** " + "; ".join(f"{k.replace('_', ' ')} ({v})" for k, v in ins.most_common(6)) + ".")
        ferr = Counter(x.strip().lower() for l in fp.ferramentas for x in l)
        md.append("**Ferramentas e técnicas mais usadas:** " + "; ".join(f"{k} ({v})" for k, v in ferr.most_common(6)) + ".")
        calc = [c for l in fp.calculos for c in l][:4]
        if calc:
            md.append("**Exemplos de cálculo:** " + "; ".join(_limpa(c, 110) for c in calc) + ".")
        sin = Counter(x.get("tipo") for l in fp.sinais for x in l)
        if sin:
            md.append("**Sinais de perda nas peças:** " + "; ".join(
                f"{ROTULO_SINAL.get(k, k)} ({v})" for k, v in sin.most_common()) + ".")
        md.append("")
        for r in g.itertuples():
            passos = tarefas[tarefas.numero == r.numero]
            md += [f"### {r.numero} — caso {r.papel}", "", f"{r.assunto}", "", mermaid(passos), ""]
    (RAIZ / "docs" / "ASIS_PILOTO.md").write_text("\n".join(md), encoding="utf-8")
    print(resumo[["numero", "processo_principal", "lead_du", "horas_proxy", "horas_modelo", "horas_llm",
                  "eficiencia_ciclo_modelo_pct", "pct_tempo_espera_dominante_modelo"]].to_string())


if __name__ == "__main__":
    main()
