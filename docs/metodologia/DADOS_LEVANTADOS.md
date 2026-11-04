# Dados levantados para a melhoria

Inventário de cada dado que sustenta a linha de base, a conformidade e o TO-BE: de onde vem, que script o gera, onde
fica, quanto se pode confiar nele e o que o aluno precisa obter no próprio órgão, e com quem.

Graus de confiança:

- **Medido** — sai do registro do SEI por regra determinística testada (tempo, sequência, contagem).
- **Estimado** — sai de leitura por LLM ancorada em trecho literal, ou de regra com cobertura parcial; tem taxa de erro
  medida por amostra.
- **Hipótese** — parâmetro adotado para calcular, sem medição no órgão; tem de ser dito como hipótese no entregável.

## 1. Tempo e fluxo

| Dado | Para quê | Fonte | Script → arquivo | Confiança | No caso AGENERSA | O que obter no seu órgão (com quem) |
|---|---|---|---|---|---|---|
| Estadias, posse, tempo sem unidade | Onde o processo esteve e com quem | Andamentos do SEI | `trilhas.py` → `saida/estadias.csv`, `posse.csv` | Medido | Posse de 250 processos sem lacuna nem sobreposição (`saida/auditoria/auditoria_automatica.json`) | Conferir a trilha de um caso com a unidade (secretaria ou protocolo) |
| Linha do tempo por caso (ocorrências, espera antes, execução, espera por unidade) | Base da linha de base e da simulação | Peças atribuídas a atividades + posse | `procedimento.py` → `saida/fase2/casos_<cod>.json` | Medido (tempos) sobre rótulo estimado (atividade da peça, com concordância medida) | 18, 12 e 11 casos nativos nos três processos do TO-BE (`saida/fase3/linha_base_*.json`) | Nada além do SEI; validar nomes das atividades com a unidade dona |
| Tempo de resposta de terceiros | Separar o que o órgão não controla | Ofício com prazo (ficha) + data real da resposta (análise por peça) | `trilhas.py` → `saida/janelas_terceiros.csv`; por ocorrência em `casos_<cod>.json` | Medido onde há data real; **indeterminado** onde não há | Data real em cerca de 56% das peças externas ([AUDITORIA.md](../AUDITORIA.md)); mediana de 15,5 du por caso no reajuste (`linha_base_P01.json`) | Prazos contratuais de resposta das reguladas (área técnica); se possível, data de protocolo das respostas |
| Lead time por caso | Indicador principal | Linha do tempo | `linha_base.py` → `saida/fase3/linha_base_<cod>.json` | Medido | Mediana 337,5 / 351 / 469 du (reajuste / fiscalização / ocorrência) | — |
| Caminhos, transições, laços | Variantes e decisões do BPMN | Atribuições | `procedimento.py` → `procedimento_<cod>.json` | Medido sobre rótulo estimado | 17 caminhos em 18 casos no reajuste ([RESULTADOS_FASE2.md](../RESULTADOS_FASE2.md)) | Confirmar variantes com a unidade |

## 2. Trabalho e custo

| Dado | Para quê | Fonte | Script → arquivo | Confiança | No caso AGENERSA | O que obter no seu órgão (com quem) |
|---|---|---|---|---|---|---|
| Horas por peça (piso e teto) | Esforço, FTE, R$ | Ficha de trabalho (piso) e modelo por laudas e complexidade (teto) | `fichas_trabalho.py`, `asis_piloto.py` → `saida/esforco_documentos.csv` | **Hipótese** até a calibração | Mediana por caso de 24,9–64 h no reajuste (`linha_base_P01.json`) | **Estudo de tempo curto** com ~20 peças-tipo (parecer, relatório técnico, voto, ofício, relatório de fiscalização), com os servidores das unidades |
| Horas produtivas por dia útil | Razão trabalho/tempo, espera dominante | Parâmetro | `HORAS_DIA = 6` em `trilhas.py` | Hipótese | 6 h | Jornada e tempo de expediente efetivo (RH, chefias) |
| Horas de um FTE por ano | Converter horas em FTE | 8 h × (dias úteis do ano − 22 du de férias) | `comum.horas_ano_fte` | Hipótese | Calculado para 2025 | Jornada, férias, afastamentos médios (RH) |
| Custo-hora por cargo | Resultado em R$ | Vencimento base inicial de edital ÷ 173,3 h/mês | `comum.CUSTO_HORA_BASE` | Hipótese (piso) | R$ 32,71/h para o cargo técnico de nível superior adotado como padrão (`linha_base_*.json`, `parametros`) | Remuneração média por cargo com adicionais, progressão e encargos patronais (**RH**); cargo que de fato produz cada tipo de peça (chefias) |
| Fator de custo total | Encargos, adicionais, progressão | Parâmetro | `comum.FATOR_CUSTO_TOTAL` = 1,0 / 1,6 / 2,2 | **Hipótese** | Piso, esperado, teto | Folha real (RH) — substitui o fator |
| Horas, FTE e R$ por ano (AS-IS) | Tamanho do ganho | Média de horas por caso × volume anual × custo-hora | `linha_base.py` → `anual` | Hipótese (herda horas, volume e custo) | Reajuste: 1.261–2.736 h/ano; 0,69–1,51 FTE; R$ 41.254 / 104.586 / 196.852 (`linha_base_P01.json`) | Os três dados acima |
| Força de trabalho por unidade | Comparar carga estimada com capacidade | — | **Não levantado no caso** | — | Pendente com o RH | Lotação por unidade e cargo (RH) |
| Competências por unidade | Matriz de competências, talento não aproveitado | Fichas (área e nível com evidência) | `fichas_atividades.py`, planilha do piloto | Estimado | Ver [RESULTADOS_PILOTO.md](../RESULTADOS_PILOTO.md), seção 3 | Validação com chefias e RH (trilhas de capacitação) |

## 3. Volume

| Dado | Para quê | Fonte | Script → arquivo | Confiança | No caso AGENERSA | O que obter no seu órgão (com quem) |
|---|---|---|---|---|---|---|
| Volume anual por tipo | Multiplicar o ganho por caso | Processos distintos com deliberação do tipo no ano, em todo o órgão (tipo de decisão + termos no tema ou na ementa) | `volume_anual.py` → `saida/fase3/volume_anual.csv` e `.json` | Medido, mas **piso** (o que não chega a deliberação não entra) | Média 2023–2025: 34,7 / 3,7 / 26,7 por ano; revocação da regra na coorte 94,4% / 87,5% / 100% (`volume_anual.json`) | Relatório do SEI por tipo de processo e ano (secretaria ou TI), ou registro de deliberações (secretaria do colegiado). Conferir a regra de cada tipo: no caso, a fiscalização deu volume baixo e deve ser confirmada |

## 4. Lei e conformidade

| Dado | Para quê | Fonte | Script → arquivo | Confiança | No caso AGENERSA | O que obter no seu órgão (com quem) |
|---|---|---|---|---|---|---|
| Normas com trecho literal | Base legal de cada atividade | Texto integral na base normativa | `normas_processo.py` (candidatos) + agente → `saida/fase3/normas_<cod>.json`; `verificar_normas.py` | Trecho: verificado; seleção e interpretação: estimadas | 31 / 32 / 33 normas | Lei de criação, regimento, lei estadual de processo administrativo, contratos e aditivos, normas internas (**procuradoria**, secretaria do colegiado) |
| Requisitos com teste | O que é testável | Normas | agente → `normas_<cod>.json` | Estimado (tradução da norma em teste) | 20 / 20 / 19 requisitos | Conferência da matriz pela **procuradoria** |
| Conformidade por requisito | Achado legal; linha de base de indicadores | Linha do tempo + testes | `conformidade.py` → `conformidade_<cod>.csv/json` | Medido, dado o teste | Ex.: pronunciamento em 30 dias no reajuste, 17,6% (`conformidade_P01.json`) | Validar casos não conformes com a unidade e a procuradoria antes de divulgar |
| Prazos concedidos nas peças | Requisito `prazo_concedido_min`; janela de terceiros | Fichas (prazo com trecho literal) | `fichas_trabalho.py` | Estimado (sem prazo lido = sem evidência) | — | — |
| Prazos mínimos protegidos | Trava do TO-BE | Requisitos `prazo_min` | `validar_tobe.py` | Derivado | Defesa, manifestação e razões finais | Confirmar prazos legais com a procuradoria |

## 5. Referências externas e parâmetros do TO-BE

| Dado | Para quê | Fonte | Script → arquivo | Confiança | No caso AGENERSA | O que obter no seu órgão (com quem) |
|---|---|---|---|---|---|---|
| Casos de benchmarking | Lastro e parâmetro das melhorias | Literatura científica (DOI) e documentos oficiais | agente → `saida/fase3/benchmark/<familia>.json`; verificação independente | Verificado (existência, trecho, resultado); transferência ao órgão: estimada | 64 casos, 13 corrigidos ([BENCHMARKING.md](../BENCHMARKING.md)) | Experiências de outras agências do Estado e da associação de reguladores (relatos com resultado) |
| Valores dos cenários das melhorias | Simulação | Benchmark (teto), fatos AS-IS, requisitos, ou hipótese | agente → `melhorias_<cod>.json` | Hipótese ou referência externa, explicitado por melhoria | 10 de 18, 9 de 16 e 12 de 18 melhorias são hipótese | Validação com a unidade dona do processo (viabilidade e ordem de grandeza) |
| Dados para automação (fase 2 e 3) | Dependências das melhorias | Sistemas do órgão e das reguladas | `dependencias` em `melhorias_<cod>.json` | — | Relatórios ou API do SEI, dados das concessionárias, sistema da ouvidoria | Inventário de sistemas e acessos (**TI**); dados das reguladas (área técnica) |

## 6. Priorização da automação (fase 4)

| Dado | Para quê | Fonte | Script → arquivo | Confiança | No caso AGENERSA | O que obter no seu órgão (com quem) |
|---|---|---|---|---|---|---|
| Volume anual estimado por tipo | Critério de volume e retorno | Piso de deliberações ÷ (fração com deliberação × revocação) | `volume_anual.py` → `priorizacao_automacao.py` → `saida/fase4/matriz_automacao.json` (`volume.estimado`) | Estimado; sem medida quando a revocação fica abaixo de 75% | 7 tipos com volume medido, 4 sem ([PRIORIZACAO_AUTOMACAO.md](../PRIORIZACAO_AUTOMACAO.md)) | Contagem de processos por tipo e ano no SEI (**TI** ou secretaria); para tipos que não chegam ao colegiado, o sistema da área (ouvidoria, fiscalização) |
| Sinais de análise, dados, regras e padrão | Critérios da matriz | Fichas de trabalho das peças da coorte | `priorizacao_automacao.py` → `sinais` por tipo | Estimado (herda a ficha, com itens ancorados) | Ver matriz | Conferir com a unidade se as peças de análise de maior peso estão certas |
| Potencial de IA por atividade | Completude e fração automatizável | Avaliação AS-IS | `avaliacao_<cod>.json` → matriz | Julgamento do agente, sem verificação independente | 13 de 16 atividades alto ou médio no reajuste | Validar com a unidade dona as atividades de potencial alto |
| Fração automatizável por potencial | Retorno | Parâmetro | `comum.FRACAO_AUTOMATIZAVEL` | **Hipótese** | 0,4–0,8 (alto), 0,15–0,45 (médio), 0–0,1 (baixo) | Medir antes e depois no piloto do sistema |
| Horas de construção e custo-hora de desenvolvimento | Custo | Parâmetro | `comum.HORAS_CAPACIDADE`, `HORAS_PLATAFORMA`, `HORAS_CONFIG_ATIVIDADE`, `CUSTO_HORA_DEV` | **Hipótese** | R$ 100 / 150 / 220 por hora | Contrato ou custo da equipe interna (**TI**, compras); horas medidas no primeiro protótipo |
| Custo de leitura pelo modelo de linguagem | Custo anual | Caracteres por caso (fichas) × preço | `comum.PRECO_LLM_MCHAR` | **Hipótese** de preço; caracteres medidos | Desprezível frente à manutenção no caso | Preço vigente do provedor contratado (**TI**) |

## 7. Parâmetros do órgão (perfil)

| Dado | Fonte | Onde | Com quem |
|---|---|---|---|
| Feriados estaduais e municipais da sede, pontos facultativos | Decretos oficiais | Perfil do órgão | RH ou gabinete |
| Data de implantação do SEI no órgão | TI ou secretaria | Perfil do órgão | TI |
| Unidades, siglas, natureza, hub, unidades de recepção | Organograma, regimento | Perfil do órgão | Planejamento, RH |
| Catálogo de processos organizacionais | Inventário ou mapa de processos | `catalogo/` | Planejamento |
| Tipos de documento do SEI e categorias | Lista de tipos da instalação | Perfil do órgão (`CATEGORIAS`) | TI / gestor do SEI |

## Resumo do que pedir no órgão

| A quem | O quê |
|---|---|
| **RH** | Remuneração média por cargo com encargos, adicionais e progressão; jornada, férias e afastamentos; lotação por unidade |
| **Procuradoria** | Base normativa completa; conferência da matriz de requisitos, das interpretações e dos prazos mínimos |
| **Unidades finalísticas** | Conferência de uma trilha; nomes de atividades e variantes; critério das decisões; estudo de tempo de ~20 peças; viabilidade das melhorias de maior peso |
| **Secretaria do colegiado / protocolo** | Lista de processos por tipo e ano (volume); calendário de sessões |
| **TI / gestor do SEI** | Acesso à Pesquisa Pública ou relatórios; data de implantação; tipos de documento; sistemas para automação; custo-hora de desenvolvimento e preço do modelo de linguagem contratado |
| **Gestão** | Escolha do piloto do sistema a partir da matriz de priorização |
| **Planejamento** | Catálogo de processos; lacunas e fronteiras; aceite das metas |
