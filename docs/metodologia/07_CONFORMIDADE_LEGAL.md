# 07 — Conformidade legal

## Objetivo

Para cada processo do TO-BE:

1. levantar as leis, normas, cláusulas contratuais e decisões que o regem, **com o trecho literal conferido contra o
   texto integral**;
2. transformar cada obrigação em **requisito com teste computável** sobre a linha do tempo dos casos;
3. medir na coorte quanto o processo atual cumpre cada requisito;
4. deixar um **programa de auditoria** para a fiscalização (controle interno, auditoria, órgão de controle).

A conformidade tem dois papéis no método: é um achado em si (prazo legal descumprido) e é a **trava** que impede o
TO-BE de cortar etapa ou prazo exigido por lei.

## Entradas

- Base normativa em sqlite (montada por [`scripts/montar_base_normas.py`](../../scripts/montar_base_normas.py),
  guia em [BASE_NORMATIVA.md](../adaptacao/BASE_NORMATIVA.md); no caso, a base de conhecimento do órgão, apontada por
  `comum.BASE_ESPECIALISTA`, só leitura);
- `dispositivos_citados` da análise por peça da coorte e atribuições peça → atividade;
- deliberações do mesmo tipo em todo o órgão (regra de volume);
- modelo canônico (`modelo_<cod>.json`) — os ids de atividade dos testes;
- [`saida/fase3/ESPECIFICACAO_CONFORMIDADE.md`](../../saida/fase3/ESPECIFICACAO_CONFORMIDADE.md).

## Passos

1. `cd scripts && python normas_processo.py` → `saida/fase3/candidatos_normas_<cod>.json`: normas-raiz mais
   citadas nas peças da coorte e nas deliberações do tipo, com dispositivos, atividades em que aparecem e caminho do
   texto integral.
2. **Curadoria por agente** → `saida/fase3/normas_<cod>.json` (normas com trecho literal, requisitos com teste,
   programa de auditoria). O agente lê o texto integral; não escreve de memória.
3. `python verificar_normas.py <cod>` — **portão**: confere cada trecho contra o texto da base; lista à parte os
   trechos de fonte externa (com URL) para conferência manual. Repetir até não sobrar falha.
4. `python conformidade.py <cod>` → `conformidade_<cod>.csv` (caso × requisito) e `conformidade_<cod>.json`
   (% por requisito).
5. **Parada humana:** a procuradoria do órgão confere a matriz de requisitos (sobretudo as interpretações e os
   prazos) antes que ela trave o TO-BE.

## Regras de decisão

### Normas

1. **Trecho literal**, copiado do texto que o agente leu, até 60 palavras. Nunca artigo, prazo ou número de memória.
2. **Vigência.** Norma revogada ou alterada no período da coorte: registre as duas e o período de cada uma (os casos
   cobrem anos diferentes).
3. **Abrangência.** Cláusula contratual varia por concessionária: diga a quais contratos se aplica.
4. Decreto do SEI e da assinatura eletrônica **não é base normativa** do processo (aparece em toda peça; o script já
   filtra como ruído).
5. Norma fora da base: use a fonte oficial e registre a URL; ela vai para a conferência manual.

### Requisitos e testes

Cada caso é uma lista de eventos `(atividade, data da peça, prazo concedido)`, com a data de juntada. Todo teste
devolve `conforme`, `nao_conforme`, `sem_evidencia` ou `nao_aplicavel`.

| Tipo | Campos | Aplica-se quando | Conforme se |
|---|---|---|---|
| `precede` | `a`, `b` | `b` ocorre | há `a` com data ≤ 1ª data de `b` |
| `exige` | `se`, `entao` | alguma de `se` ocorre | alguma de `entao` ocorre |
| `prazo_max` | `de`, `ate`, `max`, `unidade` (du/dc), `de_ocorrencia` | `de` ocorre **antes** da 1ª `ate` | intervalo ≤ `max` |
| `prazo_min` | `de`, `ate`, `min`, `unidade` | `de` e `ate` ocorrem | (1ª `ate` − última `de` anterior) ≥ `min` |
| `prazo_concedido_min` | `atividade`, `min` | a atividade ocorre | toda peça com prazo lido concede ≥ `min` dias |
| `duracao_max` | `ate`, `max`, `unidade` (anos/du/dc), `de` opcional | `ate` ocorre | (1ª `ate` − início) ≤ `max` |
| `manual` | `procedimento` | — | não computado; descreva como testar |

Regras que vieram de falhas ou de riscos concretos:

| Regra | Por quê |
|---|---|
| **Prazo mínimo protegido:** todo prazo concedido à parte (defesa, manifestação, razões finais) vira um requisito `prazo_min` entre o ofício que o abre e o ato seguinte | É o que impede o TO-BE de tratar essa espera como desperdício ([09](09_TOBE_SIMULACAO.md), `validar_tobe.py`) |
| **Prazo máximo só com origem anterior ao ato:** `prazo_max` só conta `de` com data ≤ 1ª `ate` | Falha real: razões finais pedidas depois da deliberação (rodada de embargos) davam intervalo negativo, que virava conformidade |
| **`de_ocorrencia: ultima`** nos prazos que reabrem a cada rodada (deliberação depois de nova rodada de razões finais; parecer jurídico depois do técnico) | Contar da 1ª rodada acusava violação inexistente (teste sintético: 139 dias da 1ª rodada × 18 dias da última) |
| **Prazo não lido é `sem_evidencia`, não violação** | O LLM nem sempre lê o prazo do ofício |
| Requisito que depende de dado fora do SEI (ex.: data de publicação no diário quando não há peça) é `manual` | Não se testa o que não se mede |
| Ids de atividade e de norma conferidos contra o modelo e o inventário | Requisito testando atividade inexistente passa calado |
| `interpretacao` registrada quando a norma admite mais de uma leitura | A procuradoria precisa ver a leitura adotada |

### Programa de auditoria

Para cada teste: objetivo, critério legal, fonte de dados, população, amostra, frequência, achado-tipo e se é
automatizado. Os automatizados viram `auditoria_continua` nos controles ([10](10_CONTROLES_METAS.md)).

## Saídas e formato

`saida/fase3/normas_<cod>.json` (`normas[]` com id, norma, dispositivo, trecho, fonte, vigência, abrangência,
obrigação, responsável, prazo, atividades; `requisitos[]` com id, normas, exigência, parâmetro, atividades,
criticidade, evidência no SEI, teste, interpretação; `programa_auditoria[]`); `conformidade_<cod>.csv` (caso,
requisito, resultado, detalhe) e `conformidade_<cod>.json` (contagens e `pct_conforme` = conformes ÷ (conformes + não
conformes)).

## Portão de qualidade

- `verificar_normas.py` (portão no pipeline): comparação literal depois de normalizar espaços, aspas, travessões e
  caixa; sai com código 1 se um trecho da base não for achado.
- Testes: `test_conformidade_precede_exige_ordem_e_nao_aplica_sem_o_ato`,
  `test_conformidade_prazo_min_usa_a_ultima_notificacao_antes_do_ato`,
  `test_conformidade_prazo_concedido_sem_leitura_e_sem_evidencia_nao_violacao`,
  `test_conformidade_duracao_max_em_anos_conta_do_primeiro_evento`,
  `test_conformidade_prazo_max_nao_conta_origem_posterior_ao_ato_e_aceita_ultima_rodada` (regras) e
  `test_requisitos_testam_atividades_do_modelo` (saídas).
- Trechos de fonte externa: conferência manual, registrada.
- Leitura: requisito com conformidade muito baixa é **achado ou erro de teste**. Antes de reportar, abra três casos não
  conformes no `conformidade_<cod>.csv` (coluna `detalhe`) e confira na linha do tempo.

## Armadilhas conhecidas

- Interpretar `prazo_min` não conforme como violação sem olhar o caso: pode ser ato da agência antes do fim do prazo
  (violação) ou resposta antecipada da parte seguida de ato (não é violação). Confira o `detalhe`.
- Dias úteis × dias corridos: a norma diz qual; o teste tem de usar a mesma unidade.
- Data de juntada não é data de assinatura nem de publicação; para prazos curtos, a diferença importa.
- Conformidade em poucos casos aplicáveis (n de 3 ou 4) é frágil; mostre o n.
- Requisito "100% exigido por lei" vira meta do TO-BE sem ver se o redesenho alcança: a meta de prazo vem da simulação
  ([10](10_CONTROLES_METAS.md)).

## O que muda em outro Estado

Tudo o que é normativo: lei de criação da agência, regimento, lei estadual de processo administrativo (prazos e
contraditório), contratos de concessão, normas internas. O motor de testes e os tipos de teste valem igual. Monte a
base primeiro ([BASE_NORMATIVA.md](../adaptacao/BASE_NORMATIVA.md)); sem texto integral não há trecho verificável.

## Números do caso AGENERSA (ordem de grandeza)

| Processo | Normas / requisitos / testes de auditoria | Exemplos de conformidade medida | Origem |
|---|---|---|---|
| Reajuste tarifário | 31 / 20 / 11 | pronunciamento em até 30 dias do pedido: 17,6% (3 de 17); parecer jurídico antes da deliberação: 100% | `saida/fase3/normas_P01.json`, `conformidade_P01.json` |
| Fiscalização de campo | 32 / 20 / 9 | deliberação em até 40 dias das razões finais: 12,5% (1 de 8); parecer jurídico em até 15 dias do técnico: 11,1% | `normas_P06.json`, `conformidade_P06.json` |
| Ocorrência de usuário | 33 / 19 / 9 | deliberação em até 40 dias das razões finais: 42,9% (3 de 7); sorteio antes das razões finais: 100% | `normas_P21.json`, `conformidade_P21.json` |

Padrão do caso: os requisitos de **ordem** (parecer antes de decidir, razões finais antes da sessão) são cumpridos
quase sempre; os de **prazo máximo** quase nunca. A maior parte das normas veio de textos da própria base (29 de 31,
29 de 32 e 28 de 33 na tabela `normativo`).
