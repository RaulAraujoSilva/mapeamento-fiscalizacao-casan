# 04 — Classificação, piloto e coorte

## Objetivo

Ligar cada processo SEI a um **processo organizacional** do catálogo do órgão (o "tipo de demanda"), escolher
poucos casos para o piloto de conteúdo e, depois, montar a **coorte**: todos os processos de cada tipo com dados
suficientes para medir o procedimento, não só um caso.

O processo SEI é um caso; o processo organizacional é o tipo. Sem a classificação, não há como dizer "o reajuste
tarifário leva X" — só "este processo levou X".

## Entradas

- Catálogo do órgão em [`catalogo/`](../../catalogo/) (caso: 36 processos em 12 macroprocessos, com ondas de
  prioridade);
- trilhas e indicadores ([02](02_TRILHA_TEMPO_POSSE.md));
- títulos e análise das peças substantivas;
- cobertura de texto por processo (`dados/relator/cobertura_texto.csv`).

## Passos

### Fase 0 — classificação e piloto

1. `cd scripts && python preparar_classificacao.py` → `saida/insumo_classificacao.jsonl` (um registro por
   processo: metadados, trilha, títulos das peças substantivas e uma **sugestão por regras** de palavra-chave) e
   `saida/catalogo_processos.json`.
2. **Classificação por agente.** O agente lê cada registro e decide, pelo **objeto de mérito**, o código principal,
   um secundário opcional, a confiança (alta, média, baixa), e, quando nenhum código serve, `LACUNA` com o tipo de
   demanda. As decisões ficam versionadas em `scripts/classificacao/decisoes.py`, com justificativa de uma frase
   por processo (chave = índice da linha do insumo). A partir delas grava-se `saida/classificacao_processos.csv`,
   que é o que `selecionar_piloto.py` lê. No caso de referência essa conversão foi feita na própria sessão do
   agente, sem script versionado: se for repetir, escreva um conversor pequeno e determinístico (decisões +
   insumo → CSV) e versione-o, para que a classificação seja reproduzível.
3. **Reclassificação às cegas** por outro agente (sem ver as decisões) numa amostra; mede-se concordância e kappa.
4. `python selecionar_piloto.py` → `saida/processos_classificados.csv` e `saida/piloto.csv`.
5. `python gerar_planilha.py` → planilha da fase 0.

### Fase 2 — coorte

6. Processos que existem só no banco de conteúdo (sem andamentos): `python pecas_relator.py` →
   `saida/fase2/documentos_relator.csv`; `python classificar_novos.py` (LLM) →
   `saida/fase2/classificacao_relator.csv`; reclassificação às cegas por agente →
   `saida/fase2/verificacao_classificacao.csv`.
7. `python coorte_fase2.py` → `saida/coorte_fase2.csv` (e `saida/fase2/duplicados.csv`).
8. Exportar/coletar o texto da coorte e rodar `coorte_fase2.py` de novo: a cobertura passa a ser a do texto não
   vazio, mais estrita.

## Regras de decisão

### Classificação

- **Pelo objeto de mérito**, não pelo tipo de processo do SEI nem pela unidade de origem. O rito decisório
  transversal (instrução e julgamento colegiado) é registrado à parte, não como código principal.
- **Lacuna é achado.** Processo sem correspondência no catálogo vira `LACUNA` com o tipo de demanda descrito, e as
  lacunas recorrentes vão para a oficina com a área de planejamento. No caso, a carteira revelou três: acompanhamento
  ambiental e de mananciais (21 processos), bens reversíveis (4) e aquisição de gás pelas distribuidoras (3)
  ([RESULTADOS_FASE0.md](../RESULTADOS_FASE0.md)). A primeira virou código próprio (N01) na fase 2.
- **Fronteiras se anotam.** Quando dois códigos disputam o mesmo processo (no caso, fiscalização × sanção ×
  ocorrência de usuário × crise de abastecimento), use o secundário e leve a fronteira à validação.

### Seleção do piloto (`selecionar_piloto.py`)

Elegível = nativo do SEI · encerrado · 10 a 150 documentos · ≥ 3 unidades ativas · ao menos uma peça de análise ·
nenhum documento sem estadia · classificação de confiança alta ou média · ≥ 60% das peças substantivas com texto.
Prioridade para a onda 1 do catálogo. Por código, um caso **típico** (lead time mais próximo da mediana) e, com ao
menos 4 elegíveis, um **crítico** (mais espera dominante, retornos e terceiros). Máximo de 8 códigos no piloto.
Peça característica obrigatória onde fizer sentido (no caso, o típico de fiscalização tinha de ter relatório de
fiscalização ou notificação: o primeiro escolhido era uma conferência de habilitação de empresas).

### Coorte (`coorte_fase2.py`)

| Regra | Por quê |
|---|---|
| Entra processo com classificação de confiança média ou alta e texto suficiente (≥ 60% das substantivas) | Sem texto não há ficha nem rótulo de atividade |
| Código entra com **pelo menos 5 casos** (`MIN_CASOS`) | Abaixo disso a mediana é um caso; vira "estudo de caso" |
| Lote 1 = códigos com modelo do piloto (trilha nativa); lote 2 = tipos novos (aceita migrados e processos só com peças) | Tipos novos precisam de mais casos para o modelo |
| Processo aberto entra (dá ocorrências de atividade), mas lead time só se mede nos encerrados | Lead de processo aberto vai só até a data de corte |
| Processo só com peças que repete ≥ 90% dos textos de outro da coorte (mínimo 3) sai | Cópia de processo migrado contaria o mesmo caso duas vezes |
| Tipo novo: só entra o processo em que classificador e auditor às cegas concordam | Concordância de só 65,5% na reclassificação cega dos tipos novos ([MITIGACOES.md](../MITIGACOES.md)) |

### Situação de cada código (`procedimento.py`)

| Situação | Critério | Como falar dele |
|---|---|---|
| **procedimento** | ≥ 5 casos e concordância ≥ 85% na auditoria às cegas do classificador de atividade (peças substantivas) | "o procedimento", "na coorte" |
| **indicativo** | ≥ 5 casos, concordância abaixo de 85% ou sem auditoria | números com ressalva |
| **estudo de caso** | menos de 5 casos | nada de "padrão" nem "tendência" |

## Saídas e formato

| Arquivo | Conteúdo |
|---|---|
| `scripts/classificacao/decisoes.py` | Decisão do agente por processo: (principal, secundário, confiança, lacuna, justificativa) |
| `saida/classificacao_processos.csv` | Classificação de cada processo |
| `saida/processos_classificados.csv`, `saida/piloto.csv` | Indicadores + classificação; casos-piloto com papel típico/crítico |
| `saida/fase2/classificacao_relator.csv`, `verificacao_classificacao.csv` | Classificação dos processos só com peças e conferência cega |
| `saida/coorte_fase2.csv` | Coorte: processo, código, lote, trilha (nativa, migrada, sem), encerrado |
| `saida/fase2/duplicados.csv` | Cópias retiradas |

## Portão de qualidade

- Classificação: concordância ≥ 85% no código principal e kappa ≥ 0,8 na reclassificação cega, divergências
  explicadas ([PLANO_AUDITORIA_E_AMPLIACAO.md](../PLANO_AUDITORIA_E_AMPLIACAO.md)). Abaixo disso, reveja as
  definições do catálogo (geralmente o problema é fronteira mal escrita) e reclassifique.
- `test_coorte_tira_copia_de_processo_migrado` (regra), `test_coorte_sem_processo_duplicado` e
  `test_situacao_do_codigo_pela_auditoria` (saídas).
- **Parada humana:** leve a lista de lacunas e de fronteiras à área de planejamento do órgão antes de modelar.

## Armadilhas conhecidas

- Classificar pelo nome da unidade ("veio da ouvidoria, então é atendimento"): o mérito pode ser sanção ou
  fiscalização.
- Usar a sugestão por palavra-chave como decisão final. Ela é insumo do agente, não rótulo.
- Classificador por LLM em tipo novo sem conferência cega: no caso, 65,5% de concordância — inaceitável sem o filtro
  de consenso.
- Ampliar a coorte com processos de confiança baixa para chegar a 5 casos.
- Esquecer o viés de amostra: tipos que raramente chegam à relatoria (ouvidoria, cobrança de multa) ficam sem casos
  numa carteira de gabinete; peça listas de outras unidades.

## O que muda em outro Estado

O catálogo é do órgão: troque `catalogo/` inteiro. Se o órgão tiver só um organograma, faça um inventário
provisório (código, nome, objeto, unidade dona) e trate as primeiras lacunas como achado. As regras de seleção e de
coorte (60%, 5 casos, 85%) são de método: mantenha.

## Números do caso AGENERSA (ordem de grandeza)

| Item | Valor | Origem |
|---|---|---|
| Processos classificados / confiança alta, média, baixa | 251 / 138, 104, 9 | [RESULTADOS_FASE0.md](../RESULTADOS_FASE0.md) |
| Reclassificação cega (fase 0) | 63 processos; concordância 92,1%, kappa 0,91 | [AUDITORIA.md](../AUDITORIA.md) |
| Elegíveis ao piloto / piloto final | 56 / 12 processos em 8 códigos | [RESULTADOS_FASE0.md](../RESULTADOS_FASE0.md), [RESULTADOS_PILOTO.md](../RESULTADOS_PILOTO.md) |
| Coorte | 117 processos (92 nativos, 9 migrados, 16 só com peças); 4 cópias retiradas | [RESULTADOS_FASE2.md](../RESULTADOS_FASE2.md) |
| Códigos com procedimento calculado | 11; 10 na situação "procedimento" e 1 "estudo de caso" (sanção, 3 casos) | idem |
