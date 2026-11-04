"""Linha do tempo de cada caso-piloto e tabela de fatos — a única fonte de números das fichas de atividade
e das avaliações.

Definições (sem sobreposição, sem tempo posterior ao marco):
  ocorrência de atividade = sequência contínua de peças PRÓPRIAS (da unidade da raia) vinculadas à mesma
      atividade, na ordem das datas; uma atividade que volta depois de outras tem nova ocorrência (laço).
  execução = da primeira à última peça da ocorrência (dias úteis).
  espera antes = do fim da ocorrência anterior (qualquer atividade) ao início desta; dividida entre as unidades
      que tinham a posse do processo no intervalo (posse.csv). Ocorrências que se sobrepõem não têm espera.
  espera inicial = do início do processo à 1ª ocorrência; cauda = da última ocorrência ao último andamento.

Fase 2 — fatos da coorte (ids `coorte.*`), de saida/fase2/procedimento_<Pxx>.json: distribuições (mediana, q1, q3,
max, n) por atividade (espera antes, execução, horas), por caso nativo (soma das esperas e execuções, lead, terceiros,
ofícios, retornos), posse por unidade, transições entre atividades e sinais de perda. Tipos sem caso-piloto
(sem vinculos_<Pxx>.json) têm só fatos da coorte e da carteira.

Saída: saida/bpmn/fatos_<Pxx>.json — {"fatos": [{id, caso, descricao, valor, unidade, definicao}], "linha_do_tempo": ...}"""
from __future__ import annotations

import json
from collections import defaultdict

import pandas as pd

from comum import DESCRICAO_BASE, RAIA_ALIAS, SAIDA, dias_uteis

DIR = SAIDA / "bpmn"
DEF = {
    "execucao": "dias úteis da primeira à última peça própria da ocorrência",
    "espera_antes": "dias úteis entre o fim da ocorrência anterior e o início desta, por unidade com a posse",
    "lead": "dias úteis do início do processo ao último andamento",
    "posse": "dias úteis em que a unidade era a última a abrir o processo entre as que o tinham aberto; "
             "SEM UNIDADE = ninguém com o processo aberto (todas concluíram): processo parado sem dono",
    "terceiros": "dias úteis de ofício/notificação até a resposta (carta, petição em processo relacionado, anexo recebido "
                 "pelo protocolo), limitados ao prazo dado no ofício + 5 du (sem prazo: 60 du); intervalos unidos",
    "indeterminado": "dias úteis além do prazo dado ou até peça sem data real: não separável de processo parado",
    "horas": "horas de trabalho estimadas das peças próprias (piso = leitura da peça; teto = laudas × complexidade)",
    "coorte": "distribuição na coorte da fase 2 (processos do código com atividade atribuída a cada peça); "
              "estatística = mediana, q1, q3, max ou n (número de observações)",
}
F2 = SAIDA / "fase2"
ESTAT = ("mediana", "q1", "q3", "max", "n")


def na_raia(unidade: str, raia_txt: str) -> bool:
    u = unidade.split("/")[-1]
    return u in raia_txt or (u in RAIA_ALIAS and RAIA_ALIAS[u] in raia_txt)


def posse_no_intervalo(po: pd.DataFrame, a, b) -> dict:
    """Dias úteis de posse por unidade dentro de [a, b]."""
    out = defaultdict(float)
    for r in po.itertuples():
        i, f = max(r.inicio, a), min(r.fim, b)
        if f > i:
            out[r.sigla] += dias_uteis(i, f)
    return {k: v for k, v in out.items() if v > 0}


def linha_do_tempo(numero, atrib, tarefas, ordem, raias, esf, pi, po) -> list[dict]:
    """Ocorrências de atividade de um processo: atrib = [(atividade, ref da peça)]; só peças próprias (unidade da
    raia) contam. Cada ocorrência traz início, fim, peças, horas, execução e espera antes (repartida pela posse)."""
    ev = []
    for tid, r in atrib:
        if r in esf.index and esf.loc[r, "numero_processo"] == numero                 and na_raia(esf.loc[r, "unidade"], raias[tarefas[tid]["raia"]]):
            x = esf.loc[r]
            ev.append((x.data_inclusao, ordem[tid], tid, r, x.horas_llm, x.horas_modelo, x.tipo))
    ev.sort()
    ocorr = []
    for data, _, tid, r, hp, ht, tipo in ev:
        if ocorr and ocorr[-1]["atividade"] == tid:
            o = ocorr[-1]
            o["fim"] = data
        else:
            o = dict(atividade=tid, nome=tarefas[tid]["nome"], inicio=data, fim=data, pecas=[],
                     horas_piso=0.0, horas_teto=0.0)
            ocorr.append(o)
        o["pecas"].append(f"{tipo} ({r.split(':')[1]})")
        o["horas_piso"] += hp
        o["horas_teto"] += ht
    for k, o in enumerate(ocorr):
        o["execucao_du"] = dias_uteis(o["inicio"], o["fim"])
        antes = ocorr[k - 1]["fim"] if k else pi.inicio
        o["espera_antes_du"] = dias_uteis(antes, o["inicio"]) if o["inicio"] > antes else 0.0
        o["espera_antes_por_unidade"] = posse_no_intervalo(po, antes, o["inicio"]) if o["inicio"] > antes else {}
    return ocorr


def fatos_coorte(cod: str, fato) -> bool:
    """Fatos `coorte.*` do procedimento do código; False se o código não tem procedimento."""
    arq = F2 / f"procedimento_{cod}.json"
    if not arq.exists():
        return False
    p = json.loads(arq.read_text(encoding="utf-8"))

    def dist(base, desc, d, un):
        for k in ESTAT if d else ():
            fato(f"{base}.{k}", None, f"{desc} — {k}", float(d[k]) if k != "n" else d[k],
                 "observações" if k == "n" else un, DEF["coorte"])

    fato("coorte.casos", None, "Processos na coorte", p["casos"], "processos", DEF["coorte"])
    for k, v in p["trilha"].items():
        fato(f"coorte.trilha.{k}", None, f"Processos da coorte com trilha {k}", v, "processos",
             "nativa = trâmite completo no SEI; migrada = processo físico migrado, trâmite parcial; sem = só as peças")
    fato("coorte.n_caminhos", None, "Caminhos distintos (ordem da 1ª ocorrência de cada atividade)", p["n_caminhos"],
         "caminhos", DEF["coorte"])
    if p["caminhos"]:
        fato("coorte.caminho_mais_frequente.casos", None,
             f"Casos no caminho mais frequente ({p['caminhos'][0]['sequencia']})", p["caminhos"][0]["casos"], "casos",
             DEF["coorte"])
    a = p.get("auditoria_classificador") or {}
    if a.get("concordancia_substantivas") is not None:
        fato("coorte.auditoria.concordancia_substantivas", None,
             "Concordância da auditoria às cegas nas peças substantivas", round(100 * a["concordancia_substantivas"]),
             "%", "auditoria independente do classificador fora do piloto")
    dist("coorte.lead_nativos_encerrados", "Lead time dos processos nativos encerrados", p["lead_nativos_encerrados"], "du")
    dist("coorte.fora_do_modelo_substantivas", "Peças substantivas fora do modelo por caso",
         p["fora_do_modelo_pct_substantivas"], "%")
    nomes = {"espera_entre_atividades": ("Soma das esperas entre atividades por caso nativo", "du"),
             "execucao_atividades": ("Soma das execuções das atividades por caso nativo", "du"),
             "horas_piso": ("Horas das peças mapeadas por caso nativo (piso)", "h"),
             "horas_teto": ("Horas das peças mapeadas por caso nativo (teto)", "h"),
             "lead": ("Lead time dos casos nativos (encerrados ou não)", "du"),
             "terceiros": ("Espera de resposta de terceiros por caso nativo (confirmada)", "du"),
             "indeterminado": ("Ofício até peça externa sem data real, por caso nativo", "du"),
             "oficios": ("Ofícios por caso nativo", "ofícios"),
             "retornos": ("Retornos a unidade já visitada por caso nativo", "retornos"),
             "unidades_ativas": ("Unidades ativas por caso nativo", "unidades")}
    for k, d in (p.get("por_caso_nativo") or {}).items():
        desc, un = nomes.get(k, (k, ""))
        dist(f"coorte.caso.{k}", desc, d, un)
    for u, d in (p.get("posse_por_unidade_nativos") or {}).items():
        dist(f"coorte.posse.{u}", f"Posse total da {u} por caso nativo em que aparece", d, "du")
    for t, x in p["atividades"].items():
        fato(f"coorte.{t}.casos", None, f"{x['nome']} — casos em que ocorre", x["casos"], "casos", DEF["coorte"])
        fato(f"coorte.{t}.pct_casos", None, f"{x['nome']} — % dos casos em que ocorre", x["pct_casos"], "%", DEF["coorte"])
        fato(f"coorte.{t}.casos_com_laco", None, f"{x['nome']} — casos com 2 ou mais ocorrências", x["casos_com_laco"],
             "casos", DEF["coorte"])
        dist(f"coorte.{t}.espera_antes", f"{x['nome']} — espera antes", x["espera_antes_du"], "du")
        dist(f"coorte.{t}.execucao", f"{x['nome']} — execução", x["execucao_du"], "du")
        dist(f"coorte.{t}.horas_piso", f"{x['nome']} — horas por ocorrência (piso)", x["horas_piso"], "h")
        dist(f"coorte.{t}.horas_teto", f"{x['nome']} — horas por ocorrência (teto)", x["horas_teto"], "h")
        for s_ in x["sinais_perda"]:
            fato(f"coorte.{t}.perda.{s_['item']}", None, f"{x['nome']} — casos com sinal de perda {s_['item']}",
                 s_["casos"], "casos", DEF["coorte"])
    for a_, saidas in p["transicoes"].items():
        tot = sum(x["n"] for x in saidas)
        for x in saidas:
            fato(f"coorte.transicao.{a_}.{x['para']}", None, f"Passagens de {a_} para {x['para']}", x["n"], "passagens",
                 f"passagens observadas entre ocorrências consecutivas (total que sai de {a_}: {tot})")
            fato(f"coorte.transicao.{a_}.{x['para']}.pct", None, f"% das saídas de {a_} que vão para {x['para']}",
                 x["pct"], "%", DEF["coorte"])
    return True


def fatos_carteira(cod: str, cls: pd.DataFrame, fato):
    cart = cls[cls.processo_principal == cod]
    if cart.empty:  # tipo novo, achado na fase 2: não tem carteira na classificação da fase 0
        return
    nat = cart[cart.nativo_sei]
    fato("carteira.processos", None, "Processos SEI do código na base", len(cart), "processos", DESCRICAO_BASE)
    if len(nat):
        fato("carteira.lead_mediano_nativos", None, "Lead time mediano — só processos nativos do SEI",
             float(nat.lead_du.median()), "du", DEF["lead"])
    fato("carteira.lead_mediano_todos", None, "Lead time mediano — todos os processos (inclui migrados)",
         float(cart.lead_du.median()), "du", DEF["lead"])
    fato("carteira.com_deliberacao_pct", None, "Processos com deliberação", round(100 * cart.tem_deliberacao.mean()), "%", "")


def coletor(fatos: list):
    def fato(id_, caso, descricao, valor, unidade, definicao):
        fatos.append(dict(id=id_, caso=caso, descricao=descricao,
                          valor=round(valor, 1) if isinstance(valor, float) else valor,
                          unidade=unidade, definicao=definicao))
    return fato


def gravar(cod, fatos, linhas):
    (DIR / f"fatos_{cod}.json").write_text(json.dumps(dict(codigo=cod, definicoes=DEF, fatos=fatos, linha_do_tempo=linhas),
                                                      ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def main():
    piloto = pd.read_csv(SAIDA / "piloto.csv")
    cls = pd.read_csv(SAIDA / "processos_classificados.csv")
    ind = pd.read_csv(SAIDA / "processos_indicadores.csv", parse_dates=["inicio", "ultimo_andamento"]).set_index("numero")
    esf = pd.read_csv(SAIDA / "esforco_documentos.csv", dtype={"numero": str}, parse_dates=["data_inclusao"])
    esf["ref"] = esf.numero_processo + ":" + esf.numero
    esf = esf.set_index("ref")
    posse = pd.read_csv(SAIDA / "posse.csv", parse_dates=["inicio", "fim"])
    for arq in sorted(DIR.glob("vinculos_*.json")):
        vin = json.loads(arq.read_text(encoding="utf-8"))
        cod = vin["codigo"]
        mod = json.loads((DIR / f"modelo_{cod}.json").read_text(encoding="utf-8"))
        raias = {r["id"]: (r["id"] + " " + r["nome"]).upper() for r in mod["raias"]}
        tarefas = {e["id"]: e for e in mod["elementos"] if e["tipo"] == "tarefa"}
        ordem = {e["id"]: k for k, e in enumerate(mod["elementos"])}
        casos = piloto[piloto.processo_principal == cod]
        fatos, linhas = [], {}
        fato = coletor(fatos)

        for c in casos.itertuples():
            papel = "tipico" if c.papel.startswith("t") else "critico"
            pi = ind.loc[c.numero]
            po = posse[posse.numero == c.numero]
            atrib = [(tid, r) for tid, a in vin["atividades"].items() if tid in tarefas for r in a.get("docs", [])]
            ocorr = linha_do_tempo(c.numero, atrib, tarefas, ordem, raias, esf, pi, po)
            fim_proc = pi.ultimo_andamento
            for k, o in enumerate(ocorr):
                n = sum(1 for x in ocorr[:k + 1] if x["atividade"] == o["atividade"])
                base = f"{papel}.{o['atividade']}.{n}"
                fato(f"{base}.execucao", c.numero, f"{o['nome']} — execução (ocorrência {n})", o["execucao_du"], "du", DEF["execucao"])
                fato(f"{base}.espera_antes", c.numero, f"{o['nome']} — espera antes (ocorrência {n})", o["espera_antes_du"], "du", DEF["espera_antes"])
                for u, v in o["espera_antes_por_unidade"].items():
                    fato(f"{base}.espera_antes.{u}", c.numero, f"{o['nome']} — espera antes com posse da {u}", v, "du", DEF["posse"])
                fato(f"{base}.horas_piso", c.numero, f"{o['nome']} — horas (piso)", o["horas_piso"], "h", DEF["horas"])
                fato(f"{base}.horas_teto", c.numero, f"{o['nome']} — horas (teto)", o["horas_teto"], "h", DEF["horas"])
                fato(f"{base}.inicio", c.numero, f"{o['nome']} — 1ª peça (ocorrência {n})", str(o["inicio"].date()), "data", "data de juntada da 1ª peça própria")
                fato(f"{base}.fim", c.numero, f"{o['nome']} — última peça (ocorrência {n})", str(o["fim"].date()), "data", "data de juntada da última peça própria")
            cauda = dias_uteis(ocorr[-1]["fim"], fim_proc) if ocorr else None
            fato(f"{papel}.lead", c.numero, "Lead time do caso", float(pi.lead_du), "du", DEF["lead"])
            if cauda is not None:
                fato(f"{papel}.cauda", c.numero, "Da última peça mapeada ao último andamento", cauda, "du",
                     "dias úteis entre a última ocorrência e o último andamento")
            for u, v in po.groupby("sigla").du.sum().items():
                fato(f"{papel}.posse.{u}", c.numero, f"Posse total da {u}", float(v), "du", DEF["posse"])
            fato(f"{papel}.terceiros", c.numero, "Espera de resposta de terceiros (confirmada)", float(pi.espera_externa_du), "du", DEF["terceiros"])
            fato(f"{papel}.indeterminado", c.numero, "Ofício até peça externa sem data real", float(pi.espera_indeterminada_du), "du", DEF["indeterminado"])
            fato(f"{papel}.horas_piso", c.numero, "Horas do caso (piso)", float(esf[esf.numero_processo == c.numero].horas_llm.sum()), "h", DEF["horas"])
            fato(f"{papel}.horas_teto", c.numero, "Horas do caso (teto)", float(esf[esf.numero_processo == c.numero].horas_modelo.sum()), "h", DEF["horas"])
            exec_tot = sum(o["execucao_du"] for o in ocorr)
            esp_tot = sum(o["espera_antes_du"] for o in ocorr)
            fato(f"{papel}.execucao_total", c.numero, "Soma das execuções das atividades", exec_tot, "du", DEF["execucao"])
            fato(f"{papel}.espera_total", c.numero, "Soma das esperas entre atividades (inclui a inicial)", esp_tot, "du", DEF["espera_antes"])
            linhas[c.numero] = [dict(o, inicio=str(o["inicio"].date()), fim=str(o["fim"].date())) for o in ocorr]
        fatos_carteira(cod, cls, fato)
        fatos_coorte(cod, fato)
        gravar(cod, fatos, linhas)
        print(cod, len(fatos), "fatos;", {k[-9:]: len(v) for k, v in linhas.items()}, "ocorrências")
    pilotos = {a.stem.split("_")[1] for a in DIR.glob("vinculos_*.json")}
    for arq in sorted(F2.glob("procedimento_*.json")):  # tipos sem caso-piloto: só coorte e carteira
        cod = arq.stem.split("_")[1]
        if cod in pilotos:
            continue
        fatos = []
        fato = coletor(fatos)
        fatos_carteira(cod, cls, fato)
        fatos_coorte(cod, fato)
        gravar(cod, fatos, {})
        print(cod, len(fatos), "fatos da coorte")

if __name__ == "__main__":
    main()
