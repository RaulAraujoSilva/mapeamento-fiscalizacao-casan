# 05 — Modelagem BPMN, vínculos e classificador de atividade

## Objetivo

Para cada processo organizacional, chegar a um **modelo canônico** (o fluxo que um servidor reconhece: raias,
tarefas, decisões, laços) e ligar cada peça real a uma atividade desse modelo. A ligação é o que transforma
documentos soltos em **ocorrências comparáveis entre casos**, das quais saem tempos, horas e caminhos.

Divisão de trabalho, que não se negocia: **o agente escreve nomes, fluxo e decisões; o código calcula
frequência, dias, horas e situação**.

## Entradas

- Trilhas, fichas de trabalho e fichas por peça ([02](02_TRILHA_TEMPO_POSSE.md), [03](03_CONTEUDO_ESFORCO.md));
- piloto (`saida/piloto.csv`) e coorte (`saida/coorte_fase2.csv`) ([04](04_CLASSIFICACAO_COORTE.md));
- especificações: [`saida/bpmn/ESPECIFICACAO_MODELO.md`](../../saida/bpmn/ESPECIFICACAO_MODELO.md) e
  [`saida/bpmn/ESPECIFICACAO_VINCULOS.md`](../../saida/bpmn/ESPECIFICACAO_VINCULOS.md).

## Passos

### Piloto (tipos com caso típico e crítico)

1. `cd scripts && python evidencias_bpmn.py` → `saida/bpmn/evidencias_<cod>.md`: participação das unidades e
   transições em todos os processos do código, mais as tarefas em ordem dos casos típico e crítico, com dias,
   faixa de horas, sinais de perda e espera dominante.
2. **Modelo canônico por agente** → `saida/bpmn/modelo_<cod>.json`, no formato da especificação.
3. `python gerar_bpmn.py` → `saida/bpmn/<cod>.bpmn` e visualizador `docs/bpmn/index.html`;
   `python checar_bpmn.py ../saida/bpmn/*.bpmn` mede a legibilidade (rodar depois de mexer no layout).
4. `python insumo_vinculos.py` → `saida/bpmn/docs_<cod>.csv` (peças dos casos-piloto em ordem, com unidade, tipo,
   autoria, tarefa e entregável da ficha).
5. **Vínculos por agente** → `saida/bpmn/vinculos_<cod>.json` (cada tarefa → peças próprias, peças de entrada,
   descritivo, gatilho, saída, observações).
6. `python fatos.py` e `python fichas_atividades.py` → linha do tempo, fatos e ficha de cada atividade.

### Coorte (tipos novos e ampliação)

7. Tipos sem piloto: `python evidencias_novos.py` → `saida/bpmn/evidencias_<cod>.md` a partir da coorte inteira
   (participação, transições, frequência de tipos de peça e de tarefas das fichas, sequência completa de até 4 casos
   de referência). Modelo por agente, **com `gatilho` e `saida` em toda tarefa**.
8. **Classificador de atividade** (LLM): `python classificar_atividades.py` → `saida/fase2/atribuicoes_<cod>.csv`.
   `python classificar_atividades.py --avaliar` mede contra os vínculos do piloto.
9. **Auditoria às cegas do classificador:** `python auditoria_classificador.py --preparar` → pacotes em
   `dados/auditoria_classificador/`; um agente auditor, **sem ver os rótulos**, grava
   `rotulos_<cod>.json`; `python auditoria_classificador.py --comparar` → `saida/fase2/auditoria_classificador.json`.
10. `python procedimento.py` → `saida/fase2/procedimento_<cod>.json` e `casos_<cod>.json`;
    `python resumo_fase2.py` → `docs/RESULTADOS_FASE2.md`.
11. `python gerar_bpmn.py` de novo: com a coorte, as tarefas mostram % dos casos e medianas da coorte, e os ramos de
    decisão mostram o % das passagens observadas.

## Regras de decisão

### Modelo canônico (resumo da especificação)

1. **Canônico, não transcrição.** Consolidar típico + crítico + trilhas dos demais processos do código num fluxo
   reconhecível. Variação observada vira decisão (`xor`) com laço; o que só aparece em parte dos casos, ramo
   alternativo.
2. **No máximo 25 elementos.** Encaminhamento puro da secretaria não vira tarefa; ela só vira tarefa quando faz algo
   (sortear relator, oficiar, publicar, certificar, encerrar).
3. **Sem invenção.** Toda tarefa, decisão e laço tem de estar nas evidências. Etapa do escopo teórico do catálogo
   que não aparece nos processos não entra.
4. **Raias com a sigla SEI exata** de cada unidade que representam (ex.: "Câmara técnica (CAENE ou CASAN)"): é por
   ela que as peças são ligadas à raia (`fatos.na_raia`). Externos numa raia `EXT`, a última.
5. **Tarefa** = verbo no infinitivo + objeto, até ~7 palavras; `gatilho` e `saida` em até 12 palavras cada.
6. **Nenhum número no modelo.** `freq`, `du`, `horas`, `nota` e `status` são recusados pelo teste
   `test_modelo_sem_numeros_dos_agentes`.
7. Rito legal (razões finais, publicação, prazo de defesa) é etapa normal, não perda.

> **Falha real (D1).** Na primeira versão, os agentes escreveram frequência, dias e horas no modelo e erraram.
> Hoje tudo isso é calculado (`gerar_bpmn.metricas_das_fichas`) e a auditoria D achou 0 divergência de frequência
> em 91 tarefas (`saida/auditoria/auditoria_automatica.json`).

### Vínculos (piloto)

- `docs`: só peças **produzidas pelo órgão**, cada uma em no máximo uma atividade. `docs_entrada`: peças externas que
  são insumo direto.
- `descritivo`: 2 a 4 frases sobre o trabalho observado, sem adjetivo de avaliação, sem inventar. **Sem tempo
  medido** no descritivo (falha E1: "du" escrito pelo agente divergia do calculado; o validador barra).
- Toda tarefa tem entrada; sem documento que a sustente, `docs` vazio e explicação em `observacoes`.

### Classificador de atividade

- Só peças **próprias** são rotuladas; as de fora entram como contexto da sequência.
- Candidatas de uma peça = atividades cuja raia é a unidade da peça. **Peça sem candidata fica "fora da raia" sem
  consulta ao LLM.** Rótulo fora das candidatas é descartado e vira `fora_do_modelo` (esquema com enum).
- O LLM vê a sequência inteira do processo (data, unidade, tipo, tarefa e entregável da ficha, ação e pedidos da
  análise por peça) e as atividades com gatilho e saída. Peça de trâmite pertence à atividade que a unidade está
  executando.
- **Gatilho e saída do modelo valem primeiro**; os vínculos do piloto só suprem o modelo que não os tem.

> **Falha real.** O classificador guiado pelos vínculos do piloto aprendeu particularidades de um caso (num tipo,
> "restituir sem parecer") e rotulou mal o resto da coorte. A correção foi priorizar o gatilho e a saída genéricos do
> modelo e refazer a rotulagem às cegas ([MITIGACOES.md](../MITIGACOES.md)).

- A avaliação contra o piloto é **otimista** (as atividades foram descritas a partir dos mesmos casos). O critério
  vale na auditoria **fora do piloto**: por código, até 14 peças substantivas e 6 de expediente, semente fixa; o
  auditor recebe o mesmo retrato do processo com só as peças da amostra marcadas e pode ler o texto integral.
  **Concordância ≥ 85% nas peças substantivas.**
- Mudou o modelo de um tipo que já tinha auditoria? Reclassifique, rode `--preparar <cod>` e faça nova rotulagem às
  cegas; os rótulos antigos vão para `dados/auditoria_classificador/v1/`.

### Procedimento (agregação da coorte)

- **Caminho** = atividades na ordem da 1ª ocorrência, sem repetição (quase todo caso tem laços próprios; a variante
  completa raramente se repete).
- **Conformidade ao modelo**: atividades ausentes por caso e % das peças **substantivas** fora do modelo; expediente
  fora do modelo é contado à parte (não infla a não conformidade).
- **Transições** entre atividades com probabilidade; % de ramo de decisão só de transições observadas, com no mínimo
  3, e sem % quando os ramos levam à mesma atividade.
- Espera antes da 1ª ocorrência só em processo com trilha; espera entre ocorrências vale para todos.
- Empates nas listas de frequência desfeitos pelo nome (duas rodadas, mesmo hash).

## Saídas e formato

| Arquivo | Conteúdo |
|---|---|
| `saida/bpmn/modelo_<cod>.json` | Raias, elementos (início, fim, tarefa com gatilho e saída, xor, junção, paralelo, eventos), fluxos com `principal` |
| `saida/bpmn/<cod>.bpmn` | BPMN 2.0 com BPMNDI; abre no Camunda Modeler, bpmn.io e Bizagi |
| `saida/bpmn/vinculos_<cod>.json` | Tarefa → peças próprias e de entrada, descritivo, gatilho, saída, observações |
| `saida/bpmn/fichas_<cod>.json` | Ficha por atividade: executor, tempos, entradas, ferramentas, competências, base normativa, perdas, lacunas |
| `saida/fase2/atribuicoes_<cod>.csv` | Peça → atividade (ou `fora_do_modelo` / fora da raia), confiança, motivo |
| `saida/fase2/auditoria_classificador.json` | Concordância por código e divergências |
| `saida/fase2/procedimento_<cod>.json` | Casos, situação, caminhos, transições, distribuições por atividade, posse por unidade, fichas por modelo |

## Portão de qualidade

- `checar_bpmn.py`: setas atravessando elemento = 0 e rótulos sobrepostos = 0 (`test_bpmn_sem_seta_atravessando_elemento`,
  `test_bpmn_rotulo_de_fluxo_nao_cobre_forma_nem_rotulo`).
- `test_modelo_sem_numeros_dos_agentes`, `test_modelo_fase2_completo`, `test_atribuicao_so_com_rotulo_valido_e_na_raia`,
  `test_procedimento_consistente` (q1 ≤ mediana ≤ q3 ≤ máx; casos + ausentes = total; % das transições bate com as
  contagens), `test_auditoria_do_classificador_atinge_criterio`, `test_bpmn_da_coorte_mostra_percentuais_que_batem_com_o_procedimento`,
  `test_probabilidade_dos_ramos_pela_transicao_observada`.
- Auditoria por leitura (amostra): afirmações do modelo e dos descritivos conferidas contra as peças; critério
  alucinação ≤ 2%, imprecisão ≤ 10%.
- **Parada humana:** as "perguntas a validar" de cada modelo ([BPMN_PILOTO.md](../BPMN_PILOTO.md), seção final)
  vão às unidades antes da avaliação. Decisão inferida (sem critério escrito nas peças) tem de ser marcada como tal.

## Armadilhas conhecidas

- Modelar o processo "como deveria ser" (escopo teórico do catálogo) em vez do observado.
- Raia sem a sigla exata: as peças da unidade não são ligadas e a atividade fica sem tempo nem horas.
- Tipo com um só caso elegível: o fluxo é uma trilha, não um padrão — diga isso.
- Dois casos de natureza diferente no mesmo código (no caso, plano de contingência de gás e rompimento de adutora):
  confirme se é um processo ou duas variantes.
- Medir a qualidade do classificador só contra o piloto (98% no caso, otimista).
- Ordem das raias e roteamento manuais: deixe o gerador escolher a ordem de menor custo visual medido.

## O que muda em outro Estado

As especificações e os scripts valem como estão. Mudam: as siglas das raias, os nomes das atividades, e o prompt do
classificador (nome do órgão). Se o órgão não tem colegiado (decisão monocrática), o trecho "sortear relator → razões
finais → sessão" do caso não existe: não o copie dos modelos de referência.

## Números do caso AGENERSA (ordem de grandeza)

| Item | Valor | Origem |
|---|---|---|
| Modelos auditados (piloto) | 81 tarefas, 356 afirmações | [AUDITORIA.md](../AUDITORIA.md) |
| Descritivos: sem lastro ou contradito / imprecisos | 0,6% / 5% (corrigidos) | idem |
| BPMN antes × depois do roteamento (8 diagramas) | setas atravessando elementos 6 → 0; trechos sobrepostos 5 → 2; cruzamentos 26 → 27 | [BPMN_PILOTO.md](../BPMN_PILOTO.md) |
| Classificador contra os vínculos do piloto | 98% em 290 peças (otimista) | [RESULTADOS_FASE2.md](../RESULTADOS_FASE2.md) |
| Auditoria às cegas fora do piloto | 216 peças de 11 códigos; 88% no total, 92% nas 150 substantivas; um código (sanção) com 64% | `saida/fase2/auditoria_classificador.json` |
| Caminhos distintos | 17 em 18 casos no reajuste tarifário; 9 em 12 na fiscalização | [RESULTADOS_FASE2.md](../RESULTADOS_FASE2.md) |
