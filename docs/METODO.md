# Mapeamento de processos da AGENERSA a partir do processo SEI real

Versão 1 — 30/10/2026

## 1. Ideia central

O mapeamento tradicional parte de entrevistas: o servidor descreve o processo como acha que ele
acontece. Aqui invertemos a ordem. O processo SEI é o registro do que de fato aconteceu: quem
juntou cada documento, quando o processo entrou e saiu de cada setor, o que cada peça diz e quanto
trabalho ela contém. Reconstruímos o fluxo real a partir desse registro e só depois levamos o
resultado aos servidores, para validar e calibrar, não para descrever do zero.

Cada processo SEI vira uma sequência de **tarefas**. Uma tarefa é a passagem de um setor pelo
processo (uma *estadia*) somada aos documentos que esse setor juntou durante a passagem. Dela
extraímos sete dimensões:

| Dimensão | Pergunta | Fonte no SEI |
|---|---|---|
| Sequência | Que setores atuaram, em que ordem? | Andamentos + unidade autora de cada documento |
| Tempo | Quanto tempo o processo ficou em cada setor? | Andamentos (entrada, recebimento, conclusão, remessa) |
| Esforço | Quanto trabalho a tarefa exigiu? | Tipo do documento, laudas, complexidade do conteúdo |
| Insumos | Usou só o próprio processo ou bases externas? | Conteúdo do documento (fontes citadas) |
| Ferramentas | Que cálculos, análises e testes fez? | Conteúdo do documento |
| Competências | Que conhecimento o servidor precisou ter? | Derivado de insumos + ferramentas + natureza da peça |
| Perdas | Houve retrabalho, complementação ou fila? | Retornos na sequência, ofícios de diligência, permanências longas com pouco trabalho |

## 2. Fontes de dados

| Fonte | Conteúdo | Situação |
|---|---|---|
| SEI 2 — Controle de processos (dump `sei2.sql`, 16/06/2026) | 251 processos do gabinete CONS-02, 19.095 andamentos, 12.986 protocolos (tipo, data, unidade que juntou) | Carregado em `dados/sei2_dump/` |
| Relator de voto — Postgres no Railway | Texto integral de cada documento (`doc_text`), MIME e nº de caracteres (`documentos`), análise por IA de cada peça (`extractions`, prompt map-v3: resumo detalhado, pontos-chave, pedidos e determinações, prazos, dispositivos citados, números, documentos referenciados) | Acesso pendente (precisa da URL pública do banco) |
| Especialista AGENERSA | Contratos, resoluções, deliberações e normas | Para interpretar o rito e os prazos legais de cada etapa |
| Diagnóstico organizacional | Inventário de 36 processos em 12 macroprocessos, critérios e top 20, ondas de mapeamento | Usado como catálogo de classificação |

O banco do relator é o que transforma o metadado em mapa de trabalho: o SEI 2 diz *que* a CAPET
juntou um parecer em 12 dias; o texto e a análise do relator dizem *o que* esse parecer fez
(conferiu a fórmula paramétrica com IPCA e IRC, comparou com a tarifa vigente, apontou erro na
base) e *quanto* trabalho isso representa.

## 3. Reconstrução da trilha (Etapa 1 — `scripts/trilhas.py`)

### 3.1 Estadias

O SEI registra, na unidade de destino, "Processo remetido pela unidade X", "Processo recebido na
unidade", "Conclusão do processo na unidade" e "Reabertura do processo na unidade". O processo pode
estar aberto em várias unidades ao mesmo tempo. Regras:

- **Entrada** em uma unidade: geração do processo, remessa para ela, reabertura ou recebimento
  sem estadia aberta. A entrada conta a partir da remessa (o processo já está na caixa da
  unidade), não do recebimento.
- **Saída**: conclusão na unidade ou remessa feita por ela. Se a unidade remeteu e depois aparece
  uma conclusão sem reabertura, ela manteve o processo aberto: a estadia é estendida até a
  conclusão.
- Estadia ainda aberta na data de corte é medida até o corte e marcada `em_aberto`.

### 3.2 Documentos atribuídos

Cada documento é ligado à estadia da unidade que o juntou cuja janela contém a data de inclusão;
na falta, à estadia mais próxima da mesma unidade. Na base atual, 95% caem dentro de uma estadia,
4% na mais próxima e 0,3% ficam sem estadia (documentos de processos físicos anteriores ao SEI).

Os documentos são agrupados em categorias pelo tipo SEI (`scripts/comum.py`), cada uma com uma
natureza de trabalho:

| Natureza | Categorias |
|---|---|
| Tramitação | despacho de encaminhamento, termo de encerramento/juntada, registro de entrada |
| Juntada | peças externas (petição, carta, manifestação), anexos |
| Comunicação | ofício, e-mail, publicação, correspondência interna |
| Instrução | despacho de mérito, minuta |
| Fiscalização | relatório de fiscalização, termo de notificação, auto de infração |
| Análise | parecer, relatório, nota técnica, informação, manifestação da PGE |
| Decisão | voto, deliberação, decisão, ata, ato normativo, despacho decisório |

A estadia recebe o **perfil** da natureza mais densa que produziu (decisão > análise >
fiscalização > instrução > comunicação > juntada > tramitação). Estadia sem documento é
**passagem**.

### 3.3 Tempo

Para cada estadia: tempo total em dias corridos e úteis (calendário com feriados nacionais, do RJ
e do município do Rio), espera até a primeira juntada e cauda entre o último documento e a saída.

Como o processo fica aberto em várias unidades ao mesmo tempo, somar estadias conta o mesmo dia
mais de uma vez, e a estadia se estende depois do marco que interessa. **A estadia não mede espera**
(lição da auditoria: ela produziu o falso gargalo "fila de relatoria").

**Posse.** Em cada instante, o processo pertence à unidade que o abriu mais recentemente entre as que
o têm aberto. Quando todas concluíram e ninguém reabriu, o tempo é **SEM UNIDADE**: processo parado
sem dono. A posse particiona o lead time sem sobreposição.

**Linha do tempo** (`scripts/fatos.py`). Cada atividade do modelo tem ocorrências: sequências
contínuas de peças próprias (da unidade da raia) vinculadas a ela. Para cada ocorrência:
- **execução** = da 1ª à última peça própria;
- **espera antes** = do fim da ocorrência anterior (de qualquer atividade) ao início desta, dividida
  entre as unidades que tinham a posse nesse intervalo.
Esses são os tempos do diagrama, das fichas e das avaliações.

**Terceiros.** De cada ofício ou notificação até a resposta (carta, petição protocolada em processo
relacionado, anexo recebido pelo protocolo), com a data real escrita na peça quando existe, limitada
ao prazo dado no ofício + 5 du (sem prazo conhecido: 60 du). O excesso, e o intervalo sem data real,
é **indeterminado**: não se separa de processo parado.

**Tabela de fatos** (`saida/bpmn/fatos_<Pxx>.json`): a única fonte de números das avaliações. Cada
bloco da avaliação cita os fatos que usa e `scripts/validar_avaliacao.py` barra número que não seja
valor de fato citado.

### 3.4 Esforço

O esforço é estimado em duas camadas:

1. **Proxy por tipo** (já aplicado): horas-base por categoria de documento — 0,1 h para um
   despacho de encaminhamento, 0,75 h para um ofício, 6 h para um parecer ou voto, 8 h para um
   relatório de fiscalização ou nota técnica. São hipóteses iniciais, explícitas em
   `scripts/comum.py`, para calibrar.
2. **Modelo por conteúdo** (Fase de piloto): com o texto do documento,

   `horas = horas_base(categoria) + laudas_autorais × horas_por_lauda(complexidade) + documentos_analisados × horas_de_leitura + fontes_externas × horas_por_fonte`

   - lauda = 1.250 caracteres com espaços, contando só o texto autoral (transcrições de peças
     anteriores, comuns em relatórios e votos, são descontadas pela fração autoral estimada);
   - complexidade de 1 a 5: (1) encaminhamento; (2) comunicação ou instrução simples; (3) análise
     de um documento; (4) análise cruzada de vários documentos ou dados, com cálculo; (5)
     auditoria ou análise com bases externas, modelagem ou teste;
   - documentos analisados e fontes externas vêm da análise do conteúdo (documentos referenciados,
     números e dispositivos citados).

   Na leitura do documento, a ficha também atribui horas à peça. As duas estimativas ordenam as
   peças do mesmo jeito, mas a da ficha dá cerca de 40% das horas do modelo. Até a calibração, o
   esforço é apresentado como faixa: a ficha é o piso e o modelo, o teto.

**Autoria.** Só conta como trabalho da unidade o documento que ela produziu. O editor do SEI gera
HTML; PDF é peça de fora juntada (ofício de terceiros, publicação, deliberação ou ata copiadas),
salvo relatórios técnicos e notificações, que as câmaras sobem em PDF. Peça externa conta só como
juntada (0,1 h) e não recebe ficha.

A **razão trabalho/tempo** de cada período de posse (horas estimadas ÷ dias úteis × 6 h) separa
trabalho de espera. Um período de 20 dias úteis ou mais em que o trabalho estimado ocupa menos de 5% da
capacidade é marcada como **espera dominante**; se além disso só produziu peças leves (≤ 1 h), é
**fila longa com trabalho curto** — o padrão "processo parado meses que depois recebe um despacho".

### 3.5 Insumos, ferramentas e competências (Fase de piloto)

Para cada peça substantiva (parecer, relatório, nota técnica, voto, informação, relatório de
fiscalização) uma segunda leitura por IA preenche uma **ficha de trabalho**:

| Campo | Valores |
|---|---|
| Natureza do trabalho | encaminhamento, comunicação, instrução, análise jurídica, análise técnica de engenharia, análise econômico-financeira, fiscalização de campo, auditoria, decisão |
| Entregável | o que a peça entrega (opinião, cálculo, notificação, decisão) |
| Insumos | documentos do próprio processo; documentos da regulada; bases externas (IPCA/IBGE, SNIS/SINISA, ANP, dados de concessionária, jurisprudência); normas e contratos; vistoria |
| Ferramentas e técnicas | cálculo tarifário paramétrico, fluxo de caixa e taxa de desconto, análise de indicadores, conferência documental, amostragem, teste de auditoria, vistoria e registro fotográfico, análise normativa e de precedentes, planilha, SIG |
| Competências | área (jurídico-regulatória, econômico-financeira, engenharia de saneamento, engenharia de gás e segurança, auditoria e controle, dados e estatística, redação oficial, gestão processual, atendimento ao usuário, ambiental) e nível (básico, intermediário, especialista) |
| Complexidade, fração autoral, horas estimadas | com a justificativa |
| Sinais de perda | pedido de complementação, devolução por vício, refazimento, prazo concedido à regulada |

A ficha reaproveita a análise map-v3 que já existe no banco (resumo detalhado, pedidos e
determinações, dispositivos citados, números, documentos referenciados) e acrescenta só o que falta
para o mapeamento. Peças de tramitação não passam por IA: a categoria basta.

### 3.6 Perdas: retrabalho, complementação e fila

| Sinal | Como se detecta |
|---|---|
| Iteração | Retorno a uma unidade (fora a secretaria, que é passagem obrigatória) já visitada; padrão A → B → A (pingue-pongue) |
| Complementação | Ofício ou despacho cujo conteúdo pede complementação, esclarecimento ou correção, seguido de nova juntada da regulada e nova análise |
| Espera externa | Tempo entre ofício/notificação e a resposta juntada; vistas e razões finais (acessos externos) |
| Fila | Espera dominante e fila longa com trabalho curto (seção 3.4) |
| Passagem | Estadias sem documento: o processo passou pela unidade sem que ela juntasse nada |
| Fragmentação | Processos anexados, apensados ou relacionados que tratam do mesmo objeto |

### 3.7 Do processo SEI ao processo organizacional

Cada processo SEI é classificado no inventário do diagnóstico (P01–P36) pelo objeto de mérito, com
P15 (instrução e julgamento) registrado à parte como rito transversal. Dentro de cada processo
organizacional, as trilhas são agregadas em:

- **variantes**: sequências de unidades ativas e sua frequência;
- **grafo de sucessão** (quem passa para quem), com frequência e tempo mediano de cada transição;
- **modelo AS-IS** em BPMN, com raias pelas unidades que de fato atuam, tarefas nomeadas pela
  natureza do trabalho e anotações de tempo, esforço e perda;
- **SIPOC por tarefa** (entradas, saídas, fornecedores e clientes vêm dos insumos e entregáveis);
- **matriz de competências** por unidade e por processo;
- **capacidade**: horas estimadas por unidade e ano comparadas com a força de trabalho declarada.

## 4. Etapas

| Fase | O que faz | Produto |
|---|---|---|
| 0. Base e trilhas | Reconstrói estadias, atribui documentos, calcula tempos e proxies; classifica os 251 processos; seleciona o piloto | `saida/*.csv`, planilha da Fase 0 (feito em 30/10/2026) |
| 1. Piloto de conteúdo | Exporta texto e análises do relator para os processos-piloto; gera a ficha de trabalho por peça; ajusta o modelo de esforço; desenha o AS-IS dos processos organizacionais do piloto | Fichas, AS-IS piloto, relatório de lições |
| 2. Validação e calibração | Apresenta as trilhas reconstruídas às unidades; coleta tempo real de ~20 peças-tipo (estudo de tempo curto, não entrevista aberta); confirma variantes e nomes de tarefa | Coeficientes calibrados, variantes validadas |
| 3. Escala | Aplica o modelo calibrado à carteira toda; amplia a base SEI para além do gabinete CONS-02 (outras unidades e processos que não chegam ao colegiado) | Catálogo AS-IS por processo, painel de tempos e perdas |
| 4. Diagnóstico e redesenho | Gargalos, retrabalho, competências críticas, oportunidades de automação | Recomendações e TO-BE |

## 5. Limites conhecidos

- **Viés de amostra.** A base é a carteira do gabinete CONS-02: só processos que chegaram à
  relatoria. Cobre bem o núcleo finalístico e o rito decisório; não cobre processos de suporte
  (pessoas, contratações, orçamento) nem demandas que terminam sem decisão colegiada (a maior parte
  das manifestações da Ouvidoria, por exemplo). A Fase 3 precisa de listas de processos de outras
  unidades.
- **Processos migrados.** Os andamentos começam em novembro de 2019. Processos físicos anteriores
  (79 dos 251) têm trilha parcial e servem para conteúdo, não para tempo.
- **Data do dump.** O SEI 2 em produção é atualizado diariamente; o dump local é de 16/06/2026.
  Para a escala, ler do banco de produção.
- **Documentos restritos.** Peças sigilosas não têm texto; entram pela categoria, sem ficha.
- **Esforço é estimativa.** O SEI não registra horas. O modelo dá ordem de grandeza comparável
  entre tarefas e unidades; a calibração com servidores é o que o aproxima do tempo real.
- **Quem assina não é quem trabalha.** A unidade autora é certa; a pessoa e a equipe que
  prepararam a peça, não. O mapeamento é por unidade.
