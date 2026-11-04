"""Inventário de processos candidatos da AGENERSA e pré-pontuação (fonte única
para o Excel e para o dossiê). Notas de 1 a 5 por critério; pesos em CRITERIOS.

Fontes citadas por documento e página (fichas em 02_fichas/).

FORMATO PARA OUTRO ÓRGÃO (o pipeline importa este módulo e o oficina_dados.py da pasta CATALOGO do perfil;
substitua os dados, mantenha os nomes):
- MACROS: dict código do macroprocesso → (tipo, nome). Ex.: {"F1": ("Finalístico", "Regulação tarifária")}.
- P: lista de dicts, um por processo organizacional, montada por proc(...). Campos lidos pelo pipeline:
    id        código estável do processo ("P01"…): chave da classificação, dos modelos BPMN e do perfil
              (REGRAS_SUGESTAO, CODIGOS_FASE3, FAMILIA_BENCHMARK…). Tipo achado fora do catálogo vai para
              TIPOS_FORA_CATALOGO do perfil (ex.: "N01").
    macro     código de MACROS
    nome      nome do processo
    escopo    fluxo resumido (gatilho → etapas → saída): é o que a classificação dos processos SEI lê
    unidades  siglas das unidades envolvidas
    volume, dores, base   texto livre com fonte (vão para a ficha do processo)
    oe, fontes            texto livre (documentação do diagnóstico)
    E, V, U, D, R, G      notas de 1 a 5 nos critérios de CRITERIOS (tupla `notas`, último argumento de proc)
- CRITERIOS: (código, nome, peso %, o que mede, régua 1 → 5); os pesos somam 100.
- RANKING: P ordenada pela nota ponderada, com "score" e "rank" (calculados no fim deste arquivo; não editar).
oficina_dados.py precisa de ONDAS: lista de (nome da onda, descrição, [ids]); os processos da 1ª onda têm prioridade
na escolha do piloto. Os demais nomes de oficina_dados.py (agenda, grupos) servem só à oficina de validação, mas
GRUPOS tem de cobrir todos os ids de P (há um assert ao importar)."""

CRITERIOS = [
    # código, nome, peso (%), o que mede, régua 1 → 5
    ("E", "Alinhamento ao mandato e à estratégia", 20,
     "Quanto o processo realiza competência legal nuclear e objetivo do Planejamento Estratégico 2022–2026",
     "1 = apoio indireto · 3 = ligado a um OE · 5 = competência legal nuclear e objetivo estratégico explícito"),
    ("V", "Volume e frequência", 15,
     "Demanda anual: deliberações, processos tramitados, manifestações, fiscalizações",
     "1 = eventual · 3 = dezenas por ano · 5 = centenas/milhares por ano ou >20% das deliberações"),
    ("U", "Impacto no usuário e na sociedade", 20,
     "Efeito direto sobre tarifa, qualidade e continuidade do serviço, segurança e direitos do usuário",
     "1 = interno · 3 = efeito indireto · 5 = efeito direto sobre tarifa, abastecimento ou segurança"),
    ("D", "Problemas evidenciados", 20,
     "Gargalos, atrasos e falhas documentados pela própria agência ou por terceiros",
     "1 = sem evidência · 3 = fragilidade declarada · 5 = falha documentada por controle externo e pela agência"),
    ("R", "Risco legal, de controle e institucional", 15,
     "Obrigação legal com prazo, determinação do TCE-RJ, TAC, judicialização, exposição pública",
     "1 = baixo · 3 = recomendação pendente · 5 = determinação/TAC descumprido ou risco jurídico alto"),
    ("G", "Governabilidade da melhoria", 10,
     "Capacidade de a própria agência redesenhar o processo sem depender de lei, RRF ou terceiros",
     "1 = depende de lei/RRF/governo · 3 = depende parcialmente de terceiros · 5 = depende só da agência"),
]

# Macroprocessos da cadeia de valor proposta
MACROS = {
    "F1": ("Finalístico", "Regulação econômico-tarifária"),
    "F2": ("Finalístico", "Fiscalização, monitoramento e sanção"),
    "F3": ("Finalístico", "Regulamentação"),
    "F4": ("Finalístico", "Decisão regulatória colegiada"),
    "F5": ("Finalístico", "Gestão das concessões e outorgas"),
    "F6": ("Finalístico", "Relacionamento com usuários e sociedade"),
    "G1": ("Gerencial", "Governança, estratégia e controle"),
    "G2": ("Gerencial", "Informação e conhecimento regulatório"),
    "S1": ("Suporte", "Pessoas"),
    "S2": ("Suporte", "Contratações e logística"),
    "S3": ("Suporte", "Orçamento, finanças e arrecadação"),
    "S4": ("Suporte", "Tecnologia e comunicação"),
}

P = []


def proc(id_, macro, nome, escopo, unidades, oe, base, volume, dores, fontes, notas):
    e, v, u, d, r, g = notas
    P.append(dict(id=id_, macro=macro, nome=nome, escopo=escopo, unidades=unidades, oe=oe,
                  base=base, volume=volume, dores=dores, fontes=fontes,
                  E=e, V=v, U=u, D=d, R=r, G=g))


# ---------- F1 Regulação econômico-tarifária ----------
proc("P01", "F1", "Reajuste tarifário anual (saneamento e gás)",
     "Pedido da concessionária ou data contratual → cálculo paramétrico (IPCA-E/IRC e IDG) pela CAPET → parecer jurídico → relatoria e deliberação (ou decisão cautelar) → publicação e monitoramento da aplicação",
     "CAPET; Procuradoria; Conselheiro-Relator; CODIR; SECEX",
     "OE1, OE2",
     "Lei 4.556/2005, art. 4º, III e XII; Decreto 38.618/2005, art. 15, III e art. 41, p. único; contratos (fórmula paramétrica)",
     "Tarifas/reajuste/revisão = 211 deliberações em 2022–2026 (28,5%, 1º tipo de demanda); 16 documentos de reajuste (deliberações, decisões cautelares e tabelas) em 2025–2026",
     "Reajustes dos maiores contratos (Águas do Rio BL1, CEDAE, Iguá, Rio+) saíram por decisão cautelar; IDG neutralizado no reajuste de dez/2025; processos paralelos CEG e CEG Rio com prazo curto até a vigência",
     "Estatísticas das deliberações, seção 4.2; Tarifas em vigor 2025–2026; Verificador P13-R3 Bloco 1, p. 15–16; SEI-480002/011112/2026 e 011114/2026",
     (5, 5, 5, 5, 5, 4))
proc("P02", "F1", "Revisão tarifária ordinária (quinquenal) de gás e saneamento",
     "Agenda da revisão → plano de negócios e base de ativos → taxa de remuneração → notas técnicas CAPET → consulta/audiência pública → deliberação → novas tarifas",
     "CAPET; CODIR; Procuradoria; consultoria externa (FGV)",
     "OE1, OE2",
     "Lei 4.556/2005, art. 4º, III; Lei 11.445/2007, art. 38; Lei 8.987/1995, art. 9º; contratos (cláusulas de revisão); IN 105/2023",
     "5ª RTQ de CEG e CEG Rio em curso (TRC fixada em 22/12/2025); revisões dos Blocos 1 a 4, CAJ, Condessa e Prolagos",
     "Plano de negócios reapresentado por erro material; agenda dos Blocos 1 e 4 readequada em 2026; dependência entre a 4ª e a 5ª revisão da CAJ; metodologias NR 6 e NR 10 ainda a iniciar",
     "RTQ5 CEG e CEG Rio (Deliberações 4.987 e 4.988/2025); Agenda regulatória Blocos 1–4; CAJ 5ª RTQ preliminar; Relatório de Atividades 2025, p. 19–22",
     (5, 3, 5, 4, 5, 3))
proc("P03", "F1", "Reequilíbrio econômico-financeiro e aditivos contratuais",
     "Pleito de reequilíbrio → análise de risco e fluxo de caixa marginal (CAPET) → parecer jurídico → negociação/termo → deliberação → aditivo",
     "CAPET; Procuradoria; CODIR; poder concedente",
     "OE1",
     "Lei 4.556/2005, art. 4º, III; Decreto 38.618/2005, art. 10, VII; contratos de concessão",
     "Pleitos recorrentes nos Conselhos de Titulares e nos contratos de gás e saneamento (não quantificado)",
     "Pedidos de R$ 2,7 bi das concessionárias de saneamento por divergência de cobertura de esgoto no edital; R$ 900 mi reconhecidos à Águas do Rio, acordo suspenso pelo TCE-RJ e objeto de inquérito civil do MPRJ (out/2025); planilha de reequilíbrio ainda em aprimoramento; matriz de risco 'a iniciar' na agenda 2025",
     "Relatório de Atividades 2025, p. 19–22; Atas dos Conselhos de Titulares 2025–2026; O Globo, republicado em Tribuna do Sertão (17/10/2025)",
     (4, 2, 5, 5, 5, 3))
proc("P04", "F1", "Homologação de planos de investimento e obras",
     "Apresentação do plano/projeto → análise técnica e econômica → deliberação de homologação → acompanhamento da execução",
     "CAPET; Câmara de Saneamento (CASAN); CODIR",
     "OE1, OE3",
     "Contratos de concessão; Decreto 38.618/2005, art. 28",
     "Planos/investimentos = 53 deliberações em 2022–2026 (7,2%); 8 homologações da Prolagos em fev–jun/2026",
     "Processos de homologação abertos desde 2013–2018; recadenciamento de obras fora de efeito vinculante",
     "Estatísticas das deliberações, seção 4.2; Homologações Prolagos 2026; Deliberação 4.976/2025",
     (3, 3, 4, 4, 3, 4))
proc("P05", "F1", "Acompanhamento econômico-financeiro das reguladas",
     "Recebimento de demonstrações anuais, movimentações de outorga variável e certidões → análise CAPET → nota técnica → decisão em reunião interna",
     "CAPET; CODIR",
     "OE3",
     "IN 142/2026; IN 138/2025; IN 121/2024",
     "Envios anuais e mensais de todas as concessionárias; regularidade fiscal recorrente por concessionária e ano",
     "Mesmo fundamento tratado em processos separados por concessionária; verificação documental vira processo regulatório",
     "Matriz de competências (linhas 25–27); SEI E-12/003.155 e 003.156/2018",
     (3, 3, 2, 3, 3, 5))

# ---------- F2 Fiscalização, monitoramento e sanção ----------
proc("P06", "F2", "Fiscalização técnica de campo (programada e por demanda)",
     "Plano anual de fiscalização → agenda → vistoria in loco → Relatório de Fiscalização (RF) → notificação de não conformidade → acompanhamento da correção",
     "CASAN (saneamento); CAENE (energia/gás); CARES (resíduos)",
     "OE3",
     "Lei 4.556/2005, art. 4º, IV; Decreto 38.618/2005, arts. 26–28 e 33-A; IN 128/2024",
     "662 fiscalizações em 2025 (587 em 2024; 222 em 2023); CASAN tramitou 6.569 processos em 2025",
     "Volume triplicou sem padronização declarada (manuais e checklists ainda em criação); planejamento por risco não evidenciado; fiscalizações motivadas por reclamações em áreas críticas (Gramacho, Nova Iguaçu)",
     "Relatórios de Atividades 2023 (p. 10), 2024 (p. 15), 2025 (p. 23–24); Planejamento Estratégico, OE3; Relatórios técnicos e agendas de fiscalização",
     (5, 5, 5, 5, 4, 4))
proc("P07", "F2", "Processo sancionador (auto de infração à cobrança da multa)",
     "Notificação de infração → auto de infração → defesa/impugnação (5 dias) → parecer jurídico → julgamento (Câmara ou CODIR) → recurso → cobrança/inscrição em dívida ativa",
     "Câmaras Técnicas; SECEX; Procuradoria; CAPET (cálculo); CODIR",
     "OE3",
     "Lei 4.556/2005, art. 4º, IV; Regimento Interno, art. 21, XX–XXI; IN 96/2023; IN 128/2024, arts. 10–18",
     "109 autos em 2022–2023 (R$ 1,99 mi); 55 autos em 2025 (35 advertências)",
     "63 de 109 autos (58%) ainda 'iniciados'; multa depende de cálculo prévio da CAPET sem prazo fixado; crítica pública de processos contra a CEDAE sem punição; não há documento com o passo a passo do auto à cobrança",
     "Tabela consolidada de autos de infração; IN 128/2024, arts. 10–18; Relatório de Atividades 2025, p. 11; Monitor Mercantil (parecer do IAB)",
     (5, 3, 4, 5, 5, 4))
proc("P08", "F2", "Monitoramento de metas contratuais e do IDG (verificador independente)",
     "Reporte mensal/anual da concessionária → aferição trimestral pelo verificador (FIPE) → validação pela AGENERSA → publicação de metas e IDG → efeito no reajuste",
     "Câmara de Saneamento; CAPET; verificador independente",
     "OE1, OE3",
     "Lei 14.026/2020, art. 11-B; Lei estadual 9.370/2021; IN 137/2025; Deliberação 4.939/2025; contratos (Anexos III e V)",
     "4 blocos × aferição trimestral; 103 relatórios mensais e 11 anuais do verificador",
     "Ciclo não fecha: cronogramas e indicadores (IPD, IDA, IRD, ISA, IAI, CTS) aguardam validação/metodologia da própria agência; relatório de out/2026 cobre 2025; metodologia reeditada; contrato do verificador termina ~2027",
     "Metas Rio+ 2025 (p. 2–3); Metas Iguá Bloco 2 (p. 2); Verificador P11-R11 (p. 3); Contrato 016/2022",
     (5, 4, 5, 5, 5, 3))
proc("P09", "F2", "Inspeção periódica de segurança em instalações de gás",
     "Cronograma de inspeções quinquenais → credenciamento de inspetores → registro e acompanhamento → aplicação de multa por descumprimento",
     "CAENE; Ouvidoria",
     "OE3",
     "Lei estadual 6.890/2014; IN 113/2024 (alterada pelas INs 136/2025 e 149/2026); TAC MPRJ/DPE/AGENERSA",
     "Universo de edificações com gás canalizado no estado (não quantificado)",
     "Só 10 empresas credenciadas em 2023; prazo do TAC prorrogado até 22/03/2026 e cumprimento não verificado; norma alterada duas vezes em dois anos",
     "TAC MPRJ/Defensoria/AGENERSA 06/03/2023 (p. 2–3); IN 113/2024",
     (3, 3, 4, 5, 5, 3))
proc("P10", "F2", "Cooperação técnica com municípios para fiscalização complementar",
     "Adesão do município → termo de cooperação → capacitação → registro de ocorrências pelo município → tratamento pela Câmara",
     "SECEX; CASAN",
     "OE3",
     "Lei 4.556/2005, art. 4º, IV e §1º; IN 133/2025 e IN 146/2026",
     "Novo em 2026 (minutas enviadas aos municípios)",
     "Sistema de registro e capacitação ainda em desenvolvimento; baixa presença municipal nos conselhos",
     "Ata Conselho de Titulares Bloco 2 (16/07/2026, p. 2); IN 133/2025",
     (3, 2, 3, 2, 2, 4))
proc("P11", "F2", "Certificação de informações regulatórias (SNIS/SINISA)",
     "Recebimento dos dados da prestadora → auditoria de consistência → relatório de certificação → publicação",
     "CASAN",
     "OE3",
     "Lei 11.445/2007; normas do SNIS",
     "Anual, por prestadora",
     "Conclusões dos relatórios não consolidadas",
     "Relatórios de certificação SNIS (Prolagos, Juturnaíba, Condessa)",
     (2, 2, 2, 2, 3, 4))
proc("P35", "F2", "Gestão de interrupções e crises de abastecimento",
     "Aviso prévio de paradas programadas → monitoramento da operação (CSFA/CCO) → acionamento em crise (plano de contingência, caminhão-pipa, prioridade a hospitais) → vistoria → comunicação pública → apuração de responsabilidade e sanção",
     "CASAN; CSFA; Ouvidoria; Comunicação; Presidência",
     "OE1, OE3",
     "Lei 11.445/2007, art. 40; contratos dos Blocos 1–4 (Anexo X); Deliberação CSFA 03/2024 (CCO)",
     "Falta d'água = 3.777 reclamações na Ouvidoria em 2025 (35%, 1º tema); 17 de 29 episódios na imprensa 2023–2026; crises de dez/2024 (27 bairros), set/2026 (19) e out/2026 (24)",
     "Agência ausente da resposta pública nas grandes crises (multa de R$ 13,6 mi aplicada pelo Procon Carioca em dez/2024); sanções de episódios de 2023 só em 2025; alerta sobre medição de vazão no Km 32 sem efeito antes de ação da Defensoria; informações da CEDAE sobre paradas do Guandu pendentes no CSFA",
     "Série da Ouvidoria 2023–2026; Brasil de Fato (02/12/2024, 28/11/2023); Super Rádio Tupi (03/12/2024); Diário do Rio (01/09/2026); Folha do Leste (23/10/2026); Ata 50ª do CSFA",
     (5, 5, 5, 5, 4, 3))

# ---------- F3 Regulamentação ----------
proc("P12", "F3", "Elaboração de normas (agenda regulatória, AIR, consulta e edição)",
     "Agenda regulatória → AIR → minuta → consulta/audiência pública → análise das contribuições → aprovação pelo CODIR → publicação → avaliação de resultado (ARR)",
     "Comissão da Agenda Regulatória; Câmaras Técnicas; Procuradoria; CODIR",
     "OE2",
     "Lei 4.556/2005, art. 4º; IN 135/2025 (agenda); IN 150/2026 (participação social); Lei 13.848/2019 como referência; NR ANA",
     "cerca de 150 instruções normativas publicadas; 8 INs em 2025; ~50 temas na agenda regulatória",
     "AIR não integrada ao processo normativo (recomendação do TCE-RJ, meta de 30% até 2026); norma de AIR ainda em elaboração; várias INs alteradas em menos de dois anos; Regimento de 2013 desatualizado",
     "PCA 2023 (p. 4); Relatório TCE-RJ 100.805-1/22, achado 04; Relatório de Atividades 2025, p. 13 e 18–22; Matriz de competências, observação 1",
     (5, 3, 4, 5, 5, 4))
proc("P13", "F3", "Consulta e audiência pública",
     "Proposta da unidade → autuação → aviso → período de contribuições → audiência → relatório de análise das contribuições → decisão",
     "SECEX; Relator; unidade proponente; Ouvidoria",
     "OE2",
     "Regimento Interno, arts. 89–93; IN 150/2026",
     "12 consultas listadas no site; 0 menções nas ementas das deliberações",
     "Prazos e relatórios de contribuições não regulamentados até 2026 (TCE achado 09); prazo de cerca de 10 dias na consulta da CUSD; resultado de consultas 'não informado' no site",
     "Relatório TCE-RJ 100.805-1/22, achado 09; Consultas e audiências públicas (página); CUSD mercado livre",
     (4, 2, 3, 4, 4, 5))
proc("P14", "F3", "Interpretação contratual e solução de conflitos (conciliação)",
     "Pedido de interpretação ou conflito → instrução → Comissão de Conciliação ou relatoria → acordo homologado ou deliberação definitiva",
     "Relator; Comissão de Conciliação; Procuradoria; CODIR",
     "OE2",
     "Lei 4.556/2005, art. 4º, II e XV; Regimento, arts. 50–51; IN 105/2023; IN 131/2024",
     "Não quantificado; 2 deliberações de conciliação em 29/11/2023 (Blocos 1 e 3)",
     "Prazo de decisão definitiva fixado por IN para os Blocos 1–4 por pressão contratual",
     "IN 105/2023 e 131/2024; Aditivos dos Blocos 1 e 3",
     (3, 2, 3, 3, 3, 4))

# ---------- F4 Decisão regulatória colegiada ----------
proc("P15", "F4", "Instrução e julgamento do processo regulatório",
     "Pleito/abertura → classificação e autuação (SECEX) → parecer técnico da Câmara → parecer jurídico → sorteio de relator → relatório e voto → pauta → sessão (presencial ou virtual) → deliberação → publicação no DOERJ",
     "SECEX; Câmaras Técnicas; Procuradoria; Conselheiros-Relatores; CODIR",
     "OE2",
     "Lei 4.556/2005, art. 12; Decreto 38.618/2005, arts. 34–40; Regimento Interno, arts. 46–80; IN 130/2024 e IN 145/2026",
     "3.164 processos de todos os tipos tramitados pelos gabinetes dos conselheiros em 2025; 147 deliberações e 12 sessões em 2025; ~27 processos por pauta",
     "Sem prazo global; processos autuados em 2014, 2016, 2020 e 2021 pautados em 2026 (5 a 12 anos); vistas e retiradas de pauta frequentes; deliberações caíram de 375/ano (2011–19) para 158/ano (2020–25)",
     "Síntese do bloco decisório; Rito decisório; Estatísticas das deliberações, seção 1; Relatório de Atividades 2025, p. 10–11",
     (5, 5, 4, 5, 4, 4))
proc("P16", "F4", "Recursos e embargos contra deliberações",
     "Interposição (embargos 5 dias; recurso 10 dias) → contrarrazões → novo relator → julgamento",
     "SECEX; Procuradoria; Conselheiro-Relator; CODIR",
     "OE2",
     "Decreto 38.618/2005, arts. 61–63; Regimento Interno, arts. 78–80",
     "83 deliberações de recurso/embargo em 2022–2026 (11,2%; 3º tipo); de 8 (2022) para 26 (2025)",
     "Recursos triplicaram em quatro anos; sem efeito suspensivo como regra; judicialização posterior (gás, mercado livre)",
     "Estatísticas das deliberações, seção 4.2; Rito decisório",
     (4, 3, 3, 4, 4, 4))
proc("P17", "F4", "Cumprimento de deliberações e encerramento de processos",
     "Publicação da deliberação → notificação → acompanhamento das determinações → certificação do cumprimento → arquivamento ou novo processo",
     "SECEX; Câmaras Técnicas",
     "OE2, OE3",
     "Res. CODIR 787/2022",
     "Todo processo julgado (147 deliberações em 2025)",
     "Descumprimento gera novo processo regulatório (caso de deliberação de 2017 ainda em julgamento em 2026); sem controle de prazos",
     "SEI E-12/003.333/2016; Res. CODIR 787/2022",
     (4, 3, 3, 4, 3, 5))

# ---------- F5 Gestão das concessões e outorgas ----------
proc("P18", "F5", "Prorrogação, relicitação e alteração de concessões",
     "Manifestação do poder concedente → estudos e modelagem → parecer da agência sobre edital/prorrogação → aditivos e transferências de controle",
     "CODIR; CAPET; CAENE; Procuradoria",
     "OE1",
     "Decreto 38.618/2005, art. 10, VI e VII; IN 123/2024 (prorrogação do gás)",
     "Contratos de CEG e CEG Rio vencem em jul/2027, segundo a imprensa especializada",
     "Renovação questionada pelo TCE-RJ e adiada em 2026; IBP cobra transparência no processo",
     "W2 (Isto É Dinheiro 29/01/2026; eixos); IN 123/2024",
     (4, 1, 5, 4, 5, 2))
proc("P19", "F5", "Regulação do mercado livre de gás (CUSD e migração)",
     "Minuta de CUSD → consulta pública → pareceres CAENE/CAPET → regras de migração e consumo mínimo → análise de pedidos de migração → acordo/aditivo",
     "CAENE; CAPET; Procuradoria; CODIR",
     "OE1, OE2",
     "Lei 14.134/2021, art. 29; Deliberações 3.862/2019 a 4.936/2025; 4º TA CEG/CEG Rio",
     "2 consultas (17 e 34 documentos); pedidos de migração de grandes consumidores; termo de acordo de 15/08/2026",
     "Controvérsia judicial com migrações suspensas, segundo a imprensa especializada; patamar mudou de 100 mil para 10 mil m³/dia por acordo",
     "CUSD mercado livre; Termo de Acordo 2026; Ata 7ª sessão 2025 (p. 2–3); eixos.com.br",
     (4, 2, 4, 4, 4, 3))

# ---------- F6 Relacionamento com usuários e sociedade ----------
proc("P20", "F6", "Atendimento e tratamento de manifestações dos usuários (Ouvidoria)",
     "Registro da manifestação → triagem e classificação → encaminhamento à concessionária → resposta e verificação → reiteração → encerramento ou ocorrência à Câmara",
     "Ouvidoria; Câmaras Técnicas",
     "OE1",
     "Lei 4.556/2005, art. 4º, XI; Decreto 38.618/2005, art. 25; IN 103/2023 (prazos de 5/10/15 dias úteis); Lei 13.460/2017",
     "33.726 manifestações e 10.911 reclamações em 2025 (46.657 manifestações em 2024); reclamações do 2T2026 86% acima do 2T2025",
     "42% das reclamações do 2º trimestre de 2026 em andamento ao fim do período; prazo médio de resolução não publicado; 60,7% das reclamações concentradas em Águas do Rio BL1 e BL4; autonomia da Ouvidoria questionada (TCE achado 08)",
     "Relatórios trimestrais da Ouvidoria (2T2026, p. 6–8 e 18–19); Relatório de Atividades 2025, p. 36; TCE achado 08",
     (5, 5, 5, 5, 4, 5))
proc("P21", "F6", "Apuração de ocorrência de usuário pelo Conselho-Diretor",
     "Reclamação não resolvida na Ouvidoria → abertura de ocorrência → instrução técnica → relatoria → deliberação (determinação ou penalidade)",
     "Ouvidoria; SECEX; Câmaras Técnicas; Relator; CODIR",
     "OE1, OE3",
     "Regimento Interno, arts. 46–47; Lei 4.556/2005, art. 4º, II",
     "Ouvidoria/ocorrência = 161 deliberações em 2022–2026 (21,8%, 2º tipo de demanda)",
     "Ocorrência autuada em 2021 e pautada para julgamento só em outubro de 2026; reiterações antes da decisão",
     "Estatísticas das deliberações, seção 4.2; SEI-220007/001346/2021",
     (4, 4, 5, 5, 3, 4))
proc("P22", "F6", "Transparência e resposta a órgãos de controle e ao Ministério Público",
     "Recebimento de ofício/recomendação → distribuição → resposta técnica e jurídica → acompanhamento de prazos e determinações → publicação",
     "Procuradoria; SECEX; gabinetes; Ouvidoria",
     "OE1, OE4",
     "Lei 12.527/2011 (LAI); IN 124/2024 (governança regulatória)",
     "Demanda de órgão externo = 43 deliberações em 2022–2026; determinações do TCE-RJ pendentes",
     "Recomendação do MPRJ (jul/2026) por falhas de acesso à informação; determinação do TCE de comunicar os Comitês de Monitoramento não cumprida",
     "W2 (MPRJ 08/07/2026); PCA 2023, p. 3; Estatísticas das deliberações",
     (4, 3, 3, 4, 5, 4))
proc("P23", "F6", "Secretariado dos colegiados contratuais (Comitês, Conselhos de Titulares, CSFA)",
     "Convocação → pauta → reunião → ata → encaminhamento de demandas → resposta da agência",
     "Câmara de Saneamento; SECEX",
     "OE1, OE2",
     "Contratos de concessão (Anexos IX, X e XII); Lei 11.445/2007, arts. 11 e 47",
     "Reuniões mensais do Comitê e do CSFA (116 e 79 documentos publicados); 2–4 reuniões/ano por Conselho de Titulares",
     "Baixa presença municipal; respostas parciais e temas parados em pauta; pendência da CEDAE sobre paradas do Guandu",
     "Síntese do bloco de saneamento; Ata 50ª do CSFA; PCA 2023 (det. c)",
     (3, 3, 3, 4, 4, 4))
proc("P36", "F6", "Regulação e fiscalização comercial (faturamento, medição, corte, religação e tarifa social)",
     "Regras de faturamento, medição e tarifa social → fiscalização amostral de contas e cadastros → tratamento de reclamações comerciais → determinação de devolução ou correção → sanção → acompanhamento de cumprimento",
     "CASAN; CAPET; Ouvidoria; Procuradoria",
     "OE1, OE2",
     "Lei 4.556/2005, art. 4º; IN 119 (troca de hidrômetro, alterada pela IN 120); Lei federal 14.898/2024 (tarifa social); Lei 13.460/2017; regulamento de serviços (Decreto 48.225/2022)",
     "Cobrança, medição e corte = cerca de 2.800 reclamações na Ouvidoria em 2025 (26%); cobrança indevida = 32,8% das queixas da Águas do Rio no Reclame Aqui (fev–jul/2026); Procon Carioca: 4.370 reclamações de água e esgoto em 2024; Grupo Aegea 6º maior litigante do TJRJ em 2025 (25.381 processos)",
     "Temas resolvidos fora da agência: ação civil pública do Procon-RJ contra cobrança de dívidas antigas (nov/2024) e decisão judicial (out/2025) sem participação da AGENERSA; TAC do hidrômetro (2024) seguido de queixas; contas multiplicadas pela regra 'tarifa mínima × economias'; norma de tarifa social ainda em preparação e favelas fora do incentivo contratual",
     "Série da Ouvidoria 2023–2026; Correio da Manhã (19/11/2024); O Globo via Tribuna do Sertão (10/10/2025); Brasil de Fato (26/03/2024, 07/10/2025); TJRJ, maiores litigantes 2025 (13/01/2026); Super Rádio Tupi (04/07/2025)",
     (4, 5, 5, 5, 5, 4))

# ---------- G1 Governança, estratégia e controle ----------
proc("P24", "G1", "Planejamento estratégico, plano anual e relatório de atividades",
     "Diagnóstico → objetivos e metas → planos anuais das unidades (05/10–30/11) → monitoramento → relatório anual (até 05/01)",
     "Presidência; SECEX; Assessoria de Relações Institucionais; todas as unidades",
     "OE1",
     "Lei 4.556/2005, art. 4º, X; Regimento Interno, arts. 15, 19, 21 e 43",
     "Ciclo anual; plano estratégico vence em 2026",
     "Indicadores do plano não aparecem nos relatórios anuais; séries com lacunas (sessões e deliberações 2022–2024 só em gráfico); missão divergente entre site e plano",
     "Planejamento Estratégico 2022–2026; Relatórios de Atividades 2021–2025",
     (3, 2, 2, 3, 3, 5))
proc("P25", "G1", "Gestão de riscos, integridade e controle interno",
     "Política de riscos → matriz por processo → plano de auditoria interna (PLANAT) → relatório (RANAT) → acompanhamento de recomendações",
     "Auditoria/UCI; Corregedoria; UGI; Presidência",
     "OE2",
     "IN 74/2019; IN 95/2023; IN 124/2024; Deliberação TCE-RJ 278/2017",
     "1 PLANAT e 1 RANAT por ano; 17 riscos mapeados no Plano de Integridade 2023",
     "Política de riscos só parcial (TCE rec. V-d); recomendações de 2017 e 2020–2022 sem classificação; estrutura (UGI, Inteligência) fora do Regimento",
     "PCA 2023 (p. 2–4); Plano de Integridade 2023 (p. 15–17)",
     (3, 2, 2, 4, 4, 4))

# ---------- G2 Informação e conhecimento ----------
proc("P26", "G2", "Gestão documental e do processo eletrônico (SEI)",
     "Protocolo → classificação (regulatório/administrativo) → autuação → tramitação → nível de acesso → arquivamento",
     "SECEX; ASSIN; protocolo",
     "OE4",
     "Regimento Interno, arts. 46–47-A; Lei 12.527/2011",
     "CASAN 6.569 e SECEX 6.314 processos tramitados em 2025",
     "Restrição indevida de acesso e falta de categorização (TCE achado 02); padronização do trâmite como meta de 2026",
     "Relatório de Atividades 2025, p. 24 e 33; TCE achado 02",
     (3, 5, 2, 4, 3, 5))
proc("P27", "G2", "Inteligência regulatória e gestão de dados e conhecimento",
     "Coleta de dados das reguladas → base integrada → painéis e indicadores → apoio a decisões, crises e fiscalização baseada em risco",
     "Unidade de Inteligência Regulatória; ASSIN; Câmaras",
     "OE4, OE5",
     "IN 112/2024; Planejamento Estratégico, OE4",
     "Fluxos de dados de 11 concessionárias (indicadores, demonstrações, reclamações)",
     "Sem sala de controle nem base integrada (TCE achado 07); assimetria de informação declarada; gestão do conhecimento sem competências formalizadas",
     "TCE achado 07; PCA 2023 (rec. V-k); Planejamento Estratégico (SWOT, p. 17)",
     (4, 2, 3, 4, 3, 3))

# ---------- Suporte ----------
proc("P28", "S1", "Gestão de pessoas (provimento, carreira e capacitação)",
     "Planejamento da força de trabalho → concurso e provimento → avaliação e progressão → capacitação (Escola de Regulação)",
     "ASRHU; SUPAD; Presidência",
     "OE6",
     "Lei 4.556/2005, arts. 13–14; Lei 6.848/2014; Regime de Recuperação Fiscal",
     "~80 a 122 servidores, poucos efetivos; concurso de 2022 com 50 vagas",
     "4 a 5 efetivos concursados em 2022; progressão não implementada; sem plano de capacitação; cargos em comissão sob exame do TCE; dependência do RRF",
     "TCE achados 05 e 06; Planejamento Estratégico (p. 17); RANAT 2024 (p. 4)",
     (4, 2, 2, 5, 4, 1))
proc("P29", "S2", "Contratações e licitações",
     "Demanda → estudo técnico preliminar → termo de referência → licitação/pregão → homologação → contrato",
     "SUPAD; Comissão de Contratação; Procuradoria",
     "OE5",
     "Lei 14.133/2021; Regimento Interno, arts. 39–41",
     "661 processos tramitados pela SUPAD em 2025; 12 licitações em 2023–2026",
     "Aquisições burocráticas (PEDTIC FR4); duplicidade de contratações (TCE Voto GCS-2); Regimento ainda cita a Lei 8.666/1993",
     "Relatório de Atividades 2025, p. 28–29; PEDTIC; RANAT 2024 (p. 4–5)",
     (3, 4, 2, 4, 4, 4))
proc("P30", "S2", "Gestão de contratos administrativos (inclusive verificador independente)",
     "Designação de fiscal → acompanhamento da execução → medição e pagamento → aditivos → renovação ou nova contratação",
     "SUPAD; fiscais de contrato; Câmaras",
     "OE5",
     "Lei 14.133/2021; Contrato 016/2022 (verificador)",
     "40 contratos vigentes, R$ 115 mi (maio/2026)",
     "Alta dependência de terceiros (mão de obra e TI); contrato do verificador de 60 meses sem prorrogação vence ~2027",
     "Contratos administrativos vigentes (planilha); Contrato 016/2022, cláusulas 1ª e 2ª",
     (3, 3, 2, 3, 4, 4))
proc("P31", "S3", "Arrecadação da Taxa de Regulação e gestão do Fundo",
     "Apuração da base de cálculo (0,5% da receita) → recolhimento até o 10º dia útil → conferência → multa e juros por atraso → repartição e aplicação",
     "CAPET; SUPOF",
     "OE1",
     "Lei 4.556/2005, art. 19; Lei 6.334/2012, art. 3º; Decreto 37.930/2005",
     "R$ 93,7 mi realizados em 2025",
     "Repartição com a AGETRANSP incompatível com a natureza do tributo (TCE achado 10); estudo do Fundo só parcial; destino da taxa divergente entre leis",
     "TCE achado 10; PCA 2023, p. 3; Histórico e marco legal, divergência 3",
     (3, 2, 1, 4, 5, 3))
proc("P32", "S3", "Orçamento, finanças, contabilidade e patrimônio",
     "Proposta orçamentária (PPA/LDO/LOA) → execução (empenho, liquidação, pagamento) → contabilidade → patrimônio e almoxarifado → prestação de contas",
     "SUPOF; Assessoria de Contabilidade; SUPAD",
     "OE5",
     "Regimento Interno, arts. 43 e 45; Deliberação TCE-RJ 278/2017",
     "1.037 processos tramitados pela SUPOF em 2025",
     "Restos a pagar e dívida ativa sem regularização; bens móveis e almoxarifado sem prestação de contas; a própria agência fixou meta de mapear 100% dos processos-chave da SUPOF em 2026",
     "PCA 2022 (p. 9–15); Planejamento de Atividades 2026; Relatório de Atividades 2025, p. 28 e 33",
     (3, 4, 1, 4, 4, 5))
proc("P33", "S4", "Gestão de tecnologia da informação",
     "Demanda de sistema → priorização no PDTIC → desenvolvimento ou aquisição → sustentação",
     "ASSIN",
     "OE5",
     "PEDTIC 2024–2027; Lei 14.129/2021",
     "9 sistemas planejados ou em andamento em 2025",
     "Estrutura e recursos de TI insuficientes; turnover elevado (FR5); mapeamento de processos incipiente (FR2)",
     "PEDTIC (FR2, FR4, FR5, FR7); Planejamento Estratégico (p. 17)",
     (3, 2, 2, 4, 3, 3))
proc("P34", "S4", "Comunicação institucional",
     "Plano de comunicação → produção de conteúdo e site → imprensa → campanhas (Agenersa na Rua)",
     "Assessoria de Comunicação",
     "OE1",
     "Plano de Comunicação",
     "Contínuo",
     "Site confuso e desatualizado (fraqueza declarada); crítica de transparência do MPRJ; agência ausente da imprensa nas grandes crises de abastecimento",
     "Planejamento Estratégico (p. 17); Plano de Comunicação; levantamento de imprensa 2023–2026",
     (2, 2, 4, 4, 2, 4))


def pontua(p):
    return round(sum(p[c] * peso for c, _, peso, _, _ in CRITERIOS) / 5, 1)


for p in P:
    p["score"] = pontua(p)
    p["macro_tipo"], p["macro_nome"] = MACROS[p["macro"]]

RANKING = sorted(P, key=lambda p: (-p["score"], p["id"]))
for i, p in enumerate(RANKING, 1):
    p["rank"] = i

if __name__ == "__main__":
    for p in RANKING:
        print(f"{p['rank']:>2} {p['score']:>5} {p['id']} {p['macro']} {p['nome']}")
