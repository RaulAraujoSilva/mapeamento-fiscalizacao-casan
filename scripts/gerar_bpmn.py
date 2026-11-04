"""Etapa 4b — gera BPMN 2.0 (XML com BPMNDI) a partir dos modelos canônicos saida/bpmn/modelo_<Pxx>.json
e um visualizador HTML com todos os diagramas.

Layout (regras da skill bpmn-process-mapping): raias horizontais, fluxo da esquerda para a direita,
colunas por camada topológica (caminho mais longo), saída não principal de decisão para baixo,
laços (back-edges) roteados num corredor abaixo da piscina, roteamento ortogonal.
Cores: vermelho = espera dominante; âmbar = sinal de perda.
Números das tarefas: da coorte (saida/fase2/procedimento_<Pxx>.json) quando existe — % dos casos em que a
atividade ocorre, mediana da espera antes e das horas-piso —, senão dos casos do piloto (fichas_<Pxx>.json).
Ramos de decisão: % das transições observadas na coorte entre a atividade anterior à decisão e a primeira
atividade de cada ramo (só quando os ramos não levam à mesma atividade e há 3 transições ou mais).

Saídas: saida/bpmn/<Pxx>.bpmn e docs/bpmn/index.html"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from itertools import permutations
from pathlib import Path
from xml.sax.saxutils import escape

from checar_bpmn import metricas_segs
from comum import ORDEM_CODIGOS, ORGAO, RAIZ, SAIDA

DIR = SAIDA / "bpmn"
F2 = SAIDA / "fase2"
VIEWER = RAIZ / "docs" / "bpmn"
ESPERA_DOMINANTE_DU = 20  # mediana da espera antes da atividade
PERDA_FRAC = 0.5  # sinal de perda em pelo menos metade dos casos da atividade
MIN_TRANSICOES = 3
SITUACAO = {"procedimento": "procedimento", "indicativo": "indicativo, com ressalva", "estudo_de_caso": "estudo de caso"}
TASK_W, TASK_H = 150, 90
GAP = 60  # intervalo horizontal mínimo entre colunas
TRILHO = 12  # distância entre trilhos verticais num vão
PASSO_CORR = 22  # distância entre faixas do corredor de laços (cabe um rótulo entre elas)
EV, GW = 36, 50
LANE_LABEL, POOL_LABEL = 30, 30
X0 = POOL_LABEL + LANE_LABEL + 40
LANE_PAD_TOP, SUBROW_H, LANE_MIN = 115, 160, 200
NOTA_H = 52
ROT_MAX = 230  # largura máxima do rótulo de fluxo (uma linha: nome do ramo + % observado)
CORES = {"espera": ("#f8d7da", "#b02a37"), "perda": ("#fff3cd", "#b58105")}
TIPO_XML = {"inicio": "startEvent", "fim": "endEvent", "tarefa": "task", "xor": "exclusiveGateway",
            "xor_juncao": "exclusiveGateway", "paralelo": "parallelGateway", "paralelo_juncao": "parallelGateway",
            "evento_tempo": "intermediateCatchEvent", "evento_mensagem": "intermediateCatchEvent"}


def tamanho(tipo: str) -> tuple[int, int]:
    if tipo == "tarefa":
        return TASK_W, TASK_H
    if tipo.startswith(("xor", "paralelo")):
        return GW, GW
    return EV, EV


def validar(m: dict) -> list[str]:
    erros = []
    ids = [e["id"] for e in m["elementos"]]
    raias = {r["id"] for r in m["raias"]}
    if len(ids) != len(set(ids)):
        erros.append("ids duplicados")
    for e in m["elementos"]:
        if e["raia"] not in raias:
            erros.append(f"raia inexistente em {e['id']}")
        if e["tipo"] not in TIPO_XML:
            erros.append(f"tipo inválido em {e['id']}: {e['tipo']}")
    for f in m["fluxos"]:
        if f["de"] not in ids or f["para"] not in ids:
            erros.append(f"fluxo com ponta inexistente: {f}")
    if sum(e["tipo"] == "inicio" for e in m["elementos"]) != 1:
        erros.append("precisa de exatamente 1 início")
    saidas = defaultdict(list)
    for f in m["fluxos"]:
        saidas[f["de"]].append(f)
    for e in m["elementos"]:
        if e["tipo"] == "xor" and len(saidas[e["id"]]) > 1:
            if not e.get("nome", "").endswith("?"):
                erros.append(f"decisão sem pergunta: {e['id']}")
            if any(not f.get("rotulo") for f in saidas[e["id"]]):
                erros.append(f"saída de decisão sem rótulo: {e['id']}")
    if len(m["elementos"]) > 30:
        erros.append(f"{len(m['elementos'])} elementos (> 30)")
    return erros


def _back_edges(m: dict, els: dict) -> set[int]:
    """Laços por DFS a partir do início (saída principal primeiro)."""
    suc = defaultdict(list)
    for i, f in enumerate(m["fluxos"]):
        suc[f["de"]].append((f["para"], i))
    back, estado = set(), {}

    def dfs(n):
        estado[n] = 1
        for v, i in sorted(suc[n], key=lambda x: not m["fluxos"][x[1]].get("principal", False)):
            if estado.get(v) == 1:
                back.add(i)
            elif v not in estado:
                dfs(v)
        estado[n] = 2

    sys.setrecursionlimit(10000)
    dfs(next(e["id"] for e in m["elementos"] if e["tipo"] == "inicio"))
    for n in els:
        if n not in estado:
            dfs(n)
    return back


def _ordenar_raias(m: dict, els: dict, back: set[int]) -> list[str]:
    """Ordem das raias que minimiza a distância vertical percorrida pelos fluxos. Raias externas
    (concessionária, terceiros) ficam no fim; laços pesam para baixo (o corredor fica sob a piscina)."""
    ids = [r["id"] for r in m["raias"]]
    nomes = {r["id"]: r["nome"].lower() for r in m["raias"]}
    ext = [r for r in ids if r == "EXT" or any(k in nomes[r] for k in ("concession", "extern", "terceir"))]
    livres = [r for r in ids if r not in ext]
    if len(livres) > 7:
        return livres + ext
    inicio = next(e for e in m["elementos"] if e["tipo"] == "inicio")["raia"]
    melhor, custo_min = None, None
    for perm in permutations(livres):
        ordem = list(perm) + ext
        idx = {r: k for k, r in enumerate(ordem)}
        fundo = len(ordem) - 1
        c = 0.0
        for i, f in enumerate(m["fluxos"]):
            a, b = idx[els[f["de"]]["raia"]], idx[els[f["para"]]["raia"]]
            c += 0.4 * ((fundo - a) + (fundo - b)) if i in back else abs(a - b)
        c += 0.5 * idx[inicio] + 0.01 * sum(abs(k - ids.index(r)) for k, r in enumerate(ordem))
        if custo_min is None or c < custo_min:
            melhor, custo_min = ordem, c
    return melhor


def _colorir(intervalos: list[tuple[float, float, object]], folga: float) -> dict:
    """Coloração gulosa de intervalos: intervalos que se sobrepõem recebem trilhos diferentes."""
    trilho, fins = {}, []
    for a, b, chave in sorted(intervalos, key=lambda t: (t[0], t[1])):
        for k, f in enumerate(fins):
            if f + folga <= a:
                fins[k] = b
                trilho[chave] = k
                break
        else:
            fins.append(b)
            trilho[chave] = len(fins) - 1
    return trilho


def _ordenar_trilhos(pedidos: list) -> list:
    """Ordem dos trilhos verticais de um vão que minimiza cruzamentos. Cada trilho tem duas pontas
    (y, lado do trecho horizontal: E = esquerda, D = direita). Com o trilho i à esquerda de j, cruzam:
    pontas de i que seguem à direita na altura do trecho de j, e pontas de j que vêm da esquerda na
    altura do trecho de i."""
    def faixa(pts):
        return min(y for y, _ in pts), max(y for y, _ in pts)

    def custo_par(a, b):  # a à esquerda de b
        (a1, a2), (b1, b2) = faixa(a), faixa(b)
        cruz = (sum(1 for y, l in a if l == "D" and b1 < y < b2)
                + sum(1 for y, l in b if l == "E" and a1 < y < a2))
        # sobreposição: toco que vem da esquerda até b corre na mesma altura do toco que sai de a para a direita
        sobre = sum(1 for y, l in b if l == "E" for y2, l2 in a if l2 == "D" and abs(y - y2) < 3)
        return cruz + 3 * sobre

    n = len(pedidos)
    if n <= 1:
        return [k for _, k in pedidos]
    par = {(i, j): custo_par(pedidos[i][0], pedidos[j][0]) for i in range(n) for j in range(n) if i != j}
    if n <= 7:
        melhor = min(permutations(range(n)),
                     key=lambda p: sum(par[(p[a], p[b])] for a in range(n) for b in range(a + 1, n)))
    else:  # inserção gulosa
        melhor = []
        for i in range(n):
            pos_ = min(range(len(melhor) + 1), key=lambda k: sum(par[(x, i)] for x in melhor[:k])
                       + sum(par[(i, x)] for x in melhor[k:]))
            melhor.insert(pos_, i)
    return [pedidos[i][1] for i in melhor]


def diagramar(m: dict, ordem_raia: list[str] | None = None, dobra_cedo: bool = False) -> dict:
    """Layout + roteamento. Colunas por camada topológica; cada vão entre colunas tem trilhos verticais
    próprios (um por fluxo cujo trecho vertical se sobrepõe a outro); trechos horizontais só cruzam
    colunas por linhas livres — senão correm pela margem inferior da raia; laços usam o corredor sob a
    piscina. Entradas e saídas das tarefas são espalhadas ao longo da lateral."""
    els = {e["id"]: e for e in m["elementos"]}
    fl = m["fluxos"]
    back = _back_edges(m, els)
    ordem_raia = ordem_raia or _ordenar_raias(m, els, back)

    # colunas: caminho mais longo no DAG
    pred = defaultdict(list)
    for i, f in enumerate(fl):
        if i not in back:
            pred[f["para"]].append(f["de"])
    col = {}

    def coluna(n, pilha=()):
        if n not in col:
            col[n] = 0 if not pred[n] else max(coluna(p, pilha + (n,)) + 1 for p in pred[n] if p not in pilha)
        return col[n]

    for n in els:
        coluna(n)

    # sub-linhas (ramo alternativo na mesma raia desce; conflitos empilham)
    n_saidas = defaultdict(int)
    for f in fl:
        n_saidas[f["de"]] += 1
    sub = {n: 0 for n in els}
    for i, f in enumerate(fl):
        o, d = els[f["de"]], els[f["para"]]
        if (i not in back and o["tipo"] in ("xor", "paralelo") and not f.get("principal")
                and o["raia"] == d["raia"] and n_saidas[o["id"]] > 1):
            sub[d["id"]] = max(sub[d["id"]], sub[o["id"]] + 1)
    for _ in range(len(els)):
        mudou = False
        for n in els:
            ps = [p for p in pred[n] if els[p]["raia"] == els[n]["raia"]]
            if ps and els[n]["tipo"] not in ("xor_juncao", "paralelo_juncao") and min(sub[p] for p in ps) > sub[n]:
                sub[n] = min(sub[p] for p in ps)
                mudou = True
        if not mudou:
            break
    ocupado = defaultdict(list)
    for n in sorted(els, key=lambda n: (col[n], sub[n])):
        chave = (els[n]["raia"], col[n])
        while sub[n] in ocupado[chave]:
            sub[n] += 1
        ocupado[chave].append(sub[n])

    # raias e coordenada y de cada elemento
    max_sub = defaultdict(int)
    for n, e in els.items():
        max_sub[e["raia"]] = max(max_sub[e["raia"]], sub[n])
    topo, altura, y = {}, {}, 0
    for r in ordem_raia:
        topo[r] = y
        altura[r] = max(LANE_MIN, LANE_PAD_TOP + TASK_H // 2 + 45 + SUBROW_H * max_sub[r])
        y += altura[r]
    alt_raias = y
    cy = {n: topo[e["raia"]] + LANE_PAD_TOP + sub[n] * SUBROW_H for n, e in els.items()}
    wh = {n: tamanho(e["tipo"]) for n, e in els.items()}
    celula = {(els[n]["raia"], sub[n], col[n]): n for n in els}
    linha = {n: (els[n]["raia"], sub[n]) for n in els}

    def livre(lin, c1, c2):  # colunas c1..c2 (inclusive) da linha `lin` sem elementos
        return all((lin[0], lin[1], c) not in celula for c in range(c1, c2 + 1))

    # portas: espalha entradas (lado esquerdo) e saídas (lado direito) das tarefas
    entradas, saidas_ = defaultdict(list), defaultdict(list)
    for i, f in enumerate(fl):
        entradas[f["para"]].append(i)
        saidas_[f["de"]].append(i)
    y_ent, y_sai = {}, {}

    def espalhar(n, lista, chave_ordem, destino):
        if els[n]["tipo"] != "tarefa" or len(lista) < 2:
            for i in lista:
                destino[i] = cy[n]
            return
        passo = min(18, (TASK_H - 24) // (len(lista) - 1))
        base = cy[n] - passo * (len(lista) - 1) / 2
        for k, i in enumerate(sorted(lista, key=chave_ordem)):
            destino[i] = round(base + k * passo)

    for n in els:
        espalhar(n, entradas[n], lambda i: (i in back, cy[fl[i]["de"]]), y_ent)
        espalhar(n, saidas_[n], lambda i: (i in back, cy[fl[i]["para"]]), y_sai)

    # plano de cada fluxo (independente de x)
    plano, pedidos_trilho, pedidos_canal, pedidos_corr = {}, [], [], []
    vertice_usado, vertice_ent = defaultdict(set), defaultdict(set)  # vértices de saída / entrada já usados
    eh_gw = {n: e["tipo"].startswith(("xor", "paralelo")) for n, e in els.items()}

    def coluna_livre(c, y1, y2, exceto):
        return not [n for n in els if col[n] == c and n != exceto and min(y1, y2) < cy[n] < max(y1, y2)]

    for i, f in enumerate(fl):
        s, t = f["de"], f["para"]
        cs, ct = col[s], col[t]
        sy, ty = y_sai[i], y_ent[i]
        if i in back:
            # laço: decisão sai pelo vértice de baixo e junção recebe pelo vértice de baixo, se a coluna
            # estiver livre até o corredor; senão, trilho no vão
            sai_v = (eh_gw[s] and "baixo" not in vertice_usado[s] and "baixo" not in vertice_ent[s]
                     and coluna_livre(cs, cy[s], alt_raias + 1, s))
            ent_v = (eh_gw[t] and "baixo" not in vertice_ent[t] and not vertice_usado[t] & {"baixo", "baixo_laco"}
                     and coluna_livre(ct, cy[t], alt_raias + 1, t))
            if sai_v:
                vertice_usado[s].add("baixo_laco")
            if ent_v:
                vertice_ent[t].add("baixo")
            plano[i] = ("laco", cs, ct - 1, sai_v, ent_v)
            pedidos_corr.append((min(cs, ct), max(cs, ct), i))
            continue
        o = els[s]
        if o["tipo"] in ("xor", "paralelo") and not f.get("principal") and n_saidas[s] > 1 and cy[t] != cy[s]:
            dirv = "baixo" if cy[t] > cy[s] else "cima"
            # várias saídas para o mesmo lado formam um pente: tronco no vértice e um braço por destino
            if (coluna_livre(cs, cy[s], cy[t], s) and livre(linha[t], cs, ct - 1)
                    and dirv not in vertice_ent[s] and dirv + "_laco" not in vertice_usado[s]):
                vertice_usado[s].add(dirv)
                plano[i] = ("vertice", dirv)
                continue
        if eh_gw[t] and len(entradas[t]) > 1 and cy[s] != cy[t]:
            # junção: quem vem de cima entra pelo vértice de cima; quem vem de baixo, pelo de baixo
            dirv = "cima" if cy[s] < cy[t] else "baixo"
            if (dirv not in vertice_ent[t] and not vertice_usado[t] & {dirv, dirv + "_laco"}
                    and livre(linha[s], cs + 1, ct) and coluna_livre(ct, sy, cy[t], t)):
                vertice_ent[t].add(dirv)
                plano[i] = ("entra_vertice", dirv)
                continue
        # dobra perto do destino (segue na linha da origem) ou perto da origem (segue na linha do destino)
        opcoes = [(ct - 1, livre(linha[s], cs + 1, ct - 1)), (cs, livre(linha[t], cs + 1, ct - 1))]
        if dobra_cedo:
            opcoes.reverse()
        vao = next((g for g, ok in opcoes if ok), None)
        if sy == ty and livre(linha[s], cs + 1, ct - 1):
            plano[i] = ("reta",)
        elif vao is not None:
            plano[i] = ("trilho", vao)
            pedidos_trilho.append((vao, [(sy, "E"), (ty, "D")], (i, 0)))
        else:  # canal na margem inferior da raia de origem (destino abaixo) ou da raia de cima (destino acima)
            rs = els[s]["raia"]
            ri = ordem_raia.index(rs)
            raia_canal = rs if (cy[t] >= cy[s] or ri == 0) else ordem_raia[ri - 1]
            plano[i] = ("canal", cs, ct - 1, raia_canal)
            pedidos_canal.append((raia_canal, cs, ct, i))

    # canais (margem inferior das raias) e corredor (sob a piscina): coloração por faixa de colunas
    canal_slot = {}
    for r in ordem_raia:
        canal_slot.update(_colorir([(a, b, i) for rr, a, b, i in pedidos_canal if rr == r], 0.5))
    y_canal = {i: topo[p[3]] + altura[p[3]] - 14 - 8 * canal_slot[i] for i, p in plano.items() if p[0] == "canal"}
    # corredor: laços mais curtos mais perto da piscina, os que os envolvem mais fundo (sem cruzar as subidas)
    corr_slot, faixas = {}, []
    for a, b, i in sorted(pedidos_corr, key=lambda t: (t[1] - t[0], t[0])):
        k = 0
        while any(kk == k and not (b < aa or bb < a) for aa, bb, kk in faixas):
            k += 1
        corr_slot[i] = k
        faixas.append((a, b, k))
    n_corr = max(corr_slot.values(), default=-1) + 1
    y_corr = {i: alt_raias + 20 + PASSO_CORR * k for i, k in corr_slot.items()}
    for i, p in plano.items():
        if p[0] == "canal":
            pedidos_trilho.append((p[1], [(y_sai[i], "E"), (y_canal[i], "D")], (i, 0)))
            pedidos_trilho.append((p[2], [(y_canal[i], "E"), (y_ent[i], "D")], (i, 1)))
        elif p[0] == "laco":
            if not p[3]:
                pedidos_trilho.append((p[1], [(y_sai[i], "E"), (y_corr[i], "E")], (i, 0)))
            if not p[4]:
                pedidos_trilho.append((p[2], [(y_corr[i], "D"), (y_ent[i], "D")], (i, 1)))

    # trilhos por vão; largura do vão conforme o número de trilhos
    n_col = max(col.values()) + 1
    trilho, n_trilhos = {}, defaultdict(int)
    for g in range(-1, n_col):
        ordem = _ordenar_trilhos([(pts, k) for gg, pts, k in pedidos_trilho if gg == g])
        trilho.update({(g, k): v for v, k in enumerate(ordem)})
        n_trilhos[g] = len(ordem)
    larg_vao = {g: max(GAP if g >= 0 else 24, 36 + TRILHO * max(n_trilhos[g] - 1, 0)) for g in range(-1, n_col)}
    larg_col = [max([wh[n][0] for n in els if col[n] == c] or [GW]) for c in range(n_col)]
    x_col, x_vao, xa = [], {}, X0
    x_vao[-1] = xa
    xa += larg_vao[-1]
    for c in range(n_col):
        x_col.append(xa + larg_col[c] // 2)
        xa += larg_col[c]
        x_vao[c] = xa
        xa += larg_vao[c]
    largura = xa + 30

    def x_trilho(g, i, parte):
        n = max(n_trilhos[g], 1)
        ini = x_vao[g] + (larg_vao[g] - TRILHO * (n - 1)) / 2
        return round(ini + TRILHO * trilho[(g, (i, parte))])

    pos = {n: (x_col[col[n]], cy[n], *wh[n]) for n in els}

    def dir_(n):
        return pos[n][0] + pos[n][2] // 2

    def esq(n):
        return pos[n][0] - pos[n][2] // 2

    caminhos, rotulos, larguras = {}, {}, {}
    for i, f in enumerate(fl):
        s, t = f["de"], f["para"]
        sx, sy, ex, ty = dir_(s), y_sai[i], esq(t), y_ent[i]
        p = plano[i]
        if p[0] == "reta":
            pts = [(sx, sy), (ex, ty)]
        elif p[0] == "vertice":
            sinal = 1 if p[1] == "baixo" else -1
            vx, vy = pos[s][0], pos[s][1] + sinal * pos[s][3] // 2
            pts = [(vx, vy), (vx, ty), (ex, ty)]
        elif p[0] == "entra_vertice":
            sinal = -1 if p[1] == "cima" else 1
            vx, vy = pos[t][0], pos[t][1] + sinal * pos[t][3] // 2
            pts = [(sx, sy), (vx, sy), (vx, vy)]
        elif p[0] == "trilho":
            xt = x_trilho(p[1], i, 0)
            pts = [(sx, sy), (xt, sy), (xt, ty), (ex, ty)]
        elif p[0] == "canal":
            yc = y_canal[i]
            x1, x2 = x_trilho(p[1], i, 0), x_trilho(p[2], i, 1)
            pts = [(sx, sy), (x1, sy), (x1, yc), (x2, yc), (x2, ty), (ex, ty)]
        else:  # laço pelo corredor sob a piscina
            yc = y_corr[i]
            ini = ([(pos[s][0], pos[s][1] + pos[s][3] // 2), (pos[s][0], yc)] if p[3]
                   else [(sx, sy), (x_trilho(p[1], i, 0), sy), (x_trilho(p[1], i, 0), yc)])
            fim_ = ([(pos[t][0], yc), (pos[t][0], pos[t][1] + pos[t][3] // 2)] if p[4]
                    else [(x_trilho(p[2], i, 1), yc), (x_trilho(p[2], i, 1), ty), (ex, ty)])
            pts = ini + fim_
        pts = [pt for k, pt in enumerate(pts) if k == 0 or pt != pts[k - 1]]
        caminhos[i] = pts
        larguras[i] = min(ROT_MAX, 6.5 * len(f.get("rotulo") or "") + 8)
        if f.get("rotulo"):
            larg = min(ROT_MAX, 6.5 * len(f["rotulo"]) + 8)
            if p[0] == "vertice" and len([j for j in saidas_[s] if plano[j] == p]) > 1:
                # pente: rótulo no braço; se o braço for curto, à esquerda do tronco
                braco = pts[2][0] - pts[1][0]
                rotulos[i] = ((pts[1][0] + 6) if braco >= larg + 10 else (pts[1][0] - larg - 4), pts[1][1] - 19)
            elif f.get("principal") and pts[1][1] == pts[0][1]:
                # saída principal: logo à direita do losango; acima da linha se algo desce pelo vértice de baixo
                desce = vertice_usado[s] & {"baixo", "baixo_laco"}
                rotulos[i] = (sx + 6, sy - 20 if desce else sy + 4)
            elif p[0] == "laco" and p[3] and len([j for j in saidas_[s] if plano[j][0] == "laco" and plano[j][3]]) > 1:
                rotulos[i] = (pts[1][0] - larg - 6, pts[1][1] - 18)  # pente de laços: rótulo no braço do corredor
            elif p[0] == "vertice" or (p[0] == "laco" and p[3]):
                desce = p[0] == "laco" or p[1] == "baixo"
                rotulos[i] = (pts[0][0] + 6, pts[0][1] + (4 if desce else -22))
            elif len(pts) >= 3 and pts[-1][0] - pts[-2][0] >= larg + 12:
                rotulos[i] = (pts[-1][0] - larg - 6, pts[-1][1] - 19)  # no trecho que chega ao destino
            elif len(pts) >= 3:
                (xa, ya), (xb, yb) = pts[1], pts[2]
                rotulos[i] = (xa + 5, (ya + yb) / 2 - 9)  # ao lado do trilho vertical
            else:
                rotulos[i] = (sx + 4, sy - 20)
    alt_total = alt_raias + (26 + PASSO_CORR * n_corr if n_corr else 0)
    return dict(els=els, pos=pos, caminhos=caminhos, rotulos=rotulos, larguras=larguras, ordem_raia=ordem_raia, topo=topo,
                altura=altura, largura=largura, alt_raias=alt_raias, alt_total=alt_total, larg_vao=larg_vao, col=col,
                vizinho_esq={n: (els[n]["raia"], sub[n], col[n] - 1) in celula for n in els},
                sai_cima={n: "cima" in vertice_usado[n] or "cima" in vertice_ent[n] for n in els})


def melhor_diagrama(m: dict) -> dict:
    """Testa as ordens de raia (externas sempre no fim) e fica com a de menor custo visual medido no
    próprio desenho: atravessar elemento pesa 10, sobreposição 3, cruzamento 1, cada raia acima da do
    início 1,5; empate pela ordem que minimiza a distância vertical dos fluxos."""
    els = {e["id"]: e for e in m["elementos"]}
    base = _ordenar_raias(m, els, _back_edges(m, els))
    nomes = {r["id"]: r["nome"].lower() for r in m["raias"]}
    ext = [r for r in base if r == "EXT" or any(k in nomes[r] for k in ("concession", "extern", "terceir"))]
    livres = [r for r in base if r not in ext]
    inicio = next(e for e in m["elementos"] if e["tipo"] == "inicio")["raia"]
    candidatos = [base] + ([list(p) + ext for p in permutations(livres)] if len(livres) <= 6 else [])
    melhor, custo_min = None, None
    for k, (ordem, cedo) in enumerate((o, c) for o in candidatos for c in (False, True)):
        D = diagramar(m, ordem, cedo)
        caixas = {n: (x - w / 2, y - h / 2, w, h) for n, (x, y, w, h) in D["pos"].items()}
        fluxos = {i: (f["de"], f["para"]) for i, f in enumerate(m["fluxos"])}
        segs = {i: list(zip(p, p[1:])) for i, p in D["caminhos"].items()}
        a, s_, c = metricas_segs(caixas, fluxos, segs)
        # início no alto: cada raia acima da do início custa 1,5 (leitura de cima para baixo)
        custo = (10 * a + 3 * s_ + c + 1.5 * ordem.index(inicio), k > 0)
        if custo_min is None or custo < custo_min:
            melhor, custo_min = D, custo
    melhor["custo"] = custo_min[0]
    return melhor


def nome_tarefa(e: dict) -> str:
    met = " · ".join(x for x in [e.get("freq") and f"{e['freq']} casos", e.get("du") and f"espera {e['du']} du",
                                 e.get("horas")] if x)
    return e["nome"] + (f"\n[{met}]" if met else "")


def _faixa_num(s):
    v = [float(x.replace(",", ".")) for x in re.findall(r"\d+(?:[.,]\d+)?", str(s or ""))]
    return (min(v), max(v)) if v else None


def metricas_das_fichas(m: dict) -> dict:
    """Casos, dias úteis e horas de cada tarefa vêm das fichas calculadas (fichas_<Pxx>.json), não do texto
    do modelo: uma única fonte para o desenho, o painel e a avaliação."""
    arq = DIR / f"fichas_{m['codigo']}.json"
    if not arq.exists():
        return m
    fic = json.loads(arq.read_text(encoding="utf-8"))
    n_casos = len(fic["processo"]["casos"])
    m = json.loads(json.dumps(m))
    for e in m["elementos"]:
        a = fic["atividades"].get(e["id"])
        if e["tipo"] != "tarefa" or not a:
            continue
        e["freq"] = f"{a['casos_com_evidencia']}/{n_casos}"
        e["du"] = a["espera_du"]["antes"]
        # situação e nota saem dos fatos, não do texto do modelo
        maior_espera = (_faixa_num(a["espera_du"]["antes"]) or (0, 0))[1]
        e["status"] = "espera" if maior_espera >= 20 else ("perda" if a["sinais_perda"] else "normal")
        partes = []
        if maior_espera >= 20 and a["espera_du"]["posse_na_espera"]:
            partes.append("Espera com " + ", ".join(a["espera_du"]["posse_na_espera"][:2]))
        if a["sinais_perda"]:
            partes.append("Perda: " + ", ".join(k.lower() for k in list(a["sinais_perda"])[:2]))
        e["nota"] = "; ".join(partes) or None
        piso, teto = _faixa_num(a["trabalho_h"]["piso"]), _faixa_num(a["trabalho_h"]["teto"])
        if piso and teto:
            lo, hi = min(piso[0], teto[0]), max(piso[1], teto[1])
            e["horas"] = f"{lo:.0f}–{hi:.0f} h" if round(lo) != round(hi) else f"{lo:.0f} h"
    return m


def _num(v) -> str:
    return f"{v:g}".replace(".", ",")


def procedimento(cod: str) -> dict | None:
    arq = F2 / f"procedimento_{cod}.json"
    return json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else None


def metricas_da_coorte(m: dict, proc: dict) -> dict:
    """Casos (%), espera antes e horas-piso (medianas) de cada tarefa na coorte; situação pela mediana da espera
    e pela frequência dos sinais de perda ancorados nas fichas."""
    m = json.loads(json.dumps(m))
    for e in m["elementos"]:
        a = proc["atividades"].get(e["id"])
        if e["tipo"] != "tarefa" or not a:
            continue
        e["freq"] = f"{a['pct_casos']}% de {proc['casos']}"
        if not a["casos"]:
            continue
        esp, hp = a.get("espera_antes_du"), a.get("horas_piso")
        if esp:
            e["du"] = _num(esp["mediana"])
        if hp:
            e["horas"] = f"{_num(hp['mediana'])} h"
        perdas = [s_ for s_ in a.get("sinais_perda") or [] if s_["casos"] >= PERDA_FRAC * a["casos"]]
        espera = bool(esp) and esp["mediana"] >= ESPERA_DOMINANTE_DU
        e["status"] = "espera" if espera else ("perda" if perdas else "normal")
        partes = []
        if espera:
            partes.append(f"Espera mediana {_num(esp['mediana'])} du (q3 {_num(esp['q3'])})")
        if perdas:
            partes.append("Perda: " + ", ".join(f"{s_['item'].replace('_', ' ')} ({round(100 * s_['casos'] / a['casos'])}%)"
                                                for s_ in perdas[:2]))
        e["nota"] = "; ".join(partes) or None
    return m


def probabilidades_ramos(m: dict, transicoes: dict) -> dict[int, tuple[int, int]]:
    """Fluxo que sai de uma decisão → (transições observadas, %). Atividade anterior = tarefas (ou início) que
    chegam à decisão passando só por eventos e junções; ramo = primeiras tarefas (ou fim) alcançadas pelo fluxo."""
    els = {e["id"]: e for e in m["elementos"]}
    ent, sai = defaultdict(list), defaultdict(list)
    for i, f in enumerate(m["fluxos"]):
        ent[f["para"]].append(f["de"])
        sai[f["de"]].append((i, f["para"]))
    t = {a: {x["para"]: x["n"] for x in v} for a, v in transicoes.items()}

    def andar(n, viz, vis, para_tras):
        if n in vis:
            return set()
        vis.add(n)
        tipo = els[n]["tipo"]
        if tipo == "tarefa":
            return {n}
        if tipo == "inicio" and para_tras:
            return {"início"}
        if tipo == "fim" and not para_tras:
            return {"fim"}
        return set().union(*[andar(x, viz, vis, para_tras) for x in viz(n)]) if viz(n) else set()

    out = {}
    for g, e in els.items():
        if e["tipo"] != "xor" or len(sai[g]) < 2:
            continue
        antes = set().union(*[andar(x, lambda n: ent[n], set(), True) for x in ent[g]])
        ramos = {i: andar(p, lambda n: [b for _, b in sai[n]], {g}, False) for i, p in sai[g]}
        todos = [x for r in ramos.values() for x in r]
        if len(todos) != len(set(todos)) or not all(ramos.values()):
            continue  # ramos que levam à mesma atividade: a trilha não distingue o caminho
        n = {i: sum(t.get(a, {}).get(b, 0) for a in antes for b in r) for i, r in ramos.items()}
        tot = sum(n.values())
        if tot >= MIN_TRANSICOES:
            out.update({i: (v, round(100 * v / tot)) for i, v in n.items()})
    return out


def _desencostar(D: dict) -> None:
    """Rótulo de fluxo que cobre uma forma ou outro rótulo vai para a 1ª posição livre ao redor (acima, abaixo,
    à esquerda); se nenhuma estiver livre, fica onde estava."""
    caixas = [(x - w / 2, y - h / 2, w, h) for x, y, w, h in D["pos"].values()]
    ov = lambda a, b: a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]  # noqa: E731
    postos = []
    for i, (lx, ly) in sorted(D["rotulos"].items()):
        w = D["larguras"][i]
        for dx, dy in [(dx, dy) for dx in (0, -w / 2, -w - 12) for dy in (0, -20, 20, -40, 40, -50, 60, -64)]:
            r = (lx + dx, ly + dy, w, 18)
            if not any(ov(r, c) for c in caixas + postos):
                D["rotulos"][i] = (r[0], r[1])
                break
        postos.append((*D["rotulos"][i], w, 18))


def bpmn_xml(m: dict) -> str:
    proc = procedimento(m["codigo"])
    nome_pool = m["nome"] + " (AS-IS)"
    if proc:
        m = metricas_da_coorte(m, proc)
        nome_pool = f"{m['nome']} (AS-IS · {proc['casos']} casos · {SITUACAO[proc['situacao']]})"
        prob = probabilidades_ramos(m, proc["transicoes"])
        for i, (v, pct) in prob.items():
            f = m["fluxos"][i]
            f["rotulo"] = f"{f['rotulo']} · {pct}%" if f.get("rotulo") else f"{pct}%"
            f["_n"] = v
    else:
        m = metricas_das_fichas(m)
    D = melhor_diagrama(m)
    _desencostar(D)
    els, pos, caminhos, topo, altura = D["els"], D["pos"], D["caminhos"], D["topo"], D["altura"]
    largura, alt_raias, alt_total = D["largura"], D["alt_raias"], D["alt_total"]
    raias = sorted(m["raias"], key=lambda r: D["ordem_raia"].index(r["id"]))
    cod = m["codigo"]
    pid, colab = f"Processo_{cod}", f"Colab_{cod}"
    entra, sai = defaultdict(list), defaultdict(list)
    for i, f in enumerate(m["fluxos"]):
        sai[f["de"]].append(f"F{i}")
        entra[f["para"]].append(f"F{i}")
    q = lambda s: escape(str(s), {'"': "&quot;", "\n": "&#10;"})  # noqa: E731
    x = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" '
         'xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" '
         'xmlns:di="http://www.omg.org/spec/DD/20100524/DI" '
         'xmlns:color="http://www.omg.org/spec/BPMN/non-normative/color/1.0" '
         f'id="Defs_{cod}" targetNamespace="https://agenersa.rj.gov.br/mapeamento" exporter="mapeamento-sei" exporterVersion="1">',
         f'  <bpmn:collaboration id="{colab}">',
         f'    <bpmn:participant id="Part_{cod}" name="{q(cod + " — " + nome_pool)}" processRef="{pid}" />']
    notas = [(n, e["nota"]) for n, e in els.items() if e.get("nota")]
    x += [f'  </bpmn:collaboration>', f'  <bpmn:process id="{pid}" isExecutable="false">',
          f'    <bpmn:documentation>{q(m.get("escopo", ""))} Fontes: {q(m.get("fontes", ""))}</bpmn:documentation>',
          f'    <bpmn:laneSet id="LaneSet_{cod}">']
    for r in raias:
        x.append(f'      <bpmn:lane id="Lane_{r["id"].replace("-", "_")}" name="{q(r["nome"])}">')
        x += [f'        <bpmn:flowNodeRef>{n}</bpmn:flowNodeRef>' for n, e in els.items() if e["raia"] == r["id"]]
        x.append('      </bpmn:lane>')
    x.append('    </bpmn:laneSet>')
    for n, e in els.items():
        tag = TIPO_XML[e["tipo"]]
        nome = nome_tarefa(e) if e["tipo"] == "tarefa" else e.get("nome", "")
        x.append(f'    <bpmn:{tag} id="{n}" name="{q(nome)}">')
        doc = "; ".join(f"{k}: {e[k]}" for k in ("freq", "du", "horas", "status", "nota") if e.get(k))
        if doc:
            x.append(f'      <bpmn:documentation>{q(doc)}</bpmn:documentation>')
        x += [f'      <bpmn:incoming>{f}</bpmn:incoming>' for f in entra[n]]
        x += [f'      <bpmn:outgoing>{f}</bpmn:outgoing>' for f in sai[n]]
        if e["tipo"] == "evento_tempo":
            x.append(f'      <bpmn:timerEventDefinition id="Timer_{n}" />')
        if e["tipo"] == "evento_mensagem":
            x.append(f'      <bpmn:messageEventDefinition id="Msg_{n}" />')
        x.append(f'    </bpmn:{tag}>')
    for i, f in enumerate(m["fluxos"]):
        rot = f' name="{q(f["rotulo"])}"' if f.get("rotulo") else ""
        doc = (f'<bpmn:documentation>{f["_n"]} transições observadas na coorte</bpmn:documentation>'
               if "_n" in f else "")
        x.append(f'    <bpmn:sequenceFlow id="F{i}"{rot} sourceRef="{f["de"]}" targetRef="{f["para"]}">{doc}'
                 '</bpmn:sequenceFlow>')
    for j, (n, txt) in enumerate(notas):
        x += [f'    <bpmn:textAnnotation id="Nota_{j}"><bpmn:text>{q(txt)}</bpmn:text></bpmn:textAnnotation>',
              f'    <bpmn:association id="Assoc_{j}" sourceRef="{n}" targetRef="Nota_{j}" />']
    x += ['  </bpmn:process>', f'  <bpmndi:BPMNDiagram id="Diag_{cod}">',
          f'    <bpmndi:BPMNPlane id="Plane_{cod}" bpmnElement="{colab}">',
          f'      <bpmndi:BPMNShape id="Part_{cod}_di" bpmnElement="Part_{cod}" isHorizontal="true">',
          f'        <dc:Bounds x="0" y="0" width="{largura}" height="{alt_total}" /></bpmndi:BPMNShape>']
    for r in raias:
        lid = f'Lane_{r["id"].replace("-", "_")}'
        h = altura[r["id"]] + (alt_total - alt_raias if r["id"] == raias[-1]["id"] else 0)
        x.append(f'      <bpmndi:BPMNShape id="{lid}_di" bpmnElement="{lid}" isHorizontal="true">'
                 f'<dc:Bounds x="{POOL_LABEL}" y="{topo[r["id"]]}" width="{largura - POOL_LABEL}" height="{h}" /></bpmndi:BPMNShape>')
    for n, e in els.items():
        cx, cy, w, h = pos[n]
        cor = ""
        if e.get("status") in CORES:
            f_, b_ = CORES[e["status"]]
            cor = f' color:background-color="{f_}" color:border-color="{b_}"'
        rotulo = ""
        if e["tipo"] != "tarefa" and e.get("nome"):
            # decisão: rótulo acima do losango (abaixo saem os ramos alternativos); eventos: abaixo
            if e["tipo"].startswith(("xor", "paralelo")):
                # acima e à esquerda (não corta a saída pelo vértice de cima); se houver elemento logo à
                # esquerda na mesma linha, acima e à direita
                lx = cx + 8 if D["vizinho_esq"][n] and not D["sai_cima"][n] else cx - 130
                ly = cy - h // 2 - 36
            else:
                lx, ly = cx - 60, cy + h // 2 + 4
            rotulo = (f'<bpmndi:BPMNLabel><dc:Bounds x="{lx}" y="{ly}" width="120" height="34" />'
                      f'</bpmndi:BPMNLabel>')
        x.append(f'      <bpmndi:BPMNShape id="{n}_di" bpmnElement="{n}"{cor}>'
                 f'<dc:Bounds x="{cx - w // 2}" y="{cy - h // 2}" width="{w}" height="{h}" />{rotulo}</bpmndi:BPMNShape>')
    for i, pts in caminhos.items():
        wp = "".join(f'<di:waypoint x="{a}" y="{b}" />' for a, b in pts)
        lab = ""
        if i in D["rotulos"]:
            lx, ly = D["rotulos"][i]
            lab = (f'<bpmndi:BPMNLabel><dc:Bounds x="{lx}" y="{ly}" width="{D["larguras"][i]:.0f}" height="18" />'
                   '</bpmndi:BPMNLabel>')
        x.append(f'      <bpmndi:BPMNEdge id="F{i}_di" bpmnElement="F{i}">{wp}{lab}</bpmndi:BPMNEdge>')
    for j, (n, _) in enumerate(notas):
        cx, cy, w, h = pos[n]
        ax, ay = cx - w // 2, cy - h // 2 - NOTA_H - 10
        x.append(f'      <bpmndi:BPMNShape id="Nota_{j}_di" bpmnElement="Nota_{j}">'
                 f'<dc:Bounds x="{ax}" y="{ay}" width="{w + 10}" height="{NOTA_H}" /></bpmndi:BPMNShape>')
        x.append(f'      <bpmndi:BPMNEdge id="Assoc_{j}_di" bpmnElement="Assoc_{j}">'
                 f'<di:waypoint x="{cx}" y="{cy - h // 2}" /><di:waypoint x="{cx}" y="{ay + NOTA_H}" /></bpmndi:BPMNEdge>')
    x += ['    </bpmndi:BPMNPlane>', '  </bpmndi:BPMNDiagram>', '</bpmn:definitions>']
    return "\n".join(x)


VIEWER_HTML = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>AS-IS __ORGAO__</title>
<style>
:root{--bg:#fff;--fg:#1d1d1f;--mut:#5f6368;--line:#d0d4d9;--acc:#1f4e79;--chip:#eef2f6}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#16181b;--fg:#e8eaed;--mut:#9aa0a6;--line:#3a3f45;--acc:#8ab4f8;--chip:#24282d}}
:root[data-theme="dark"]{--bg:#16181b;--fg:#e8eaed;--mut:#9aa0a6;--line:#3a3f45;--acc:#8ab4f8;--chip:#24282d}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,Segoe UI,Roboto,sans-serif}
header{padding:16px 16px 8px}h1{font-size:20px;margin:0 0 4px}p{margin:0;color:var(--mut);max-width:980px}
nav{display:flex;flex-wrap:wrap;gap:6px;padding:8px 16px}
nav button{border:1px solid var(--line);background:var(--chip);color:var(--fg);border-radius:6px;padding:6px 10px;cursor:pointer;font:inherit;font-size:14px}
nav button[aria-pressed="true"]{border-color:var(--acc);outline:2px solid var(--acc)}
.leg{display:flex;flex-wrap:wrap;gap:14px;padding:4px 16px 8px;color:var(--mut);font-size:13px}
.leg span::before{content:"";display:inline-block;width:12px;height:12px;margin-right:6px;vertical-align:-1px;border:1px solid}
.l1::before{background:#f8d7da;border-color:#b02a37!important}.l2::before{background:#fff3cd;border-color:#b58105!important}.l3::before{background:#fff;border-color:#222!important}
#info{padding:0 16px 8px;color:var(--mut);font-size:13px}
#canvas{height:calc(100vh - 210px);min-height:420px;border-top:1px solid var(--line);background:#fff}
.tools{padding:0 16px 8px;display:flex;gap:8px}.tools a,.tools button{font:inherit;font-size:13px;color:var(--acc);background:none;border:none;cursor:pointer;padding:0;text-decoration:underline}
</style></head><body>
<header><h1>AS-IS dos processos — __ORGAO__</h1>
<p>Fluxos canônicos reconstruídos da trilha real dos processos SEI. Em cada tarefa: % dos casos da coorte em que aparece, espera mediana antes da atividade (dias úteis) e horas de trabalho medianas (piso, a calibrar). Nos ramos de decisão: % das passagens observadas. Processos sem coorte mostram os casos do piloto.</p></header>
<nav id="tabs"></nav>
<div class="leg"><span class="l1">espera dominante (≥ 20 du com pouco trabalho)</span><span class="l2">sinal de perda (complementação, prazo, reiteração)</span><span class="l3">trabalho efetivo</span></div>
<div id="info"></div>
<div class="tools"><button id="fit">Ajustar à tela</button><a id="dl" download>Baixar .bpmn</a></div>
<div id="canvas"></div>
<script src="https://unpkg.com/bpmn-js@17.11.1/dist/bpmn-navigated-viewer.production.min.js"></script>
<script>
const MODELOS = __MODELOS__;
const viewer = new BpmnJS({container:'#canvas'});
const tabs = document.getElementById('tabs');
async function abrir(i){
  const m = MODELOS[i];
  [...tabs.children].forEach((b,j)=>b.setAttribute('aria-pressed', j===i));
  document.getElementById('info').textContent = m.escopo + ' — ' + m.fontes;
  await viewer.importXML(m.xml);
  viewer.get('canvas').zoom('fit-viewport');
  const a = document.getElementById('dl');
  a.href = URL.createObjectURL(new Blob([m.xml], {type:'application/xml'})); a.download = m.codigo + '.bpmn';
  try { localStorage.setItem('asis_aba', i) } catch(e) {}
}
MODELOS.forEach((m,i)=>{const b=document.createElement('button');b.textContent=m.codigo+' · '+m.nome;b.onclick=()=>abrir(i);tabs.appendChild(b)});
document.getElementById('fit').onclick=()=>viewer.get('canvas').zoom('fit-viewport');
let ini=0; try{ini=+(localStorage.getItem('asis_aba')||0)}catch(e){}
abrir(Math.min(ini, MODELOS.length-1));
</script></body></html>"""


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelos", type=Path, default=DIR, help="pasta com modelo_*.json (e destino dos .bpmn)")
    ap.add_argument("--visualizador", type=Path, default=VIEWER, help="pasta do index.html")
    args = ap.parse_args()
    modelos = sorted(args.modelos.glob("modelo_*.json"))
    args.visualizador.mkdir(parents=True, exist_ok=True)
    pacote, falhas = [], 0
    for arq in modelos:
        m = json.loads(arq.read_text(encoding="utf-8"))
        erros = validar(m)
        if erros:
            falhas += 1
            print(arq.name, "ERROS:", erros)
            continue
        xml = bpmn_xml(m)
        (args.modelos / f"{m['codigo']}.bpmn").write_text(xml, encoding="utf-8")
        pacote.append(dict(codigo=m["codigo"], nome=m["nome"], escopo=m.get("escopo", ""), fontes=m.get("fontes", ""),
                           xml=xml))
        print(m["codigo"], "ok —", len(m["elementos"]), "elementos")
    ordem = ORDEM_CODIGOS
    pacote.sort(key=lambda p: ordem.index(p["codigo"]) if p["codigo"] in ordem else 99)
    html = VIEWER_HTML.replace("__ORGAO__", ORGAO).replace("__MODELOS__", json.dumps(pacote, ensure_ascii=False).replace("</", "<\\/"))
    (args.visualizador / "index.html").write_text(html, encoding="utf-8")
    print("visualizador:", args.visualizador / "index.html", "| falhas:", falhas)


if __name__ == "__main__":
    main()
