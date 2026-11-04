"""Fase 2 — peças dos processos que só existem no banco do relator, no formato de saida/documentos.csv.

Esses processos não têm andamentos no SEI 2: não há estadia, posse nem espera entre unidades; as peças têm data de
inclusão, unidade e tipo, o que basta para fichas, esforço e classificação de atividade (conteúdo e execução).
Peças de apensos ficam fora (pertencem a outro processo). Data real = desconhecida (sem análise de terceiros).

Saída: saida/fase2/documentos_relator.csv"""
from __future__ import annotations

import pandas as pd

from comum import DADOS, SAIDA, categoria_documento


def _data(s: pd.Series) -> pd.Series:
    """O relator grava data brasileira (dd/mm/aaaa) ou ISO com hora; nunca ler mês-dia."""
    br = pd.to_datetime(s, format="%d/%m/%Y", errors="coerce")
    iso = pd.to_datetime(s.where(br.isna()).str[:10], format="%Y-%m-%d", errors="coerce")
    return br.fillna(iso)


def main():
    r = pd.read_parquet(DADOS / "relator" / "documentos.parquet")
    sei2 = set(pd.read_csv(SAIDA / "documentos.csv", usecols=["numero_processo"]).numero_processo)
    r = r[~r.processo.isin(sei2) & r.origem_apenso.isna()].copy()
    cat = [categoria_documento(t or "", str(n)) for t, n in zip(r.tipo, r.sei_doc_id)]
    d = pd.DataFrame(dict(
        numero=r.sei_doc_id.astype(str), tipo=r.tipo,
        data=_data(r.data), data_inclusao=_data(r.data_inclusao),
        unidade=r.unidade, descricao="", categoria=[c[0] for c in cat], natureza_trabalho=[c[1] for c in cat],
        horas_base=[c[2] for c in cat], estadia_idx=float("nan"), atribuicao="sem_trilha",
        numero_processo=r.processo))
    d["data_efetiva"] = d.data_inclusao
    d["data_real_conhecida"] = False
    d["pede_prorrogacao"] = False
    (SAIDA / "fase2").mkdir(parents=True, exist_ok=True)
    d.to_csv(SAIDA / "fase2" / "documentos_relator.csv", index=False, encoding="utf-8-sig")
    print(f"{len(d)} peças de {d.numero_processo.nunique()} processos; sem data: {d.data_inclusao.isna().sum()}")


if __name__ == "__main__":
    main()
