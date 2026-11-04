"""Perfil-modelo: roteiro para adaptar o pipeline a outro órgão (outro Estado, outra agência).

Copie este arquivo para `perfis/<uf>_<orgao>.py` (ex.: `sp_arsesp.py`), troque cada valor pelo do seu órgão e rode
com a variável de ambiente PERFIL=<uf>_<orgao>. Os nomes são os mesmos de `rj_agenersa.py` (o caso de referência,
com os valores reais da AGENERSA); nenhum script precisa mudar. Os valores abaixo são EXEMPLOS fictícios de um órgão
"ARXX" — cada comentário diz o que levantar e onde.

Regra de ouro: todo valor tem fonte (norma, edital, organograma, consulta ao SEI). Anote a fonte no comentário; o que
for hipótese (horas-base, fator de custo) fica marcado como hipótese até a calibração com os servidores."""
import re

# ---------------------------------------------------------------- identidade e caminhos
# Sigla do órgão como aparece antes da barra no nome das unidades do SEI ("ARXX/DIRTEC"). Onde ver: tela de
# andamentos de qualquer processo ("Processo remetido pela unidade ARXX/..."). Separa peça própria de peça externa.
ORGAO = "ARXX"
# Uma frase dizendo de onde vieram os processos analisados (gabinete, diretoria, recorte de assuntos). Aparece nos
# fatos ("Processos SEI do código na base") e no site.
DESCRICAO_BASE = "base da Diretoria Técnica"
# Como os prompts dos LLM apresentam o órgão ("agência reguladora (ARXX, XX)") e os setores regulados. Os prompts
# (fichas_trabalho.py, classificar_atividades.py, classificar_novos.py) também citam unidades da AGENERSA como
# exemplo (CAPET, Procuradoria): revise esses exemplos para as unidades do seu órgão.
DESCRICAO_ORGAO = "ARXX, XX"
SETORES_ORGAO = "saneamento e energia"
# Pastas relativas à raiz do repositório. Cada uma pode ser sobrescrita por variável de ambiente sem editar o perfil:
DADOS = "dados"  # (SEI_DADOS) saída do coletor em coleta/ (sei2_dump/*.tsv) e textos; fica fora do git
CATALOGO = "catalogo"  # (SEI_CATALOGO) catálogo de processos do órgão — formato no topo de catalogo/dados_processos.py
# (BASE_NORMAS) sqlite da base normativa, relativo a DADOS; monte com scripts/montar_base_normas.py
# (esquema e insumos em docs/adaptacao/BASE_NORMATIVA.md). Os textos ficam relativos à pasta-avó do sqlite
# (TEXTOS_NORMAS sobrescreve).
BASE_NORMAS = "normas/base_normas.sqlite"

# ---------------------------------------------------------------- calendário
# Data em que o órgão passou a tramitar no SEI (ato de implantação do SEI no Estado ou no órgão; ou o andamento mais
# antigo do dump). Processo gerado antes disso é "migrado": a trilha é parcial e não entra nas medidas de tempo.
INICIO_SEI = "2020-03-01"
# Feriados que fecham o expediente do órgão: nacionais + estaduais (lei estadual de feriados) + municipais da cidade-
# sede (lei municipal) + pontos facultativos que de fato fecham (decreto anual do governador). Os móveis são dias
# contados a partir da Páscoa: Carnaval (−48, −47), Sexta-feira Santa (−2), Corpus Christi (+60).
FERIADOS_MOVEIS = (-48, -47, -2, 60)
# Fixos (mês, dia). Nacionais: 1/1, 21/4, 1/5, 7/9, 12/10, 2/11, 15/11, 20/11, 25/12. Acrescente os do Estado e do
# município-sede (exemplo: 9/7 em SP, 25/1 na cidade de São Paulo).
FERIADOS_FIXOS = [(1, 1), (4, 21), (5, 1), (9, 7), (10, 12), (11, 2), (11, 15), (11, 20), (12, 25)]
ANOS_FERIADOS = range(2013, 2028)  # cubra do processo mais antigo do dump até o ano seguinte ao atual

# ---------------------------------------------------------------- unidades
# Natureza de cada unidade (sigla depois da barra). Onde levantar: organograma/regimento interno do órgão e a lista
# de unidades que aparecem em saida/estadias.csv. Sigla não listada vira "Apoio/assessoria".
NATUREZA_UNIDADE = {
    "SECGER": "Secretaria Executiva", "PROJUR": "Procuradoria", "DIRCOL": "Diretoria colegiada",
    "PRES": "Presidência", "DIRTEC": "Câmara técnica", "DIRECO": "Câmara técnica", "OUV": "Ouvidoria",
}
# Prefixo da sigla dos gabinetes dos dirigentes que relatam (conselheiros, diretores). Ex.: "DIR-" para "DIR-01".
PREFIXO_GABINETE = "DIR-"
# Unidade(s) de passagem obrigatória (secretaria, protocolo central): voltar a ela não conta como retrabalho.
# Onde ver: unidade que mais aparece entre duas outras nas trilhas (saida/estadias.csv).
SECRETARIA = {"SECGER"}
# Unidades que recebem e juntam correspondência externa (protocolo, ouvidoria, secretaria).
RECEPCAO = {"SECGER", "PROT", "OUV"}
# Sigla → palavra que identifica a unidade no nome da raia do BPMN quando a raia não usa a sigla (ou {}).
RAIA_ALIAS = {"SECGER": "SECRETARIA"}

# ---------------------------------------------------------------- tipos de documento do SEI do órgão
# Cada órgão configura no SEI a sua lista de "tipos de documento". Levante os tipos distintos da coluna "tipo" de
# dados/sei2_dump/protocolos.tsv (do mais frequente ao menos) e associe cada um a uma categoria. Mantenha os NOMES DE
# CATEGORIA (segunda coluna): o resto do pipeline depende deles. Ajuste só as expressões regulares (primeira coluna)
# e, depois da calibração com os servidores, as horas-base (quarta coluna, HIPÓTESE). A primeira regra que casar vence.
CATEGORIAS = [
    (r"^Despacho de Encaminhamento", "despacho_encaminhamento", "tramitacao", 0.1),
    (r"^Despacho de Publica", "despacho_publicacao", "tramitacao", 0.2),
    (r"^Despacho de Decis", "despacho_decisorio", "decisao", 2.0),
    (r"^Despacho", "despacho", "instrucao", 0.5),
    (r"^Termo de Encerramento", "termo_encerramento", "tramitacao", 0.1),
    (r"^Termo de (Juntada|Desentranhamento|Abertura|Apensa|Anexa)", "termo_juntada", "tramitacao", 0.1),
    (r"^Termo de Notifica|^Auto de Infra|^Notifica", "notificacao_autuacao", "fiscalizacao", 2.0),
    (r"^Relat[oó]rio de (Fiscaliza|Vistoria|Inspe)", "relatorio_fiscalizacao", "fiscalizacao", 8.0),
    (r"^Relat[oó]rio", "relatorio", "analise", 6.0),
    (r"^Parecer", "parecer", "analise", 6.0),
    (r"^Nota T[eé]cnica", "nota_tecnica", "analise", 8.0),
    (r"^Informa[cç][aã]o", "informacao", "analise", 1.5),
    (r"^Cota|^Manifesta[cç][aã]o Jur[ií]dica", "manifestacao_pge", "analise", 2.0),  # peça da procuradoria
    (r"^Voto", "voto", "decisao", 6.0),
    (r"^Delibera|^Resolu[cç][aã]o Autorizativa", "deliberacao", "decisao", 1.0),
    (r"^Decis[aã]o", "decisao", "decisao", 2.0),
    (r"^Resolu|^Instru[cç][aã]o Normativa|^Portaria", "ato_normativo", "decisao", 3.0),
    (r"^Ata", "ata", "decisao", 2.0),
    (r"^Publica|^Extrato", "publicacao", "comunicacao", 0.3),
    (r"^Minuta", "minuta", "instrucao", 2.0),
    (r"^Of[ií]cio", "oficio", "comunicacao", 0.75),
    (r"^E-?mail", "email", "comunicacao", 0.25),
    (r"^Memorando|^Comunica[cç][aã]o Interna", "comunicacao_interna", "comunicacao", 0.5),
    (r"^Peticionamento|^Recibo|^Protocolo|^Comprovante", "registro_entrada", "tramitacao", 0.1),
    (r"^(Peti[cç][aã]o|Recurso|Manifesta|Carta|Solicita|Requerimento|Defesa|Impugna)", "peca_externa", "juntada", 0.2),
    (r"^(Anexo|Documento|Outros|Planilha|Contrato|Certid|Mapa|Foto)", "anexo", "juntada", 0.1),
]

# ---------------------------------------------------------------- catálogo de processos
# Palavras-chave → código do catálogo (catalogo/dados_processos.py), sobre tipo + especificação + assunto do processo
# SEI. Primeira que casar vence; é só sugestão para a classificação revisada. Monte olhando os tipos de processo mais
# frequentes em dados/sei2_dump/processos.tsv. Os códigos têm de existir no catálogo.
REGRAS_SUGESTAO = [
    (r"auto de infra|multa|penalidade", "P07"),
    (r"reajuste|revis[aã]o tarif|tarifa", "P01"),
    (r"ouvidoria|reclama[cç][aã]o", "P20"),
    (r"fiscaliza|vistoria|notifica", "P06"),
]
# Código → coluna booleana de saida/processos_indicadores.csv que o caso típico do piloto precisa ter (ex.: processo
# de fiscalização sem relatório de fiscalização não é típico). Pode ficar vazio.
PECA_CARACTERISTICA = {"P06": "tem_fiscalizacao"}
# Códigos que entram na coorte da fase 2 mesmo sem modelo BPMN do piloto (decisão da equipe; pode ficar vazio).
CODIGOS_NOVOS_FASE2 = set()
# Tipos recorrentes achados fora do catálogo: código → (início do texto da LACUNA sugerida na classificação, nome).
TIPOS_FORA_CATALOGO = {}
# Ordem de apresentação no site e no visualizador BPMN (códigos com modelo; os não listados vão para o fim).
ORDEM_CODIGOS = ["P01", "P06", "P20"]

# ---------------------------------------------------------------- fase 3: piloto do TO-BE, normas e volume
CODIGOS_FASE3 = ["P01", "P06", "P20"]  # processos escolhidos para conformidade, linha de base, TO-BE e controles
# Família de benchmarking de cada código: nome do arquivo saida/fase3/benchmark/<familia>.json (além de
# "transversal", que vale para todos) e título de cada família no relatório.
FAMILIA_BENCHMARK = {"P01": "tarifa", "P06": "fiscalizacao", "P20": "usuario"}
FAMILIAS_BENCHMARK = {"tarifa": "Revisão e reajuste tarifário", "fiscalizacao": "Fiscalização técnica",
                      "usuario": "Reclamação de usuário", "transversal": "Fluxo decisório, automação e IA (transversal)"}

# Normas citadas em toda peça por serem do próprio SEI (decreto de implantação do SEI no Estado, assinatura
# eletrônica, Lei 14.063/2020 etc.): não são base normativa da atividade. Levante no texto das peças as citações
# que aparecem em quase todos os documentos, de todos os tipos.
RUIDO_NORMA = re.compile(r"14\.?063|assinatura eletr", re.I)

# Volume anual por tipo: processos distintos com deliberação/decisão do tipo no ano, em todo o órgão (tabela
# "deliberacoes" da base normativa). Código → (valores de tipo_decisao, regex sobre tema + ementa). Teste a regra
# contra os processos do código na coorte (volume_anual.json traz a revocação).
# Para a priorização da automação (fase 4), escreva uma regra para CADA código da coorte, não só para os do TO-BE.
# Premissas da fase 4 (CUSTO_HORA_DEV, HORAS_CAPACIDADE etc.) podem ser declaradas aqui e sobrescrevem as de comum.py.
VOLUME_REGRAS = {
    "P01": (("tarifa",), r"reajust"),
    "P06": (("penalidade",), r"fiscaliza|vistoria"),
    "P20": (("administrativo",), r"ouvidoria|reclama"),
}
VOLUME_ANOS = (2023, 2024, 2025)  # anos completos da planilha de deliberações usados na média

# ---------------------------------------------------------------- custo do trabalho
# Vencimento base inicial (R$/mês) dos cargos efetivos que produzem as peças: lei de carreira do órgão ou último
# edital de concurso (tabela de remuneração). Jornada semanal do mesmo edital. Encargos, gratificações e progressão
# ficam no fator de custo total (HIPÓTESE até os dados do RH/folha).
HORAS_SEMANAIS = 40
VENCIMENTO_BASE = {"Especialista em Regulação": 6000.00, "Analista Administrativo": 4500.00}
CARGO_PADRAO = "Especialista em Regulação"  # cargo usado no custo das peças técnicas e jurídicas
FATOR_CUSTO_TOTAL = {"piso": 1.0, "esperado": 1.6, "teto": 2.2}  # hipótese: gratificações + progressão + encargos
FERIAS_DU = 22  # dias úteis de férias por ano (30 dias corridos ≈ 22 du)
