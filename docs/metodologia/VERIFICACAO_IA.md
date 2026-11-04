# Verificação do que foi produzido ou julgado por IA

Esta matriz lista **tudo** o que, no caso de referência, foi produzido ou julgado por LLM ou agente, como foi
verificado, quanto acertou quando foi medido e o que continua sem verificação. Use-a de duas formas: para saber quanto
confiar em cada saída do caso, e como lista mínima de verificações ao replicar.

Legenda de método: **portão** = script que barra a sequência; **automática** = checagem por código em 100% dos itens;
**às cegas** = outro agente, sem ver a resposta, refaz a tarefa sobre o mesmo insumo; **leitura** = auditor
independente julga afirmação por afirmação contra a fonte primária; **comparação** = mesma tarefa por dois modelos.

## Matriz

| # | Saída de IA | Quem produziu | Como foi verificado | Resultado medido no caso | O que continua sem verificação |
|---|---|---|---|---|---|
| 1 | Classificação dos processos SEI no catálogo (código principal, secundário, confiança, lacuna) | Agente, por processo | Às cegas (amostra) | 63 processos: concordância 92,1%, kappa 0,91; 96,8% considerando o secundário; 100% nas de confiança alta; 5 divergências de fronteira ([AUDITORIA.md](../AUDITORIA.md)) | Os processos fora da amostra; fronteiras entre códigos levadas à validação, ainda não decididas pelo órgão |
| 2 | Classificação dos processos que só têm peças (tipos novos) | LLM (`classificar_novos.py`) | Às cegas por agente (`verificacao_classificacao.csv`) | Concordância de 65,5% ([MITIGACOES.md](../MITIGACOES.md)) → **só entra na coorte o processo com consenso** | A classificação dos processos sem consenso (ficaram fora) |
| 3 | Análise por peça (data escrita, ação, pedidos, dispositivos citados, resumo) | LLM (no caso, sistema anterior; na replicação, `coleta/extrair.py`) | Automática: cruzamento de unidade, tipo e data entre as duas fontes; leitura de data com formato explícito | 12.306 peças cruzadas, 0 divergência de unidade e de data, 1 de tipo (`saida/auditoria/auditoria_automatica.json`); data real presente em cerca de 56% das peças externas ([AUDITORIA.md](../AUDITORIA.md)) | **Acerto do campo de data real e dos dispositivos citados não foi auditado por leitura.** Mitigação: sem data real o tempo vai para "indeterminado"; dispositivo citado é só candidato (a norma é conferida no item 9) |
| 4 | Ficha de trabalho por peça (natureza, insumos, ferramentas, cálculos, competências, complexidade, horas, perdas, prazos) | LLM (`fichas_trabalho.py`) | Automática (trecho literal de cada item conferido no texto; números ancorados); leitura (amostras v1 e v2); comparação entre modelos | v2: 0% sem lastro + contradito, 11,1% parcial, 7,8% incoerência (amostra de 30 peças, 332 itens); 97,3% dos itens ancorados ([AUDITORIA.md](../AUDITORIA.md)); 3.183 fichas com 0,3% de números sem âncora (`auditoria_automatica.json`); dois modelos: natureza igual em 78%, complexidade em 76%, horas 1,42× (`comparacao_modelos_fichas.json`) | **Horas** (sem calibração); imprecisão residual de cerca de 11% em prazos e fontes; não há registro nas saídas de auditoria por leitura das fichas da coorte (só a automática e a comparação) |
| 5 | Modelo canônico BPMN (raias, tarefas, decisões, laços, gatilho e saída) | Agente | Automática (modelo × vínculos × trilha; números proibidos no modelo); leitura | 81 tarefas e 356 afirmações auditadas; 1 evento corrigido; frequência divergente 0 em 91 tarefas ([AUDITORIA.md](../AUDITORIA.md), `auditoria_automatica.json`) | Decisões inferidas (sem critério escrito nas peças) e variantes: pendentes de validação com as unidades ([BPMN_PILOTO.md](../BPMN_PILOTO.md)) |
| 6 | Vínculos atividade → peças e descritivos | Agente | Automática (unidade da peça × raia; ordem das datas × ordem do fluxo; tempo proibido no descritivo); leitura | 492 afirmações: 0,6% sem lastro ou contraditas, 5% imprecisas, corrigidas; inversões de cronologia entre 0% e 12,7% dos pares por caso (`auditoria_automatica.json`) | Atribuição de despachos de trâmite (julgamento) |
| 7 | Classificador de atividade (peça → atividade do modelo) | LLM (`classificar_atividades.py`) | Contra os vínculos do piloto; às cegas fora do piloto | 98% em 290 peças contra o piloto (otimista); 216 peças às cegas: 88% no total e 92% nas 150 substantivas; um código com 64% → "estudo de caso" (`auditoria_classificador.json`) | Amostra de 14 substantivas por código: margem larga por código; peças de expediente medidas, mas sem critério próprio |
| 8 | Avaliação AS-IS (síntese, gargalo, desperdícios, valor, potencial de IA, oportunidades) | Agente | Portão (validador de ancoragem + carimbo); leitura em 3 rodadas | Rodada 3: 371 afirmações, 1,3% contraditas (nenhuma sem lastro), 0,5% cálculo errado, 0,5% sentido errado, 6,5% imprecisas; validador com 0 problema ([AUDITORIA.md](../AUDITORIA.md)) | Avaliações dos tipos sem caso-piloto (versão 3, só coorte): passaram pelo validador; não há registro de rodada de leitura independente para elas. Sentido errado não é pego por código |
| 9 | Curadoria de normas (norma, dispositivo, trecho, vigência, abrangência, obrigação) | Agente | Portão: trecho literal conferido contra o texto integral; ids conferidos; fonte externa listada para conferência manual | 96 normas nos 3 processos do TO-BE com trecho verificado (`verificar_normas.py` passa no pipeline) | **Completude** (faltou alguma norma?) e **interpretação jurídica**: dependem da procuradoria. Trechos de fonte externa dependem da conferência manual |
| 10 | Requisitos e testes computáveis | Agente | Testes sintéticos do motor; ids de atividade conferidos contra o modelo | Motor coberto pelos testes `test_conformidade_*` | A **tradução da norma em teste** (parâmetro, unidade du/dc, `de_ocorrencia`) não foi auditada às cegas; o plano previa amostra auditada dos resultados de conformidade e não há registro dela nas saídas |
| 11 | Benchmarking (casos, trecho, resultado, aplicabilidade, parâmetro de ganho) | Agente por família | Verificação independente por outro agente (DOI no Crossref, trecho por comparação normalizada, resultado e parâmetro contra a fonte) | 64 casos: 51 ok, 13 corrigidos, 0 excluídos; 44 DOIs existentes e compatíveis; 1 trecho não literal (`verificacao.json`) | Completude da busca; julgamento de aplicabilidade ao órgão |
| 12 | Melhorias do TO-BE (efeito, valores dos cenários, justificativa) | Agente | Portão (`validar_tobe.py`); simulação determinística; sensibilidade | 0 problema no validador; 10 de 18, 9 de 16 e 12 de 18 melhorias marcadas como hipótese (`melhorias_*.json`) | **Valores dos parâmetros** (sobretudo os de hipótese) e viabilidade: dependem da unidade dona do processo |
| 13 | Controles, indicadores e metas | Agente | Portão (`validar_controles.py`) | 0 problema; toda melhoria de fase 3 com controle de qualidade | Viabilidade de cálculo contínuo com os dados reais do SEI; aceite das metas pelo órgão |
| 14 | Sugestão por palavra-chave da classificação | Código (não é IA) | — | — | É insumo do agente, não decisão |
| 15 | Matriz de priorização da automação | Código (não é IA), sobre saídas de IA | Testes das regras (régua, volume, fração, custo, payback) e das saídas (piloto único e nos portões; números iguais às fontes) | Testes passam; saídas determinísticas, exceto os metadados da planilha | **Herda** o que não foi verificado nas fontes: o potencial de IA alto/médio/baixo da avaliação (item 8) não teve verificação independente, e as fichas (item 4) não têm horas calibradas. As premissas de custo e de fração automatizável são hipótese |

## O que nenhuma verificação cobre

- **Horas e custo.** São estimativa até o estudo de tempo com as unidades. Nenhuma auditoria por leitura valida horas.
- **Trabalho fora do SEI.** O que não deixa peça não aparece.
- **Peças restritas.** Sem texto, sem ficha; afirmação sobre elas se apoia em peças que as relatam.
- **Quem preparou a peça.** A unidade autora é certa; a pessoa, não.

## Protocolo de verificação para qualquer etapa nova

Siga estes passos sempre que acrescentar uma etapa em que um LLM ou agente produz ou julga algo.

1. **Classifique a etapa.** Ela gera texto, rótulo, número, citação ou proposta? Número calculável → faça por código,
   não por agente. Citação → precisa de trecho literal e de fonte conferível.
2. **Escreva a especificação antes** (`ESPECIFICACAO_<etapa>.md`): entradas permitidas, formato JSON com esquema, listas
   fechadas, regras, o que é proibido (número de memória, rótulo fora da lista) e como será validada.
3. **Ancore.** Todo item extraído traz evidência literal ou id de fato; escreva o código que confere a evidência e
   descarta o que não ancora.
4. **Escreva o portão** (script que sai com código 1 se houver problema) e ponha-o em `pipeline.py` depois da etapa.
   O portão confere existência (ids, fatos, requisitos, casos), coerência (ordem, monotonia, soma) e regras de proteção
   (rito legal, terceiros).
5. **Fixe o critério de aceite antes de medir**: alucinação ≤ 2% e nenhuma em número que sustente conclusão; imprecisão
   ≤ 10%; concordância ≥ 85% (kappa ≥ 0,8) para rótulos.
6. **Audite às cegas** uma amostra com outro agente: mesmo insumo, sem a resposta, semente fixa, amostra estratificada
   (por tipo, por unidade). Fora dos casos usados para escrever a especificação.
7. **Meça e registre** em `saida/` (concordância, divergências, exemplos). Não descarte as divergências: leia-as.
8. **Se falhou:** corrija na origem (especificação, prompt, regra ou dado), crie um teste sintético que reproduz a falha
   em `tests/test_regras.py`, registre a linha em [MITIGACOES.md](../MITIGACOES.md), dê nova versão ao prompt (o cache
   antigo deixa de valer) e reaudite.
9. **Registre o modelo e a versão do prompt** em cada saída; se trocar de modelo, rode a comparação na mesma amostra.
10. **Declare o residual** no entregável: o que não se verifica por código nem por amostra (horas, interpretação jurídica,
    trabalho fora do SEI).
11. **Leve à validação humana** o que o registro não decide (critério de decisão, interpretação de norma, parâmetro de
    ganho, meta).
