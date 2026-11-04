"""Validador dos controles, indicadores e metas do TO-BE (formato em saida/fase3/ESPECIFICACAO_TOBE.md): linha de base
igual ao fato citado, meta com origem conferível (simulação, norma ou benchmark), melhorias e testes de auditoria
existentes, controle de qualidade para toda melhoria de fase 3. Sai com código 1 se houver problema."""
from __future__ import annotations

import json
import sys

from comum import CODIGOS_FASE3, SAIDA

OUT, DIR = SAIDA / "fase3", SAIDA / "bpmn"
TIPOS = {"lead", "espera_antes", "posse_sem_unidade", "laco", "horas", "conformidade", "estoque_idade"}


def _j(p):
    return json.loads(p.read_text(encoding="utf-8"))


def caminho(d, ref: str):
    for k in ref.split("."):
        d = d[k]
    return d


def problemas(cod: str) -> list[str]:
    ctl = _j(OUT / f"controles_{cod}.json")
    fatos = {f["id"]: f["valor"] for f in _j(DIR / f"fatos_{cod}.json")["fatos"]}
    normas = _j(OUT / f"normas_{cod}.json")
    req, aud = {r["id"] for r in normas["requisitos"]}, {a["id"] for a in normas.get("programa_auditoria", [])}
    mel = {m["id"]: m for m in _j(OUT / f"melhorias_{cod}.json")["melhorias"]}
    res = _j(OUT / f"resultado_tobe_{cod}.json")
    bench = {c["id"] for a in (OUT / "benchmark").glob("*.json") if a.name != "verificacao.json" for c in _j(a)["casos"]}
    tarefas = {e["id"] for e in _j(DIR / f"modelo_{cod}.json")["elementos"] if e["tipo"] == "tarefa"}
    conf = _j(OUT / f"conformidade_{cod}.json")["requisitos"]
    simulavel = set(res["linha_base"].get("conformidade_temporal") or {})
    out = []
    for i in ctl.get("indicadores", []):
        k, c = i["id"], i.get("calculo", {})
        if c.get("tipo") not in TIPOS:
            out.append(f"{k}: tipo de cálculo desconhecido {c.get('tipo')}")
        out += [f"{k}: atividade inexistente {a}" for a in c.get("atividades", []) if a not in tarefas]
        if c.get("requisito") and c["requisito"] not in req:
            out.append(f"{k}: requisito inexistente {c['requisito']}")
        lb = i.get("linha_base") or {}
        if lb.get("fato"):
            if lb["fato"] not in fatos:
                out.append(f"{k}: fato da linha de base inexistente {lb['fato']}")
            elif not isinstance(fatos[lb["fato"]], (int, float)) or abs(float(fatos[lb["fato"]]) - float(lb["valor"])) > 0.051:
                out.append(f"{k}: linha de base {lb['valor']} ≠ fato {lb['fato']} = {fatos[lb['fato']]}")
        elif c.get("tipo") == "conformidade":
            r = c.get("requisito")
            if r not in conf or conf[r]["pct_conforme"] is None or abs(conf[r]["pct_conforme"] - float(lb.get("valor", -1))) > 0.051:
                out.append(f"{k}: linha de base de conformidade ≠ conformidade_{cod}.json ({r})")
            if r in simulavel:  # requisito de prazo: a meta por fase é a conformidade simulada, não a exigência legal
                for mt in i.get("metas", []):
                    ref = (mt.get("origem") or {}).get("ref", "")
                    if (mt.get("origem") or {}).get("tipo") != "simulacao" or not ref.endswith(f"conformidade_temporal.{r}"):
                        out.append(f"{k}: meta da fase {mt.get('fase')} de requisito de prazo sem origem na conformidade "
                                   f"simulada (use fases.<f>.esperado.conformidade_temporal.{r}; a exigência legal vai em "
                                   f"referencia_legal)")
        else:
            out.append(f"{k}: linha de base sem fato")
        if not i.get("metas"):
            out.append(f"{k}: sem meta")
        for mt in i.get("metas", []):
            o = mt.get("origem") or {}
            if o.get("tipo") == "simulacao":
                try:
                    v = caminho(res, o["ref"])
                    if abs(float(v) - float(mt["valor"])) > 0.051:
                        out.append(f"{k}: meta {mt['valor']} ≠ simulação {o['ref']} = {v}")
                except (KeyError, TypeError):
                    out.append(f"{k}: caminho de simulação inexistente {o.get('ref')}")
            elif o.get("tipo") == "norma":
                if o.get("ref") not in req:
                    out.append(f"{k}: meta com requisito inexistente {o.get('ref')}")
            elif o.get("tipo") == "benchmark":
                if o.get("ref") not in bench:
                    out.append(f"{k}: meta com benchmark inexistente {o.get('ref')}")
            else:
                out.append(f"{k}: meta sem origem conferível")
        out += [f"{k}: melhoria inexistente {m}" for m in i.get("melhorias", []) if m not in mel]
        if not (i.get("alerta") or {}).get("regra"):
            out.append(f"{k}: sem regra de alerta")
    cobertas = set()
    for q in ctl.get("controles_qualidade_ia", []):
        out += [f"{q['id']}: melhoria inexistente {m}" for m in q.get("melhorias", []) if m not in mel]
        cobertas |= set(q.get("melhorias", []))
        out += [f"{q['id']}: campo vazio {c}" for c in ("verificacao", "amostragem", "criterio_aceite", "responsavel")
                if not str(q.get(c) or "").strip()]
    out += [f"{m}: melhoria de fase 3 sem controle de qualidade" for m, x in mel.items() if x["fase"] == 3 and m not in cobertas]
    out += [f"auditoria_continua: teste inexistente {a}" for a in ctl.get("auditoria_continua", []) if a not in aud]
    return out


def main(codigos: list[str]) -> int:
    erro = 0
    for cod in codigos:
        if not (OUT / f"controles_{cod}.json").exists():
            print(f"aviso: {cod} sem controles_{cod}.json; controles não validados")
            continue
        p = problemas(cod)
        print(f"{cod}: {len(p)} problema(s)")
        for x in p:
            print("  ✗", x)
        erro |= bool(p)
    return int(erro)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or CODIGOS_FASE3))
