"""Validador das melhorias do TO-BE (regras em saida/fase3/ESPECIFICACAO_TOBE.md): evidência AS-IS citada existe,
requisitos e casos de benchmark existem, sem benchmark é hipótese, prazo legal mínimo não vira desperdício,
cenários monotônicos, fase 3 com controle humano. Sai com código 1 se houver problema."""
from __future__ import annotations

import json
import sys

from comum import CODIGOS_FASE3, SAIDA

OUT, DIR = SAIDA / "fase3", SAIDA / "bpmn"
TETO = {"teto_espera"}


def problemas(cod: str) -> list[str]:
    mel = json.loads((OUT / f"melhorias_{cod}.json").read_text(encoding="utf-8"))["melhorias"]
    fatos = {f["id"] for f in json.loads((DIR / f"fatos_{cod}.json").read_text(encoding="utf-8"))["fatos"]}
    arq_n = OUT / f"normas_{cod}.json"
    req = {r["id"]: r for r in json.loads(arq_n.read_text(encoding="utf-8"))["requisitos"]} if arq_n.exists() else {}
    bench = {c["id"] for a in (OUT / "benchmark").glob("*.json") if a.name != "verificacao.json"
             for c in json.loads(a.read_text(encoding="utf-8"))["casos"]}
    tarefas = {e["id"] for e in json.loads((DIR / f"modelo_{cod}.json").read_text(encoding="utf-8"))["elementos"]
               if e["tipo"] == "tarefa"}
    protegidas = {}  # atividade cuja espera antes contém prazo legal mínimo → menor prazo exigido
    for r in req.values():
        t = r["teste"]
        if t["tipo"] == "prazo_min":
            protegidas[t["ate"]] = max(protegidas.get(t["ate"], 0), t["min"])
    out = []
    for m in mel:
        i, e = m["id"], m["efeito"]
        if not m.get("fatos"):
            out.append(f"{i}: sem fato AS-IS citado")
        out += [f"{i}: fato inexistente {f}" for f in m.get("fatos", []) if f not in fatos]
        out += [f"{i}: requisito inexistente {r}" for r in m.get("requisitos", []) if r not in req]
        out += [f"{i}: benchmark inexistente {b}" for b in m.get("benchmark", []) if b not in bench]
        if not m.get("benchmark") and not m.get("hipotese"):
            out.append(f"{i}: sem benchmark e sem hipotese: true")
        alvos = set(e.get("atividades") or []) | {e.get(k) for k in ("a", "b") if e.get(k)}
        out += [f"{i}: atividade inexistente {a}" for a in sorted(alvos) if a not in tarefas]
        c = e["cenarios"]
        seq = [float(c[k]) for k in ("conservador", "esperado", "otimista")]
        if e["tipo"] != "paralelo" and seq != sorted(seq, reverse=e["tipo"] in TETO):
            out.append(f"{i}: cenários não monotônicos {seq}")
        for a in alvos & set(protegidas):
            if e["tipo"] == "reduz_espera_pct":
                out.append(f"{i}: reduz espera de {a}, que contém prazo legal mínimo ({protegidas[a]})")
            if e["tipo"] == "teto_espera" and min(seq) < protegidas[a]:
                out.append(f"{i}: teto {min(seq)} abaixo do prazo legal mínimo de {a} ({protegidas[a]})")
            if e["tipo"] == "paralelo" and a == e.get("b"):
                out.append(f"{i}: paraleliza {a}, cuja espera contém prazo legal mínimo")
        if m["fase"] == 3 and not (m.get("controle_humano") or "").strip():
            out.append(f"{i}: fase 3 sem controle humano")
    return out


def main(codigos: list[str]) -> int:
    erro = 0
    for cod in codigos:
        if not (OUT / f"melhorias_{cod}.json").exists():
            print(f"aviso: {cod} sem melhorias_{cod}.json; TO-BE não validado")
            continue
        p = problemas(cod)
        print(f"{cod}: {len(p)} problema(s)")
        for x in p:
            print("  ✗", x)
        erro |= bool(p)
    return int(erro)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or CODIGOS_FASE3))
