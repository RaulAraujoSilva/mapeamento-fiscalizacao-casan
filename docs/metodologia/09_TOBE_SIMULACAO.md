# 09 — TO-BE e simulação

## Objetivo

Propor melhorias em **três fases cumulativas** e calcular o resultado **reaplicando cada caso real da coorte** com as
mudanças, em três cenários, contra uma linha de base congelada. O resultado não é uma estimativa de planilha: é a
mesma linha do tempo do AS-IS, refeita com cada efeito, e medida pela mesma regra.

| Fase | Conteúdo | Exemplos no caso |
|---|---|---|
| 1. Ajuste do fluxo | Organização e regras de trabalho, sem tecnologia nova (eliminar, combinar, reordenar, simplificar; paralelizar; prazo-padrão; dono do processo; pauta contínua) | Dono e marco de início para a etapa depois da publicação; diligência em rodada única |
| 2. Automação de regras e dados | Sem IA: painel de prazos e alertas sobre os andamentos, cálculo por regra, documento por modelo, testes de conformidade contínuos | Motor de cálculo da fórmula paramétrica; ofício-modelo com campos preenchidos |
| 3. Automação com IA | Extração de dados de peças, triagem e pré-análise, avaliação assistida, minuta com citação verificada — **sempre com revisão humana** | Extração do pleito e minuta do parecer técnico, com cada número ligado à página de origem |

A camada de controles, indicadores e metas acompanha as três ([10](10_CONTROLES_METAS.md)).

## Entradas

| Arquivo | O que traz |
|---|---|
| `saida/fase3/linha_base_<cod>.json` | Linha de base congelada (com carimbo) |
| `saida/fase2/casos_<cod>.json` | Linha do tempo de cada caso nativo (ocorrências com espera, execução, espera por unidade, espera de terceiros, horas) |
| `saida/bpmn/fatos_<cod>.json` | Números citáveis |
| `saida/fase3/normas_<cod>.json`, `conformidade_<cod>.json` | Requisitos legais e quanto a coorte cumpre |
| `saida/fase3/benchmark/*.json` | Casos de referência |
| `saida/fase3/insumo_tobe_<cod>.md` | Resumo para o agente: onde está o tempo por atividade e unidade, fatos citáveis, esperas protegidas, conformidade, oportunidades da avaliação, benchmarking da família |
| [`saida/fase3/ESPECIFICACAO_TOBE.md`](../../saida/fase3/ESPECIFICACAO_TOBE.md) | Formato e regras |

## Passos

1. `cd scripts && python volume_anual.py && python linha_base.py` → linha de base com carimbo
   ([DADOS_LEVANTADOS.md](DADOS_LEVANTADOS.md)).
2. `python insumo_tobe.py` → `saida/fase3/insumo_tobe_<cod>.md`.
3. **Melhorias por agente**, fase 1 primeiro → `saida/fase3/melhorias_<cod>.json`.
4. `python validar_tobe.py <cod>` — **portão**, até 0 problema.
5. `python simular_tobe.py <cod>` → `saida/fase3/resultado_tobe_<cod>.json`.
6. Ler o resultado e a sensibilidade; ajustar e repetir 3–5 se preciso.
7. Fases 2 e 3: **acrescentar** ao mesmo arquivo, sem alterar as melhorias de fase 1; repetir 4–6.
8. **Parada humana:** as melhorias de maior peso na sensibilidade e todas as marcadas como hipótese vão à unidade dona
   do processo antes de virar meta.

## Regras de decisão

### Cada melhoria cita três coisas

| Campo | Regra |
|---|---|
| `fatos` | Pelo menos um fato existente: é a evidência AS-IS do problema |
| `requisitos` | Requisitos legais que limitam a mudança (pode ficar vazio se nenhum se aplica) |
| `benchmark` | Casos de referência; **se vazio, `hipotese: true` é obrigatório** e `justificativa_parametro` diz de onde vem o valor |

`justificativa_parametro` explica cada valor dos três cenários. `controle_humano` é obrigatório na fase 3 (quem revisa,
o que confere, amostragem).

### Tipos de efeito (o que o simulador sabe aplicar)

| Tipo | Efeito em cada ocorrência das atividades citadas |
|---|---|
| `teto_espera` (`parte`: `toda` ou `sem_unidade`) | Espera antes limitada ao teto (ou só a parte em que o processo ficou sem unidade) |
| `reduz_espera_pct` | Espera antes × (1 − %) |
| `reduz_execucao_pct` | Execução × (1 − %) |
| `reduz_horas_pct` | Horas piso e teto × (1 − %) |
| `elimina_laco_pct` | Nas ocorrências repetidas (2ª em diante), espera, execução e horas × (1 − %) |
| `paralelo` (`a`, `b`) | Ocorrência de `b` logo depois de `a`: espera antes de `b` vai a zero |
| `reduz_cauda_pct` | Tempo depois da última atividade × (1 − %) |

Lead time simulado = cauda + Σ (espera antes + execução) das ocorrências. Atividade criada no TO-BE (um controle
automático, por exemplo) não entra na simulação.

### Proteções embutidas (todas vieram de risco real)

| Proteção | Onde | Por quê |
|---|---|---|
| **Prazo legal mínimo protegido:** sem `teto_espera` abaixo de `prazo_min`, sem `reduz_espera_pct` nem `paralelo` na espera protegida | `validar_tobe.py` | Prazo de defesa ou de razões finais não é desperdício |
| **Tempo de terceiro intocável:** a parte da espera que é resposta de terceiro (`espera_antes_terceiros_du`) não é cortada por teto nem por redução | `simular_tobe.aplicar` | O órgão não controla o tempo de resposta da concessionária ou do poder concedente (`test_tobe_teto_e_reducao_nao_cortam_resposta_de_terceiro`) |
| **Cauda só em caso encerrado** | `simular_tobe.aplicar` | No caso aberto, a cauda vai até a data de corte, não até o encerramento (`test_tobe_cauda_so_reduz_em_caso_encerrado`) |
| **Fase 0 reproduz o AS-IS** | `simular_tobe` | Sem isso, o ganho é contra outra base (`test_tobe_fase_zero_reproduz_o_lead_da_linha_do_tempo`, `test_linha_base_bate_com_os_casos_da_coorte`) |
| **Cenários monotônicos:** conservador ≤ esperado ≤ otimista em ganho | `validar_tobe.py` | Cenário fora de ordem é erro de digitação ou de raciocínio |
| **Fases cumulativas:** fase f aplica as melhorias de fase ≤ f | `simular_tobe.simular` | `test_tobe_laco_so_reduz_ocorrencia_repetida_e_fases_sao_cumulativas` |
| **Linha de base congelada** com carimbo (sha-256 das entradas) e conferida no resultado | `linha_base.py`, `test_resultado_tobe_atual_e_coerente` | Linha de base que muda por baixo da simulação invalida o ganho |

### Conformidade simulada

O simulador refaz a linha do tempo de cada caso em datas de calendário e roda **os mesmos testes** de prazo máximo e
duração do capítulo [07](07_CONFORMIDADE_LEGAL.md). Na fase 0 ele reproduz a conformidade medida
(`test_tobe_conformidade_simulada_reproduz_a_medida_na_fase_zero`). É a conformidade simulada, não a exigência legal,
que vira meta de prazo ([10](10_CONTROLES_METAS.md)). `prazo_min` fica fora da simulação: o validador já impede o corte
da espera que ele protege.

### Fases 2 e 3: horas líquidas e contagem dupla

- **Ganho em horas é líquido da revisão humana.** Se a minuta economiza a redação mas toda minuta é revista, o
  percentual desconta a revisão; a conta vai em `justificativa_parametro`. No caso, por exemplo: parcela de leitura,
  transcrição e redação × ganho bruto do benchmark − tempo de revisão, por cenário (`saida/fase3/melhorias_P01.json`).
- **Resultado de benchmark de outro setor é teto, não meta**: o esperado fica abaixo e a transferência é explicada.
- **Contagem dupla:** as fases se compõem. Um alerta de fase 2 sobre uma espera que a fase 1 já limitou não soma nada,
  a menos que baixe o teto, e então se justifica pela nova capacidade.

### Sensibilidade

`resultado_tobe_<cod>.json` traz, para a última fase no cenário esperado, quanto pioram o lead mediano, o lead médio e
as horas médias se cada melhoria for retirada. **As de maior peso são as que mais precisam de validação**; se o ganho
depende de uma ou duas melhorias, diga isso no entregável.

### Hipótese explícita

Toda melhoria sem caso de referência é `hipotese: true`, e o entregável a apresenta como hipótese. Horas e custo são
hipótese até a calibração, mesmo quando a melhoria tem benchmark.

## Saídas e formato

`saida/fase3/melhorias_<cod>.json` (lista de melhorias com id, fase, título, descrição, atividades, efeito com valores
por cenário, fatos, requisitos, benchmark, hipótese, justificativa, riscos, dependências, controle humano) e
`saida/fase3/resultado_tobe_<cod>.json`: `linha_base` (lead e horas com média, mediana, q1, q3; totais anuais em horas,
FTE e R$; conformidade temporal) e, por fase e cenário, as mesmas medidas mais `ganho_lead_mediano_pct` e
`ganho_horas_media_pct`; `sensibilidade`. Os números entram nos textos só como fatos citados, com o mesmo princípio de
ancoragem das avaliações.

Previstos no plano e **não produzidos** no caso: modelos e BPMN TO-BE por fase (`modelo_tobe<f>_<cod>.json`, no
formato do AS-IS) e o relatório consolidado do TO-BE. Se for produzi-los, use o mesmo gerador e os mesmos portões.

## Portão de qualidade

- `validar_tobe.py` (portão): fato, requisito, benchmark e atividade existem; sem benchmark → hipótese; prazo mínimo
  protegido; cenários monotônicos; fase 3 com controle humano.
- Testes `test_tobe_*` em `tests/test_regras.py` e `test_resultado_tobe_atual_e_coerente`, `test_linha_base_bate_com_os_casos_da_coorte`
  em `tests/test_saidas.py`.
- Leitura crítica (humana): ganho de lead acima de 60% no esperado, ou concentrado numa só melhoria, pede revisão do
  parâmetro e conversa com a unidade.

## Armadilhas conhecidas

- **Esperar que a IA reduza o lead time.** No caso, a fase 3 não mudou o lead mediano da fiscalização nem da ocorrência
  de usuário (igual ao da fase 2); ela reduz horas. O lead cai com as fases 1 e 2, porque o tempo é espera.
- Teto de espera que corta prazo de defesa ou resposta de terceiro (o validador e o simulador barram; não contorne
  mudando o tipo de efeito).
- Ganho de horas bruto, sem descontar revisão.
- Linha de base recalculada à mão ou de outra versão dos dados.
- Ganho em R$ apresentado como certo: custo-hora e fator de custo total são hipótese.

## O que muda em outro Estado

Nada no motor. Mudam os requisitos que protegem prazos (lei de processo administrativo do Estado), o volume anual e o
custo-hora (linha de base) e o que já existe de ferramenta no órgão (no caso, uma ferramenta de minuta de relatório a
partir dos autos e uma base de normas e deliberações já existiam e foram consideradas insumo da fase 3).

## Números do caso AGENERSA (ordem de grandeza)

Lead time mediano por caso nativo, em dias úteis, e ganho sobre a linha de base, cenário esperado
(`saida/fase3/resultado_tobe_P01.json`, `_P06.json`, `_P21.json`):

| Processo | Casos | Linha de base | Fase 1 | Fase 2 | Fase 3 | Ganho de horas na fase 3 |
|---|---|---|---|---|---|---|
| Reajuste tarifário | 18 | 337,5 | 155,8 (53,8%) | 149,3 (55,8%) | 145,5 (56,9%) | 24,9% |
| Fiscalização de campo | 12 | 351 | 152,5 (56,6%) | 115,5 (67,1%) | 115,5 (67,1%) | 27,5% |
| Ocorrência de usuário | 11 | 469 | 300,1 (36,0%) | 245,2 (47,7%) | 245,2 (47,7%) | 23,0% |

| Processo | Melhorias (fase 1 / 2 / 3) | Marcadas como hipótese | Origem |
|---|---|---|---|
| Reajuste tarifário | 18 (8 / 6 / 4) | 10 | `saida/fase3/melhorias_P01.json` |
| Fiscalização de campo | 16 (5 / 6 / 5) | 9 | `melhorias_P06.json` |
| Ocorrência de usuário | 18 (8 / 6 / 4) | 12 | `melhorias_P21.json` |

Sensibilidade: no reajuste, retirar a melhoria de maior peso piora o lead mediano em 37,8 du; na ocorrência de usuário,
as duas de maior peso pioram 48,6 du cada (`sensibilidade` nos mesmos arquivos). Com 11 a 18 casos, medianas são
instáveis: trate os percentuais como ordem de grandeza.
