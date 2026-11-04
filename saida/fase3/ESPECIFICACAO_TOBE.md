# Especificação do TO-BE (fase 3)

Cada processo recebe uma proposta de melhoria em três fases cumulativas. Cada fase parte da anterior:

1. **Fase 1 — ajuste do fluxo.** Organização e regras de trabalho, sem tecnologia nova.
2. **Fase 2 — automação de regras e dados** na atividade-fim.
3. **Fase 3 — automação com IA.** Extração de dados de documentos, avaliação qualitativa assistida e redação de minutas, sempre com revisão humana.

Acompanha as três fases a **camada de controles**: indicadores, metas e alertas automatizados, em `controles_<cod>.json`.

## Entradas

| Arquivo | O que traz |
|---|---|
| `linha_base_<cod>.json` | Linha de base congelada |
| `../fase2/casos_<cod>.json` | Linha do tempo de cada caso nativo |
| `../bpmn/fatos_<cod>.json` | Números citáveis |
| `normas_<cod>.json` e `conformidade_<cod>.json` | Requisitos legais e quanto a coorte cumpre |
| `benchmark/*.json` | Casos de referência |

## Formato: `melhorias_<cod>.json`

```json
{
  "codigo": "P01",
  "melhorias": [
    {"id": "M-P01-01", "fase": 1, "titulo": "frase curta", "descricao": "o que muda no processo",
     "atividades": ["t8"],
     "efeito": {"tipo": "teto_espera", "atividades": ["t8"], "parte": "sem_unidade|toda",
                "cenarios": {"conservador": 20, "esperado": 10, "otimista": 5}},
     "fatos": ["coorte.t8.espera_antes"], "requisitos": ["R-P01-03"], "benchmark": ["B-transversal-04"],
     "hipotese": false, "justificativa_parametro": "de onde vem cada valor dos cenários",
     "riscos": "", "dependencias": "", "controle_humano": "só na fase 3"}
  ]
}
```

- `fatos`: pelo menos um. É a evidência AS-IS do problema.
- `requisitos`: os requisitos legais que limitam a mudança. Pode ficar vazio se nenhum se aplica.
- `benchmark`: ids dos casos de referência. Se vazio, `hipotese` tem de ser `true` e a justificativa diz de onde vem o parâmetro.

## Tipos de efeito (o que `scripts/simular_tobe.py` aplica em cada caso nativo)

| tipo | campos | efeito |
|---|---|---|
| `teto_espera` | `atividades`, `parte` (`toda` ou `sem_unidade`), valor = teto em du | A espera antes da atividade (ou só a parte em que o processo ficou sem unidade) fica limitada ao teto |
| `reduz_espera_pct` | `atividades`, valor = % | Espera antes × (1 − %) |
| `reduz_execucao_pct` | `atividades`, valor = % | Execução × (1 − %) |
| `reduz_horas_pct` | `atividades`, valor = % | Horas piso e teto × (1 − %) |
| `elimina_laco_pct` | `atividades`, valor = % | Nas ocorrências repetidas da atividade (2ª em diante), espera, execução e horas × (1 − %) |
| `paralelo` | `a`, `b` | Ocorrência de `b` logo depois de `a`: a espera antes de `b` vai a zero (correm juntas) |
| `reduz_cauda_pct` | valor = % | Tempo depois da última atividade (até o encerramento) × (1 − %) |

A parte da espera que é tempo de resposta de terceiro (ofício com prazo, da emissão até a resposta ou o prazo + 5 du,
campo `espera_antes_terceiros_du` de cada ocorrência) não é cortada por `teto_espera` nem por `reduz_espera_pct`: o teto
vale para a parte da agência. `reduz_cauda_pct` só se aplica aos casos encerrados; no caso aberto a cauda vai até a data de
corte, não até o encerramento. Antes de propor, leia `insumo_tobe_<cod>.md` (`scripts/insumo_tobe.py`): onde está o tempo
por atividade e unidade, fatos citáveis, esperas protegidas, conformidade, oportunidades da avaliação e benchmarking.

Os valores vêm por cenário: `conservador`, `esperado` e `otimista`. Atividade criada no TO-BE (por exemplo, um controle automático) não entra na simulação. Ela só aparece no modelo TO-BE.

## Regras do validador (`scripts/validar_tobe.py`)

1. Toda melhoria cita pelo menos 1 fato existente em `fatos_<cod>.json`. Todo requisito e todo caso de benchmark citado precisa existir.
2. Sem benchmark, a melhoria é obrigatoriamente `hipotese: true`.
3. Não pode haver `teto_espera` abaixo de prazo mínimo legal nem `reduz_espera_pct` na espera protegida por um requisito `prazo_min` (por exemplo, o prazo de defesa ou de razões finais). Prazo de defesa não é desperdício.
4. Os valores dos cenários são monotônicos: conservador ≤ esperado ≤ otimista em ganho.
5. Toda melhoria de fase 3 tem o campo `controle_humano` preenchido (quem revisa, o que confere, amostragem).
6. Toda atividade citada existe em `modelo_<cod>.json`.

## Saída da simulação: `resultado_tobe_<cod>.json`

Para cada fase cumulativa e cada cenário:

- lead time por caso (mediana, q1 e q3);
- horas por caso;
- totais anuais (horas, FTE-equivalente e R$, com o volume e o custo-hora da linha de base);
- ganho contra a linha de base.

Os números entram nos textos só como fatos `tobe.*`, com o mesmo princípio de ancoragem das avaliações.

## Fases 2 e 3 (acrescentar ao mesmo `melhorias_<cod>.json`, sem alterar as de fase 1)

- **Fase 2 — automação de regras e dados.** Sem IA. Exemplos: painel de prazos e alertas sobre o andamento do SEI (idade
  do processo por unidade, prazo vencido); cálculo por regra (fórmula paramétrica do reajuste, conferência de faturas e
  indicadores contra limites); geração de ofício, notificação e despacho por modelo com campos preenchidos dos dados do
  processo; testes de conformidade (`normas_<cod>.json`) rodando de forma contínua. Diga em `dependencias` o dado ou
  acesso necessário (relatórios ou API do SEI, dados das concessionárias, sistema da Ouvidoria).
- **Fase 3 — automação com IA.** Extração de dados de peças (relatório da concessionária e do verificador, fatura,
  defesa, manifestação), triagem e pré-análise, avaliação qualitativa assistida e minuta (ofício, parecer, relatório,
  voto) com citação verificada contra a base normativa. A agência já tem dois insumos para isso: a ferramenta de minuta
  de relatório a partir dos autos do SEI (Relator de Voto) e a base de normas e deliberações (Especialista). Toda
  melhoria de fase 3 tem `controle_humano`: quem revisa, o que confere (citação, número, conclusão), amostragem.
- **Horas.** O ganho em horas (`reduz_horas_pct`, `reduz_execucao_pct`) é **líquido** do tempo de revisão humana: se a
  minuta economiza a redação, mas toda minuta é revista, o percentual desconta a revisão. Diga a conta em
  `justificativa_parametro`. Resultado de benchmark em outro setor ou ferramenta (tribunal, saúde, uso geral) é teto,
  não meta: o esperado fica abaixo e a transferência é explicada.
- **Contagem dupla.** As fases se compõem. Um alerta de fase 2 sobre uma espera que a fase 1 já limitou não soma nada,
  a menos que baixe o teto; se baixar, justifique pela nova capacidade (por exemplo, o painel mostra o vencimento).

## Análise de sensibilidade (no resultado)

`resultado_tobe_<cod>.json` traz, para a última fase, no cenário esperado, o efeito de retirar cada melhoria: quanto o
lead mediano, o lead médio e as horas médias pioram. As melhorias de maior peso são as que mais precisam de validação.

## Controles, indicadores e metas: `controles_<cod>.json`

```json
{
  "codigo": "P01",
  "indicadores": [
    {"id": "I-P01-01", "nome": "Lead time do pleito à deliberação", "definicao": "fórmula exata (de que evento a que evento, unidade, estatística)",
     "calculo": {"tipo": "lead|espera_antes|posse_sem_unidade|laco|horas|conformidade|estoque_idade", "atividades": ["t8"], "requisito": "R-P01-05"},
     "fonte_dados": "andamentos do SEI | peças do SEI | sistema X", "frequencia": "mensal",
     "linha_base": {"valor": 337.5, "unidade": "du", "fato": "coorte.caso.lead.mediana"},
     "metas": [{"fase": 1, "valor": 156.3, "origem": {"tipo": "simulacao", "ref": "fases.1.esperado.lead.mediana"}},
               {"fase": 2, "valor": 30, "origem": {"tipo": "norma", "ref": "R-P01-05"}}],
     "alerta": {"regra": "quando dispara", "destinatario": "unidade ou função"},
     "melhorias": ["M-P01-01"], "responsavel": "unidade"}
  ],
  "controles_qualidade_ia": [
    {"id": "Q-P01-01", "melhorias": ["M-P01-12"], "verificacao": "o que se confere em cada saída", "amostragem": "100% | n por mês",
     "criterio_aceite": "", "indicador": "taxa de correção, de citação inválida...", "meta": "", "responsavel": ""}
  ],
  "auditoria_continua": ["A-P01-01"]
}
```

- `linha_base.fato` existe em `fatos_<cod>.json` e `linha_base.valor` é o valor dele (arredondado).
- Origem da meta: `simulacao` (`ref` é o caminho em `resultado_tobe_<cod>.json` e `valor` é o valor desse caminho),
  `norma` (`ref` é um requisito de `normas_<cod>.json`) ou `benchmark` (`ref` é um caso). Nada de meta sem origem.
- Indicador de conformidade (`calculo.tipo = conformidade`): a linha de base é o `pct_conforme` de
  `conformidade_<cod>.json`. Se o requisito é de prazo máximo ou de duração, a meta de cada fase é a conformidade
  simulada (`fases.<f>.esperado.conformidade_temporal.<R>` em `resultado_tobe_<cod>.json`), e a exigência legal (100%)
  vai em `referencia_legal`. Se o TO-BE não chega à exigência, diga em `observacao` o que falta (capacidade, rito, norma).
  O simulador refaz a linha do tempo de cada caso e roda os testes; na fase 0 ele reproduz a conformidade medida.
- Inclua indicadores de qualidade ao lado dos de prazo (o caso de prazo-alvo mostra que prazo sozinho empurra decisões
  para a véspera): por exemplo, recursos e embargos providos, retrabalho, devoluções.
- Toda melhoria de fase 3 tem pelo menos um controle em `controles_qualidade_ia`. `auditoria_continua` lista os testes do
  `programa_auditoria` que passam a rodar de forma automatizada.
- Validador: `scripts/validar_controles.py`.
