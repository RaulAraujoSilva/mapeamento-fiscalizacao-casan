"""Portão de qualidade da coleta: confere se as tabelas em dados/sei2_dump/ (e, se houver, dados/relator/) servem ao
pipeline antes de rodar `scripts/pipeline.py`.

Lê as TSVs exatamente como o pipeline lê (`scripts/comum.py::carregar`) e classifica cada andamento com a mesma
função (`comum.tipo_andamento`). O sinal mais importante é a fração de andamentos com frase NÃO reconhecida: se for
alta, ou se um evento essencial (geração, remessa, recebimento, conclusão) não aparece em nenhum processo, a redação
dos andamentos do seu SEI difere da canônica e o perfil do Estado precisa de uma `RegraAndamento` (ver
coleta/perfil_sei.py). O relatório lista as frases não reconhecidas mais frequentes, já com números e unidades
trocados por marcadores, para facilitar escrever a regra.

Checagens (limiar padrão; sai com código 1 se alguma reprovar):
  esquema                    colunas das TSVs, ids únicos, chaves que apontam para processo existente   (0 falha)
  processos_sem_andamento    fração de processos sem nenhum andamento                                  (≤ 5%)
  andamentos_nao_reconhecidos fração de andamentos que tipo_andamento classifica como "outro"          (≤ 25%)
  eventos_essenciais         gerado/remetido/recebido/conclusao presentes na coleta (≥ 20 andamentos)  (todos)
  datas_fora_de_ordem        andamento sem data, antes da geração do processo ou no futuro; documento
                             incluído antes da geração                                                 (≤ 2%)
  unidades_sem_prefixo       unidades sem "ORGAO/" em andamentos e protocolos                          (≤ 5%)
  documentos_sem_unidade     protocolos sem unidade                                                    (≤ 5%)
  cobertura_texto            média de cobertura_substantivas (dados/relator/cobertura_texto.csv)       (≥ 30%)
  falhas_download            fração de documentos com download_status = failed                         (≤ 10%)

Uso:
  python -m coleta.validar_coleta --perfil RJ
  python -m coleta.validar_coleta --perfil RJ --max-nao-reconhecidos 0.10 --json saida/validacao_coleta.json"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from coleta.perfil_sei import EVENTOS_ESSENCIAIS, PerfilSEI, carregar_perfil
from coleta.util import COLUNAS, DUMP, RELATOR, comum

LIMIARES = dict(max_sem_andamento=0.05, max_nao_reconhecidos=0.25, min_andamentos_essenciais=20,
                max_fora_de_ordem=0.02, max_sem_prefixo=0.05, max_sem_unidade=0.05, min_cobertura=0.30,
                max_falhas_download=0.10)


@dataclass
class Checagem:
    nome: str
    valor: float | int | str
    limiar: str
    ok: bool
    detalhe: list = field(default_factory=list)


def frase_modelo(descr: str) -> str:
    """Forma genérica de uma descrição para agrupar: números e unidades viram marcadores, nomes ficam cortados."""
    s = re.sub(r"\b[A-ZÀ-Ü0-9]{2,}(?:[-/][A-ZÀ-Ü0-9-]+)+\b", "<UNIDADE>", str(descr or ""))
    s = re.sub(r"\d+([./-]\d+)*", "9", s)
    return " ".join(s.split()[:7])


def carregar_dump(destino: Path):
    """(processos, andamentos, protocolos) lidos por comum.carregar apontado para `destino`."""
    c = comum()
    antigo = c.DUMP
    c.DUMP = Path(destino)
    try:
        return c.carregar()
    finally:
        c.DUMP = antigo


def validar(destino: Path = DUMP, relator: Path | None = RELATOR, perfil: PerfilSEI | None = None,
            limiares: dict | None = None, hoje=None) -> list[Checagem]:
    import pandas as pd
    lim = dict(LIMIARES, **(limiares or {}))
    c = comum()
    out: list[Checagem] = []

    # ---- esquema (antes de tudo: se não lê, o resto não faz sentido)
    problemas = []
    for nome, cols in COLUNAS.items():
        arq = Path(destino) / nome
        if not arq.exists():
            problemas.append(f"{nome} ausente")
            continue
        cab = arq.read_text(encoding="utf-8").split("\n", 1)[0].split("\t")
        if cab != cols:
            problemas.append(f"{nome}: colunas {cab} ≠ {cols}")
    if problemas:
        return [Checagem("esquema", len(problemas), "0 falha", False, problemas)]
    p, a, d = carregar_dump(destino)
    if p.id.duplicated().any():
        problemas.append(f"{int(p.id.duplicated().sum())} id(s) de processo repetido(s)")
    for nome, df in (("andamentos", a), ("protocolos", d)):
        orf = ~df.processo_id.isin(p.id)
        if orf.any():
            problemas.append(f"{int(orf.sum())} {nome} de processo inexistente")
    for col, df in (("data_hora", a), ("data_inclusao", d), ("data_geracao", p)):
        if len(df) and not pd.api.types.is_datetime64_any_dtype(df[col]):
            problemas.append(f"coluna {col} não foi lida como data (formato fora de AAAA-MM-DD)")
    out.append(Checagem("esquema", len(problemas), "0 falha", not problemas, problemas))
    if problemas:
        return out

    # ---- processos sem andamento
    sem = ~p.id.isin(a.processo_id)
    fr = float(sem.mean()) if len(p) else 0.0
    out.append(Checagem("processos_sem_andamento", round(fr, 4), f"≤ {lim['max_sem_andamento']:.0%}",
                        fr <= lim["max_sem_andamento"], list(p.numero[sem].head(10))))

    # ---- andamentos reconhecidos
    eventos = [c.tipo_andamento(s)[0] for s in a.descricao.fillna("")]
    a = a.assign(evento=eventos)
    outros = a[a.evento == "outro"]
    fr = len(outros) / len(a) if len(a) else 0.0
    top = Counter(frase_modelo(s) for s in outros.descricao.fillna(""))
    det = [f"{n / len(a):.1%}  ({n})  {f}" for f, n in top.most_common(12)]
    out.append(Checagem("andamentos_nao_reconhecidos", round(fr, 4), f"≤ {lim['max_nao_reconhecidos']:.0%}",
                        fr <= lim["max_nao_reconhecidos"], det))
    cont = Counter(eventos)
    faltam = [e for e in EVENTOS_ESSENCIAIS if cont.get(e, 0) == 0]
    aplica = len(a) >= lim["min_andamentos_essenciais"]
    out.append(Checagem("eventos_essenciais", ", ".join(f"{e}={cont.get(e, 0)}" for e in EVENTOS_ESSENCIAIS),
                        f"todos > 0 (com ≥ {lim['min_andamentos_essenciais']} andamentos)",
                        not (aplica and faltam), [f"sem nenhum '{e}': a redação local precisa de regra no perfil"
                                                  for e in faltam] if aplica else []))

    # ---- datas
    hoje = pd.Timestamp(hoje) if hoje is not None else pd.Timestamp.now()
    ger = p.set_index("id").data_geracao
    a_ger = a.processo_id.map(ger)
    ruins_a = a.data_hora.isna() | (a.data_hora.dt.normalize() < a_ger) | (a.data_hora > hoje)
    d_ger = d.processo_id.map(ger)
    ruins_d = d.data_inclusao.notna() & (d.data_inclusao.dt.normalize() < d_ger)
    total = len(a) + len(d)
    fr = (int(ruins_a.sum()) + int(ruins_d.sum())) / total if total else 0.0
    det = [f"{int(a.data_hora.isna().sum())} andamento(s) sem data/hora (formato do perfil?)",
           f"{int((a.data_hora.dt.normalize() < a_ger).sum())} andamento(s) antes da geração do processo",
           f"{int((a.data_hora > hoje).sum())} andamento(s) no futuro",
           f"{int(ruins_d.sum())} documento(s) incluído(s) antes da geração (processo físico migrado? ver INICIO_SEI)"]
    out.append(Checagem("datas_fora_de_ordem", round(fr, 4), f"≤ {lim['max_fora_de_ordem']:.0%}",
                        fr <= lim["max_fora_de_ordem"], det))

    # ---- unidades
    unid = pd.concat([a.unidade, d.unidade]).dropna()
    sem_pref = unid[~unid.str.contains("/", regex=False)]
    fr = len(sem_pref) / len(unid) if len(unid) else 0.0
    det = [f"{u} ({n})" for u, n in sem_pref.value_counts().head(10).items()]
    if perfil is not None and len(unid):
        externas = unid[unid.str.contains("/", regex=False) & ~unid.str.startswith(perfil.orgao + "/")]
        det.append(f"informativo: {len(externas) / len(unid):.1%} das menções são de unidades de outros órgãos")
    out.append(Checagem("unidades_sem_prefixo", round(fr, 4), f"≤ {lim['max_sem_prefixo']:.0%}",
                        fr <= lim["max_sem_prefixo"], det))
    fr = float(d.unidade.isna().mean()) if len(d) else 0.0
    out.append(Checagem("documentos_sem_unidade", round(fr, 4), f"≤ {lim['max_sem_unidade']:.0%}",
                        fr <= lim["max_sem_unidade"]))

    # ---- conteúdo (só se a coleta de documentos já rodou)
    if relator is not None and (Path(relator) / "cobertura_texto.csv").exists():
        cob = pd.read_csv(Path(relator) / "cobertura_texto.csv")
        media = float(cob.cobertura_substantivas.mean()) if len(cob) else 0.0
        baixa = cob[cob.cobertura_substantivas < 0.6].processo.head(10).tolist()
        out.append(Checagem("cobertura_texto", round(media, 4), f"≥ {lim['min_cobertura']:.0%}",
                            media >= lim["min_cobertura"], [f"abaixo de 60%: {x}" for x in baixa]))
    if relator is not None and (Path(relator) / "documentos.parquet").exists():
        docs = pd.read_parquet(Path(relator) / "documentos.parquet", columns=["download_status"])
        st = docs.download_status.value_counts()
        fr = float(st.get("failed", 0) / len(docs)) if len(docs) else 0.0
        out.append(Checagem("falhas_download", round(fr, 4), f"≤ {lim['max_falhas_download']:.0%}",
                            fr <= lim["max_falhas_download"], [f"{k}: {v}" for k, v in st.items()]))
    return out


def imprimir(checagens: list[Checagem]):
    for ch in checagens:
        v = f"{ch.valor:.1%}" if isinstance(ch.valor, float) else str(ch.valor)
        print(f"[{'ok ' if ch.ok else 'FALHA'}] {ch.nome:<28} {v:<40} limiar {ch.limiar}")
        for x in ch.detalhe:
            print(f"        {x}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--perfil", default="RJ")
    ap.add_argument("--destino", type=Path, default=DUMP)
    ap.add_argument("--relator", type=Path, default=RELATOR)
    ap.add_argument("--json", type=Path, help="grava o relatório em JSON")
    for k, v in LIMIARES.items():
        ap.add_argument("--" + k.replace("_", "-"), type=type(v), default=v)
    args = ap.parse_args(argv)
    perfil = carregar_perfil(args.perfil)
    lim = {k: getattr(args, k) for k in LIMIARES}
    ch = validar(args.destino, args.relator, perfil, lim)
    imprimir(ch)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps([vars(c) for c in ch], ensure_ascii=False, indent=1), encoding="utf-8")
    reprovadas = [c.nome for c in ch if not c.ok]
    if reprovadas:
        print(f"\nREPROVADO: {', '.join(reprovadas)}. Ajuste o perfil ou a coleta antes de rodar o pipeline.")
        raise SystemExit(1)
    print("\naprovado: a coleta pode seguir para scripts/pipeline.py")


if __name__ == "__main__":
    main()
