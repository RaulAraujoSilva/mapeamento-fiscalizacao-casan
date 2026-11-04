# 11. Priorização da automação: do mapeamento ao sistema

Este capítulo fecha o método. Depois de mapear, avaliar e redesenhar os processos, a pergunta passa a ser:
**qual tipo de processo serve de piloto para um sistema que o automatize por inteiro, e quanto isso custa e
retorna?** A resposta é uma matriz de priorização com critérios medidos nas saídas das fases anteriores e um modelo
de custo × retorno em três cenários. Nada nela é opinião digitada: o script
[`scripts/priorizacao_automacao.py`](../../scripts/priorizacao_automacao.py) calcula tudo a partir dos arquivos que
já passaram pelos portões.

Resultado do caso de referência: [`docs/PRIORIZACAO_AUTOMACAO.md`](../PRIORIZACAO_AUTOMACAO.md), com a planilha
`saida/fase4/Priorizacao_Automacao.xlsx` e o gráfico `saida/fase4/matriz_automacao.png`.

## 1. O que se procura

Um bom piloto de automação completa por IA tem quatro propriedades. Cada uma vira um critério medido:

| Propriedade | Por que importa | Critério |
|---|---|---|
| **Alto volume** | Construir regras, modelos de documento e conjunto de teste só se paga com repetição | Volume |
| **Análise de dados estruturados e não estruturados** | É onde a IA agrega mais: ler peças, extrair, calcular e conferir. Processo só de trâmite é caso de RPA, não de IA | Foco em análise; Dados estruturados e não estruturados |
| **Regras claras** | Sem regra escrita não há contra o que medir a saída do sistema, nem como auditá-la | Regras claras |
| **Padrões** | Texto padronizado e fluxo estável reduzem exceções e o custo de configuração | Padronização |

Um quinto critério, **completude**, mede quanto do trabalho está em atividades que a avaliação AS-IS classificou com
potencial de IA alto: é a chance de automatizar o processo inteiro, e não só uma peça.

## 2. Pré-requisitos

A matriz só roda para tipos de processo que já têm:

- coorte e procedimento (`saida/fase2/procedimento_<cod>.json` e `casos_<cod>.json`, [capítulo 05](05_MODELAGEM_BPMN.md));
- fichas de trabalho das peças da coorte (`saida/fichas_trabalho.jsonl`, [capítulo 03](03_CONTEUDO_ESFORCO.md));
- avaliação AS-IS com potencial de IA por atividade (`saida/bpmn/avaliacao_<cod>.json`, [capítulo 06](06_AVALIACAO_ASIS.md));
- fatos (`saida/bpmn/fatos_<cod>.json`);
- volume anual (`saida/fase3/volume_anual.json`, [capítulo 09](09_TOBE_SIMULACAO.md)), com **uma regra de volume para
  cada código** em `VOLUME_REGRAS` do perfil, não só para os do TO-BE.

Normas, conformidade, melhorias e controles da fase 3 não entram na nota (nem todo tipo os tem), mas aparecem na
seção de especificação quando o tipo escolhido como piloto os tiver.

## 3. Como cada critério é medido

| Critério | Peso | Cálculo | Fonte |
|---|---|---|---|
| Volume | 25% | Piso de deliberações por ano ÷ (fração da carteira com deliberação × revocação da regra na coorte) | `volume_anual.json`; fato `carteira.com_deliberacao_pct` |
| Foco em análise | 15% | Horas das peças de natureza analítica (jurídica, técnica, econômica, conferência, fiscalização, relatoria) ÷ horas de todas as peças do tipo | Fichas (`natureza_trabalho`, `horas_estimadas`) |
| Dados estruturados e não estruturados | 15% | Média de duas frações das peças de análise: com dado estruturado (cálculo, base externa, sistema interno) e com dado não estruturado (documento da regulada, precedente, documentos examinados) | Fichas (`calculos`, `insumos`, `n_documentos_analisados`) |
| Regras claras | 20% | Média de duas frações das peças de análise: ancoradas em norma ou contrato e com teste contra um padrão | Fichas (`insumos` do tipo `norma_ou_contrato`, `testes_auditoria`) |
| Padronização | 15% | Média entre a fração do texto que é padrão ou transcrição (ponderada por horas) e a fração dos casos no caminho mais frequente | Fichas (`composicao_texto`); procedimento |
| Completude | 10% | Horas dos casos em atividades de potencial de IA alto ÷ horas de todas as atividades | Avaliação AS-IS; `casos_<cod>.json` |

Cada métrica vira nota de 1 a 5 por uma **régua fixada antes de olhar o resultado** (`PRIORIZACAO_CRITERIOS` em
`scripts/comum.py`): nota 1 abaixo do primeiro corte, +1 a cada corte atingido. A nota composta vai de 0 a 100
(Σ peso × nota ÷ 5), como no diagnóstico organizacional. **Critério sem medida deixa a nota composta vazia**: o
script não presume nota baixa nem alta.

Por que essas fontes: são as saídas mais verificadas do método. As fichas têm cada item ancorado por trecho literal
no texto da peça; a avaliação passou pelo validador e pelo carimbo; o volume tem a revocação da regra medida na
coorte. A matriz herda essa verificação e também os limites dela (seção 8).

## 4. Portões

Para ser **piloto de automação completa**, o tipo precisa passar em todos (`PORTOES_PILOTO`):

1. volume medido com revocação da regra ≥ 75%;
2. nota de volume ≥ 3;
3. nota de regras ≥ 3;
4. pelo menos 8 casos na coorte (abaixo disso, a mediana é instável).

Classificação: **piloto** = maior nota composta entre os que passam (empate pelo saldo no horizonte);
**candidato a piloto** = passa, mas não é o maior; **próxima onda** = nota ≥ 60 e falha num portão;
**reavaliar com dados** = sem volume medido ou coorte pequena; **não priorizar agora** = o resto.

## 5. Modelo de custo × retorno

Três cenários (conservador, esperado, otimista), como na simulação do TO-BE. Fórmulas:

- **Horas liberadas por ano** = volume × horas por caso × fração automatizável.
  - Horas por caso: mediana dos casos nativos, no piso (conservador), na média de piso e teto (esperado) e no teto
    (otimista).
  - Fração automatizável: média das atividades ponderada pelas horas, com a fração de cada uma dada pelo potencial
    de IA da avaliação (`FRACAO_AUTOMATIZAVEL`; **hipótese**).
- **Retorno anual (R$)** = horas liberadas × custo-hora do servidor × fator de custo total do cenário (os mesmos da
  linha de base, [capítulo 09](09_TOBE_SIMULACAO.md)).
- **Custo de construção isolado** = (plataforma + capacidades de IA usadas pelo tipo + configuração por atividade
  automatizável × (1 + 0,5 × caminhos distintos por caso)) × custo-hora de desenvolvimento + validação por servidor
  (casos de referência × horas por caso × custo-hora do servidor).
- **Custo incremental** = só a configuração das atividades e a validação, supondo plataforma e capacidades já
  construídas para outro tipo.
- **Custo anual** = manutenção (fração do custo de construção) + leitura pelo modelo de linguagem (milhões de
  caracteres por caso × volume × preço).
- **Payback** = custo de construção ÷ (retorno anual − custo anual). Vazio quando o retorno não cobre o custo anual.

As **capacidades de IA** são os dez tipos de IA usados na avaliação AS-IS (redação assistida de minuta,
verificação de conformidade, extração de dados, sumarização e linha do tempo, busca de precedentes e normas,
cálculo e conferência, classificação e triagem, monitoramento de prazos, painel, automação de tramitação). A
tabela de **capacidades transversais** soma, para cada uma, quantos tipos e atividades a usam e quantas horas por
ano elas alcançam. É a leitura de plataforma: a capacidade que alcança mais horas por hora de construção vem
primeiro, qualquer que seja o tipo-piloto.

Todas as premissas de custo (`HORAS_CAPACIDADE`, `HORAS_PLATAFORMA`, `HORAS_CONFIG_ATIVIDADE`, `CUSTO_HORA_DEV`,
`PRECO_LLM_MCHAR`, `MANUTENCAO_ANUAL`) são **hipótese** e ficam em `scripts/comum.py`. O perfil do órgão pode trocar
qualquer uma delas: basta declarar o mesmo nome em `perfis/<orgao>.py`.

O que **não** está no retorno: redução de prazo, ganho de conformidade, rastreabilidade e redução de risco. Diga
isso no entregável. Tempo de terceiros e prazo legal mínimo também não são ganho, pela mesma regra do TO-BE.

## 6. O que o caso de referência ensinou

Lições do caso AGENERSA, com os números em [`docs/PRIORIZACAO_AUTOMACAO.md`](../PRIORIZACAO_AUTOMACAO.md). Use-as
como hipóteses a testar no seu órgão:

1. **O volume por tipo é baixo num órgão regulador.** Poucos tipos passam de algumas dezenas de processos por ano.
   Automação de processo inteiro só se paga onde há repetição; nos demais, o retorno vem das capacidades
   compartilhadas. Por isso o custo incremental importa tanto quanto o isolado.
2. **A espera pesa tanto quanto o trabalho.** Automatizar a redação e a análise reduz horas, mas o prazo só cai se o
   sistema também vigiar posse, prazos vencidos e processos sem unidade com eles abertos.
3. **Nenhum fluxo é padronizado.** O caminho mais frequente cobre uma minoria dos casos. O sistema deve agir por
   atividade, disparado pelo gatilho de cada tarefa do modelo, e não impor uma sequência fixa.
4. **A análise mistura texto e dado.** Quase toda peça de análise lê documento não estruturado; uma parte menor faz
   cálculo. O sistema precisa extrair do texto e conferir contra a regra e o cálculo.
5. **A IA acerta quando a regra está escrita.** As etapas de IA do método só passaram nos portões porque tinham
   especificação prévia, saída em formato fixo e conferência. O sistema herda esse desenho.

## 7. Do piloto à especificação do sistema

A matriz também lista o que o método já produziu para o tipo escolhido. Cada artefato vira uma parte da
especificação:

| Artefato do método | Vira, no sistema |
|---|---|
| Tarefas do modelo com gatilho e saída (`modelo_<cod>.json`) | Casos de uso: gatilho → entrada → regra → saída |
| Atividades com potencial e tipos de IA (`avaliacao_<cod>.json`) | Escopo de cada caso de uso e capacidade de IA usada |
| Fichas por peça (insumos, cálculos, testes, ferramentas) | Dados de entrada e verificações de cada atividade |
| Requisitos com teste computável (`normas_<cod>.json`) | Verificações automáticas de conformidade |
| Conformidade medida (`conformidade_<cod>.json`) e linha de base | Linha de base para medir o efeito do sistema |
| Casos nativos (`casos_<cod>.json`) | Conjunto de aceite, rotulado por servidor |
| Melhorias e controles (`melhorias_<cod>.json`, `controles_<cod>.json`) | Regras de humano no laço, indicadores e auditoria contínua em produção |

O piloto do sistema deve medir, antes e depois, a fração automatizável real de cada atividade e o custo efetivo de
construção. Com isso, as premissas da matriz são substituídas por medidas e a priorização das ondas seguintes fica
mais precisa.

## 8. Limites

- **Volume.** É estimado a partir de deliberações. Tipo que raramente chega à deliberação fica sem medida, e tipo
  que quase não chega ao colegiado (atendimento de manifestações, por exemplo) pode ter volume real muito maior do
  que a base de um gabinete mostra. Meça com outra fonte antes de descartar.
- **Potencial de IA.** É julgamento do agente na avaliação AS-IS. O validador confere os números citados, não a
  classificação alto/médio/baixo, que não teve verificação independente (ver [VERIFICACAO_IA.md](VERIFICACAO_IA.md)).
- **Premissas.** Fração automatizável, horas de construção e custo-hora de desenvolvimento são hipóteses; o retorno
  e o custo escalam linearmente com elas. O cenário conservador combina três escolhas pessimistas e pode não se pagar.
- **Horas.** As horas por caso vêm das fichas e são hipótese até a calibração com os servidores.

## 9. Como replicar

1. Escreva em `VOLUME_REGRAS` do perfil uma regra para **cada código da coorte** e rode `python volume_anual.py`.
   Revocação abaixo de 75% deixa o tipo sem volume medido: melhore a regra ou meça o volume por outra fonte.
2. Troque as premissas de custo pelas do órgão no perfil, sobretudo `CUSTO_HORA_DEV` (valor do contrato ou da
   equipe interna). Mantenha as réguas e os portões do caso de referência na primeira rodada, para comparar.
3. Rode `python priorizacao_automacao.py` (também está no `pipeline.py`).
4. Confira com `python -m pytest ../tests -k "priorizacao or matriz"`.
5. **PARADA 10 (gestão e TI):** apresente a matriz, o gráfico e a tabela de capacidades. A escolha do piloto é do
   órgão; a matriz é o insumo. Registre a escolha e o motivo se ela divergir da matriz.
