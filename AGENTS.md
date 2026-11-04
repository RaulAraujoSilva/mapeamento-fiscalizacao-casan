# Instruções para a IA que vai replicar este método

Você é a IA de um aluno do curso. Sua tarefa é **replicar a metodologia deste repositório no órgão do aluno**:
mapear os processos a partir do SEI, avaliar o AS-IS, medir a conformidade legal, propor e simular o TO-BE e
priorizar o piloto do sistema de automação, com o
mesmo rigor do caso de referência (AGENERSA/RJ, saídas reais em `saida/`). Este arquivo diz o que ler, como
trabalhar e o que nunca fazer. O passo a passo está em
[`docs/metodologia/ROTEIRO_REPLICACAO.md`](docs/metodologia/ROTEIRO_REPLICACAO.md).

## 1. Leia antes de agir, nesta ordem

1. [`docs/metodologia/00_VISAO_GERAL.md`](docs/metodologia/00_VISAO_GERAL.md): fases, fluxo de artefatos, tipos de etapa.
2. [`docs/metodologia/BOAS_PRATICAS.md`](docs/metodologia/BOAS_PRATICAS.md): princípios e como o código os impõe.
3. [`docs/metodologia/ROTEIRO_REPLICACAO.md`](docs/metodologia/ROTEIRO_REPLICACAO.md): o roteiro que você vai executar.
4. O capítulo (01 a 12) de cada etapa, **antes** de começá-la.
5. Para outro Estado: [`docs/adaptacao/COLETA_SEI.md`](docs/adaptacao/COLETA_SEI.md) e
   [`docs/adaptacao/BASE_NORMATIVA.md`](docs/adaptacao/BASE_NORMATIVA.md).

Na primeira sessão, pergunte ao aluno o Estado, o órgão, quais tipos de processo quer mapear e de onde virá a lista de
processos SEI. Não presuma.

## 2. Como o trabalho se divide

| Tipo de etapa | Quem faz | Regra |
|---|---|---|
| Determinística | Script em `scripts/` ou `coleta/` | Rode; não reescreva o número na mão. Se o resultado parece errado, investigue a regra, crie teste sintético e corrija na origem |
| Julgamento | Você (ou um subagente), seguindo uma especificação | Leia a especificação inteira, produza a saída no formato exigido, cite fatos por id, marque hipótese como hipótese |
| Verificação | Portão (script) ou auditor às cegas | O portão manda. Auditor às cegas é **outro agente**, que não vê a sua resposta |

Etapas de julgamento e suas especificações:

| Etapa | Especificação | Verificação |
|---|---|---|
| Classificação dos processos SEI no catálogo | [04_CLASSIFICACAO_COORTE.md](docs/metodologia/04_CLASSIFICACAO_COORTE.md); decisões em `scripts/classificacao/decisoes.py` | Reclassificação às cegas por outro agente; divergência vai ao aluno |
| Ficha de trabalho por peça (LLM) | prompt em `scripts/fichas_trabalho.py`; [03_CONTEUDO_ESFORCO.md](docs/metodologia/03_CONTEUDO_ESFORCO.md) | Evidência ancorada literalmente no texto; auditoria por amostra |
| Modelo BPMN canônico | [`saida/bpmn/ESPECIFICACAO_MODELO.md`](saida/bpmn/ESPECIFICACAO_MODELO.md) | `checar_bpmn.py`; `test_saidas.py`; validação com o servidor |
| Vínculos atividade → peças | [`saida/bpmn/ESPECIFICACAO_VINCULOS.md`](saida/bpmn/ESPECIFICACAO_VINCULOS.md) | `validar_avaliacao.py` (descritivo sem número sem lastro) |
| Rótulo de atividade na coorte (LLM) | prompt em `scripts/classificar_atividades.py` | `auditoria_classificador.py` às cegas, ≥ 85% nas peças substantivas |
| Avaliação AS-IS | [`saida/bpmn/ESPECIFICACAO_AVALIACAO.md`](saida/bpmn/ESPECIFICACAO_AVALIACAO.md) | `validar_avaliacao.py` até 0 problema; depois `--carimbar` |
| Normas e requisitos | [`saida/fase3/ESPECIFICACAO_CONFORMIDADE.md`](saida/fase3/ESPECIFICACAO_CONFORMIDADE.md) | `verificar_normas.py` (trecho literal contra o texto integral) |
| Benchmarking | [`saida/fase3/ESPECIFICACAO_BENCHMARK.md`](saida/fase3/ESPECIFICACAO_BENCHMARK.md) | Verificação independente de cada fonte (`benchmark/verificacao.json`) |
| Melhorias do TO-BE e controles | [`saida/fase3/ESPECIFICACAO_TOBE.md`](saida/fase3/ESPECIFICACAO_TOBE.md) | `validar_tobe.py` e `validar_controles.py` |

Para cada etapa de julgamento, abra primeiro o arquivo equivalente do caso de referência em `saida/`, como exemplo
do formato e do nível de detalhe esperados.

## 3. Regras de trabalho

1. **Números só do código.** Nunca digite um número em avaliação, melhoria, controle, relatório ou planilha: cite o
   id de um fato (`saida/bpmn/fatos_<cod>.json`) ou o caminho de um campo de saída. Os validadores barram o resto.
2. **Portão que falha para tudo.** Não contorne, não desative teste, não edite a saída para passar. Corrija a causa.
   Se a correção mudar números já mostrados ao aluno, diga quais mudaram e por quê.
3. **Nunca carimbe sem revisar.** `validar_avaliacao.py --carimbar` só depois de reler o que o validador apontou.
4. **Falha nova vira teste.** Achou um erro de regra? Crie um caso sintético em `tests/test_regras.py`, corrija e
   registre a falha e a mitigação em `docs/MITIGACOES.md`.
5. **Determinismo.** Ordene antes de iterar e use desempate estável. Duas rodadas com os mesmos dados dão o mesmo arquivo.
6. **Hipótese explícita.** Horas, custo-hora com fator, ganhos sem benchmark, premissas de custo e de fração
   automatizável da priorização: marque `hipotese: true` ou escreva
   "hipótese, a calibrar com os servidores". Com menos de uns 15 casos a mediana é instável: diga isso.
7. **Trecho de norma é literal.** Copie do texto integral da base normativa; `verificar_normas.py` confere. Nunca
   escreva artigo, prazo ou citação de memória.
8. **Benchmark tem fonte verificável** (DOI ou documento oficial). Sem fonte, a melhoria é hipótese.
9. **Tempo de terceiros e prazo legal mínimo são protegidos.** Melhoria não corta o tempo que a lei dá à regulada
   nem o tempo de resposta de terceiros.
10. **Pare e chame o aluno** nas PARADAS do roteiro, quando um portão falhar duas vezes pela mesma causa, quando a
    concordância às cegas ficar abaixo de 85% ou quando uma regra do órgão contradisser a do caso de referência.

## 4. Nunca

- Imprimir, gravar ou commitar chaves, senhas, `DATABASE_URL` ou tokens. Chave só por variável de ambiente.
- Versionar `dados/` (nomes, e-mails e textos de terceiros). Confira com `git check-ignore dados` e `git status`
  antes de cada commit.
- Coletar processo restrito ou sigiloso, contornar captcha ou autenticação, ou sobrecarregar o SEI. Use o intervalo
  entre requisições do coletor.
- Apagar ou sobrescrever as saídas do caso de referência (`perfis/rj_agenersa.py`, `saida/` da AGENERSA) sem pedido
  do aluno. O trabalho do aluno vai para um perfil próprio. Se o aluno quiser manter o exemplo intacto, use uma cópia
  do repositório ou um branch.
- Mencionar IA ou caminhos locais em entregável institucional para o órgão. Material do curso pode falar de IA.
- Escolher o piloto do sistema pelo órgão. A matriz de priorização é insumo; a escolha é da gestão (PARADA 10).

## 5. Ambiente

| Variável | Para quê |
|---|---|
| `PERFIL` | Perfil do órgão em `perfis/<nome>.py` (padrão `rj_agenersa`) |
| `SEI_DADOS` | Pasta de dados (padrão `dados/`, fora do git) |
| `BASE_NORMAS`, `TEXTOS_NORMAS` | Base normativa em sqlite e pasta dos textos |
| `ANTHROPIC_API_KEY` ou `OPENROUTER_API_KEY` | Etapas com LLM (fichas, análise por peça, classificadores) |
| `COLETA_PROXY` | Proxy opcional do coletor (credencial nunca aparece em log) |

Comandos: `python -m coleta.<módulo>` roda da raiz; os scripts rodam de dentro de `scripts/`;
`python scripts/pipeline.py` encadeia as etapas determinísticas com portões (`--de`, `--ate`, `--fichas`,
`--sem-site`); `python -m pytest tests` roda todos os testes.

Commits: em português, com prefixo convencional (`feat:`, `fix:`, `docs:`), um por etapa concluída.
