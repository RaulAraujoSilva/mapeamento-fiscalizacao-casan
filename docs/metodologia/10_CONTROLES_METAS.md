# 10 — Controles, indicadores e metas

## Objetivo

Garantir e medir o ganho do TO-BE depois da implantação: indicadores com fórmula exata, linha de base que é um fato do
AS-IS, metas com origem conferível, alertas automáticos, controles de qualidade para toda saída de IA e os testes do
programa de auditoria que passam a rodar continuamente.

## Entradas

- `saida/fase3/resultado_tobe_<cod>.json` (metas simuladas), `melhorias_<cod>.json`;
- `saida/bpmn/fatos_<cod>.json` (linhas de base);
- `saida/fase3/normas_<cod>.json` (requisitos e programa de auditoria), `conformidade_<cod>.json`;
- `saida/fase3/benchmark/*.json`;
- formato em [`saida/fase3/ESPECIFICACAO_TOBE.md`](../../saida/fase3/ESPECIFICACAO_TOBE.md), seção "Controles".

## Passos

1. **Controles por agente** → `saida/fase3/controles_<cod>.json`.
2. `cd scripts && python validar_controles.py <cod>` — **portão**, até 0 problema.
3. **Parada humana:** a unidade dona do processo e a área de planejamento aceitam (ou ajustam) as metas e os
   destinatários dos alertas; o controle interno aceita os testes de auditoria contínua.

## Regras de decisão

### Indicador

| Campo | Regra |
|---|---|
| `definicao` | Fórmula exata: de que evento a que evento, unidade, estatística, janela (ex.: mediana dos processos dos últimos 12 meses, com q1 e q3) |
| `calculo.tipo` | `lead`, `espera_antes`, `posse_sem_unidade`, `laco`, `horas`, `conformidade`, `estoque_idade` — com as atividades e, se for o caso, o requisito |
| `fonte_dados` | Andamentos do SEI, peças do SEI ou outro sistema nomeado |
| `linha_base` | `fato` existente em `fatos_<cod>.json` e `valor` igual ao valor dele (arredondado). **Nunca digitada** |
| `metas[]` | Uma por fase, cada uma com `origem` |
| `alerta` | Regra de disparo e destinatário (unidade ou função) |

### Origem da meta (nada de meta sem origem)

| `origem.tipo` | `ref` | Conferência |
|---|---|---|
| `simulacao` | Caminho em `resultado_tobe_<cod>.json` (ex.: `fases.1.esperado.lead.mediana`) | `valor` = valor desse caminho |
| `norma` | Id de requisito em `normas_<cod>.json` | requisito existe |
| `benchmark` | Id de caso | caso existe |

### Indicador de conformidade

- Linha de base = `pct_conforme` de `conformidade_<cod>.json`.
- Requisito de prazo máximo ou de duração: a meta de cada fase é a **conformidade simulada**
  (`fases.<f>.esperado.conformidade_temporal.<R>`), e a exigência legal (100%) vai em `referencia_legal`.
- Se o TO-BE não chega à exigência, `observacao` diz o que falta (capacidade, rito, norma). Meta legal de 100% que a
  simulação não alcança é promessa sem lastro.

### Qualidade ao lado de prazo

Inclua indicadores de qualidade junto dos de prazo: recursos e embargos providos, retrabalho, devoluções. O benchmarking
mostrou que prazo sozinho empurra decisões para a véspera, com mais problemas de qualidade
([08](08_BENCHMARKING.md)).

### Controles de qualidade da IA

Toda melhoria de fase 3 tem pelo menos um controle em `controles_qualidade_ia`:

| Campo | Exemplo do caso (minuta de parecer técnico) |
|---|---|
| `verificacao` | Cada número extraído conferido contra a página de origem; cada citação de norma ou deliberação passa pela verificação automática contra a base; conclusão revista pelo coordenador |
| `amostragem` | 100% dos campos extraídos e das citações; amostra trimestral refeita às cegas por um segundo analista |
| `criterio_aceite` | Peça assinada sem número divergente da origem e sem citação que não confira |
| `indicador` | Taxa de erro de extração (campos corrigidos ÷ extraídos) e taxa de citação inválida |
| `meta`, `responsavel` | Meta explícita e unidade responsável |

### Auditoria contínua

`auditoria_continua` lista os testes do `programa_auditoria` ([07](07_CONFORMIDADE_LEGAL.md)) que passam a rodar
automaticamente sobre o SEI.

## Saídas e formato

`saida/fase3/controles_<cod>.json` com `indicadores[]`, `controles_qualidade_ia[]` e `auditoria_continua[]`.

## Portão de qualidade

`validar_controles.py` (portão no pipeline) confere: linha de base igual ao fato citado; meta com origem conferível
(caminho da simulação com o mesmo valor, requisito ou caso existente); melhorias e testes de auditoria citados
existem; controle de qualidade para toda melhoria de fase 3. Falha = corrigir `controles_<cod>.json`, nunca o validador.

## Armadilhas conhecidas

- Meta "redonda" (ex.: 30 dias) sem origem: o validador recusa; se a norma diz 30, a origem é a norma e a meta da fase
  vem da simulação.
- Indicador sem fórmula operacional ("tempo do processo"): ninguém vai conseguir calcular igual duas vezes.
- Alerta sem destinatário.
- Controle de IA que confere só amostra quando o erro é caro (número de tarifa, citação de norma): confira 100%.
- Esquecer que o indicador precisa de dado contínuo: se ele depende de peça que o SEI não registra, diga a fonte.

## O que muda em outro Estado

Destinatários dos alertas (organograma), frequência (rito do colegiado, calendário de reajuste) e fontes de dados
disponíveis (relatórios do SEI, API, sistemas da ouvidoria). As regras de origem e o validador valem igual.

## Números do caso AGENERSA (ordem de grandeza)

| Processo | Indicadores | Controles de qualidade de IA | Testes em auditoria contínua | Origem |
|---|---|---|---|---|
| Reajuste tarifário | 10 | 4 | 7 | `saida/fase3/controles_P01.json` |
| Fiscalização de campo | 9 | 5 | 6 | `controles_P06.json` |
| Ocorrência de usuário | 10 | 4 | 7 | `controles_P21.json` |

Exemplo de leitura: o lead time do reajuste tem linha de base de 337,5 du (fato `coorte.caso.lead.mediana`) e metas de
155,8, 149,3 e 145,5 du nas fases 1, 2 e 3, todas com origem na simulação; a conferência das faturas iniciada em até 90
dias da publicação tem linha de base de 50% (6 de 12 casos) e meta simulada de 100% na fase 1, com observação de que no
cenário conservador ela fica em 83,3% (`saida/fase3/controles_P01.json`).
