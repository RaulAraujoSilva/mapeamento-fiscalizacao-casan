# 02 — Trilha, tempo e posse

## Objetivo

Transformar a lista de andamentos e documentos de cada processo em medidas de tempo que **não se sobrepõem e
não contam o mesmo dia duas vezes**: por onde o processo passou (estadias), com quem estava em cada instante
(posse), quanto durou cada atividade e quanto se esperou antes dela (linha do tempo), e quanto do tempo foi
resposta de terceiros.

Este é o capítulo em que o caso de referência mais errou antes de acertar. As três regras centrais (posse,
linha do tempo e terceiros) foram reescritas depois da auditoria; leia as falhas antes de mexer em qualquer
regra.

## Entradas

- Tabelas canônicas `dados/sei2_dump/*.tsv` ([01](01_COLETA_E_BASE.md));
- `dados/relator/extractions.parquet` (data real escrita nas peças externas, pedido de prorrogação);
- fichas de trabalho (prazo dado em cada ofício, [03](03_CONTEUDO_ESFORCO.md)) — para as janelas de terceiros;
- vínculos ou atribuições peça → atividade ([05](05_MODELAGEM_BPMN.md)) — para a linha do tempo;
- perfil do órgão: feriados, hub, unidades de recepção, categorias de documento.

## Passos

1. `cd scripts && python trilhas.py` → estadias, documentos atribuídos, posse, janelas de terceiros e
   indicadores por processo.
2. Depois do modelo e dos vínculos (piloto) ou das atribuições (coorte): `python fatos.py` monta a linha do
   tempo de cada caso e a tabela de fatos; `python procedimento.py` faz o mesmo para todos os casos da coorte
   (usa a função `fatos.linha_do_tempo`).
3. Rodar os testes: `python -m pytest ../tests/test_regras.py` (regras) e, com as saídas prontas,
   `../tests/test_saidas.py` (propriedades).

## Regras de decisão

### 2.1 Estadia (passagem de uma unidade pelo processo)

- **Entrada** na unidade: geração do processo, remessa para ela, reabertura nela, ou recebimento sem estadia
  aberta. Conta a partir da **remessa** (o processo já está na caixa da unidade), não do recebimento.
- **Saída**: conclusão na unidade ou remessa feita por ela. Se a unidade remeteu e depois aparece uma conclusão
  dela sem reabertura, ela manteve o processo aberto: a estadia vai até a conclusão.
- Estadia aberta na data de corte é medida até o corte e marcada `em_aberto`.
- Estadia com documento juntado é **ativa**; sem documento é **passagem**. A estadia recebe o perfil da natureza
  mais densa que produziu (decisão > análise > fiscalização > instrução > comunicação > juntada > tramitação).

**Atribuição de documento:** cada documento vai para a estadia da unidade que o juntou cuja janela contém a data
de inclusão; na falta, para a estadia mais próxima da mesma unidade.

### 2.2 A estadia não mede espera

O SEI permite o processo aberto em várias unidades ao mesmo tempo. Somar estadias conta o mesmo dia mais de uma
vez, e a estadia se estende depois do marco que interessa.

> **Falha real (A1).** A permanência no gabinete do relator foi lida como espera e produziu o gargalo falso
> "fila de relatoria". Na verdade, nos casos verificados, a deliberação saiu poucos dias depois da chegada ao
> gabinete; o tempo longo estava na instrução e depois da decisão ([AUDITORIA.md](../AUDITORIA.md)).

Use a estadia para sequência, contagem de passagens e iteração; **nunca** para espera ou gargalo.

### 2.3 Posse (com quem estava o processo)

Em cada instante, a posse é da unidade que **abriu mais recentemente** entre as que têm o processo aberto.
Quando todas concluíram e ninguém reabriu, a posse é **SEM UNIDADE**: processo parado, sem dono. A posse
particiona o lead time sem lacuna nem sobreposição.

> **Falha real (A2).** A posse ficava com a unidade da última remessa mesmo depois de ela concluir. O tempo
> "sem dono" sumia dentro de unidades que já não tinham o processo. Corrigido em `trilhas.montar_posse`; o
> "processo parado sem dono" virou achado próprio (no caso, até 108 du num único intervalo).

### 2.4 Linha do tempo (execução e espera por atividade)

Definida em [`scripts/fatos.py`](../../scripts/fatos.py):

- **Ocorrência** de atividade = sequência contínua de peças **próprias** (da unidade da raia da atividade)
  ligadas à mesma atividade, na ordem das datas. Atividade que volta depois de outra tem nova ocorrência (laço).
- **Execução** = da 1ª à última peça da ocorrência, em dias úteis.
- **Espera antes** = do fim da ocorrência anterior (de qualquer atividade) ao início desta, **repartida entre as
  unidades que tinham a posse** nesse intervalo. Ocorrências que se sobrepõem não têm espera.
- **Espera inicial** = do início do processo à 1ª ocorrência; **cauda** = da última ocorrência ao último andamento.
- Peça de outra unidade fica como trâmite associado: não mede o tempo nem soma horas da atividade (falha D2).

Esses são os únicos tempos usados no diagrama, nas fichas de atividade, nas avaliações e na simulação do TO-BE.

### 2.5 Terceiros (resposta da concessionária, do poder concedente, de outro órgão)

Uma janela de espera de terceiros é aberta por ofício ou notificação da agência que dá prazo a terceiro e é
fechada pela resposta. Regras (em `trilhas.janelas_espera_externa` e `trilhas.datas_reais`):

| Regra | Por quê (falha real) |
|---|---|
| Só abre janela ofício **da agência** que **dá prazo** a terceiro (lido na ficha). Ofício de outro órgão, ou sem prazo, não abre | A5: todo ofício abria janela, inclusive os que não pediam nada |
| Ofício sem ficha → tempo indeterminado | A5 |
| A resposta usa a **data real escrita na peça** (análise por peça), não a data da juntada | A3: a janela fechava na juntada, que pode ser semanas depois |
| Sem data real → **indeterminado**, nunca terceiros | A3, A10 |
| Peticionamento em processo relacionado e anexo recebido por unidade de recepção contam como resposta; anexo da própria unidade não | A4 |
| A janela é limitada ao prazo dado + 5 du; sem prazo conhecido, 60 du. O excesso é **indeterminado** | A5 |
| Pedido de prorrogação ou dilação do terceiro **não fecha** a janela; prazo de natureza "prorrogação" não define a janela | A6: a prorrogação contava como resposta e subestimava a espera |
| Uma linha por ofício em `saida/janelas_terceiros.csv` | A7: o total por processo não era conferível |

**Indeterminado** quer dizer: não se separa de processo parado. O texto dos entregáveis tem de dizer isso.

### 2.6 Dias úteis

`comum.dias_uteis` conta dias úteis com o calendário do perfil (feriados nacionais, estaduais, municipais da
sede e Carnaval). Intervalo invertido vale 0. Toda métrica de tempo é em dias úteis (du); dias corridos (dc)
só onde a norma conta em corridos (ver [07](07_CONFORMIDADE_LEGAL.md)).

### 2.7 Indicadores derivados (fase 0)

- **Iteração:** retorno a unidade já visitada, fora a secretaria (hub, passagem obrigatória); pingue-pongue
  A → B → A.
- **Razão trabalho/tempo** de cada período de posse = horas estimadas ÷ (dias úteis × 6 h). Período de 20 du ou
  mais com trabalho abaixo de 5% da capacidade = **espera dominante**; se além disso só produziu peças leves
  (≤ 1 h), **fila longa com trabalho curto**. As 6 h por dia útil são hipótese (`HORAS_DIA`).

## Saídas e formato

| Arquivo | Conteúdo |
|---|---|
| `saida/estadias.csv` | Uma linha por passagem de processo por unidade (entrada, saída, du, dc, documentos, perfil, `em_aberto`) |
| `saida/documentos.csv` | Cada protocolo com a estadia, categoria, natureza, horas-base, autoria |
| `saida/posse.csv` | Períodos de posse (unidade ou SEM UNIDADE), sem sobreposição |
| `saida/janelas_terceiros.csv` | Uma linha por ofício: resposta, prazo, situação (terceiros ou indeterminado), du |
| `saida/processos_indicadores.csv` | Lead time, passagens, retornos, espera dominante, terceiros por processo |
| `saida/bpmn/fatos_<cod>.json` | Linha do tempo e tabela de fatos (ver [06](06_AVALIACAO_ASIS.md)) |
| `saida/fase2/casos_<cod>.json` | Linha do tempo de cada caso nativo da coorte: por ocorrência, `espera_antes_du`, `execucao_du`, `espera_antes_por_unidade`, `espera_antes_terceiros_du`, horas piso e teto |

## Portão de qualidade

- `tests/test_regras.py` (primeira etapa do pipeline): casos sintéticos de cada regra — `test_posse_*`,
  `test_resposta_*`, `test_oficio_*`, `test_peticionamento_*`, `test_anexo_*`, `test_excesso_*`,
  `test_pedido_de_prorrogacao_*`, `test_regex_de_prorrogacao`, `test_dias_uteis_*`, `test_data_da_peca_*`.
- `tests/test_saidas.py`: `test_posse_sem_lacuna_nem_sobreposicao`, `test_janelas_de_terceiros_cobrem_os_totais`,
  `test_fatos_consistentes` (espera ≥ 0; soma por unidade = total), `test_tramite_de_outra_unidade_fica_fora_do_tempo_e_das_horas`.

Falha em `test_regras` = uma regra regrediu: não gere nada, leia o teste que falhou. Falha em `test_saidas` =
a saída viola uma propriedade: não publique.

**Conferência humana obrigatória antes de seguir:** reconstrua à mão a trilha de um processo (andamentos na tela
do SEI × `estadias.csv` × `posse.csv`) e confira com um servidor da unidade se a sequência faz sentido. No caso,
a verificação independente recalculou a posse dia a dia a partir das estadias e achou diferença de 0 a 1 du
([AUDITORIA.md](../AUDITORIA.md)).

## Armadilhas conhecidas

- Somar estadias ou permanências para medir espera (A1).
- Deixar a posse com quem remeteu por último (A2).
- Usar a data de juntada como data da resposta do terceiro (A3) e contar pedido de prorrogação como resposta (A6).
- Medir "atraso de juntada" pela data escrita no anexo: a data é a do conteúdo, não da chegada. A métrica foi
  retirada (A8).
- Ler data `dd-mm-aaaa` como mês primeiro (A9).
- **Mudar uma regra de tempo sem rever as conclusões.** Toda avaliação carimbada fica inválida; o pipeline acusa
  pelo carimbo ([06](06_AVALIACAO_ASIS.md)). Não recarimbe sem revisar.
- Comparar mediana de lead time de nativos com a de todos: migrados distorcem. Os dois fatos existem; diga qual
  está usando (F3).

## O que muda em outro Estado

- Feriados estaduais e municipais da sede (no perfil do órgão).
- Siglas do hub e das unidades de recepção.
- Textos dos andamentos, se a versão do SEI for diferente (perfil do SEI).
- O limite de +5 du sobre o prazo e o teto de 60 du sem prazo são parâmetros de método: mantenha-os, a menos que
  haja razão documentada para mudar (e então rode de novo os testes e reveja as avaliações).

## Números do caso AGENERSA (ordem de grandeza)

| Item | Valor | Origem |
|---|---|---|
| Documentos dentro da estadia / na estadia mais próxima / sem estadia | 95% / 4% / 36 documentos | [RESULTADOS_FASE0.md](../RESULTADOS_FASE0.md) |
| Estadias / com documento juntado | 6.795 / 4.437 | idem |
| Processos com posse / com lacuna ou sobreposição | 250 / 0 | `saida/auditoria/auditoria_automatica.json` |
| Data real disponível nas peças externas | cerca de 56% | [AUDITORIA.md](../AUDITORIA.md) |
| Efeito da regra de prorrogação (A6) | terceiros 136 → 114 du num caso crítico; nenhuma conclusão de gargalo mudou | [MITIGACOES.md](../MITIGACOES.md) |
| Lead time mediano por caso nativo (coorte) | reajuste 337,5 du; fiscalização 351 du; ocorrência de usuário 469 du | `saida/fase3/linha_base_P01.json`, `_P06.json`, `_P21.json` |

Os números da fase 0 em [RESULTADOS_FASE0.md](../RESULTADOS_FASE0.md) (por exemplo, a mediana de 90 du de
terceiros por processo) foram calculados **antes** das correções de posse e de terceiros. Use-os só como ilustração
do método inicial, não como referência.
