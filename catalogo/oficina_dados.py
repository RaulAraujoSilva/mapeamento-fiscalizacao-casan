"""Dados da oficina de validação: agenda, grupos de calibração e ondas (fonte única para
apresentação, roteiro e formulário)."""
from dados_processos import P, RANKING

PROC = {p["id"]: p for p in P}

DURACAO = "3h30"

# (início, duração em min, bloco, objetivo, dinâmica)
AGENDA = [
    ("09:00", 15, "Abertura", "Alinhar objetivo, regras e resultados esperados", "Fala da Presidência e da coordenação do projeto"),
    ("09:15", 25, "Achados do diagnóstico", "Nivelar a leitura sobre demanda, gargalos e pressões externas", "Apresentação com perguntas de esclarecimento"),
    ("09:40", 25, "Dinâmica 1 — Cadeia de valor", "Validar macroprocessos e completar o inventário", "Parede de cartões: incluir, fundir, renomear"),
    ("10:05", 30, "Dinâmica 2 — Pesos dos critérios", "Definir os pesos que a agência adota", "Distribuição individual de 100 pontos e debate das divergências"),
    ("10:35", 15, "Intervalo", "", ""),
    ("10:50", 45, "Dinâmica 3 — Calibração das notas", "Ajustar as notas de 1 a 5 com o conhecimento das áreas", "Quatro grupos por macroprocesso, com formulário"),
    ("11:35", 30, "Plenária — Ranking validado", "Recalcular a prioridade e confirmar o top 20", "Matriz recalculada ao vivo; consenso nas fronteiras"),
    ("12:05", 20, "Dinâmica 4 — Donos e Onda 1", "Nomear dono e ponto focal dos processos da Onda 1", "Quadro de responsáveis e agenda de entrevistas"),
    ("12:25", 5, "Encerramento", "Registrar decisões e próximos passos", "Leitura das decisões tomadas"),
]

# grupos de calibração: nome, unidades convidadas, processos
GRUPOS = [
    ("Grupo A — Regulação econômica e concessões", "CAPET, CAENE, Procuradoria, gabinete de conselheiro",
     ["P01", "P02", "P03", "P04", "P05", "P18", "P19", "P31"]),
    ("Grupo B — Fiscalização, metas e sanção", "CASAN, CAENE, CARES, SECEX",
     ["P06", "P07", "P08", "P09", "P10", "P11", "P35"]),
    ("Grupo C — Decisão, normas e usuário", "SECEX, Ouvidoria, Procuradoria, gabinetes, Relações Institucionais",
     ["P12", "P13", "P14", "P15", "P16", "P17", "P20", "P21", "P22", "P23", "P36"]),
    ("Grupo D — Gestão e suporte", "SUPAD, SUPOF, ASSIN, ASRHU, Auditoria/UCI, UGI, Comunicação",
     ["P24", "P25", "P26", "P27", "P28", "P29", "P30", "P32", "P33", "P34"]),
]
assert sorted(i for _, _, ids in GRUPOS for i in ids) == sorted(PROC), "grupos não cobrem todos os processos"

ONDAS = [
    ("Onda 1", "Núcleo de massa e de maior exposição", ["P20", "P36", "P21", "P06", "P35", "P07", "P01", "P15"]),
    ("Onda 2", "Ciclo regulatório e controle das concessões", ["P08", "P02", "P12", "P13", "P16", "P17"]),
    ("Onda 3", "Concessões, segurança e relacionamento institucional", ["P09", "P22", "P18", "P19", "P03", "P04", "P26", "P23"]),
]

PARTICIPANTES = [
    ("Conselheiro-Presidente e conselheiros", "Abertura, Dinâmica 2 e Plenária (decisão final sobre pesos e carteira)"),
    ("Secretaria Executiva (SECEX)", "Todas as dinâmicas; dona provável do rito processual"),
    ("Câmaras técnicas: CAPET, CAENE, CASAN, CARES", "Todas as dinâmicas; donas dos processos finalísticos"),
    ("Procuradoria", "Dinâmicas 1, 3 e 4"),
    ("Ouvidoria", "Todas as dinâmicas"),
    ("Superintendências SUPAD e SUPOF", "Dinâmicas 1, 3 e 4"),
    ("Assessorias de TI (ASSIN), RH (ASRHU), Comunicação e Relações Institucionais", "Dinâmicas 1 e 3"),
    ("Auditoria/Controle Interno, Corregedoria e UGI", "Dinâmicas 2 e 3 (visão de risco e controle)"),
]

PERGUNTAS_CADEIA = [
    "Algum processo relevante da sua área não aparece no inventário?",
    "Há processos que, na prática, são um só e deveriam ser fundidos?",
    "O nome e o escopo (início → fim) refletem o que a área faz?",
    "Algum processo está no macroprocesso errado?",
]

DECISOES = [
    "Pesos dos seis critérios adotados pela agência",
    f"Notas calibradas dos {len(PROC)} processos",
    "Top 20 validado e carteira da Onda 1",
    "Dono e ponto focal de cada processo da Onda 1",
    "Agenda de entrevistas e acesso a dados do SEI para medir tempos",
]
