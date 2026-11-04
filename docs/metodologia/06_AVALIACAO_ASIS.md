# 06 — Avaliação AS-IS

## Objetivo

Diagnosticar cada processo com referenciais de melhoria (Lean, mapeamento do fluxo de valor, Teoria das Restrições,
Seis Sigma, análise de valor, ECRS) e apontar onde a IA ajudaria — **sem nenhum número que não venha da tabela de
fatos**. A avaliação é texto escrito por agente; os números dentro dela são do código.

## Entradas

| Arquivo | O que traz |
|---|---|
| `saida/bpmn/fatos_<cod>.json` | **Única fonte de números**: linha do tempo do caso e fatos `coorte.*` |
| `saida/bpmn/fichas_<cod>.json` | Atividades com tempos, entradas, ferramentas, competências, perdas (tipos com piloto) |
| `saida/fase2/procedimento_<cod>.json` | Contagens da coorte (tipos sem piloto) |
| `saida/bpmn/modelo_<cod>.json`, `evidencias_<cod>.md` | Fluxo e evidências |
| `saida/auditoria/auditoria_claims_<cod>.json` | Afirmações da versão anterior julgadas erradas, com a correção (não podem reaparecer) |
| [`saida/bpmn/ESPECIFICACAO_AVALIACAO.md`](../../saida/bpmn/ESPECIFICACAO_AVALIACAO.md) | Formato, lentes, regras v2 (ancoragem) e v3 (coorte) |

## Passos

1. `cd scripts && python fatos.py` (gera os fatos; tem de rodar **antes** da avaliação).
2. **Avaliação por agente** → `saida/bpmn/avaliacao_<cod>.json` (formato da especificação).
3. `python validar_avaliacao.py <cod>` — repetir a correção até **0 problema**.
4. **Verificação independente** dos blocos de conclusão (síntese, gargalo, desperdícios, oportunidades) por outro
   agente, afirmação por afirmação, contra as fontes primárias.
5. Revisado tudo: `python validar_avaliacao.py <cod> --carimbar`.
6. `python pipeline.py --de validar_avaliacoes` (portões finais e site).

## A tabela de fatos

Cada fato tem `id`, `caso`, `descricao`, `valor`, `unidade` e `definicao`. Famílias de identificadores:

| Prefixo | Exemplos | Uso |
|---|---|---|
| `tipico.` / `critico.` | `tipico.t2.1.espera_antes`, `critico.t10.1.espera_antes.SEM UNIDADE`, `tipico.posse.CAPET`, `tipico.lead`, `.cauda`, `.terceiros`, `.indeterminado`, `.inicio`, `.fim` | Casos do piloto |
| `coorte.` | `coorte.t8.espera_antes.mediana` (e `.q1`, `.q3`, `.max`, `.n`), `coorte.t2.horas_piso.mediana`, `coorte.t4.pct_casos`, `coorte.t4.casos_com_laco`, `coorte.t2.perda.refazimento`, `coorte.caso.lead.mediana`, `coorte.posse.SEM UNIDADE.q3`, `coorte.transicao.t9.t10`, `coorte.auditoria.concordancia_substantivas` | Procedimento na coorte |
| `carteira.` | `carteira.lead_mediano_nativos`, `carteira.lead_mediano_todos` | Toda a base |

No caso, a tabela do reajuste tarifário tem 975 fatos (683 da coorte, 124 do típico, 164 do crítico, 4 da carteira)
(`saida/bpmn/fatos_P01.json`).

## Regras de decisão

### Conteúdo (especificação, regras 1–6)

1. Toda tarefa do modelo tem entrada em `atividades`, e nenhuma a mais (o validador exige).
2. 4 a 7 oportunidades priorizadas (impacto alto e esforço baixo primeiro). Diga se a oportunidade **reduz espera**
   ou só **tempo de trabalho** — espera é o desperdício dominante.
3. **IA não decide.** Decisão colegiada, juízo jurídico final e assinatura ficam com servidores.
4. **Rito legal é necessário sem valor.** Razões finais, publicação e prazos de defesa não se suprimem; a melhoria é
   fazê-los mais rápido.
5. Ganho com base (faixa de horas ou de dias da ficha); sem base, "a medir".
6. Rótulos fechados de aplicação de IA (extração de dados de documentos, classificação e triagem, sumarização e linha
   do tempo, redação assistida de minuta, cálculo e conferência automática, verificação de conformidade,
   monitoramento de prazos e alertas, busca de precedentes e normas, automação de tramitação, painel e indicadores).

### Ancoragem (versão 2, obrigatória)

- **Tempo só da tabela de fatos.** Não use duração de estadia nem calcule intervalos, somas ou proporções novas.
- **Cada bloco cita os fatos que usa**: `fatos_sintese`, `fatos_leitura_metricas`, `fatos_variabilidade` no topo e
  `fatos_usados` em `gargalo`, em cada desperdício, oportunidade e atividade.
- Número seguido de "du" tem de ser **valor de um fato citado**. Demais números: valor de fato citado ou número
  presente na ficha do processo (ou no procedimento, no tipo sem piloto).
- Data completa só se estiver nos fatos, numa peça, no texto das peças ou na análise por peça.
- Mediana da carteira: diga se é dos nativos ou de todos.
- Ficam fora da checagem: identificadores de peça e norma, ordinais e anos.

### Coorte (versão 3)

- Ao citar uma mediana, diga que é mediana e de quê ("mediana de 19 du de espera antes da atividade, em 28
  ocorrências"). **Não some nem divida medianas.**
- A `sintese` diz a situação do código (procedimento, indicativo, estudo de caso).
- Variabilidade = dispersão na coorte (q1 × q3, máximo, casos com laço, número de caminhos), não típico × crítico.
- Processos sem trilha não têm espera antes da 1ª atividade nem lead time: diga isso quando forem a maioria.
- Horas são estimativa (hipótese até a calibração); se vieram de dois modelos, use como ordem de grandeza.

## O carimbo

`validar_avaliacao.py --carimbar` grava em `avaliacao_<cod>.json` a impressão digital (sha-256 dos pares id → valor)
da tabela de fatos validada (`validado_contra.fatos_sha`). O pipeline roda `validar_avaliacao.py --exigir-carimbo`
antes do site: **se qualquer fato mudou depois do carimbo, o pipeline para** e aponta a avaliação a rever.

> **Falha real (F4).** Duas regenerações simultâneas e uma regra de tempo alterada deixaram avaliações com números de
> uma versão anterior dos fatos. O carimbo e a trava de execução única fecharam essa porta.

Ao mudar uma regra de tempo: rode o pipeline; o portão das avaliações falha pelo carimbo; revise **o que o validador
aponta**; valide até 0; só então carimbe. **Nunca carimbe sem revisar.** Exceção conferida: quando os fatos novos só
se somam aos antigos (no caso, os fatos `coorte.*` acrescentados às avaliações do piloto), confira que nenhum fato
antigo mudou de valor antes de recarimbar (0 diferenças em 8 códigos no caso — [MITIGACOES.md](../MITIGACOES.md)).

## Saídas e formato

`saida/bpmn/avaliacao_<cod>.json` com `sintese`, `leitura_metricas`, `gargalo` (onde, evidência, atividades),
`variabilidade`, `desperdicios[]` (tipo Lean, evidência, atividades, severidade), `atividades{tN}` (valor,
justificativa, potencial e tipos de IA, aplicação, ganho esperado, controle humano, melhoria Lean),
`oportunidades[]` (categoria IA / Lean / IA + Lean, impacto, esforço, pré-requisitos, riscos),
`indicadores_sugeridos`, `perguntas_validacao`, listas de fatos e `validado_contra`. O site e
[`docs/AVALIACAO_ASIS.md`](../AVALIACAO_ASIS.md) são gerados a partir delas por `gerar_site.py`.

## Portão de qualidade

- `validar_avaliacao.py` (0 problema) e `--exigir-carimbo` no pipeline.
- Testes: `test_validador_aceita_texto_ancorado`, `test_validador_barra[...]` (número sem fato, du recalculado, data
  sem lastro, mediana sem dizer de quê…), `test_validador_barra_tempo_medido_no_descritivo`,
  `test_validador_exige_entrada_para_cada_tarefa_do_modelo`, `test_validador_sem_caso_piloto_usa_numeros_da_coorte`,
  `test_carimbo_invalida_quando_fato_muda`, `test_avaliacao_ancorada_e_carimbada`.
- O validador **não pega sentido errado** (fato certo lido ao contrário, causalidade inventada). Isso só a verificação
  independente pega (F5). Critério: alucinação ≤ 2% e nenhuma em número que sustente conclusão; imprecisão ≤ 10%.
- **Parada humana:** as `perguntas_validacao` e o gargalo declarado vão à unidade dona do processo antes do TO-BE.

## Armadilhas conhecidas

- Ler permanência como espera ("fila de relatoria"): foi o erro mais caro do caso ([02](02_TRILHA_TEMPO_POSSE.md)).
- Apontar a unidade com maior posse como gargalo sem olhar se ela trabalhava ou esperava: no caso, a Procuradoria
  deixou de ser apontada como gargalo num tipo depois da verificação final ([AUDITORIA.md](../AUDITORIA.md)).
- Chamar de "padrão" o que é estudo de caso.
- Tratar o tempo "indeterminado" como espera de terceiros (ou como desperdício da agência). Ele não se separa.
- Somar medianas de atividades para estimar o lead time.

## O que muda em outro Estado

Nada no método. Mudam as lentes que fazem sentido (num órgão sem colegiado, o rito decisório é outro) e os rótulos de
IA, se o órgão já usar alguma ferramenta. As regras de ancoragem e o carimbo valem igual.

## Números do caso AGENERSA (ordem de grandeza)

| Item | Valor | Origem |
|---|---|---|
| Avaliações: afirmações e erro por rodada | 909 afirmações, 4,7% sem lastro + contradito (rodada 1) → 835, 0,4% (rodada 2, fatos + validador) → 371 verificadas, 1,3% e nenhuma sem lastro (rodada 3) | [AUDITORIA.md](../AUDITORIA.md) |
| Cálculo errado por rodada | 3,9% → 0,1% → 0,5% | idem |
| Portfólio avaliado | 160 atividades em 13 processos; 56 com potencial alto de IA, 88 médio; 44 agregam valor, 103 necessárias sem valor, 13 não agregam | [AVALIACAO_ASIS.md](../AVALIACAO_ASIS.md) |
| Achado transversal | o gargalo não é a redação da relatoria; aparece o "processo parado sem dono" | [AUDITORIA.md](../AUDITORIA.md) |
