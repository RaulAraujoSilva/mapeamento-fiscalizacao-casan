"""Desenha um .bpmn (BPMN 2.0 com DI) em PNG usando as coordenadas do próprio arquivo — mesma geometria validada por
checar_bpmn.py. Uso: python ferramentas_caso/renderizar_bpmn.py saida/bpmn/P06.bpmn docs/relatorio/bpmn_P06.png"""
import sys, textwrap
import xml.etree.ElementTree as ET
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle, Circle, Polygon

NS = {"bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL", "bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI",
      "dc": "http://www.omg.org/spec/DD/20100524/DC", "di": "http://www.omg.org/spec/DD/20100524/DI"}
src, dst = sys.argv[1], sys.argv[2]
root = ET.parse(src).getroot()
el = {}
for e in root.iter():
    tag = e.tag.split("}")[-1]
    if e.get("id"):
        el[e.get("id")] = (tag, e.get("name") or "")
for t in root.iter(f"{{{NS['bpmn']}}}textAnnotation"):
    tx = t.find("bpmn:text", NS)
    el[t.get("id")] = ("textAnnotation", tx.text if tx is not None else "")
shapes = [(s.get("bpmnElement"), s.find("dc:Bounds", NS)) for s in root.iter(f"{{{NS['bpmndi']}}}BPMNShape")]
edges = [(e.get("bpmnElement"), [(float(w.get("x")), float(w.get("y"))) for w in e.findall("di:waypoint", NS)])
         for e in root.iter(f"{{{NS['bpmndi']}}}BPMNEdge")]
B = {k: tuple(float(b.get(a)) for a in "x y width height".split()) for k, b in shapes}
xs = [x for x, y, w, h in B.values()] + [x + w for x, y, w, h in B.values()]
ys = [y for x, y, w, h in B.values()] + [y + h for x, y, w, h in B.values()]
for _, pts in edges:
    xs += [p[0] for p in pts]; ys += [p[1] for p in pts]
W, H = max(xs) - min(xs), max(ys) - min(ys)
fig, ax = plt.subplots(figsize=(W / 95, H / 95), dpi=200)
ax.set_xlim(min(xs) - 10, max(xs) + 10); ax.set_ylim(max(ys) + 10, min(ys) - 10); ax.axis("off")
COR, FUNDO = "#222222", "#f4f4f4"
def wrap(s, n): return "\n".join(textwrap.wrap(s, n))
for k, (x, y, w, h) in B.items():
    tag, nome = el.get(k, ("", ""))
    if tag == "participant":
        ax.add_patch(Rectangle((x, y), w, h, fill=False, lw=1.2, ec=COR))
        ax.text(x + 15, y + h / 2, wrap(nome, 60), rotation=90, ha="center", va="center", fontsize=6.5, weight="bold")
    elif tag == "lane":
        ax.add_patch(Rectangle((x, y), w, h, fc="#fbfbfb", lw=0.8, ec="#888"))
        ax.text(x + 14, y + h / 2, wrap(nome, 28), rotation=90, ha="center", va="center", fontsize=6.5, color="#333")
for k, (x, y, w, h) in B.items():
    tag, nome = el.get(k, ("", ""))
    cx, cy = x + w / 2, y + h / 2
    if tag == "task":
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=8", fc=FUNDO, ec=COR, lw=1))
        ax.text(cx, cy, wrap(nome, 20), ha="center", va="center", fontsize=6.2)
    elif tag in ("startEvent", "endEvent", "intermediateCatchEvent"):
        ax.add_patch(Circle((cx, cy), w / 2, fc="white", ec=COR, lw=3 if tag == "endEvent" else 1))
        if tag == "intermediateCatchEvent":
            ax.add_patch(Circle((cx, cy), w / 2 - 3, fill=False, ec=COR, lw=0.8))
            ax.add_patch(Rectangle((cx - 7, cy - 5), 14, 10, fill=False, ec=COR, lw=0.8))
            ax.plot([cx - 7, cx, cx + 7], [cy - 5, cy + 1, cy - 5], color=COR, lw=0.8)
        ax.text(cx, y + h + 4, wrap(nome, 22), ha="center", va="top", fontsize=5.6)
    elif tag == "exclusiveGateway":
        ax.add_patch(Polygon([(cx, y), (x + w, cy), (cx, y + h), (x, cy)], fc="white", ec=COR, lw=1))
        ax.text(cx, cy, "×", ha="center", va="center", fontsize=9)
        if nome:
            ax.text(cx, y - 4, wrap(nome, 24), ha="center", va="bottom", fontsize=5.6, style="italic")
    elif tag == "textAnnotation":
        ax.plot([x + 8, x, x, x + 8], [y, y, y + h, y + h], color="#777", lw=0.7)
        ax.text(x + 4, y + 3, wrap(nome, 34), ha="left", va="top", fontsize=5.2, color="#444")
for k, pts in edges:
    tag, nome = el.get(k, ("", ""))
    px, py = zip(*pts)
    if tag == "association":
        ax.plot(px, py, color="#999", lw=0.6, ls=":"); continue
    ax.plot(px, py, color=COR, lw=0.9)
    ax.annotate("", xy=pts[-1], xytext=pts[-2], arrowprops=dict(arrowstyle="-|>", color=COR, lw=0.9, mutation_scale=8))
    if nome:
        (x0, y0), (x1, y1) = pts[0], pts[1]
        ax.text((x0 + x1) / 2 + 3, (y0 + y1) / 2 - 3, nome, fontsize=5.4, color="#333", ha="left", va="bottom")
fig.savefig(dst, bbox_inches="tight", facecolor="white"); print(dst, W, H)
