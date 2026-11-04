"""Propriedades das saídas geradas (saida/, docs/site/). Rodam depois de cada geração — no pipeline, são o portão
entre gerar e publicar. Pulam se a saída ainda não existe."""
import json
import re

import pandas as pd
import pytest

import validar_avaliacao as va
from checar_bpmn import metricas, rotulos_sobrepostos
from comum import RAIZ, SAIDA

DIR = SAIDA / "bpmn"
CODS = sorted(p.stem.split("_")[1] for p in DIR.glob("fatos_*.json"))
pytestmark = pytest.mark.skipif(not CODS, reason="saídas ainda não geradas")


def _json(nome):
    return json.loads((DIR / nome).read_text(encoding="utf-8"))


# ------------------------------------------------------------------ camada A: trilha

def test_posse_sem_lacuna_nem_sobreposicao():
    po = pd.read_csv(SAIDA / "posse.csv", parse_dates=["inicio", "fim"])
    for _, g in po.groupby("numero"):
        g = g.sort_values("inicio")
        assert (g["inicio"].iloc[1:].values == g["fim"].iloc[:-1].values).all()
        assert (g["fim"] >= g["inicio"]).all()


def test_janelas_de_terceiros_cobrem_os_totais():
    j = pd.read_csv(SAIDA / "janelas_terceiros.csv")
    ind = pd.read_csv(SAIDA / "processos_indicadores.csv").set_index("numero")
    soma = j.groupby("numero_processo")[["terceiros_du", "indeterminado_du"]].sum()
    for n, r in ind[ind.espera_externa_du > 0].iterrows():
        # total é a união dos intervalos: nunca maior que a soma das janelas
        assert r.espera_externa_du <= soma.loc[n, "terceiros_du"] + 1e-9, n
    assert not j["resposta_categoria"].isin(["oficio", "despacho"]).any()


def test_metrica_de_juntada_saiu_das_conclusoes():
    for c in CODS:
        assert not any("juntada" in f["id"] for f in _json(f"fatos_{c}.json")["fatos"]), c


# ------------------------------------------------------------------ camada B: fichas de trabalho

def test_fichas_sao_v2_e_legado_so_ancorado():
    for ln in open(SAIDA / "fichas_trabalho.jsonl", encoding="utf-8"):
        d = json.loads(ln)
        assert d["prompt_versao"] == "ficha-v2", d["sei_doc_id"]
        f = d["ficha"]
        for k in ("insumos", "competencias", "sinais_perda"):
            assert all(x.get("ancorado") for x in f.get(k) or []), (d["sei_doc_id"], k)


# ------------------------------------------------------------------ linha do tempo e fatos

@pytest.mark.parametrize("cod", CODS)
def test_fatos_consistentes(cod):
    fatos = {f["id"]: f["valor"] for f in _json(f"fatos_{cod}.json")["fatos"]}
    for k, v in fatos.items():
        if isinstance(v, (int, float)):
            assert v >= 0, k
    # espera antes = soma das parcelas por unidade com a posse
    for k, v in fatos.items():
        if k.endswith(".espera_antes"):
            partes = [x for kk, x in fatos.items() if kk.startswith(k + ".")]
            if partes:
                assert abs(sum(partes) - v) <= 1, (k, v, sum(partes))
    if (DIR / f"fichas_{cod}.json").exists():  # tipo com caso-piloto; tipo novo pode não ter carteira na fase 0
        assert "carteira.lead_mediano_nativos" in fatos and "carteira.lead_mediano_todos" in fatos


# ------------------------------------------------------------------ modelos e fichas de atividade

@pytest.mark.parametrize("cod", CODS)
def test_modelo_sem_numeros_dos_agentes(cod):
    for e in _json(f"modelo_{cod}.json")["elementos"]:
        assert not {"freq", "du", "horas", "nota", "status"} & set(e), (cod, e["id"])


@pytest.mark.parametrize("cod", CODS)
def test_tramite_de_outra_unidade_fica_fora_do_tempo_e_das_horas(cod):
    # peças de outra unidade só aparecem como trâmite associado; se a atividade tem peça na raia, nenhuma unidade
    # do trâmite é a da raia (senão a peça teria sido contada em tempo e horas)
    if not (DIR / f"fichas_{cod}.json").exists():
        pytest.skip("tipo sem caso-piloto: sem ficha de atividade")
    modelo = {e["id"]: e for e in _json(f"modelo_{cod}.json")["elementos"]}
    for t, a in _json(f"fichas_{cod}.json")["atividades"].items():
        raia = modelo[t]["raia"].upper()
        for x in a.get("tramite_associado") or []:
            un = re.search(r"\(([^()]+)\)$", x).group(1).upper()
            assert un not in raia, (cod, t, x)


@pytest.mark.parametrize("cod", CODS)
def test_bpmn_sem_seta_atravessando_elemento(cod):
    atravessa, _, _ = metricas(str(DIR / f"{cod}.bpmn"))
    assert atravessa == 0


@pytest.mark.parametrize("arq", sorted(DIR.glob("*.bpmn")), ids=lambda p: p.stem)
def test_bpmn_rotulo_de_fluxo_nao_cobre_forma_nem_rotulo(arq):
    assert rotulos_sobrepostos(str(arq)) == 0


@pytest.mark.parametrize("cod", sorted(p.stem.split("_")[1] for p in (SAIDA / "fase2").glob("procedimento_*.json")))
def test_bpmn_da_coorte_mostra_percentuais_que_batem_com_o_procedimento(cod):
    from gerar_bpmn import probabilidades_ramos
    p = json.loads((SAIDA / "fase2" / f"procedimento_{cod}.json").read_text(encoding="utf-8"))
    xml = (DIR / f"{cod}.bpmn").read_text(encoding="utf-8")
    assert f"{p['casos']} casos" in xml
    for i, (_, pct) in probabilidades_ramos(_json(f"modelo_{cod}.json"), p["transicoes"]).items():
        assert re.search(rf'sequenceFlow id="F{i}" name="[^"]*{pct}%"', xml)


# ------------------------------------------------------------------ camada F: avaliações

@pytest.mark.parametrize("cod", sorted(p.stem.split("_")[1] for p in (SAIDA / "fase2").glob("procedimento_*.json")))
def test_fatos_da_coorte_batem_com_o_procedimento(cod):
    """Os fatos coorte.* (única fonte de números da avaliação) são cópia fiel do procedimento da coorte."""
    p = json.loads((SAIDA / "fase2" / f"procedimento_{cod}.json").read_text(encoding="utf-8"))
    f = {x["id"]: x["valor"] for x in json.loads((DIR / f"fatos_{cod}.json").read_text(encoding="utf-8"))["fatos"]}
    assert f["coorte.casos"] == p["casos"]
    for t, a in p["atividades"].items():
        assert f[f"coorte.{t}.pct_casos"] == a["pct_casos"]
        if a["espera_antes_du"]:
            assert f[f"coorte.{t}.espera_antes.mediana"] == a["espera_antes_du"]["mediana"]
    for k, d in (p.get("por_caso_nativo") or {}).items():
        assert f[f"coorte.caso.{k}.mediana"] == d["mediana"]


@pytest.mark.parametrize("cod", sorted(p.stem.split("_")[1] for p in DIR.glob("avaliacao_*.json")))
def test_avaliacao_ancorada_e_carimbada(cod):
    p = va.validar(cod, exigir_carimbo=True)
    if not (va.DADOS / "relator" / "doc_text_piloto.parquet").exists():
        # clone sem dados/ (fora do git): datas citadas do texto das peças não têm como ser conferidas aqui
        p = [x for x in p if not re.search(r": data \d{2}/\d{2}/\d{4} (sem lastro|não aparece)", x)]
    assert p == []


def test_auditoria_automatica_dentro_dos_limites():
    a = json.loads((SAIDA / "auditoria" / "auditoria_automatica.json").read_text(encoding="utf-8"))
    assert a["A_trilha"]["posse_com_lacuna_ou_sobreposicao"] == 0
    assert a["A_trilha"]["unidade_diverge"] == 0 and a["A_trilha"]["data_diverge"] == 0
    assert a["B_fichas"]["pct_sem_ancora"] <= 1.0
    assert a["D_modelos"]["freq_diverge"] == 0


# ------------------------------------------------------------------ site

SITE = RAIZ / "docs" / "site" / "index.html"


@pytest.mark.skipif(not SITE.exists(), reason="site não gerado")
def test_site_sem_dados_pessoais_nem_campos_antigos():
    s = SITE.read_text(encoding="utf-8")
    assert not re.search(r"\d{3}\.\d{3}\.\d{3}-\d{2}", s), "CPF"
    assert not re.search(r"[\w.+-]+@(?:gmail|hotmail|yahoo|outlook|bol|uol)\.", s, re.I), "e-mail pessoal"
    assert not re.search(r"\(\d{2}\)\s?9\d{4}-\d{4}", s), "celular"
    for campo in ("atraso_juntada", "permanencia_du", "estadia_du"):
        assert campo not in s, campo


# ------------------------------------------------------------------ fase 2: do caso ao procedimento

F2 = SAIDA / "fase2"
COD_F2 = sorted(p.stem.split("_")[1] for p in F2.glob("atribuicoes_*.csv"))


def test_coorte_sem_processo_duplicado():
    co = pd.read_csv(SAIDA / "coorte_fase2.csv")
    assert co.numero.is_unique
    dup = F2 / "duplicados.csv"
    if dup.exists():
        assert not set(pd.read_csv(dup).numero) & set(co.numero)


@pytest.mark.parametrize("cod", COD_F2)
def test_modelo_fase2_completo(cod):
    m = _json(f"modelo_{cod}.json")
    ids = [e["id"] for e in m["elementos"]]
    raias = {r["id"] for r in m["raias"]}
    assert len(ids) == len(set(ids)) and len(ids) <= 25
    assert all(e["raia"] in raias for e in m["elementos"])
    assert all(f["de"] in ids and f["para"] in ids for f in m["fluxos"])
    if not (DIR / f"vinculos_{cod}.json").exists():  # tipo novo: o classificador depende de gatilho e saída
        assert all(e.get("gatilho") and e.get("saida") for e in m["elementos"] if e["tipo"] == "tarefa")


@pytest.mark.parametrize("cod", COD_F2)
def test_atribuicao_so_com_rotulo_valido_e_na_raia(cod):
    from fatos import na_raia
    m = _json(f"modelo_{cod}.json")
    raias = {r["id"]: (r["id"] + " " + r["nome"]).upper() for r in m["raias"]}
    tarefas = {e["id"]: e for e in m["elementos"] if e["tipo"] == "tarefa"}
    a = pd.read_csv(F2 / f"atribuicoes_{cod}.csv")
    assert set(a.atividade) <= set(tarefas) | {"fora_do_modelo", "fora_da_raia"}
    co = pd.read_csv(SAIDA / "coorte_fase2.csv")
    assert set(a.processo) <= set(co[co.processo_principal == cod].numero)
    t = a[a.atividade.isin(tarefas)]
    assert all(na_raia(u, raias[tarefas[x]["raia"]]) for u, x in zip(t.unidade, t.atividade))


@pytest.mark.parametrize("cod", COD_F2)
def test_procedimento_consistente(cod):
    p = json.loads((F2 / f"procedimento_{cod}.json").read_text(encoding="utf-8"))
    assert sum(p["trilha"].values()) == p["casos"]
    assert sum(v["casos"] for v in p["caminhos"]) <= p["casos"] and p["n_caminhos"] <= p["casos"]
    for a in p["atividades"].values():
        assert 0 <= a["pct_casos"] <= 100 and a["casos"] + a["ausente_em"] == p["casos"]
        for k in ("execucao_du", "espera_antes_du", "horas_piso"):
            d = a[k]
            assert d is None or (0 <= d["q1"] <= d["mediana"] <= d["q3"] <= d["max"])
    for saidas in p["transicoes"].values():
        tot = sum(s["n"] for s in saidas)
        assert all(abs(s["pct"] - 100 * s["n"] / tot) <= 0.5 for s in saidas)


def test_auditoria_do_classificador_atinge_criterio():
    arq = F2 / "auditoria_classificador.json"
    if not arq.exists():
        pytest.skip("auditoria do classificador ainda não feita")
    t = json.loads(arq.read_text(encoding="utf-8"))["resumo"]["_total"]
    assert t["concordancia_substantivas"] >= t["criterio"]


# ------------------------------------------------------------------ fase 3: conformidade, benchmarking, linha de base

F3 = SAIDA / "fase3"
COD_F3 = sorted(p.stem.split("_")[1] for p in F3.glob("normas_*.json"))


@pytest.mark.parametrize("cod", COD_F3)
def test_requisitos_testam_atividades_do_modelo(cod):
    from conformidade import avaliar  # noqa: F401
    tarefas = {e["id"] for e in _json(f"modelo_{cod}.json")["elementos"] if e["tipo"] == "tarefa"}
    n = json.loads((F3 / f"normas_{cod}.json").read_text(encoding="utf-8"))
    ids_normas = {x["id"] for x in n["normas"]}
    for r in n["requisitos"]:
        t = r["teste"]
        assert t["tipo"] in ("precede", "exige", "prazo_max", "prazo_min", "prazo_concedido_min", "duracao_max", "manual")
        alvos = {t.get(k) for k in ("a", "b", "de", "ate", "atividade") if t.get(k)} | set(t.get("se", [])) | set(t.get("entao", []))
        assert alvos <= tarefas, (r["id"], alvos - tarefas)
        assert set(r["normas"]) <= ids_normas, r["id"]
    conf = json.loads((F3 / f"conformidade_{cod}.json").read_text(encoding="utf-8"))
    assert set(conf["requisitos"]) == {r["id"] for r in n["requisitos"]}


def test_benchmark_verificado_sem_caso_excluido():
    bench = F3 / "benchmark"
    if not (bench / "verificacao.json").exists():
        pytest.skip("benchmarking ainda não verificado")
    ver = json.loads((bench / "verificacao.json").read_text(encoding="utf-8"))["casos"]
    for arq in bench.glob("*.json"):
        if arq.name == "verificacao.json":
            continue
        for c in json.loads(arq.read_text(encoding="utf-8"))["casos"]:
            assert c["id"] in ver and ver[c["id"]]["veredito"] != "excluir", c["id"]
            assert c["fonte"]["trecho"].strip() and c["fonte"]["camada"] in ("cientifica", "oficial")


@pytest.mark.parametrize("cod", sorted(p.stem.split("_")[2] for p in F3.glob("linha_base_*.json")))
def test_linha_base_bate_com_os_casos_da_coorte(cod):
    lb = json.loads((F3 / f"linha_base_{cod}.json").read_text(encoding="utf-8"))
    casos = json.loads((SAIDA / "fase2" / f"casos_{cod}.json").read_text(encoding="utf-8"))["casos"]
    assert lb["casos_nativos"] == len(casos)
    for c in casos:  # lead = cauda + esperas + execuções, por construção (base da simulação do TO-BE)
        soma = sum(o["espera_antes_du"] + o["execucao_du"] for o in c["ocorrencias"])
        assert abs(c["cauda_du"] + soma - c["lead_du"]) < 0.11


@pytest.mark.parametrize("cod", sorted(p.stem.split("_")[2] for p in F3.glob("resultado_tobe_*.json")))
def test_resultado_tobe_atual_e_coerente(cod):
    res = json.loads((F3 / f"resultado_tobe_{cod}.json").read_text(encoding="utf-8"))
    lb = json.loads((F3 / f"linha_base_{cod}.json").read_text(encoding="utf-8"))
    assert res["carimbo_linha_base"] == lb["carimbo"], "simulação feita sobre outra linha de base"
    assert abs(res["linha_base"]["lead"]["mediana"] - lb["por_caso"]["lead_du"]["mediana"]) < 0.11
    anterior = {c: 0.0 for c in ("conservador", "esperado", "otimista")}
    for f in sorted(res["fases"], key=int):  # cenários ordenados e fases cumulativas sem perda de ganho
        g = {c: res["fases"][f][c]["ganho_lead_mediano_pct"] for c in anterior}
        assert g["conservador"] <= g["esperado"] <= g["otimista"], (f, g)
        assert all(g[c] >= anterior[c] - 0.1 for c in g), (f, g, anterior)
        anterior = g


# ------------------------------------------------------------------ fase 4: priorização da automação

def _matriz():
    p = SAIDA / "fase4" / "matriz_automacao.json"
    if not p.exists():
        pytest.skip("matriz de priorização ainda não gerada")
    return json.loads(p.read_text(encoding="utf-8"))


def test_matriz_piloto_unico_e_passa_nos_portoes():
    m = _matriz()["codigos"]
    pil = [r for r in m if r["prioridade"] == "piloto"]
    assert len(pil) <= 1
    for r in m:
        if r["prioridade"] in ("piloto", "candidato a piloto"):
            assert all(r["portoes"].values()), r["codigo"]
    if pil:
        cand = [r for r in m if r["prioridade"] == "candidato a piloto"]
        assert all(pil[0]["nota_composta"] >= r["nota_composta"] for r in cand)


def test_matriz_numeros_batem_com_as_fontes():
    from comum import CARGO_PADRAO, CUSTO_HORA_BASE, FATOR_CUSTO_TOTAL
    vol = json.loads((SAIDA / "fase3" / "volume_anual.json").read_text(encoding="utf-8"))["codigos"]
    csv = pd.read_csv(SAIDA / "fase4" / "matriz_automacao.csv").set_index("codigo")
    for r in _matriz()["codigos"]:
        cod = r["codigo"]
        assert r["volume"]["piso_deliberacoes"] == (vol.get(cod) or {}).get("media_anual")
        fat = {f["id"]: f["valor"] for f in _json(f"fatos_{cod}.json")["fatos"]}
        assert r["horas_caso"]["conservador"] == fat.get("coorte.caso.horas_piso.mediana")
        e = r["cenarios"]["esperado"]
        if "retorno_ano" in e:
            esperado = e["horas_liberadas_ano"] * CUSTO_HORA_BASE[CARGO_PADRAO] * FATOR_CUSTO_TOTAL["esperado"]
            assert e["retorno_ano"] == pytest.approx(esperado, abs=CUSTO_HORA_BASE[CARGO_PADRAO] * 2)
            assert csv.loc[cod, "retorno_ano_esperado"] == e["retorno_ano"]
        assert e["custo_incremental"] <= e["custo_construcao"]
