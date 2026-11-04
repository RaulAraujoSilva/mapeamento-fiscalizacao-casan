# 08 — Benchmarking

## Objetivo

Reunir casos de estado da arte, no Brasil e no exterior, **documentados em fonte verificável e com resultado medido
ou avaliado**, que orientem as melhorias do TO-BE e deem parâmetro de ganho. O benchmarking é o lastro externo da
proposta: melhoria sem caso de referência só entra como hipótese explícita.

O risco aqui é específico da IA: citação inexistente, DOI inventado, resultado exagerado. Por isso a verificação é
feita por um segundo agente, independente, com regras mecânicas.

## Entradas

- Avaliações AS-IS (`saida/bpmn/avaliacao_<cod>.json`: gargalo, desperdícios, oportunidades) e modelos (atividades);
- [`saida/fase3/ESPECIFICACAO_BENCHMARK.md`](../../saida/fase3/ESPECIFICACAO_BENCHMARK.md);
- acesso à web: APIs do OpenAlex, Crossref e Semantic Scholar; SciELO; sites oficiais de reguladores.

## Passos

1. **Agrupar por família** de processo para não pesquisar a mesma coisa várias vezes (no caso: tarifa, fiscalização,
   usuário e transversal — fluxo decisório, automação e IA).
2. **Busca por agente**, uma família por agente, com a avaliação e o modelo dos processos da família lidos antes.
   Saída: `saida/fase3/benchmark/<familia>.json`, com a estratégia de busca e as lacunas.
3. **Verificação independente** por outro agente (que não buscou): `saida/fase3/benchmark/verificacao.json`, com
   veredito por caso (`ok`, `corrigir`, `excluir`) e a correção sugerida.
4. Aplicar as correções nos casos (o arquivo da família é corrigido; a verificação fica como registro).
5. `cd scripts && python benchmark_md.py` → [`docs/BENCHMARKING.md`](../BENCHMARKING.md), já com a verificação aplicada.

## Regras de decisão

### Camadas de fonte (nunca misturar)

| Camada | O que é | Conferência |
|---|---|---|
| `cientifica` | Artigo revisado por pares, capítulo acadêmico, tese ou dissertação, com DOI ou handle | DOI conferido no Crossref (`api.crossref.org/works/<doi>`) ou OpenAlex |
| `oficial` | Documento de regulador ou organismo (OCDE, Banco Mundial, BID, reguladores estrangeiros e nacionais, tribunais de contas, associações de reguladores) | URL oficial que abre |

Meta: pelo menos 60% dos casos de cada família na camada científica.

### Inclusão

Prática concreta, aplicada por órgão identificado, com **resultado medido ou avaliado** (antes × depois, comparação,
avaliação de impacto, ou ao menos resultado operacional reportado). Fora: opinião sem caso, marketing de fornecedor,
prática sem resultado, notícia de jornal.

### Verificação feita pelo próprio agente de busca

- `trecho`: citação literal curta (até 40 palavras, no idioma original) do resumo ou do texto efetivamente lido, que
  sustente o `resultado_reportado`.
- Sem texto lido que sustente o resultado, o caso não entra. **Nunca DOI, autor, ano ou número de memória.**
- `verificado_em`: a URL de onde o trecho foi lido.

### Verificação independente (segundo agente)

Por caso: `doi_ok` (DOI existe; metadados compatíveis), `metadados_ok`, `trecho_ok` (trecho achado na fonte por
comparação normalizada, sem acento, pontuação e espaço), `resultado_ok` e `parametro_ok` (o resultado e o parâmetro de
ganho não dizem mais do que a fonte), `camada_ok`. Problemas descritos e correção sugerida.

> **Falha típica encontrada.** O parâmetro de ganho afirmava que prazo-padrão "reduz a dispersão do tempo de decisão",
> o que o estudo não mede: o achado era que os prazos concentram decisões perto do vencimento, com mais problemas de
> qualidade. O caso foi mantido, com o parâmetro reescrito como **alerta** ("prazo por etapa precisa de controle de
> qualidade das peças produzidas perto do prazo") (`saida/fase3/benchmark/verificacao.json`). É daí que vem a regra de
> pôr indicadores de qualidade ao lado dos de prazo ([10](10_CONTROLES_METAS.md)).

### Uso no TO-BE

- `parametro_ganho` de um caso é **teto, não meta**, quando o caso é de outro setor ou ferramenta (tribunal, saúde,
  uso geral): o cenário esperado fica abaixo e a transferência é explicada ([09](09_TOBE_SIMULACAO.md)).
- `aplicabilidade` diz por que serve (ou não) ao órgão, considerando a situação AS-IS.
- Fonte repetida em duas famílias conta como um estudo, não dois.

## Saídas e formato

`saida/fase3/benchmark/<familia>.json`: `familia`, `processos`, `pergunta`, `estrategia_busca`, `casos[]` (id,
prática, descrição, contexto, resultado reportado, métrica antes/depois, fonte com camada, DOI, URL, trecho,
`verificado_em`, nível de evidência, `fase_melhoria`, `atividades_alvo` como `<cod>:<tN>`, aplicabilidade, parâmetro de
ganho, limitações), `lacunas`. `verificacao.json`: método, veredito por caso, resumo e observações gerais.

## Portão de qualidade

- `test_benchmark_verificado_sem_caso_excluido` (saídas): todo caso verificado e nenhum `excluir` remanescente.
- `validar_tobe.py` recusa melhoria que cite caso inexistente.
- **Parada humana:** o professor ou o coordenador lê `docs/BENCHMARKING.md` e as lacunas antes do TO-BE. Lacuna (o
  que se procurou e não se achou com evidência) é informação útil: aponta melhoria que terá de ser hipótese.

## Armadilhas conhecidas

- Agente que busca e verifica o próprio trabalho: confirma o que quer confirmar. Use outro agente, sem a conclusão.
- Resumo de artigo que não traz o número: o resultado fica qualitativo; não "complete" com número de memória.
- Trecho com palavras suprimidas sem reticências não é literal (um caso no levantamento).
- Inflar a contagem com a mesma fonte em famílias diferentes.

## O que muda em outro Estado

As famílias seguem os processos escolhidos. Reaproveite os casos transversais (fluxo decisório, automação, IA) e os de
famílias iguais às do caso; refaça a verificação se o caso for usado para outro parâmetro. Inclua reguladores e
tribunais de contas do próprio Estado na camada oficial.

## Números do caso AGENERSA (ordem de grandeza)

| Item | Valor | Origem |
|---|---|---|
| Casos | 64 (47 científicos, 17 oficiais) em 4 famílias: tarifa 14, fiscalização 15, usuário 16, transversal 19 | [BENCHMARKING.md](../BENCHMARKING.md) |
| Verificação independente | 51 sem ressalva, 13 corrigidos, 0 excluídos | `saida/fase3/benchmark/verificacao.json` |
| DOIs distintos conferidos no Crossref | 44, todos existentes e compatíveis | idem |
| Trechos achados na fonte | 64; 1 não literal (palavras suprimidas) | idem |
| Fontes repetidas entre famílias | 3 pares | idem |
