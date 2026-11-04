# Especificação do benchmarking (fase 3)

Objetivo: casos de estado da arte, no Brasil e no mundo, **documentados em fontes verificáveis**, que orientem a
melhoria dos processos da AGENERSA em quatro fases:

1. **Fase 1 — ajuste do fluxo**, sem tecnologia nova: eliminar, combinar, reordenar e simplificar; paralelizar; prazos-padrão; dono do processo; pauta contínua.
2. **Fase 2 — automação de regras e dados** na atividade-fim: cálculo, conferência, alertas, documentos padronizados, integração de sistemas.
3. **Fase 3 — automação com IA**: extração de dados de documentos, avaliação qualitativa assistida, redação de minutas.
4. **Fase 4 — controles de qualidade, indicadores e metas automatizados.**

## Camadas de fonte (nunca misturar)

- `cientifica`: artigo revisado por pares, capítulo acadêmico, tese ou dissertação, com DOI ou handle. O DOI precisa
  ser conferido no Crossref (`https://api.crossref.org/works/<doi>`) ou no OpenAlex (`https://api.openalex.org/works/doi:<doi>`).
  Busca: OpenAlex API, Semantic Scholar API (`https://api.semanticscholar.org/graph/v1/paper/search?query=...`),
  SciELO, Google Acadêmico.
- `oficial`: documento publicado por regulador ou organismo, como OCDE, Banco Mundial, BID, Ofwat, Ofgem, ARERA,
  ERSAR, ANEEL, ANP, ARSESP, ANA, TCU, CGU ou ABAR. Precisa de URL oficial que abra.

Meta: pelo menos 60% dos casos de cada família na camada `cientifica`.

## Critério de inclusão

Prática concreta, aplicada por um órgão identificado, com **resultado medido ou avaliado** (antes × depois, comparação,
avaliação de impacto, ou ao menos resultado operacional reportado). Fica de fora:

- opinião sem caso;
- marketing de fornecedor;
- prática sem resultado;
- notícia de jornal.

## Verificação (obrigatória, feita por você antes de incluir)

- `trecho`: citação literal curta (até 40 palavras, no idioma original) tirada do resumo ou do texto que você
  efetivamente leu (resumo do OpenAlex/Crossref/Semantic Scholar ou página do publicador), que sustente o
  `resultado_reportado`.
- Se não conseguir ler texto que sustente o resultado, não inclua o caso. Nunca escreva DOI, autor, ano ou número de
  memória.
- Para cada caso, registre `verificado_em` com a URL de onde o trecho foi lido.

## Formato da saída: `saida/fase3/benchmark/<familia>.json`

```json
{
  "familia": "tarifa",
  "processos": ["P01"],
  "pergunta": "o que a família procura, em uma frase",
  "estrategia_busca": ["consultas usadas e bases"],
  "casos": [
    {
      "id": "B-tarifa-01",
      "pratica": "nome curto da prática, em português",
      "descricao": "o que foi feito, 2 a 4 frases, em português",
      "contexto": {"pais": "", "orgao": "", "setor": "", "periodo": ""},
      "resultado_reportado": "o resultado, em português, com o número quando houver",
      "metrica": {"nome": "", "antes": null, "depois": null, "unidade": "", "variacao_pct": null},
      "fonte": {"camada": "cientifica|oficial", "autores": "", "ano": 0, "titulo": "", "veiculo": "",
                "doi": "", "url": "", "trecho": "", "verificado_em": ""},
      "nivel_evidencia": "avaliacao_quantitativa|quase_experimental|estudo_de_caso|revisao_sistematica|relato_oficial",
      "fase_melhoria": [1],
      "atividades_alvo": ["P01:t2"],
      "aplicabilidade": "por que serve (ou não) à AGENERSA, considerando a situação atual descrita na avaliação",
      "parametro_ganho": "o que o caso permite usar como parâmetro de ganho no TO-BE (ex.: redução de 30% no tempo de análise), ou null",
      "limitacoes": ""
    }
  ],
  "lacunas": ["o que procurou e não achou com evidência"]
}
```

Leia antes `saida/bpmn/avaliacao_<Pxx>.json` (gargalo, desperdícios, oportunidades) e `saida/bpmn/modelo_<Pxx>.json`
(atividades) dos processos da família, para buscar o que responde aos problemas reais e preencher `atividades_alvo`.
Alvo: 10 a 15 casos por família, cobrindo as quatro fases.
