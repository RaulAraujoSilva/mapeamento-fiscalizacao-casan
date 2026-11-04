"""Volume anual por tipo de processo a partir das deliberações de toda a agência (tabela deliberacoes da base
normativa, BASE_NORMAS do perfil).

Conta processos SEI distintos cuja primeira deliberação do tipo caiu no ano. Mede também a revocação da regra na
coorte: dos processos do código que têm deliberação, quantos a regra pega.

Saída: saida/fase3/volume_anual.csv (código, ano, processos) e volume_anual.json (média, revocação)."""
from __future__ import annotations

import json
import re
import sqlite3

import pandas as pd

from comum import BASE_NORMAS, SAIDA, VOLUME_ANOS, VOLUME_REGRAS

OUT = SAIDA / "fase3"


def so_digitos(s) -> str:
    return re.sub(r"\D", "", str(s))


def main() -> None:
    if not BASE_NORMAS.exists():
        print(f"aviso: sem base normativa ({BASE_NORMAS}); volume anual não calculado (montar_base_normas.py)")
        return
    OUT.mkdir(exist_ok=True)
    con = sqlite3.connect(f"file:{BASE_NORMAS}?mode=ro", uri=True)
    d = pd.read_sql("select numero, ano, processo, tipo_decisao, tema, ementa_catalogo from deliberacoes", con)
    d["p"] = d.processo.map(so_digitos)
    d["texto"] = (d.tema.fillna("") + " " + d.ementa_catalogo.fillna("")).str.lower()
    coorte = pd.read_csv(SAIDA / "coorte_fase2.csv")
    coorte["p"] = coorte.numero.map(so_digitos)
    linhas, resumo = [], {}
    for cod, (tipos, rx) in VOLUME_REGRAS.items():
        pega = d[d.tipo_decisao.isin(tipos) & d.texto.str.contains(rx, regex=True)]
        primeira = pega.groupby("p").ano.min()
        por_ano = primeira.value_counts().sort_index()
        linhas += [dict(codigo=cod, ano=int(a), processos=int(n)) for a, n in por_ano.items()]
        nos_anos = [int(por_ano.get(a, 0)) for a in VOLUME_ANOS]
        alvo = set(coorte[coorte.processo_principal == cod].p) & set(d.p)
        resumo[cod] = dict(media_anual=round(sum(nos_anos) / len(nos_anos), 1), por_ano=dict(zip(map(str, VOLUME_ANOS), nos_anos)),
                           revocacao_coorte=round(len(alvo & set(pega.p)) / len(alvo), 3) if alvo else None,
                           coorte_com_deliberacao=len(alvo))
    pd.DataFrame(linhas).to_csv(OUT / "volume_anual.csv", index=False)
    (OUT / "volume_anual.json").write_text(json.dumps(dict(
        nota="Processos distintos com deliberação do tipo no ano, em toda a agência; piso do volume (o que não chega à "
             "deliberação não entra).", anos=VOLUME_ANOS, codigos=resumo), ensure_ascii=False, indent=1), encoding="utf-8")
    for cod, r in resumo.items():
        print(cod, r)


if __name__ == "__main__":
    main()
