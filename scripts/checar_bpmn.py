"""Métricas de legibilidade de um diagrama BPMN gerado: setas que atravessam elementos, trechos de setas
diferentes sobrepostos (colineares), cruzamentos entre setas e rótulos de fluxo que cobrem uma forma ou outro
rótulo.

Uso: python checar_bpmn.py arquivo.bpmn [...]"""
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from itertools import combinations

NS = {"bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI", "dc": "http://www.omg.org/spec/DD/20100524/DC",
      "di": "http://www.omg.org/spec/DD/20100524/DI", "bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL"}


def carregar(arq):
    r = ET.parse(arq).getroot()
    nos = {e.get("id") for tag in ("task", "startEvent", "endEvent", "exclusiveGateway", "parallelGateway",
                                   "intermediateCatchEvent") for e in r.iter(f"{{{NS['bpmn']}}}{tag}")}
    fluxos = {e.get("id"): (e.get("sourceRef"), e.get("targetRef")) for e in r.iter(f"{{{NS['bpmn']}}}sequenceFlow")}
    caixas = {}
    for s in r.iter(f"{{{NS['bpmndi']}}}BPMNShape"):
        if s.get("bpmnElement") in nos:
            b = s.find("dc:Bounds", NS)
            caixas[s.get("bpmnElement")] = tuple(float(b.get(k)) for k in ("x", "y", "width", "height"))
    segs = {}
    for e in r.iter(f"{{{NS['bpmndi']}}}BPMNEdge"):
        if e.get("bpmnElement") in fluxos:
            p = [(float(w.get("x")), float(w.get("y"))) for w in e.findall("di:waypoint", NS)]
            segs[e.get("bpmnElement")] = list(zip(p, p[1:]))
    return caixas, fluxos, segs


def atravessa(seg, caixa, margem=2):
    (x1, y1), (x2, y2) = seg
    bx, by, bw, bh = caixa
    bx, by, bw, bh = bx + margem, by + margem, bw - 2 * margem, bh - 2 * margem
    if x1 == x2:
        return bx < x1 < bx + bw and max(min(y1, y2), by) < min(max(y1, y2), by + bh)
    if y1 == y2:
        return by < y1 < by + bh and max(min(x1, x2), bx) < min(max(x1, x2), bx + bw)
    return False


def metricas(arq):
    return metricas_segs(*carregar(arq))


def metricas_segs(caixas, fluxos, segs):
    atr = sum(1 for f, ss in segs.items() for s in ss for n, c in caixas.items()
              if n not in fluxos[f] and atravessa(s, c))
    sobre, cruz = 0, 0
    for (f, a), (g, b) in combinations(segs.items(), 2):
        for s in a:
            for t in b:
                (x1, y1), (x2, y2) = s
                (u1, v1), (u2, v2) = t
                if x1 == x2 == u1 == u2:
                    ov = min(max(y1, y2), max(v1, v2)) - max(min(y1, y2), min(v1, v2))
                    sobre += ov > 4 and fluxos[f][0] != fluxos[g][0]  # tronco comum da mesma decisão é intencional
                elif y1 == y2 == v1 == v2:
                    ov = min(max(x1, x2), max(u1, u2)) - max(min(x1, x2), min(u1, u2))
                    # trechos que só se juntam na porta de entrada/saída do mesmo elemento não contam
                    sobre += ov > 4 and not (fluxos[f][1] == fluxos[g][1] or fluxos[f][0] == fluxos[g][0]) or ov > 40
                elif x1 == x2 and v1 == v2:
                    cruz += min(u1, u2) < x1 < max(u1, u2) and min(y1, y2) < v1 < max(y1, y2)
                elif y1 == y2 and u1 == u2:
                    cruz += min(x1, x2) < u1 < max(x1, x2) and min(v1, v2) < y1 < max(v1, v2)
    return atr, sobre, cruz


def rotulos_sobrepostos(arq) -> int:
    """Rótulos de fluxo (BPMNLabel das arestas) que cobrem um elemento ou outro rótulo."""
    r = ET.parse(arq).getroot()
    caixa = lambda b: tuple(float(b.get(k)) for k in ("x", "y", "width", "height"))  # noqa: E731
    nos = {e.get("id") for e in r.iter() if e.tag.split("}")[1] in ("task", "startEvent", "endEvent", "exclusiveGateway",
                                                                  "parallelGateway", "intermediateCatchEvent")}
    formas = [caixa(sh.find("dc:Bounds", NS)) for sh in r.iter(f"{{{NS['bpmndi']}}}BPMNShape")
              if sh.get("bpmnElement") in nos]
    rot = [caixa(b) for ed in r.iter(f"{{{NS['bpmndi']}}}BPMNEdge") for b in ed.findall("bpmndi:BPMNLabel/dc:Bounds", NS)]
    ov = lambda a, b: a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]  # noqa: E731
    return (sum(any(ov(a, f) for f in formas) for a in rot)
            + sum(ov(a, b) for a, b in combinations(rot, 2)))


if __name__ == "__main__":
    for arq in sys.argv[1:]:
        a, s, c = metricas(arq)
        print(f"{arq.split('/')[-1].split(chr(92))[-1]:>10}: atravessa elemento {a:3d} · sobreposição {s:3d} · "
              f"cruzamentos {c:3d} · rótulos sobrepostos {rotulos_sobrepostos(arq):3d}")
