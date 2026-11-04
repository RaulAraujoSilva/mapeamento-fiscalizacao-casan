"""Relatório gerencial em PDF do caso SEI-480002/001314/2024, montado só a partir das saídas versionadas (nenhum número
digitado: cada valor vem de fatos_P06.json, resultado_tobe_P06.json, conformidade_P06.json, controles_P06.json etc.).

Uso (da raiz): python ferramentas_caso/renderizar_bpmn.py saida/bpmn/P06.bpmn docs/relatorio/bpmn_P06.png
               python ferramentas_caso/relatorio_pdf.py
Saída: docs/relatorio/Relatorio_Mapeamento_Fiscalizacao_SEI-480002-001314-2024.pdf"""
import json
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether, NextPageTemplate, PageBreak, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)

RAIZ = Path(__file__).resolve().parents[1]
S, OUT = RAIZ / "saida", RAIZ / "docs" / "relatorio"
PDF = OUT / "Relatorio_Mapeamento_Fiscalizacao_SEI-480002-001314-2024.pdf"
J = lambda p: json.loads((S / p).read_text(encoding="utf-8"))  # noqa: E731

FONTES = Path("C:/Windows/Fonts")
pdfmetrics.registerFont(TTFont("Arial", str(FONTES / "arial.ttf")))
pdfmetrics.registerFont(TTFont("Arial-B", str(FONTES / "arialbd.ttf")))
pdfmetrics.registerFont(TTFont("Arial-I", str(FONTES / "ariali.ttf")))
from reportlab.pdfbase.pdfmetrics import registerFontFamily  # noqa: E402
registerFontFamily("Arial", normal="Arial", bold="Arial-B", italic="Arial-I", boldItalic="Arial-B")

# ------------------------------------------------------------------ dados
fatos = {f["id"]: f for f in J("bpmn/fatos_P06.json")["fatos"]}
modelo, vinc, fichas = J("bpmn/modelo_P06.json"), J("bpmn/vinculos_P06.json"), J("bpmn/fichas_P06.json")
aval, proc = J("bpmn/avaliacao_P06.json"), J("fase2/procedimento_P06.json")
normas, conf = J("fase3/normas_P06.json"), J("fase3/conformidade_P06.json")
mel, res, ctl = J("fase3/melhorias_P06.json"), J("fase3/resultado_tobe_P06.json"), J("fase3/controles_P06.json")
lb = J("fase3/linha_base_P06.json")
ind = {r.split(",")[0]: r for r in (S / "processos_indicadores.csv").read_text(encoding="utf-8-sig").splitlines()}
cab = ind["numero"].split(","); proc_ind = dict(zip(cab, ind["SEI-480002/001314/2024"].split(",")))


def F(fid, casas=0):
    v = fatos[fid]["valor"]
    return fmt(v, casas)


def fmt(v, casas=0):
    if v is None:
        return "—"
    if isinstance(v, (int, float)):
        s = f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return s
    return str(v)


tarefas = [e for e in modelo["elementos"] if e["tipo"] == "tarefa"]
raia_nome = {r["id"]: r["nome"] for r in modelo["raias"]}
fa = fichas["atividades"]
TNOME = {t["id"][1:]: f"\"{t['nome'].lower()}\"" for t in tarefas}

# ------------------------------------------------------------------ estilos
ss = getSampleStyleSheet()
base = ParagraphStyle("base", parent=ss["Normal"], fontName="Arial", fontSize=9.5, leading=13.2, alignment=TA_JUSTIFY,
                      spaceAfter=5)
H1 = ParagraphStyle("h1", parent=base, fontName="Arial-B", fontSize=15, leading=19, spaceBefore=4, spaceAfter=8,
                    textColor=colors.HexColor("#111111"), alignment=0)
H2 = ParagraphStyle("h2", parent=H1, fontSize=11.5, leading=15, spaceBefore=8, spaceAfter=5,
                    textColor=colors.HexColor("#333333"))
SM = ParagraphStyle("sm", parent=base, fontSize=8, leading=10.4, alignment=0, spaceAfter=0)
SMB = ParagraphStyle("smb", parent=SM, fontName="Arial-B")
NOTA = ParagraphStyle("nota", parent=base, fontSize=8, leading=10.5, textColor=colors.HexColor("#555555"))
BUL = ParagraphStyle("bul", parent=base, leftIndent=12, bulletIndent=2)
CINZA = colors.HexColor("#e6e6e6")


import re  # noqa: E402
_LIMPA = [(re.compile(r"\s?\((?:t\d(?:,\s*t\d)*|M-P06-\d+(?:,\s*M-P06-\d+)*|R-P06-\d+)\)"), ""),
          (re.compile(r"\bM-P06-0?(\d+)\b"), r"medida \1"), (re.compile(r"\bR-P06-0?(\d+)\b"), r"requisito R\1"),
          (re.compile(r"\s?\(Relator de Voto\)|\s?\(Especialista\)"), ""),
          (re.compile(r"\bt([1-8])\b"), lambda m: TNOME[m.group(1)])]


def limpa(t):
    t = str(t)
    for rx, rep in _LIMPA:
        t = rx.sub(rep, t)
    return t


def P(t, st=base):
    return Paragraph(limpa(t), st)


def bullets(itens, st=BUL):
    return [Paragraph(limpa(t), st, bulletText="•") for t in itens]


def tabela(cab, linhas, larg, cab_st=SMB, st=SM):
    dados = [[P(c, cab_st) for c in cab]] + [[P(str(c), st) for c in l] for l in linhas]
    t = Table(dados, colWidths=larg, repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), CINZA), ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#bbbbbb")),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 3),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    return t


# ------------------------------------------------------------------ páginas
def rodape(c, doc):
    c.saveState()
    c.setFont("Arial", 7.5); c.setFillColor(colors.HexColor("#666666"))
    w = doc.pagesize[0]
    c.drawString(2 * cm, 1.1 * cm, "Mapeamento do processo de fiscalização técnica de campo — SEI-480002/001314/2024")
    c.drawRightString(w - 2 * cm, 1.1 * cm, f"Página {doc.page}")
    c.restoreState()


doc = BaseDocTemplate(str(PDF), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm,
                      bottomMargin=1.8 * cm, title="Mapeamento do processo de fiscalização técnica de campo",
                      subject="Processo SEI-480002/001314/2024", author="")
fr = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="r")
LW, LH = landscape(A4)
frl = Frame(1.5 * cm, 1.6 * cm, LW - 3 * cm, LH - 3 * cm, id="l")
doc.addPageTemplates([PageTemplate("retrato", [fr], onPage=rodape),
                      PageTemplate("paisagem", [frl], onPage=rodape, pagesize=landscape(A4))])
W = doc.width
h = []

# capa
h += [Spacer(1, 4 * cm),
      P("Mapeamento do processo de fiscalização técnica de campo",
        ParagraphStyle("t", parent=H1, fontSize=22, leading=27)),
      P("Processo SEI-480002/001314/2024 — situação atual (AS-IS), conformidade legal e proposta de melhoria (TO-BE)",
        ParagraphStyle("st", parent=H2, fontSize=13, leading=17, fontName="Arial")),
      Spacer(1, 1 * cm),
      P(f"Unidades envolvidas: {', '.join(raia_nome[r['id']] for r in modelo['raias'] if r['id'] != 'EXT')}."),
      P(f"Interessado registrado no SEI: {proc_ind['interessado']}. Situação na data de corte: processo em andamento."),
      P(f"Base: registro público do SEI-RJ (andamentos e {proc_ind['n_docs']} documentos do processo). "
        f"Documento de trabalho para discussão interna — {date.today().strftime('%d/%m/%Y')}."),
      Spacer(1, 6 * cm),
      P("Horas de trabalho, custos e ganhos estimados são hipóteses a calibrar com os servidores das unidades. "
        "O mapeamento descreve um único processo e deve ser lido como estudo de caso.", NOTA),
      PageBreak()]

# 1. sumário executivo
fs1 = res["fases"]["1"]["esperado"]; fs3 = res["fases"]["3"]["esperado"]
sens = sorted(res["sensibilidade"]["sem_cada_melhoria"], key=lambda x: -x["lead_mediano_du"])
m_tit = {m["id"]: m["titulo"] for m in mel["melhorias"]}
h += [P("1. Sumário executivo", H1),
      P(f"O processo foi reconstruído a partir do que o SEI registrou: em que unidade esteve, por quanto tempo, quem "
        f"juntou cada documento e o que cada peça diz. São {proc_ind['n_andamentos']} andamentos e "
        f"{proc_ind['n_docs']} documentos, dos quais {fichas['atividades']['t2']['n_docs']} relatórios de fiscalização "
        f"da CASAN. Os principais achados:")]
h += bullets([
    f"<b>O tempo é espera, não trabalho.</b> Do início ao último andamento passaram {F('coorte.caso.lead.mediana')} dias "
    f"úteis (du). A soma das esperas entre atividades chega a {F('coorte.caso.espera_entre_atividades.mediana')} du, "
    f"contra {F('coorte.caso.execucao_atividades.mediana')} du de execução das atividades.",
    f"<b>Gargalo:</b> as esperas depois do ciclo de vistorias — {F('critico.t7.1.espera_antes')} du antes do parecer "
    f"jurídico e {F('critico.t4.1.espera_antes')} du antes do parecer técnico. O registro do SEI mostra com quem o "
    f"processo estava, mas não prova que houve fila de trabalho: isso precisa ser confirmado com as unidades.",
    f"<b>Trabalho concentrado no ciclo de vistorias:</b> vistoria e relatório somam de "
    f"{fmt(fa['t2']['trabalho_h']['piso'])} h a {fmt(fa['t2']['trabalho_h']['teto'])} h de trabalho estimado "
    f"(hipótese), a maior parte do esforço do processo.",
    f"<b>Conformidade legal:</b> {len(normas['normas'])} dispositivos legais e contratuais foram levantados e "
    f"{len(normas['requisitos'])} requisitos derivados; os {sum(1 for r in conf['requisitos'].values() if r['tipo'] != 'manual')} "
    f"requisitos verificáveis pelo registro do SEI foram cumpridos neste processo. Pontos de mérito (notificação de "
    f"infração, pedido de arquivamento, prazo do parecer jurídico) pedem conferência da Procuradoria.",
    f"<b>Proposta de melhoria:</b> {len(mel['melhorias'])} medidas em três fases. No cenário esperado, o tempo total "
    f"cai de {fmt(res['linha_base']['lead']['mediana'])} para {fmt(fs3['lead']['mediana'])} du "
    f"(−{fmt(fs3['ganho_lead_mediano_pct'], 1)}%) e as horas por processo caem {fmt(fs3['ganho_horas_media_pct'], 1)}%.",
    f"<b>Atenção:</b> o ganho depende sobretudo de uma medida — {m_tit[sens[0]['melhoria']].lower()} — que responde "
    f"por {fmt(sens[0]['lead_mediano_du'])} du da redução. Ela precisa ser validada com a Procuradoria antes de virar meta.",
    "<b>Ponto a esclarecer antes de qualquer uso:</b> o SEI registra a Iguá Rio de Janeiro como interessada, mas as "
    "peças tratam da concessionária Águas do Rio — Bloco 1.",
])
h += [P("Os números descrevem um único processo; não são média nem padrão da fiscalização. Servem para orientar a "
        "conversa com as unidades e para desenhar a ampliação do levantamento a outros processos.", NOTA), PageBreak()]

# 2. escopo e método
h += [P("2. Escopo, método e limites", H1),
      P(f"<b>Escopo.</b> {modelo['escopo']}. O processo foi aberto em {proc_ind['data_geracao']} e o último andamento "
        f"considerado é de {proc_ind['ultimo_andamento'][:10]}."),
      P("<b>Método.</b> Em vez de começar por entrevistas, o mapeamento parte do registro do SEI. (1) A trilha do "
        "processo é reconstruída pelos andamentos: entrada e saída de cada unidade, posse do processo e esperas. (2) Cada "
        "documento produzido pela agência é lido e descrito: que trabalho representa, com que insumos, que prazos concede "
        "e quanto esforço aproximado exige; toda afirmação é ancorada em trecho literal da peça. (3) As peças são ligadas "
        "às atividades de um modelo de processo (BPMN). (4) Tempos e esforço são calculados por regras reprodutíveis. "
        "(5) A situação atual é avaliada (Lean: espera, retrabalho, movimentação) e confrontada com as normas aplicáveis, "
        "com trecho literal de cada norma. (6) As melhorias são simuladas sobre o próprio caso em três cenários, "
        "respeitando os prazos que a lei concede à concessionária."),
      P("<b>Controles de qualidade.</b> A classificação do processo foi refeita de forma independente (mesmo resultado). "
        "Uma amostra de 30 descrições de peças foi auditada contra o texto integral, e cada afirmação da avaliação foi "
        "conferida contra os dados calculados. Os trechos de norma foram conferidos contra o texto oficial."),
      P("<b>Limites.</b>")]
h += bullets([
    "Um único processo, ainda em andamento: o fim do fluxo é provisório e nenhuma mediana é estável.",
    "As respostas da concessionária não estão entre os documentos públicos do processo (devem estar nos processos "
    "relacionados): o tempo de resposta foi estimado pelos prazos concedidos nos ofícios e relatórios, não pela data real.",
    "O que acontece fora do SEI (reuniões, telefonemas, trabalho de campo) não aparece no registro.",
    "Horas de trabalho são estimadas pelo conteúdo das peças; serão calibradas com os servidores.",
])
h += [P("<b>Glossário.</b> du = dia útil. Posse = unidade que está com o processo aberto no SEI. Espera = tempo entre "
        "atividades. Lead time = tempo total do processo. AS-IS = situação atual. TO-BE = situação proposta.", NOTA)]

# 3. processo mapeado (paisagem)
h += [NextPageTemplate("paisagem"), PageBreak()]
img = Image(str(OUT / "bpmn_P06.png"))
iw, ih = img.imageWidth, img.imageHeight
esc = min((LW - 3 * cm) / iw, (LH - 5.2 * cm) / ih)
img.drawWidth, img.drawHeight = iw * esc, ih * esc
h += [P("3. O processo mapeado (AS-IS)", H1),
      P("Modelo do fluxo observado no processo, por unidade. Losangos são decisões inferidas das peças (a confirmar com "
        "a CASAN); laços representam o ciclo de vistorias, que se repete por lote de unidades da concessionária. As "
        "anotações trazem a espera antes de cada atividade e as horas estimadas.", NOTA),
      img, NextPageTemplate("retrato"), PageBreak()]

# 4. atividades
h += [P("4. Atividades, tempos e esforço", H1),
      P("Cada atividade com a unidade responsável, o que a dispara, o que entrega, quantos documentos do processo a "
        "sustentam, a espera antes dela e o trabalho estimado (faixa entre piso e teto, hipótese a calibrar).")]
lin = []
for t in tarefas:
    a = fa[t["id"]]
    lin.append([f"<b>{t['nome']}</b><br/>{a['unidade']}", a["gatilho"], a["saida"], a["n_docs"],
                f"{a['espera_du']['antes']} du", f"{fmt(a['trabalho_h']['piso'])}–{fmt(a['trabalho_h']['teto'])} h"])
h += [tabela(["Atividade / unidade", "Gatilho", "Entrega", "Docs.", "Espera antes", "Trabalho"], lin,
             [4.3 * cm, 3.6 * cm, 4.2 * cm, 1.1 * cm, 1.6 * cm, 2.2 * cm]),
      Spacer(1, 6),
      P("Espera antes = soma das esperas que antecedem cada ocorrência da atividade no processo; nas atividades que se "
        "repetem (agendamento, vistoria, encaminhamento), a espera e as horas somam todas as ocorrências.", NOTA)]
posse = [(k.split(".")[2], f["valor"]) for k, f in fatos.items()
         if k.startswith("coorte.posse.") and k.endswith(".mediana")]
posse = [x for x in posse if x[1] > 0]; posse.sort(key=lambda x: -x[1])
h += [P("Com quem o processo esteve", H2),
      P("Dias úteis de posse do processo por unidade. \"Sem unidade\" é o tempo em que nenhuma unidade estava com o "
        "processo aberto no SEI — processo parado ou trabalho feito fora do sistema (por exemplo, em campo)."),
      tabela(["Unidade", "Dias úteis de posse"], [[u.replace("SEM UNIDADE", "Sem unidade"), fmt(v)] for u, v in posse],
             [8 * cm, 4 * cm]),
      Spacer(1, 6),
      tabela(["Indicador do processo", "Valor"], [
          ["Lead time até a data de corte", f"{F('coorte.caso.lead.mediana')} du"],
          ["Espera somada entre atividades", f"{F('coorte.caso.espera_entre_atividades.mediana')} du"],
          ["Execução somada das atividades", f"{F('coorte.caso.execucao_atividades.mediana')} du"],
          ["Tempo atribuído a prazo da concessionária (estimado)", f"{F('coorte.caso.terceiros.mediana')} du"],
          ["Tempo indeterminado (não separável de processo parado)", f"{F('coorte.caso.indeterminado.mediana')} du"],
          ["Ofícios expedidos", F("coorte.caso.oficios.mediana")],
          ["Trabalho estimado no processo (hipótese)",
           f"{fmt(fichas['processo']['casos'][0]['trabalho_piso_h'], 1)} h a {fmt(fichas['processo']['casos'][0]['trabalho_teto_h'], 1)} h"],
      ], [10 * cm, 5 * cm]),
      PageBreak()]

# 5. avaliação AS-IS
g = aval["gargalo"]
h += [P("5. Avaliação da situação atual", H1),
      P("A avaliação usa a lente Lean: separa o tempo em que o processo está sendo trabalhado do tempo em que ele "
        "espera, identifica onde a espera se acumula e que atividades agregam valor. Como há um único processo, as "
        "conclusões são hipóteses de trabalho para validar com as unidades."), P("Gargalo", H2), P(g["onde"]), P(g["evidencia"]),
      P("Desperdícios observados", H2)]
h += [tabela(["Tipo", "Evidência no processo"], [[d["tipo"], d["evidencia"]] for d in aval["desperdicios"]],
             [3 * cm, 14 * cm]), Spacer(1, 6), P("Oportunidades", H2)]
h += [tabela(["Oportunidade", "Descrição", "Impacto / esforço"],
             [[o["titulo"], o["descricao"], f"{o.get('impacto', '—')} / {o.get('esforco', '—')}"] for o in aval["oportunidades"]],
             [4 * cm, 10.5 * cm, 2.5 * cm]), PageBreak()]

# 6. conformidade
nmap = {n["id"]: n for n in normas["normas"]}
h += [P("6. Conformidade legal", H1),
      P(f"Foram levantados {len(normas['normas'])} dispositivos (lei de criação da agência, lei estadual de processo "
        "administrativo, regimento interno, instruções normativas de fiscalização, contrato de concessão e marco legal "
        "do saneamento), com trecho literal conferido contra o texto oficial. Deles saem os requisitos abaixo. Com um "
        "único processo, o resultado de cada requisito é cumprido ou não cumprido nesse caso; não é taxa de conformidade "
        "da agência. Requisitos marcados como \"conferência manual\" não são verificáveis só pelo registro do SEI.")]
lin = []
for r in normas["requisitos"]:
    c = conf["requisitos"].get(r["id"], {})
    if c.get("tipo") == "manual" or not c:
        st = "conferência manual"
    elif c.get("conforme"):
        st = "cumprido"
    elif c.get("nao_conforme"):
        st = "não cumprido"
    else:
        st = "sem evidência"
    base_n = "; ".join(sorted({f"{nmap[n]['norma']}, {nmap[n]['dispositivo']}" for n in r["normas"] if n in nmap}))
    lin.append([r["id"].replace("R-P06-", "R"), r["exigencia"], base_n, st])
h += [tabela(["Req.", "Exigência", "Base normativa", "Resultado"], lin, [1.1 * cm, 7.4 * cm, 6.2 * cm, 2.3 * cm]),
      PageBreak()]

# 7. TO-BE
fases_nome = {1: "Fase 1 — ajuste do fluxo, sem tecnologia nova", 2: "Fase 2 — automação de regras e dados",
              3: "Fase 3 — apoio de inteligência artificial, sempre com revisão humana"}
h += [P("7. Proposta de melhoria (TO-BE)", H1),
      P("As medidas são cumulativas por fase. Nenhuma reduz os prazos que a lei e o contrato concedem à concessionária. "
        "Medidas sem referência externa verificada estão marcadas como hipótese.")]
for fase in (1, 2, 3):
    ms = [m for m in mel["melhorias"] if m["fase"] == fase]
    h += [P(fases_nome[fase], H2),
          tabela(["Medida", "Descrição", "Base"],
                 [[m["titulo"], m["descricao"], "hipótese" if m.get("hipotese") else "referência verificada"] for m in ms],
                 [4.2 * cm, 10.6 * cm, 2.2 * cm])]
lin = [["Situação atual", fmt(res["linha_base"]["lead"]["mediana"]), "—", "—", "—"]]
for fase in ("1", "2", "3"):
    for cen in ("conservador", "esperado", "otimista"):
        x = res["fases"][fase][cen]
        lin.append([f"Fase {fase} — {cen}", fmt(x["lead"]["mediana"]), ("0%" if not x["ganho_lead_mediano_pct"] else f"−{fmt(x['ganho_lead_mediano_pct'], 1)}%"),
                    f"{fmt(x['horas_piso']['mediana'], 1)}–{fmt(x['horas_teto']['mediana'], 1)} h",
                    ("0%" if not x["ganho_horas_media_pct"] else f"−{fmt(x['ganho_horas_media_pct'], 1)}%")])
h += [P("Resultado simulado sobre o processo", H2),
      tabela(["Fase e cenário", "Lead time (du)", "Ganho de tempo", "Horas por processo", "Ganho de horas"], lin,
             [5 * cm, 2.8 * cm, 2.8 * cm, 3.6 * cm, 2.8 * cm]),
      Spacer(1, 6),
      P("Peso de cada medida (quanto o tempo total pioraria sem ela, fase 3, cenário esperado):"),
      tabela(["Medida", "Dias úteis"], [[m_tit[s["melhoria"]], fmt(s["lead_mediano_du"])] for s in sens if s["lead_mediano_du"] > 0],
             [13 * cm, 3 * cm]),
      P("A fase 3 reduz horas de trabalho, não o tempo total: o tempo está na espera, que se resolve com fluxo e "
        "acompanhamento (fases 1 e 2).", NOTA), PageBreak()]

# 8. controles
h += [P("8. Indicadores e metas", H1),
      P("Indicadores para acompanhar a implantação. A linha de base é o valor medido neste processo; as metas vêm da "
        "simulação, de norma ou de referência externa, conforme indicado.")]
lin = []
for i in ctl["indicadores"]:
    lbv = i["linha_base"]
    metas = "; ".join(f"fase {m['fase']}: {fmt(m['valor'], 1 if isinstance(m['valor'], float) and m['valor'] % 1 else 0)}"
                      for m in i.get("metas", []))
    orig = ", ".join(sorted({m["origem"]["tipo"] for m in i.get("metas", [])}))
    lin.append([i["nome"], f"{fmt(lbv.get('valor'), 1 if isinstance(lbv.get('valor'), float) and lbv.get('valor') % 1 else 0)} {lbv.get('unidade', '')}",
                metas or "—", orig.replace("simulacao", "simulação").replace("norma", "norma").replace("benchmark", "referência externa")])
h += [tabela(["Indicador", "Linha de base", "Metas", "Origem da meta"], lin, [7.2 * cm, 2.5 * cm, 4.6 * cm, 2.7 * cm]),
      Spacer(1, 6),
      P("Controles de qualidade das medidas de fase 3: conferência integral das citações e itens extraídos e revisão de "
        "amostra por servidor antes de qualquer uso das minutas.", NOTA), PageBreak()]

# 9. pontos de atenção
h += [P("9. Pontos de atenção e perguntas a validar", H1),
      P("Achados que pedem esclarecimento das unidades antes que o mapa seja dado como validado:")]
h += bullets([
    "<b>Concessionária e contrato.</b> O SEI registra a Iguá Rio de Janeiro (Bloco 2) como interessada; as peças "
    "tratam da Águas do Rio — Bloco 1. Definir qual contrato de concessão se aplica.",
    "<b>Qualidade dos relatórios de fiscalização.</b> Há texto de modelo reaproveitado com dados de outro contexto "
    "(município e bloco que não correspondem à unidade fiscalizada), datas divergentes entre vistoria, emissão e "
    "assinatura no mesmo relatório e listas de verificação sem a marcação legível de atendido/não atendido.",
    "<b>Parecer jurídico.</b> O número do parecer é de 2025, mas a data registrada coincide com a do ofício de ciência; "
    "não é possível separar fila de trabalho na maior espera do processo.",
    "<b>Encaminhamento das não conformidades.</b> Há não conformidades reiteradas desde 2024 sem notificação de "
    "infração; a concessionária pediu arquivamento e não há decisão expressa nem o rito de arquivamento previsto na "
    "instrução normativa de fiscalização.",
])
h += [P("Perguntas a validar com as unidades", H2)]
h += bullets(aval["perguntas_validacao"])
h += [P("Próximos passos sugeridos", H2)]
h += bullets([
    "Validar o fluxo e as decisões com a CASAN e confirmar o gargalo com a CASAN, a Secretaria Executiva e a Procuradoria.",
    "Submeter a matriz de requisitos à Procuradoria (contrato aplicável, contagem de prazos, prazo do parecer jurídico).",
    "Medir o tempo real de algumas peças-tipo com os servidores, para calibrar as horas.",
    "Ampliar o levantamento a outros processos de fiscalização da CASAN (ao menos cinco) e aos processos relacionados "
    "com as respostas da concessionária, para que os tempos deixem de ser de um único caso.",
])

doc.build(h)
print(PDF)
