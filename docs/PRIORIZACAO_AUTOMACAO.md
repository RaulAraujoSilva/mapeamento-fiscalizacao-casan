# Priorização da automação: matriz de critérios e custo × retorno

Gerado por `scripts/priorizacao_automacao.py`. Os números vêm das saídas verificadas do mapeamento; as premissas de custo e de fração automatizável são **hipótese até a medição no piloto** e estão na aba “Premissas” da planilha `saida/fase4/Priorizacao_Automacao.xlsx`. Horas de trabalho são hipótese até a calibração com os servidores.

## 1. O que o mapeamento ensinou para a automação

- **O volume por tipo de processo é baixo.** Estimado a partir das deliberações de toda a agência, 0 de 0 tipos com volume medido chegam a 25 processos por ano (nenhum); P06 ficam sem volume medido. Automação do processo inteiro só se paga onde há repetição; nos demais tipos, o retorno vem de capacidades compartilhadas (seção 4).
- **A espera pesa tanto quanto o trabalho.** A soma das esperas entre atividades vai de 87% a 87% do lead time mediano dos casos nativos, conforme o tipo. Automatizar a redação e a análise reduz horas; o prazo só cai se o sistema também vigiar posse, prazos e pendências.
- **Nenhum fluxo é padronizado.** O caminho mais frequente cobre de 100% a 100% dos casos da coorte. O sistema deve automatizar por atividade, disparado pelo gatilho de cada tarefa do modelo, e não impor uma sequência fixa.
- **A IA julga melhor quando a regra está escrita.** As etapas que passaram nos portões tinham especificação prévia, saída em formato fixo e conferência automática ou às cegas; o mesmo vale para o sistema: cada atividade automatizada precisa de uma regra computável e de um conjunto de casos de referência.
- **Tempo de terceiros e prazo legal não são ganho.** A espera pela regulada e o prazo mínimo da norma ficam fora do retorno; o sistema pode cobrar prazos vencidos, não encurtar o que a lei concede.
- **A análise mistura texto e dado.** Nas peças de análise, a fração com dado não estruturado vai de 38% a 38% e a com dado estruturado, de 18% a 18%, conforme o tipo. O sistema precisa extrair do texto e conferir contra a regra e o cálculo.

## 2. Critérios e régua

| Critério | Peso | O que mede | Cortes para as notas 2, 3, 4 e 5 |
|---|---|---|---|
| Volume | 25% | Processos por ano na agência: piso de deliberações ÷ (fração com deliberação × revocação da regra) | 5 · 10 · 25 · 50 |
| Foco em análise | 15% | Fração das horas do tipo em peças de análise (jurídica, técnica, econômica, conferência, relatoria) | 0,20 · 0,35 · 0,50 · 0,65 |
| Dados estruturados e não estruturados | 15% | Peças de análise com dado estruturado (cálculo, base, sistema) e com não estruturado (documento da regulada, precedente, documentos examinados): média das duas frações | 0,30 · 0,45 · 0,60 · 0,75 |
| Regras claras | 20% | Peças de análise ancoradas em norma ou contrato e com teste contra um padrão: média das duas frações | 0,40 · 0,55 · 0,70 · 0,85 |
| Padronização | 15% | Texto padronizado ou transcrito (ponderado por horas) e fração dos casos no caminho mais frequente | 0,30 · 0,40 · 0,50 · 0,60 |
| Completude da automação | 10% | Fração das horas dos casos em atividades com potencial de IA alto na avaliação AS-IS | 0,20 · 0,35 · 0,50 · 0,65 |

Nota composta = Σ peso × nota ÷ 5 (0 a 100). Portões do piloto de automação completa: volume medido com revocação ≥ 75%, nota de volume ≥ 3, nota de regras ≥ 3 e ao menos 8 casos na coorte.

## 3. Matriz

![Matriz custo × retorno](../saida/fase4/matriz_automacao.png)

| Código | Processo | Prioridade | Nota | V | A | D | R | P | C | Volume/ano | Retorno/ano (R$) | Construção (R$) | Payback isolado (anos) | Payback com plataforma (anos) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P06 | Fiscalização técnica de campo (programada e por demanda) | reavaliar com dados | — | — | 5 | 1 | 4 | 5 | 5 | — | — | 131.540 | — | — |

V volume · A foco em análise · D dados estruturados e não estruturados · R regras claras · P padronização · C completude da automação. Valores monetários no cenário esperado; os três cenários estão em `saida/fase4/matriz_automacao.json`. Payback com plataforma = só a configuração das atividades, com a plataforma e as capacidades de IA já construídas para outro tipo. Payback vazio = o retorno anual não cobre o custo anual.

## 4. Capacidades transversais

Uma capacidade de IA construída uma vez serve a vários tipos de processo. A tabela soma, por capacidade, as atividades de potencial alto ou médio que a usam e as horas por ano que elas alcançam (só tipos com volume medido).

| Capacidade | Tipos | Atividades | Horas/ano alcançadas | Horas de construção |
|---|---|---|---|---|
| automação de tramitação (RPA no SEI) | 1 | 4 | 0,0 | 40 |
| busca de precedentes e normas | 1 | 3 | 0,0 | 60 |
| cálculo e conferência automática | 1 | 1 | 0,0 | 80 |
| extração de dados de documentos | 1 | 2 | 0,0 | 80 |
| monitoramento de prazos e alertas | 1 | 3 | 0,0 | 24 |
| redação assistida de minuta | 1 | 4 | 0,0 | 80 |
| sumarização e linha do tempo | 1 | 2 | 0,0 | 40 |
| verificação de conformidade | 1 | 1 | 0,0 | 100 |

## 5. Recomendação

O retorno em horas é só parte do valor: prazo, conformidade e rastreabilidade não estão monetizados. O piloto deve medir, antes e depois, a fração automatizável real por atividade e o custo efetivo de construção, e com isso substituir as premissas desta matriz.

## 7. Limites

- O volume é estimado a partir de deliberações; tipos que raramente chegam à deliberação ficam sem medida.
- A fração automatizável por potencial de IA, as horas de construção e o custo-hora de desenvolvimento são hipóteses; o retorno escala linearmente com elas.
- As horas por caso vêm das fichas por peça (estimativa, piso e teto) e são hipótese até a calibração.
- Coortes pequenas dão medianas instáveis: a coluna de casos na coorte diz quanto confiar.
