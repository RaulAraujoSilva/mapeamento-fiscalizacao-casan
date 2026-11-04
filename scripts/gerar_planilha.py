"""Etapa 2c — planilha da Fase 0: trilhas, indicadores, classificação e piloto.

Saída: saida/Mapeamento_SEI_Fase0.xlsx"""
from __future__ import annotations

from collections import Counter

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from comum import ORGAO, SAIDA, SECRETARIA

HUB = SECRETARIA


def por_processo_org(df: pd.DataFrame) -> pd.DataFrame:
    linhas = []
    for pid, g in df.groupby("processo_principal"):
        nativos = g[g.nativo_sei]
        variantes = Counter(g.sequencia_ativa.fillna("").map(
            lambda s: " → ".join(x for x in s.split(" → ") if x not in HUB)))
        top, freq = variantes.most_common(1)[0] if variantes else ("", 0)
        linhas.append({
            "Código": pid, "Processo organizacional": g.nome_processo.iloc[0],
            "Onda": g.onda.iloc[0], "Ranking diagnóstico": g.rank_diagnostico.iloc[0],
            "Processos SEI": len(g), "Nativos do SEI": len(nativos), "Encerrados": int(g.encerrado.sum()),
            "Elegíveis ao piloto": int(g.elegivel_piloto.sum()),
            "Lead time mediano (du, nativos)": nativos.lead_du.median(),
            "Documentos (mediana)": g.n_docs.median(),
            "Unidades ativas (mediana)": g.n_unidades_ativas.median(),
            "Com deliberação (%)": round(100 * g.tem_deliberacao.mean()),
            "Horas estimadas (mediana)": g.horas_base.median(),
            "Eficiência do ciclo (mediana, %)": round(100 * g.eficiencia_ciclo.median(), 2),
            "Dias úteis em espera dominante (mediana)": g.du_em_espera_dominante.median(),
            "Tempo em espera dominante (%, nativos)": nativos.pct_tempo_espera_dominante.median(),
            "Posse dos gabinetes (%, nativos)": nativos.pct_posse_gabinetes.median(),
            "Posse da Procuradoria (%, nativos)": nativos.pct_posse_procuradoria.median(),
            "Posse das câmaras (%, nativos)": nativos.pct_posse_camaras.median(),
            "Aguardando terceiros (du, mediana)": g.espera_externa_du.median(),
            "Retornos (média)": round(g.retornos_iteracao.mean(), 1),
            "Variante mais comum (sem a secretaria)": top, "Frequência da variante": freq,
        })
    return pd.DataFrame(linhas).sort_values(["Processos SEI"], ascending=False)


def por_unidade(est: pd.DataFrame, posse: pd.DataFrame) -> pd.DataFrame:
    e = est[est.unidade.str.startswith(ORGAO, na=False)]
    g = e.groupby("sigla")
    gp = posse[posse.unidade.str.startswith(ORGAO, na=False)].groupby("sigla")
    out = pd.DataFrame({
        "Natureza": g.natureza_unidade.first(),
        "Estadias": g.size(), "Processos": g.numero.nunique(),
        "Passagens sem documento (%)": (100 * g.n_docs.apply(lambda s: (s == 0).mean())).round(),
        "Estadias de acompanhamento": g.acompanhamento.sum(),
        "Espera até 1ª juntada, mediana (du)": g.espera_1a_juntada_du.median(),
        "Períodos de posse": gp.size(),
        "Posse total (du)": gp.du.sum(),
        "Posse mediana (du)": gp.du.median(),
        "Posse p90 (du)": gp.du.quantile(0.9).round(),
        "Posses com espera dominante": gp.espera_dominante.sum(),
        "Posse em espera dominante (du)": gp.du.apply(lambda s: s[posse.loc[s.index, "espera_dominante"]].sum()),
        "Filas longas com trabalho curto": gp.fila_longa_trabalho_curto.sum(),
        "Documentos juntados": g.n_docs.sum(),
        "Horas estimadas (proxy)": g.horas_base.sum().round(),
        "Perfil predominante": g.perfil.agg(lambda s: s[s != "passagem"].mode().iat[0] if (s != "passagem").any() else "passagem"),
    })
    return out.sort_values("Posse total (du)", ascending=False).reset_index().rename(columns={"sigla": "Unidade"})


def transicoes(est: pd.DataFrame) -> pd.DataFrame:
    """Grafo de sucessão entre estadias ativas (com documento), por ordem de entrada."""
    a = est[est.n_docs > 0].sort_values(["numero", "entrada"])
    pares = []
    for _, g in a.groupby("numero"):
        s = g[["sigla", "lead_du"]].values.tolist()
        for (u, _), (v, du) in zip(s, s[1:]):
            if u != v:
                pares.append((u, v, du))
    t = pd.DataFrame(pares, columns=["De", "Para", "du_destino"])
    return (t.groupby(["De", "Para"]).agg(Ocorrências=("du_destino", "size"),
                                          **{"Permanência mediana no destino (du)": ("du_destino", "median")})
            .reset_index().sort_values("Ocorrências", ascending=False))


LEIA_ME = [
    (f"Mapeamento de processos da {ORGAO} a partir do SEI — Fase 0", ""),
    ("Base", "251 processos SEI acompanhados pelo gabinete CONS-02 (SEI 2), andamentos até 16/06/2026"),
    ("Estadia", "Passagem de um processo por uma unidade, da entrada (remessa, geração ou reabertura) à saída (conclusão ou remessa)"),
    ("Estadia ativa / passagem", "Ativa = a unidade juntou ao menos um documento; passagem = recebeu e devolveu sem juntar"),
    ("du", "Dias úteis (feriados nacionais, do RJ e do município do Rio)"),
    ("Horas estimadas (proxy)", "Soma de horas-base por tipo de documento — hipótese a calibrar; não é tempo medido"),
    ("Eficiência do ciclo", "Horas estimadas ÷ (lead time em du × 6 h)"),
    ("Posse", "Unidade que detém o processo (gerou, recebeu a última remessa ou reabriu após o detentor concluir); particiona o lead time sem sobreposição"),
    ("Acompanhamento", "Estadia em que a unidade manteve o processo aberto ao remeter ou reabriu sem juntar nada — não conta como espera"),
    ("Espera dominante", "Período de posse ≥ 20 du em que o trabalho estimado ocupa < 5% da capacidade"),
    ("Fila longa com trabalho curto", "Espera dominante em que a unidade só juntou peças leves (≤ 1 h)"),
    ("Aguardando terceiros", "Dias úteis entre ofício/notificação e a próxima peça externa juntada"),
    ("Retornos", "Volta a uma unidade já visitada (exceto a Secretaria Executiva, passagem obrigatória)"),
    ("Nativo do SEI", "Gerado a partir de nov/2019; os anteriores têm trilha parcial (processos físicos migrados)"),
    ("Classificação", "Processo organizacional do inventário do diagnóstico (P01–P36) pelo objeto de mérito; P15 é rito transversal"),
]


def formatar(ws, larguras=None):
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="404040")
        c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for i, col in enumerate(ws.iter_cols(min_row=1, max_row=min(ws.max_row, 200)), start=1):
        w = max(len(str(c.value)) if c.value is not None else 0 for c in col)
        ws.column_dimensions[get_column_letter(i)].width = min(max(10, w + 2), (larguras or {}).get(i, 60))


def main():
    df = pd.read_csv(SAIDA / "processos_classificados.csv")
    est = pd.read_csv(SAIDA / "estadias.csv")
    posse = pd.read_csv(SAIDA / "posse.csv")
    pil = pd.read_csv(SAIDA / "piloto.csv")
    with pd.ExcelWriter(SAIDA / "Mapeamento_SEI_Fase0.xlsx", engine="openpyxl") as xw:
        pd.DataFrame(LEIA_ME, columns=["Termo", "Definição"]).to_excel(xw, sheet_name="Leia-me", index=False)
        por_processo_org(df).to_excel(xw, sheet_name="Por processo organizacional", index=False)
        pil.to_excel(xw, sheet_name="Piloto", index=False)
        cols = ["numero", "processo_principal", "nome_processo", "processo_secundario", "passa_rito_decisorio",
                "confianca", "lacuna_sugerida", "justificativa", "tipo", "natureza", "assunto", "interessado",
                "data_geracao", "nativo_sei", "encerrado", "lead_du", "n_docs", "n_estadias_ativas",
                "n_unidades_ativas", "sequencia_ativa", "retornos_iteracao", "pingpong", "n_oficios",
                "n_acesso_externo", "n_vista_razoes", "n_pareceres", "n_relatorios", "tem_voto", "tem_deliberacao",
                "horas_base", "eficiencia_ciclo", "espera_externa_du", "n_esperas_dominantes",
                "du_em_espera_dominante", "pct_tempo_espera_dominante", "maior_espera_unidade", "maior_espera_du",
                "pct_posse_secretaria", "pct_posse_camaras", "pct_posse_procuradoria", "pct_posse_gabinetes",
                "pct_posse_codir", "pct_posse_externos", "elegivel_piloto"]
        df[cols].to_excel(xw, sheet_name="Processos", index=False)
        por_unidade(est, posse).to_excel(xw, sheet_name="Por unidade", index=False)
        transicoes(est).to_excel(xw, sheet_name="Transições", index=False)
        posse.to_excel(xw, sheet_name="Posse", index=False)
        est.drop(columns=["idx"]).to_excel(xw, sheet_name="Estadias", index=False)
        for nome, ws in xw.sheets.items():
            formatar(ws, {2: 110} if nome == "Leia-me" else None)
    print("planilha:", SAIDA / "Mapeamento_SEI_Fase0.xlsx")


if __name__ == "__main__":
    main()
