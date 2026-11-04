# Mapeamento do processo de fiscalização técnica de campo — SEI-480002/001314/2024

Mapeamento, avaliação e proposta de melhoria de **um processo real do SEI-RJ**: a fiscalização técnica de campo de
saneamento conduzida pela CASAN (AGENERSA), com passagem pela Secretaria Executiva e pela Procuradoria. O trabalho
aplica, sobre esse único processo, a metodologia de mapeamento de processos a partir do registro do SEI
(andamentos, documentos juntados e texto das peças) do repositório do curso
[mapeamento-processos-sei](https://github.com/RaulAraujoSilva/mapeamento-processos-sei).

## Comece por aqui

| Para quem | Arquivo |
|---|---|
| Gestão e equipe | [Relatório gerencial em PDF](docs/relatorio/Relatorio_Mapeamento_Fiscalizacao_SEI-480002-001314-2024.pdf) |
| Ver o fluxo | [Diagrama do processo (PNG)](docs/relatorio/bpmn_P06.png) · [BPMN editável](saida/bpmn/P06.bpmn) (abre em [bpmn.io](https://demo.bpmn.io)) |
| Navegar no mapeamento | `docs/site/index.html` (baixe e abra no navegador) |
| Como foi feito, resultados e ressalvas | [docs/CASO_SEI-480002-001314-2024.md](docs/CASO_SEI-480002-001314-2024.md) |

## O que o mapeamento entrega

| Fase | Produto | Onde |
|---|---|---|
| 0. Trilha | Passagens por unidade, posse, esperas, documentos atribuídos e indicadores | `saida/estadias.csv`, `posse.csv`, `documentos.csv`, `processos_indicadores.csv`, `Mapeamento_SEI_Fase0.xlsx` |
| 1. Conteúdo e modelo | Ficha de trabalho por peça, esforço (piso–teto), BPMN AS-IS, vínculos atividade → peças, fatos | `saida/fichas_trabalho.*`, `esforco_documentos.csv`, `saida/bpmn/` |
| 2. Procedimento | Coorte de um caso, com situação "estudo de caso" | `saida/fase2/` |
| AS-IS | Avaliação Lean com gargalo, desperdícios e oportunidades, validada e verificada | `saida/bpmn/avaliacao_P06.json`, `docs/AVALIACAO_ASIS.md` |
| 3. Conformidade e TO-BE | 30 dispositivos legais com trecho literal, 17 requisitos, 14 melhorias em 3 fases simuladas em 3 cenários, indicadores e metas | `saida/fase3/`, `docs/BENCHMARKING.md` |
| 4. Priorização | Matriz de automação ("reavaliar com dados": um caso não mede volume) | `saida/fase4/`, `docs/PRIORIZACAO_AUTOMACAO.md` |
| Verificação | Reclassificação às cegas, auditoria de 30 fichas, verificação afirmação por afirmação | `saida/auditoria/` |

## Ressalvas principais

- **Um único processo, ainda em andamento.** Os números descrevem este caso, não a média da fiscalização.
- **Horas, custos e ganhos são hipóteses** até a calibração com os servidores.
- **Concessionária a esclarecer.** O SEI registra a Iguá Rio de Janeiro como interessada, mas as peças tratam da
  Águas do Rio — Bloco 1.
- As respostas da concessionária não estão entre os documentos públicos do processo.

## Reproduzir

Python 3.12. O perfil deste caso é `rj_agenersa_igua`, que herda o perfil da AGENERSA.

```bash
pip install -r requirements.txt -r requirements-coleta.txt
export PERFIL=rj_agenersa_igua
python -m pytest tests
```

Para refazer do zero:

1. Coleta: `python -m coleta.coletar --perfil RJ "<link da pesquisa pública>"` e depois `python -m coleta.documentos --perfil RJ`. Os dados vão para `dados/`, fora do git.
2. Pipeline: `cd scripts && python pipeline.py`.
3. Etapas de leitura e julgamento: [docs/CASO_SEI-480002-001314-2024.md](docs/CASO_SEI-480002-001314-2024.md) e
   `ferramentas_caso/`.

A fase 3 usa a base normativa da AGENERSA (variável `BASE_NORMAS`), que não acompanha o repositório. A metodologia
completa está em [`docs/metodologia/`](docs/metodologia/00_VISAO_GERAL.md) e as instruções para IA em
[`AGENTS.md`](AGENTS.md).

## Dados pessoais

`dados/`, com o texto integral das peças, fica fora do git. As saídas passam pelo portão
`scripts/sanear_saida.py --verificar`, que roda também no CI.
