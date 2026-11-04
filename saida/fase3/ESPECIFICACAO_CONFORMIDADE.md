# Especificação da conformidade legal (fase 3)

Objetivo, por processo:

1. Levantar a legislação, as normas contratuais e as decisões que regem o processo.
2. Transformar cada obrigação em requisito testável.
3. Medir na coorte se o processo atual cumpre cada requisito.
4. Definir os testes de auditoria que a fiscalização (controle interno, auditoria, órgão de controle) deve aplicar.

## Fontes

- **Candidatos:** `saida/fase3/candidatos_normas_<cod>.json`. São as normas-raiz mais citadas nas peças da coorte e
  nas deliberações do mesmo tipo de toda a agência, cada uma com os dispositivos, as atividades em que aparecem e,
  quando existe, o caminho do texto integral (`texto.txt`).
- **Base do Especialista AGENERSA, só leitura:** `comum.BASE_NORMAS` (perfil; ver `docs/adaptacao/BASE_NORMATIVA.md`); os caminhos `txt` são relativos a `comum.TEXTOS_NORMAS`.
  - Tabelas `normativo` (instruções normativas, leis, decretos, contratos, aditivos, resoluções) e `legislacao_externa`. Coluna `txt` = caminho relativo à pasta do Especialista.
  - Tabela `contratos_concessao`.
  - Tabelas `deliberacoes`, `dispositivos_legais`, `determinacoes` e `sumarios` (entendimento consolidado por tema, em `markdown`).
  - Para achar trechos: tabela `chunks` (colunas `numero`, `texto`, `fonte`) e o índice FTS5 `deliberacoes_fts`.
- **Conferência:** `python scripts/verificar_normas.py <cod>` confere cada trecho contra o texto da base e lista os de fonte externa. Rode até não sobrar falha.
- **Norma que não está na base** (por exemplo, a Lei estadual nº 4.556/2005, de criação da AGENERSA, se faltar): use
  a fonte oficial (ALERJ, Planalto, DOERJ) e registre a URL. Ela será conferida à parte.

## Regras

1. Todo trecho é literal, copiado do texto que você leu, com até 60 palavras. Nunca escreva artigo, prazo ou número de memória.
2. Prefira a norma vigente. Se houver sucessão (norma revogada ou alterada), registre as duas e o período de cada uma, porque os casos da coorte vão de 2019 a 2026.
3. Cláusula contratual varia por concessionária. Indique em `abrangencia` a quais concessionárias ou contratos ela se aplica.
4. Decreto do SEI e da assinatura eletrônica não é base normativa do processo.
5. Escreva em português, com acentuação correta. Não use nomes de pessoas.

## Formato: `saida/fase3/normas_<cod>.json`

```json
{
  "codigo": "P01",
  "normas": [
    {"id": "N-P01-01", "norma": "Lei estadual nº 4.556/2005", "dispositivo": "art. 4º, II",
     "trecho": "texto literal", "fonte": {"base": "normativo|legislacao_externa|deliberacoes|externa", "id_canonico": "LEI-4556/2005",
     "txt": "data/txt/...", "url": ""}, "vigencia": "desde 2005", "abrangencia": "todas as concessões",
     "obrigacao": "o que a norma obriga, em uma frase", "responsavel": "unidade ou ator",
     "prazo": {"valor": 30, "unidade": "dias_uteis|dias_corridos|anos|null", "contagem": "a partir de quê"},
     "atividades": ["t2"]}
  ],
  "requisitos": [
    {"id": "R-P01-01", "normas": ["N-P01-01"], "exigencia": "frase verificável",
     "parametro": "o parâmetro legal (prazo, ordem, ato obrigatório)", "atividades": ["t7", "t8"],
     "criticidade": "alta|media|baixa", "evidencia_sei": "que peça comprova",
     "teste": {"tipo": "...", "...": "..."},
     "interpretacao": "opcional: leitura da norma que o teste adota, quando houver mais de uma"}
  ],
  "programa_auditoria": [
    {"id": "A-P01-01", "requisitos": ["R-P01-01"], "objetivo": "", "criterio": "", "fonte_dados": "",
     "populacao": "", "amostra": "", "frequencia": "", "achado_tipo": "", "automatizado": true}
  ]
}
```

## Tipos de teste (o que `scripts/conformidade.py` sabe computar)

Cada caso da coorte é uma lista de eventos `(atividade do modelo, data da peça, prazo concedido na peça em dias)`.
As datas são as de juntada das peças. Todo teste devolve, por caso, um destes resultados: `conforme`,
`nao_conforme`, `sem_evidencia` ou `nao_aplicavel`.

| tipo | campos | aplica-se quando | conforme se |
|---|---|---|---|
| `precede` | `a`, `b` | `b` ocorre | há `a` com data ≤ a 1ª data de `b` |
| `exige` | `se` (lista), `entao` (lista) | alguma atividade de `se` ocorre | alguma atividade de `entao` ocorre |
| `prazo_max` | `de`, `ate`, `max`, `unidade` (`du` ou `dc`); `de_ocorrencia` opcional (`primeira`, padrão, ou `ultima`) | `de` ocorre antes da 1ª `ate` | (1ª `ate` − 1ª `de`, ou a última `de` antes dela quando o prazo reabre a cada rodada, como a deliberação depois de nova rodada de razões finais) ≤ `max` |
| `prazo_min` | `de`, `ate`, `min`, `unidade` | `de` e `ate` ocorrem | (1ª `ate` − última `de` anterior a ela) ≥ `min` |
| `prazo_concedido_min` | `atividade`, `min` | `atividade` ocorre | toda peça da atividade com prazo lido concede ≥ `min` dias (sem prazo lido → `sem_evidencia`) |
| `duracao_max` | `ate`, `max`, `unidade` (`anos`, `du`, `dc`); `de` opcional (atividade; padrão = 1º evento do caso) | `ate` ocorre | (1ª `ate` − início) ≤ `max` |
| `manual` | `procedimento` | — | não é computado; descreva como testar |

`du` = dias úteis do calendário do projeto (feriados do RJ); `dc` = dias corridos. Use os ids de atividade de
`saida/bpmn/modelo_<cod>.json`. Requisito que dependa de dado fora do SEI (por exemplo, a data de publicação no DOERJ
quando não há peça de publicação) vai como `manual`.

Todo prazo concedido à parte (defesa, manifestação, razões finais) também vira um requisito `prazo_min` entre o ofício
que o abre e o ato seguinte. É ele que impede o TO-BE de tratar essa espera como desperdício (`validar_tobe.py`).
