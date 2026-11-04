"""Perfil AGENERSA (Agência Reguladora de Energia e Saneamento Básico do Estado do Rio de Janeiro).

Caso de referência do repositório: as saídas em saida/ foram geradas com estes valores. Mudar um valor aqui muda os
números — por isso o perfil é a única fonte deles (os scripts leem por `comum`). Os comentários dizem de onde veio
cada valor; para outro órgão, use `modelo.py` como roteiro."""
import re

# ---------------------------------------------------------------- identidade e caminhos
ORGAO = "AGENERSA"  # prefixo das unidades no SEI ("AGENERSA/CAPET"): separa peça própria de peça externa
DESCRICAO_BASE = "base do gabinete CONS-02"  # de onde vieram os processos (aparece nos fatos e no site)
# como os prompts dos LLM apresentam o órgão: "agência reguladora (AGENERSA, RJ)" e, na classificação de processos
# novos, "(AGENERSA, RJ: saneamento e gás canalizado)". Mudar o texto muda o prompt (refaz o cache das fichas).
DESCRICAO_ORGAO = "AGENERSA, RJ"
SETORES_ORGAO = "saneamento e gás canalizado"
# caminhos relativos à raiz do repositório; sobrescrita por variável de ambiente (entre parênteses)
DADOS = "dados"  # (SEI_DADOS) dump do SEI, banco do relator, caches — fora do git: tem dados pessoais
CATALOGO = "catalogo"  # (SEI_CATALOGO) dados_processos.py e oficina_dados.py do diagnóstico organizacional
# (BASE_NORMAS) sqlite da base normativa, relativo a DADOS. Na AGENERSA é a base do Especialista AGENERSA
# (data/base_conhecimento.sqlite, fora deste repositório); os textos ficam em data/txt/... relativos à pasta-avó do
# sqlite (TEXTOS_NORMAS sobrescreve). Esquema mínimo em docs/adaptacao/BASE_NORMATIVA.md.
BASE_NORMAS = "normas/base_normas.sqlite"

# ---------------------------------------------------------------- calendário
# Início do SEI-RJ na AGENERSA: andamentos anteriores não existem no dump (processos físicos migrados)
INICIO_SEI = "2019-11-01"
# Feriados nacionais, estaduais (RJ) e municipais do Rio que fecham o expediente, mais Carnaval (ponto facultativo de
# fato no serviço público estadual). Móveis em dias a partir da Páscoa: Carnaval (−48, −47), Sexta-feira Santa (−2),
# Corpus Christi (+60). Fixos (mês, dia): Confraternização, São Sebastião (Rio), Tiradentes, São Jorge (RJ), Trabalho,
# Independência, Aparecida, Servidor Público, Finados, República, Consciência Negra, Natal.
FERIADOS_MOVEIS = (-48, -47, -2, 60)
FERIADOS_FIXOS = [(1, 1), (1, 20), (4, 21), (4, 23), (5, 1), (9, 7), (10, 12), (10, 28), (11, 2),
                  (11, 15), (11, 20), (12, 25)]
ANOS_FERIADOS = range(2013, 2028)

# ---------------------------------------------------------------- unidades
# Unidades da AGENERSA por natureza (organograma; ajustar na validação)
NATUREZA_UNIDADE = {
    "SCEXEC": "Secretaria Executiva", "SECEX": "Secretaria Executiva",
    "PROC": "Procuradoria", "CODIR": "Conselho-Diretor", "PRESI": "Presidência",
    "CAPET": "Câmara técnica", "CASAN": "Câmara técnica", "CAENE": "Câmara técnica", "CARES": "Câmara técnica",
    "OUVI": "Ouvidoria", "OUV": "Ouvidoria",
}
PREFIXO_GABINETE = "CONS-"  # siglas dos gabinetes de conselheiro (CONS-01, CONS-02, ...)
SECRETARIA = {"SCEXEC", "SECEX"}  # passagem obrigatória: retorno a ela não é iteração (o "hub" da trilha)
RECEPCAO = {"SCEXEC", "SECEX", "PROT", "OUV", "OUVI"}  # unidades que recebem e juntam correspondência externa
# sigla da unidade → palavra que a identifica no nome da raia do BPMN quando a raia não usa a sigla
RAIA_ALIAS = {"SCEXEC": "SECRETARIA"}

# ---------------------------------------------------------------- tipos de documento do SEI-RJ
# (regex sobre o "tipo" do protocolo, categoria, natureza do trabalho, horas-base de esforço)
# Horas-base são HIPÓTESE inicial para calibrar (Fase 3 do método); com o texto do documento
# o esforço passa a ser horas-base + laudas × horas/lauda × fator de complexidade.
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
    (r"^Conclusivo|^Promo[cç][aã]o|^Visto\b", "manifestacao_pge", "analise", 2.0),
    (r"^Voto", "voto", "decisao", 6.0),
    (r"^Delibera", "deliberacao", "decisao", 1.0),
    (r"^Decis[aã]o", "decisao", "decisao", 2.0),
    (r"^Resolu|^Instru[cç][aã]o Normativa|^Portaria", "ato_normativo", "decisao", 3.0),
    (r"^Ata", "ata", "decisao", 2.0),
    (r"^Publica|^Extrato", "publicacao", "comunicacao", 0.3),
    (r"^Minuta", "minuta", "instrucao", 2.0),
    (r"^Of[ií]cio", "oficio", "comunicacao", 0.75),
    (r"^E-?mail", "email", "comunicacao", 0.25),
    (r"^Correspond[eê]ncia Interna|^Memorando|^Comunica[cç][aã]o Interna", "comunicacao_interna", "comunicacao", 0.5),
    (r"^Peticionamento|^Recibo|^Protocolo|^Comprovante|^Inscri", "registro_entrada", "tramitacao", 0.1),
    (r"^(Peti[cç][aã]o|Recurso|Manifesta|Carta|Solicita|Requerimento|Defesa|Impugna|Contesta|Raz[oõ]es)",
     "peca_externa", "juntada", 0.2),
    (r"^(Anexo|Documento|Outros|Conte[uú]do|Apresenta|Planilha|Contrato|Certid|Comprovante|Volume|Mapa|Foto)",
     "anexo", "juntada", 0.1),
]

# ---------------------------------------------------------------- catálogo de processos (P01–P36)
# Sugestão por palavras-chave do processo organizacional (regex sobre tipo + natureza + assunto, código do processo):
# primeira que casar vence. É só ponto de partida para a classificação revisada por agente.
REGRAS_SUGESTAO = [
    (r"auto de infra|multa|penalidade|sancion", "P07"),
    (r"recurso|embargos|reconsidera", "P16"),
    (r"revis[aã]o (tarif[aá]ria )?(ordin|quinq)|rtq|quinquenal", "P02"),
    (r"reequil[ií]brio|aditivo", "P03"),
    (r"reajuste|revis[aã]o|tarifa", "P01"),
    (r"obras|investiment|homologa", "P04"),
    (r"taxa de regula", "P31"),
    (r"regularidade fiscal|econ[oô]mico-fisca|demonstra[cç][oõ]es|seguro garantia|financeiro|outorga", "P05"),
    (r"snis|sinisa", "P11"),
    (r"[ií]ndices de desempenho|metas|idg|verificador|perdas|educa[cç][aã]o ambiental", "P08"),
    (r"plano ver[aã]o|conting[eê]ncia|abastecimento|interrup|falta d", "P35"),
    (r"faturamento|medi[cç][aã]o|corte|religa|tarifa social|cobran", "P36"),
    (r"ouvidoria|reclama[cç][aã]o de usu", "P20"),
    (r"ocorr[eê]ncia", "P21"),
    (r"minist[eé]rio p[uú]blico|mprj|inqu[eé]rito|tce|tribunal de contas|defensoria", "P22"),
    (r"consulta p[uú]blica|audi[eê]ncia p[uú]blica", "P13"),
    (r"normativ|resolu[cç][aã]o|instru[cç][aã]o normativa", "P12"),
    (r"inspe[cç][aã]o peri[oó]dica|acidente|incidente", "P09"),
    (r"fiscaliza|notifica|vistoria|irregularidade|polui|ambiental", "P06"),
]
# peça que caracteriza o processo organizacional: o caso típico do piloto precisa tê-la
PECA_CARACTERISTICA = {"P06": "tem_fiscalizacao", "P07": "tem_fiscalizacao"}
# tipos que entram na coorte da fase 2 por decisão de 30/10/2026 ("todos os candidatos"), além dos com modelo:
# inventário sem modelo e demanda fora do inventário
CODIGOS_NOVOS_FASE2 = {"P04", "P19", "P15", "P18", "P07", "P20", "P16", "N01"}
# tipo fora do catálogo: código → (início do texto da LACUNA sugerida na classificação, nome do processo).
# N01 = acompanhamento ambiental e de mananciais (LACUNA recorrente).
TIPOS_FORA_CATALOGO = {"N01": ("Acompanhamento ambiental", "Acompanhamento ambiental e de mananciais das concessões")}
# ordem de apresentação dos processos no site e no visualizador BPMN (os demais vão para o fim)
ORDEM_CODIGOS = ["P01", "P06", "P21", "P35", "P22", "P04", "P19", "N01", "P08", "P18", "P07", "P36", "P03"]

# ---------------------------------------------------------------- fase 3: piloto do TO-BE, normas e volume
CODIGOS_FASE3 = ["P01", "P06", "P21"]  # processos da conformidade, linha de base, TO-BE e controles
# família de benchmarking de cada código (arquivo saida/fase3/benchmark/<familia>.json) e nome de cada família
FAMILIA_BENCHMARK = {"P01": "tarifa", "P06": "fiscalizacao", "P21": "usuario"}
FAMILIAS_BENCHMARK = {"tarifa": "Revisão e reajuste tarifário", "fiscalizacao": "Fiscalização técnica",
                      "usuario": "Ocorrência e reclamação de usuário",
                      "transversal": "Fluxo decisório, automação e IA (transversal)"}

# decretos do SEI e da assinatura eletrônica aparecem em toda peça: não são base normativa da atividade
RUIDO_NORMA = re.compile(r"48\.?209|46\.?730|48\.?013|assinatura eletr|8\.?539", re.I)

# Volume anual por tipo = processos distintos com deliberação no ano em toda a agência (todos os relatores). É um piso:
# processo que não chega à deliberação não entra. Regra: tipo de decisão + termos no tema ou na ementa do catálogo.
VOLUME_REGRAS = {
    "P01": (("tarifa",), r"reajust|atualiza\w+ d\w+ (?:tarifa|margen)"),
    "P06": (("penalidade", "homologacao"), r"fiscaliza|vistoria|termo de notifica|relat[oó]rio (?:de fiscaliza|p-?\s?\d)"),
    "P21": (("penalidade", "administrativo"), r"ocorr[eê]ncia|ouvidoria"),
    # fase 4 (priorização): regras dos demais códigos da coorte; a revocação na coorte diz se a regra serve.
    # P07 e P18 ficam sem regra: nenhum processo da coorte com deliberação que um termo pegue.
    "N01": (("administrativo", "prestacao_de_contas", "penalidade", "homologacao"),
            r"efluente|manancia|ambienta|recursos h[ií]dricos|qualidade d\w* [áa]gua bruta|lagoa"),
    "P04": (("homologacao",), r"(?:aprova|homologa)\w* d\w* (?:projeto|investimento|obra|plano de investiment)"
                              r"|obra emergencial|investimento emergencial"),
    "P08": (("prestacao_de_contas", "normativo", "penalidade", "administrativo"),
            r"\bmetas?\b|\bidg\b|[íi]ndice de desempenho|indicador\w* de desempenho|controle de perdas"),
    "P19": (("homologacao", "administrativo", "tarifa"),
            r"mercado livre|consumidor\w* livre|\bcusd|autoprodu|autoimporta|gasoduto dedicado"),
    "P22": (("administrativo", "penalidade", "recurso"),
            r"tribunal de contas|\btce\b|minist[ée]rio p[úu]blico|\bmprj\b|transpar[êe]ncia"),
    "P35": (("penalidade", "administrativo", "homologacao", "prestacao_de_contas"),
            r"plano de conting|interrup|desabastec|falta d.[áa]gua|rompimento|parada t[ée]cnica"),
}
VOLUME_ANOS = (2023, 2024, 2025)  # anos completos usados na média

# ---------------------------------------------------------------- custo do trabalho
# Custo-hora do trabalho (R$/h). Fonte verificada: edital do concurso AGENERSA 2022 (FGV), item 3.1, vencimento base
# inicial dos cargos da Lei nº 6.848/2014, com 40 h semanais (item 3.5) = 173,3 h/mês. Não inclui Adicional de
# Qualificação, progressão nem encargos patronais: por isso o fator abaixo, que é HIPÓTESE até os dados do RH (TASK-019).
HORAS_SEMANAIS = 40
VENCIMENTO_BASE = {"Especialista em Regulação": 5670.00, "Analista Técnico": 4536.00,
                   "Assistente Técnico de Regulação": 2160.00}
CARGO_PADRAO = "Especialista em Regulação"  # peças técnicas e jurídicas de nível superior
FATOR_CUSTO_TOTAL = {"piso": 1.0, "esperado": 1.6, "teto": 2.2}  # hipótese: AQ + progressão + encargos
# Horas de trabalho de um servidor em tempo integral no ano: 8 h × (dias úteis do ano − 22 du de férias de 30 dias)
FERIAS_DU = 22
