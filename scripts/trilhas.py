"""Etapa 1 — reconstrói a trilha real de cada processo SEI a partir dos andamentos e dos
documentos juntados.

Saídas em saida/:
  estadias.csv            uma linha por passagem de um processo por uma unidade (entrada → saída)
  documentos.csv          cada protocolo atribuído à estadia da unidade que o juntou
  processos_indicadores.csv  indicadores de tempo, esforço proxy, iteração e espera por processo

Regras (ver docs/METODO.md, seção 3):
  - entrada na unidade: geração, remessa para ela, reabertura ou recebimento sem estadia aberta;
  - saída: conclusão na unidade ou remessa feita por ela; conclusão posterior sem reabertura
    estende a estadia (a unidade manteve o processo aberto ao remeter);
  - estadia "ativa" = juntou ao menos um documento; "passagem" = só recebeu e devolveu.
"""
from __future__ import annotations

import re
from collections import defaultdict

import numpy as np
import pandas as pd

from comum import (DADOS, INICIO_SEI, ORGAO, RECEPCAO, SAIDA, SECRETARIA, somar_du, carregar, categoria_documento, dias_uteis, motivo_acesso_externo,
                   natureza_unidade, sigla, tipo_andamento)

ORDEM_EVENTO = {"gerado": 0, "reabertura": 1, "remetido": 2, "recebido": 3, "conclusao": 9}
HUB = SECRETARIA  # secretaria (perfil): passagem obrigatória, retorno a ela não é iteração
NAT_PRIORIDADE = ["decisao", "analise", "fiscalizacao", "instrucao", "comunicacao", "juntada", "tramitacao"]
HORAS_DIA = 6.0  # horas produtivas por dia útil (hipótese para a razão trabalho/espera)


def montar_estadias(and_proc: pd.DataFrame, corte: pd.Timestamp) -> list[dict]:
    ev = and_proc.copy()
    tipos = [tipo_andamento(s) for s in ev["descricao"]]
    ev["evento"] = [k for k, _ in tipos]
    ev["origem"] = [o for _, o in tipos]
    ev["ord"] = ev["evento"].map(ORDEM_EVENTO).fillna(5)
    ev = ev.sort_values(["data_hora", "ord"], kind="stable")

    abertas: dict[str, dict] = {}
    estadias: list[dict] = []
    ultima: dict[str, dict] = {}

    def abrir(u, t, motivo, origem=None):
        e = dict(unidade=u, entrada=t, recebido=pd.NaT, saida=pd.NaT, motivo_entrada=motivo,
                 origem=origem, motivo_saida=None, destino=None, mantida_aberta=False,
                 n_acesso_externo=0, motivos_acesso=[], n_anexacao=0)
        abertas[u] = e
        estadias.append(e)
        ultima[u] = e
        return e

    def fechar(u, t, motivo, destino=None):
        e = abertas.pop(u)
        e["saida"], e["motivo_saida"], e["destino"] = t, motivo, destino

    for r in ev.itertuples():
        u, t, k = r.unidade, r.data_hora, r.evento
        if k == "gerado":
            if u not in abertas:
                abrir(u, t, "geracao")
        elif k == "remetido":
            if u not in abertas:
                abrir(u, t, "remessa", r.origem)
            if r.origem in abertas and r.origem != u:
                fechar(r.origem, t, "remessa", u)
        elif k == "recebido":
            e = abertas.get(u) or abrir(u, t, "recebimento")
            if pd.isna(e["recebido"]):
                e["recebido"] = t
        elif k == "reabertura":
            if u not in abertas:
                abrir(u, t, "reabertura")
        elif k == "conclusao":
            if u in abertas:
                fechar(u, t, "conclusao")
            elif u in ultima and ultima[u]["motivo_saida"] == "remessa":
                ultima[u]["saida"], ultima[u]["mantida_aberta"] = t, True
        else:
            e = abertas.get(u) or ultima.get(u)
            if e is not None:
                if k == "acesso_externo":
                    e["n_acesso_externo"] += 1
                    e["motivos_acesso"].append(motivo_acesso_externo(r.descricao))
                elif k == "anexacao":
                    e["n_anexacao"] += 1
    for e in estadias:
        e["em_aberto"] = pd.isna(e["saida"])
        e["saida_calc"] = corte if e["em_aberto"] else e["saida"]
    return estadias


def atribuir_documentos(docs: pd.DataFrame, estadias: list[dict]) -> pd.DataFrame:
    """Liga cada documento à estadia da unidade que o juntou (data de inclusão dentro da estadia;
    senão, a estadia mais próxima da mesma unidade)."""
    por_unidade = defaultdict(list)
    for i, e in enumerate(estadias):
        por_unidade[e["unidade"]].append(i)
    idx, ajuste = [], []
    for r in docs.itertuples():
        d = r.data_inclusao if pd.notna(r.data_inclusao) else r.data
        cands = por_unidade.get(r.unidade, [])
        if pd.isna(d) or not cands:
            idx.append(np.nan)
            ajuste.append("sem_estadia")
            continue
        dd = d.normalize()
        dentro = [i for i in cands
                  if estadias[i]["entrada"].normalize() <= dd <= estadias[i]["saida_calc"].normalize()]
        if dentro:
            idx.append(max(dentro, key=lambda i: estadias[i]["entrada"]))
            ajuste.append("dentro")
        else:
            dist = [(min(abs((estadias[i]["entrada"].normalize() - dd).days),
                         abs((estadias[i]["saida_calc"].normalize() - dd).days)), i) for i in cands]
            idx.append(min(dist)[1])
            ajuste.append("proxima")
    out = docs.copy()
    out["estadia_idx"] = idx
    out["atribuicao"] = ajuste
    return out


def _unir(ints) -> float:
    """Dias úteis cobertos por uma lista de intervalos (unidos, sem contar em dobro)."""
    ints = sorted((a, b) for a, b in ints if pd.notna(a) and pd.notna(b) and b > a)
    if not ints:
        return 0.0
    tot, (a, b) = 0.0, ints[0]
    for c, d in ints[1:]:
        if c <= b:
            b = max(b, d)
        else:
            tot += dias_uteis(a, b)
            a, b = c, d
    return tot + dias_uteis(a, b)


# RECEPCAO (perfil): unidades que recebem e juntam correspondência externa


def janelas_espera_externa(docs: pd.DataFrame, prazos: dict | None = None,
                            detalhe: list | None = None) -> tuple[float, float, float]:
    """(resposta de terceiros, indeterminado, atraso de juntada) em dias úteis, intervalos unidos.

    Para cada ofício ou notificação, o intervalo vai até a próxima resposta. Conta como resposta de
    terceiros só se o ofício dá prazo a terceiro (ficha da peça), a data real da resposta é conhecida e só até
    o prazo + 5 du; o excesso, o intervalo sem data real e o ofício sem texto ficam indeterminados (não dá para
    separar espera de terceiros de processo parado). Ofício lido que não pede nada não abre janela.
    detalhe: se passado, recebe uma linha por ofício (resposta, prazo, situação) para auditoria.
    Atraso de juntada: da data real de cada correspondência recebida (carta, petição, manifestação; anexos
    não, porque a data deles é a do conteúdo, não a do recebimento) até a juntada no SEI — espera interna."""
    prazos = prazos or {}
    # só ofícios e notificações EMITIDOS pela agência abrem janela (ofício de outro órgão é resposta, não pedido)
    of = docs[docs["categoria"].isin(["oficio", "notificacao_autuacao"])
              & docs["unidade"].fillna("").str.startswith(ORGAO + "/")].dropna(subset=["data_efetiva"])
    # resposta = correspondência externa, petição protocolada em processo relacionado (peticionamento) ou anexo
    # recebido por unidade de protocolo; recibos, comprovantes e anexos produzidos pela própria unidade não são
    sig = docs["unidade"].fillna("").str.split("/").str[-1]
    resp = ((docs["categoria"].eq("peca_externa") | docs["categoria"].eq("processo_relacionado")
             | (docs["categoria"].eq("anexo") & sig.isin(RECEPCAO)))
            & ~docs.get("pede_prorrogacao", pd.Series(False, index=docs.index)).astype(bool))
    ext = docs[resp].copy()
    ext.loc[ext["categoria"].isin(["processo_relacionado", "anexo"]), "data_real_conhecida"] = True
    ext = ext.sort_values("data_efetiva")
    conf, indet = [], []
    for o in of.sort_values("data_efetiva").itertuples():
        s_ = o.data_efetiva
        prox = ext[ext["data_efetiva"] > s_]
        if not len(prox):
            continue
        r = prox.iloc[0]
        p = prazos.get(str(o.numero))
        linha = dict(oficio=str(o.numero), oficio_data=s_, resposta=str(r["numero"]), resposta_categoria=r["categoria"],
                     resposta_data=r["data_efetiva"], prazo_dias=p, terceiros_du=0, indeterminado_du=0)
        if not r["data_real_conhecida"]:
            indet.append((s_, r["data_efetiva"]))
            linha.update(situacao="indeterminado: resposta sem data real", indeterminado_du=dias_uteis(s_, r["data_efetiva"]))
        elif p == 0:  # ofício lido e sem prazo/pedido a terceiro (comunicação, acuse): não abre janela
            linha.update(situacao="sem janela: ofício sem prazo a terceiro")
        elif p is None:  # ofício sem texto: não se sabe se pedia algo — tudo indeterminado
            indet.append((s_, r["data_efetiva"]))
            linha.update(situacao="indeterminado: ofício sem ficha", indeterminado_du=dias_uteis(s_, r["data_efetiva"]))
        else:
            limite = somar_du(s_, p + 5)
            conf.append((s_, min(r["data_efetiva"], limite)))
            linha.update(situacao="terceiros", terceiros_du=dias_uteis(s_, min(r["data_efetiva"], limite)))
            if r["data_efetiva"] > limite:
                indet.append((limite, r["data_efetiva"]))
                linha.update(situacao="terceiros até prazo + 5 du; excesso indeterminado",
                             indeterminado_du=dias_uteis(limite, r["data_efetiva"]))
        if detalhe is not None:
            detalhe.append(linha)
    rec = docs[docs["categoria"] == "peca_externa"]
    atraso = list(zip(rec["data_efetiva"], rec["data_inclusao"]))
    return _unir(conf), _unir(indet), _unir(atraso)


def prazos_dos_oficios() -> dict:
    """sei_doc_id → maior prazo (dias) dado a concessionária, usuário ou órgão externo, das fichas de trabalho;
    0 = peça lida e sem prazo a terceiros. Peças sem ficha ficam fora (desconhecido)."""
    arq = SAIDA / "fichas_trabalho.jsonl"
    out = {}
    if arq.exists():
        import json
        for ln in open(arq, encoding="utf-8"):
            d = json.loads(ln)
            ps = [x.get("dias") for x in d["ficha"].get("prazos") or []
                  if isinstance(x, dict) and x.get("ancorado") and x.get("beneficiario") != "unidade_interna"
                  and x.get("natureza") != "prorrogacao"
                  and isinstance(x.get("dias"), (int, float))]
            out[str(d["sei_doc_id"])] = max(ps) if ps else 0
    return out


RE_PRORROGACAO = re.compile(r"prorroga|dila[çc][aã]o|dilata|prazo adicional|mais prazo|novo prazo|"
                            r"extens[aã]o (?:do|de) prazo", re.I)


def data_da_peca(v) -> pd.Timestamp:
    """Data escrita na peça: ISO (AAAA-MM-DD) ou brasileira (dia primeiro: 05-03-2024 é 5 de março); fora de
    2000–2035 é erro de leitura e vira NaT."""
    v = str(v or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        dt = pd.to_datetime(v, format="%Y-%m-%d", errors="coerce")
    elif re.fullmatch(r"\d{1,2}[-/.]\d{1,2}[-/.]\d{4}", v):
        dt = pd.to_datetime(re.sub(r"[-/.]", "/", v), format="%d/%m/%Y", errors="coerce")
    else:
        return pd.NaT
    return dt if pd.notna(dt) and 2000 <= dt.year <= 2035 else pd.NaT


def datas_reais() -> tuple[dict, set]:
    """Da análise do relator por peça: (processo, sei_doc_id) → data escrita na peça; e o conjunto de peças cujo
    pedido é prorrogação de prazo (não são resposta ao ofício)."""
    arq = DADOS / "relator" / "extractions.parquet"
    if not arq.exists():
        return {}, set()
    import json
    e = pd.read_parquet(arq, columns=["processo", "sei_doc_id", "extraction_json"])
    out, prorroga = {}, set()
    for p, s_, j in zip(e.processo, e.sei_doc_id, e.extraction_json):
        x = json.loads(j)
        dt = data_da_peca(x.get("data"))
        if pd.notna(dt):
            out[(p, str(s_))] = dt
        pedidos = " ".join(str(v) for v in (x.get("pedidos_e_determinacoes") or []))
        if RE_PRORROGACAO.search(pedidos) and str(x.get("acao_processual") or "").lower().startswith(("requer", "solicit")):
            prorroga.add((p, str(s_)))
    return out, prorroga


SEM_UNIDADE = "SEM UNIDADE"


def montar_posse(estadias: list[dict], docs: pd.DataFrame, fim: pd.Timestamp) -> list[dict]:
    """Partição do tempo do processo sem sobreposição. Em cada instante, a posse é da unidade que abriu o
    processo mais recentemente ENTRE AS QUE O TÊM ABERTO (estadias). Quando nenhuma unidade o tem aberto
    (todas concluíram), o período é "SEM UNIDADE": processo parado sem dono, não fila de quem concluiu."""
    est = [(e["entrada"], min(e["saida_calc"], fim), e["unidade"]) for e in estadias if e["entrada"] < fim]
    if not est:
        return []
    cortes = sorted({t for a, b, _ in est for t in (a, b)} | {fim})
    cortes = [t for t in cortes if est and t >= min(a for a, _, _ in est)]
    marcos = []
    for a, b in zip(cortes, cortes[1:]):
        meio = a + (b - a) / 2
        abertas = [(ini, u) for ini, f, u in est if ini <= meio < f]
        u = max(abertas)[1] if abertas else SEM_UNIDADE
        if not marcos or marcos[-1][0] != u:
            marcos.append((u, a))
    out = []
    for i, (u, ini) in enumerate(marcos):
        fim_i = marcos[i + 1][1] if i + 1 < len(marcos) else fim
        dj = docs[(docs.unidade == u) & (docs.categoria != "processo_relacionado")
                  & (docs.data_inclusao >= ini.normalize()) & (docs.data_inclusao <= fim_i.normalize())]
        du = dias_uteis(ini, fim_i)
        horas = dj["horas_base"].sum()
        razao = min(horas / (max(du, 1) * HORAS_DIA), 1.0)
        out.append(dict(unidade=u, sigla=sigla(u), natureza_unidade=natureza_unidade(u), inicio=ini, fim=fim_i,
                        du=du, n_docs=len(dj), horas_base=round(horas, 2), razao_trabalho=round(razao, 4),
                        espera_dominante=bool(du >= 20 and razao < 0.05),
                        fila_longa_trabalho_curto=bool(du >= 20 and horas <= 1.0)))
    return out


def main():
    p, a, d = carregar()
    corte = a["data_hora"].max()
    cat = d.apply(lambda r: pd.Series(categoria_documento(r["tipo"], r["numero"]),
                                      index=["categoria", "natureza_trabalho", "horas_base"]), axis=1)
    d = pd.concat([d, cat], axis=1)
    # data efetiva: a escrita na peça, se anterior à juntada (peça recebida e juntada depois); senão, a juntada
    reais, prorroga = datas_reais()
    prazos = prazos_dos_oficios()
    num_proc = dict(zip(p.id, p.numero))
    real = pd.Series([reais.get((num_proc.get(pi), str(n))) for pi, n in zip(d.processo_id, d.numero)], index=d.index)
    d["data_efetiva"] = d["data_inclusao"].where(~(real.notna() & (real < d["data_inclusao"])), real)
    d["data_real_conhecida"] = real.notna()
    d["pede_prorrogacao"] = [(num_proc.get(pi), str(n)) in prorroga for pi, n in zip(d.processo_id, d.numero)]

    linhas_est, linhas_doc, linhas_proc, linhas_posse, linhas_jan = [], [], [], [], []
    for proc in p.itertuples():
        ap = a[a.processo_id == proc.id]
        dp = d[d.processo_id == proc.id].copy()
        est = montar_estadias(ap, corte)
        dp = atribuir_documentos(dp, est)
        for i, e in enumerate(est):
            e["idx"] = i
            ds = dp[dp.estadia_idx == i]
            reais = ds[ds.categoria != "processo_relacionado"]
            e["n_docs"] = len(reais)
            e["horas_base"] = reais["horas_base"].sum()
            e["categorias"] = "; ".join(f"{k}:{v}" for k, v in reais["categoria"].value_counts().items())
            nats = set(reais["natureza_trabalho"])
            e["perfil"] = next((n for n in NAT_PRIORIDADE if n in nats), "passagem")
            e["primeiro_doc"] = reais["data_inclusao"].min()
            e["ultimo_doc"] = reais["data_inclusao"].max()
            e["lead_dias"] = (e["saida_calc"] - e["entrada"]).total_seconds() / 86400
            e["lead_du"] = dias_uteis(e["entrada"], e["saida_calc"])
            e["espera_1a_juntada_du"] = dias_uteis(e["entrada"], e["primeiro_doc"])
            e["cauda_du"] = dias_uteis(e["ultimo_doc"], e["saida_calc"])
            cap = max(e["lead_du"], 1) * HORAS_DIA
            e["razao_trabalho"] = min(e["horas_base"] / cap, 1.0)
            # acompanhamento: a unidade manteve o processo aberto ao remeter, ou reabriu só para consultar
            e["acompanhamento"] = bool(e["mantida_aberta"] or (e["motivo_entrada"] == "reabertura" and e["n_docs"] == 0))
            longa = e["lead_du"] >= 20 and not e["acompanhamento"]
            e["fila_longa_trabalho_curto"] = bool(longa and e["horas_base"] <= 1.0)
            # espera dominante: permanência longa em que o trabalho estimado ocupa < 5% da capacidade
            e["espera_dominante"] = bool(longa and e["razao_trabalho"] < 0.05)
        for e in est:
            linhas_est.append(dict(numero=proc.numero, idx=e["idx"], unidade=e["unidade"], sigla=sigla(e["unidade"]),
                                   natureza_unidade=natureza_unidade(e["unidade"]), entrada=e["entrada"],
                                   recebido=e["recebido"], saida=e["saida"], em_aberto=e["em_aberto"],
                                   motivo_entrada=e["motivo_entrada"], origem=e["origem"],
                                   motivo_saida=e["motivo_saida"], destino=e["destino"],
                                   mantida_aberta=e["mantida_aberta"], acompanhamento=e["acompanhamento"],
                                   lead_dias=round(e["lead_dias"], 2),
                                   lead_du=e["lead_du"], espera_1a_juntada_du=e["espera_1a_juntada_du"],
                                   cauda_du=e["cauda_du"], n_docs=e["n_docs"], categorias=e["categorias"],
                                   perfil=e["perfil"], horas_base=round(e["horas_base"], 2),
                                   razao_trabalho=round(e["razao_trabalho"], 4),
                                   fila_longa_trabalho_curto=e["fila_longa_trabalho_curto"],
                                   espera_dominante=e["espera_dominante"],
                                   n_acesso_externo=e["n_acesso_externo"],
                                   motivos_acesso="; ".join(sorted(set(e["motivos_acesso"]))),
                                   n_anexacao=e["n_anexacao"]))
        dp["numero_processo"] = proc.numero
        linhas_doc.append(dp)

        # ------------------------------------------------ indicadores do processo
        df_e = pd.DataFrame(linhas_est[-len(est):]) if est else pd.DataFrame()
        reais = dp[dp.categoria != "processo_relacionado"]
        inicio = min([x for x in [proc.data_geracao, ap["data_hora"].min()] if pd.notna(x)], default=pd.NaT)
        fim = ap["data_hora"].max()
        ativas = df_e[df_e.n_docs > 0].sort_values("entrada") if len(df_e) else df_e
        seq = []
        for s in (ativas["sigla"] if len(ativas) else []):
            if not seq or seq[-1] != s:
                seq.append(s)
        nao_hub = [s for s in seq if s not in HUB]
        retornos = len(nao_hub) - len(set(nao_hub))
        pingpong = sum(1 for i in range(len(nao_hub) - 2) if nao_hub[i] == nao_hub[i + 2])
        encerrado = bool((reais["categoria"] == "termo_encerramento").any()
                         or (len(df_e) > 0 and not df_e["em_aberto"].any()))
        lead_du = dias_uteis(inicio, fim)
        horas = reais["horas_base"].sum()
        posse = pd.DataFrame(montar_posse(est, dp, fim if encerrado else corte))
        if len(posse):
            posse.insert(0, "numero", proc.numero)
            linhas_posse.append(posse)
        fila = posse[posse.fila_longa_trabalho_curto] if len(posse) else posse
        espera = posse[posse.espera_dominante] if len(posse) else posse
        du_posse = posse.groupby("natureza_unidade")["du"].sum() if len(posse) else pd.Series(dtype=float)
        tot_posse = du_posse.sum() or np.nan
        motivos = df_e["motivos_acesso"].str.cat(sep="; ") if len(df_e) else ""
        linhas_proc.append(dict(
            numero=proc.numero, tipo=proc.tipo, natureza=proc.natureza, assunto=proc.assunto,
            interessado=proc.interessado, concessionaria=proc.concessionaria, status_gabinete=proc.status,
            data_geracao=proc.data_geracao, inicio=inicio, ultimo_andamento=fim,
            nativo_sei=bool(pd.notna(proc.data_geracao) and proc.data_geracao >= INICIO_SEI),
            encerrado=encerrado, lead_dias=(fim - inicio).days if pd.notna(inicio) and pd.notna(fim) else np.nan,
            lead_du=lead_du, n_andamentos=len(ap), n_docs=len(reais),
            n_processos_relacionados=int((dp.categoria == "processo_relacionado").sum()),
            n_estadias=len(df_e), n_estadias_ativas=int((df_e.n_docs > 0).sum()) if len(df_e) else 0,
            n_unidades=df_e["unidade"].nunique() if len(df_e) else 0,
            n_unidades_ativas=ativas["unidade"].nunique() if len(ativas) else 0,
            n_unidades_externas=int(df_e["natureza_unidade"].str.startswith("Externo").sum()) if len(df_e) else 0,
            sequencia_ativa=" → ".join(seq), retornos_iteracao=retornos, pingpong=pingpong,
            n_oficios=int((reais.categoria == "oficio").sum()),
            n_pecas_externas=int(reais.categoria.isin(["peca_externa", "anexo", "registro_entrada"]).sum()),
            n_acesso_externo=int(df_e["n_acesso_externo"].sum()) if len(df_e) else 0,
            n_vista_razoes=motivos.count("vista") + motivos.count("razoes_finais"),
            n_pareceres=int((reais.categoria == "parecer").sum()),
            n_relatorios=int(reais.categoria.isin(["relatorio", "relatorio_fiscalizacao", "nota_tecnica"]).sum()),
            tem_voto=bool((reais.categoria == "voto").any()),
            tem_deliberacao=bool((reais.categoria == "deliberacao").any()),
            tem_fiscalizacao=bool(reais.categoria.isin(["relatorio_fiscalizacao", "notificacao_autuacao"]).any()),
            horas_base=round(horas, 1),
            eficiencia_ciclo=round(horas / max(lead_du * HORAS_DIA, 1), 4) if pd.notna(lead_du) else np.nan,
            **dict(zip(["espera_externa_du", "espera_indeterminada_du", "atraso_juntada_du"],
                       janelas_espera_externa(dp, prazos, jan := []))),
            n_filas_longas=len(fila), du_em_filas_longas=fila["du"].sum() if len(fila) else 0,
            maior_fila_unidade=(fila.sort_values("du").iloc[-1]["sigla"] if len(fila) else None),
            maior_fila_du=(fila["du"].max() if len(fila) else 0),
            n_esperas_dominantes=len(espera), du_em_espera_dominante=espera["du"].sum() if len(espera) else 0,
            pct_tempo_espera_dominante=round(100 * espera["du"].sum() / tot_posse, 1) if len(espera) else 0.0,
            maior_espera_unidade=(espera.sort_values("du").iloc[-1]["sigla"] if len(espera) else None),
            maior_espera_du=(espera["du"].max() if len(espera) else 0),
            **{f"pct_posse_{k}": round(100 * du_posse.get(n, 0) / tot_posse, 1) for k, n in [
                ("secretaria", "Secretaria Executiva"), ("camaras", "Câmara técnica"), ("procuradoria", "Procuradoria"),
                ("gabinetes", "Gabinete de conselheiro"), ("codir", "Conselho-Diretor"), ("presidencia", "Presidência"),
                ("ouvidoria", "Ouvidoria")]},
            pct_posse_externos=round(100 * du_posse[du_posse.index.str.startswith("Externo")].sum() / tot_posse, 1)
            if len(du_posse) else np.nan,
            docs_sem_estadia=int((dp.atribuicao == "sem_estadia").sum()),
        ))
        linhas_jan += [dict(numero_processo=proc.numero, **j) for j in jan]

    est = pd.DataFrame(linhas_est)
    docs = pd.concat(linhas_doc, ignore_index=True)
    procs = pd.DataFrame(linhas_proc)
    est.to_csv(SAIDA / "estadias.csv", index=False, encoding="utf-8-sig")
    docs.drop(columns=["processo_id"]).to_csv(SAIDA / "documentos.csv", index=False, encoding="utf-8-sig")
    procs.to_csv(SAIDA / "processos_indicadores.csv", index=False, encoding="utf-8-sig")
    pd.concat(linhas_posse, ignore_index=True).to_csv(SAIDA / "posse.csv", index=False, encoding="utf-8-sig")
    # janelas de terceiros por ofício: lastro auditável dos totais espera_externa_du / espera_indeterminada_du
    pd.DataFrame(linhas_jan).to_csv(SAIDA / "janelas_terceiros.csv", index=False, encoding="utf-8-sig")
    print(f"corte={corte}  processos={len(procs)}  estadias={len(est)} (ativas {int((est.n_docs > 0).sum())})"
          f"  documentos={len(docs)}")
    print("atribuição dos documentos:", docs["atribuicao"].value_counts().to_dict())
    print("estadias em aberto:", int(est["em_aberto"].sum()), " mantidas abertas:", int(est["mantida_aberta"].sum()))


if __name__ == "__main__":
    main()
