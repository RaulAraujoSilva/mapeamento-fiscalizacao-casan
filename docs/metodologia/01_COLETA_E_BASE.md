# 01 — Coleta e base

## Objetivo

Reunir, num formato canônico e igual para qualquer órgão, tudo o que as etapas seguintes leem:

1. o registro dos processos no SEI (processos, andamentos, protocolos);
2. o conteúdo das peças (metadados, texto, análise por peça);
3. os parâmetros do órgão (perfil);
4. o catálogo de processos organizacionais;
5. a base normativa (leis, normas, contratos, deliberações).

Nada daqui em diante lê o SEI diretamente. Se a base estiver errada, todo o resto estará errado com
aparência de precisão. Por isso a coleta termina num portão.

## Entradas

| Entrada | Onde se obtém | Observação |
|---|---|---|
| Lista de processos a coletar | Unidade parceira, relatório do SEI, pesquisa por tipo de processo ou por unidade | No caso AGENERSA, a carteira de um gabinete de conselheiro (251 processos). Ver viés de amostra abaixo |
| Pesquisa Pública do SEI do Estado | Portal do SEI do Estado | Andamentos e documentos públicos; documentos restritos aparecem só como metadado. A busca por número tem captcha, que o coletor **não** automatiza: copie o link de cada processo no navegador ou salve a página |
| Perfil de instalação do SEI | [`coleta/perfil_sei.py`](../../coleta/perfil_sei.py) (`--perfil RJ` ou um JSON do seu Estado) | Rótulos, cabeçalhos e redação dos andamentos da sua instalação, traduzidos para a frase canônica por `RegraAndamento` |
| Perfil do órgão | `perfis/<uf>_<orgao>.py` (caso: [`perfis/rj_agenersa.py`](../../perfis/rj_agenersa.py); roteiro em [`perfis/modelo.py`](../../perfis/modelo.py)), escolhido pela variável de ambiente `PERFIL` | Ver a tabela de parâmetros em "O que muda em outro Estado" |
| Catálogo de processos | [`catalogo/`](../../catalogo/) (caso: P01–P36 em `dados_processos.py`, ondas em `oficina_dados.py`) | Inventário de processos organizacionais do órgão, com nome, macroprocesso e escopo |
| Textos normativos e planilha de deliberações | Portal do órgão, diário oficial, assembleia, Planalto, contratos de concessão | Montados em sqlite por [`scripts/montar_base_normas.py`](../../scripts/montar_base_normas.py); guia em [BASE_NORMATIVA.md](../adaptacao/BASE_NORMATIVA.md) |

O guia passo a passo da coleta é [COLETA_SEI.md](../adaptacao/COLETA_SEI.md). Este capítulo diz o que a metodologia
exige dela.

## Passos

Comandos `python -m coleta.*` rodam da raiz do repositório; os de `scripts/` rodam de dentro de `scripts/`.

1. **Perfil do órgão.** Copie `perfis/modelo.py` para `perfis/<uf>_<orgao>.py`, preencha cada valor com a fonte no
   comentário e exporte `PERFIL=<uf>_<orgao>` antes de rodar qualquer script.
2. **Perfil do SEI.** Abra três ou quatro processos na Pesquisa Pública e compare os rótulos e a redação dos
   andamentos com o perfil (`RJ` já existe). Diferente? Crie o perfil do Estado (cópia de `MODELO` em
   `coleta/perfil_sei.py` ou JSON) com uma `RegraAndamento` por frase local. **Não altere `scripts/comum.py`.**
3. **Trilha:** `python -m coleta.coletar --perfil <UF> --lista processos.txt --intervalo 3` (ou `--html-salvo
   <pasta>` com páginas salvas à mão) → `dados/sei2_dump/processos.tsv`, `andamentos.tsv`, `protocolos.tsv`,
   `observacoes.tsv`, mais `dados/coleta/indice_documentos.csv` e `andamentos_original.csv` (frase original ×
   canônica, para auditar o perfil).
4. **Conteúdo das peças:** `python -m coleta.documentos --perfil <UF> [--processos saida/piloto.csv]` →
   `dados/relator/documentos.parquet`, `doc_text_piloto.parquet`, `cobertura_texto.csv`. Baixe primeiro só o piloto e
   a coorte; o resto basta como metadado.
5. **Análise por peça (LLM):** `python -m coleta.extrair [--processos <csv>] [--limite N]` →
   `dados/relator/extractions.parquet`. Rode antes com `--limite` para medir o custo.
6. **Portão da coleta:** `python -m coleta.validar_coleta --perfil <UF>` e `python -m pytest tests/test_coleta.py`.
   Não siga adiante com falha.
7. **Base normativa** (pode ser em paralelo; só é necessária na fase 3):
   `cd scripts && python montar_base_normas.py --textos ../dados/normas/brutos --deliberacoes ../dados/normas/deliberacoes.csv`.
8. **Catálogo** em `catalogo/`, no formato descrito no topo de `catalogo/dados_processos.py`. Se o órgão não tiver
   inventário, faça um provisório com a área de planejamento antes da classificação
   ([04_CLASSIFICACAO_COORTE.md](04_CLASSIFICACAO_COORTE.md)).

## Formato das saídas (contrato que os scripts leem)

### Tabelas canônicas do SEI — `dados/sei2_dump/` (TSV, separador tabulação, `NULL` = vazio)

| Arquivo | Colunas |
|---|---|
| `processos.tsv` | `id`, `numero`, `tipo`, `interessado`, `data_geracao`, `ultima_unidade`, `data_ultimo_andamento`, `assunto`, `tipo_custom`, `natureza`, `concessionaria`, `status` |
| `andamentos.tsv` | `processo_id`, `data_hora`, `unidade`, `descricao` (frase canônica) |
| `protocolos.tsv` | `processo_id`, `numero`, `tipo`, `data`, `data_inclusao`, `unidade`, `descricao` |

A unidade vem como `ORGAO/SIGLA` (ex.: `AGENERSA/CAPET`); unidades de outros órgãos mantêm o próprio órgão. É o
prefixo `ORGAO` do perfil que separa peça própria de externa. Um protocolo cujo `numero` não é só dígitos é outro
processo (anexado ou relacionado). A leitura está em `comum.carregar()` ([`scripts/comum.py`](../../scripts/comum.py)).

### Conteúdo das peças — `dados/relator/`

| Arquivo | Colunas | Uso |
|---|---|---|
| `documentos.parquet` | `processo`, `sei_doc_id`, `tipo`, `data`, `data_inclusao`, `unidade`, `download_status`, `mime`, `n_chars`, `restrito`, `motivo_restricao`, `origem_apenso` | Autoria por MIME, cobertura de texto, restrição |
| `doc_text_piloto.parquet` | `processo`, `sei_doc_id`, `texto` | Texto integral (piloto e coorte) |
| `extractions.parquet` | `processo`, `sei_doc_id`, `model_id`, `prompt_version`, `extraction_json` | Análise por peça |
| `cobertura_texto.csv` | `processo`, `pecas`, `com_texto`, `restritas`, `substantivas`, `cobertura_substantivas` | Critério de entrada no piloto e na coorte (≥ 60%) |

Campos de `extraction_json` que os scripts usam: `data` (data escrita na peça: é a "data real" da resposta de
terceiros, ver [02](02_TRILHA_TEMPO_POSSE.md)), `acao_processual` e `pedidos_e_determinacoes` (prorrogação de prazo,
classificação das atividades), `resumo_detalhado`, `resumo_dos_fatos_relevantes`, `dispositivos_citados` (candidatos
de norma, ver [07](07_CONFORMIDADE_LEGAL.md)) e `entidades.documentos_referenciados`. No caso AGENERSA essa análise já
existia num sistema anterior; na replicação ela sai de `coleta/extrair.py`, com o mesmo formato. Peça sem texto recebe
uma análise vazia ("stub") sem chamar o LLM.

`download_status`: `ok`, `sem_texto` (PDF escaneado, imagem, planilha), `restricted` (registrado sem texto, **nunca**
se tenta contornar), `failed`, `pending`, `bloqueado` (o servidor pediu captcha: a coleta para).

### Base normativa — sqlite (`BASE_NORMAS` do perfil)

Tabelas lidas por `normas_processo.py`, `verificar_normas.py` e `volume_anual.py`: `normativo` e `legislacao_externa`
(`id_canonico`, `titulo`, `txt` = caminho do texto integral), `deliberacoes` (`numero`, `ano`, `processo`,
`tipo_decisao`, `tema`, `ementa_catalogo`), `dispositivos_legais` (`numero`, `dispositivo_legal`), `dispositivo_map` e
`dispositivos_canonicos` (normalização de citações) e `contratos_concessao`. Sem a planilha de deliberações não há
volume anual por deliberação ([DADOS_LEVANTADOS.md](DADOS_LEVANTADOS.md)).

## Regras de decisão

- **Uma fonte por dado, com data de corte.** Registre a data da coleta (`dados/coleta/fontes.csv` guarda origem e
  data). Processo ainda aberto é medido até ela e marcado `em_aberto`.
- **Respeite o servidor público.** Intervalo entre requisições (padrão 2 s), contato no User-Agent, cache local (não
  baixe de novo sem `--atualizar`). Captcha não se contorna.
- **Peça restrita entra como metadado.** Tipo, unidade e data bastam para a trilha; o conteúdo falta e a peça fica
  sem ficha.
- **Dados pessoais ficam fora do git.** As tabelas têm nomes de interessados, signatários e e-mails de terceiros.
  `dados/` não é versionado; o que vai para o site passa por limpeza ([BOAS_PRATICAS.md](BOAS_PRATICAS.md)).
- **Credenciais só por variável de ambiente** (`ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`). Nunca em log, em arquivo
  versionado ou em resposta do agente.
- **Cobertura de texto é critério, não detalhe.** Processo com menos de 60% das peças substantivas com texto não vazio
  não entra no piloto nem na coorte (falha real: no caso, um processo de acidente com 49 documentos todos restritos e
  outro nunca baixado tiveram de sair do piloto — [RESULTADOS_PILOTO.md](../RESULTADOS_PILOTO.md)).

## Portão de qualidade

`python -m coleta.validar_coleta --perfil <UF>` sai com código 1 se alguma checagem reprovar. Limiares padrão:

| Checagem | Limiar | Falhou: o que fazer |
|---|---|---|
| `esquema` (colunas, ids únicos, chaves válidas) | 0 falha | Corrigir o coletor ou o perfil do SEI; nunca editar a TSV à mão |
| `processos_sem_andamento` | ≤ 5% | Página não baixada ou leiaute diferente: ver `fontes.csv` |
| `andamentos_nao_reconhecidos` | ≤ 25% | **Sinal mais importante.** A redação do seu SEI difere da canônica: o relatório lista as frases mais frequentes; escreva a `RegraAndamento` e recolete |
| `eventos_essenciais` (gerado, remetido, recebido, conclusão) | todos presentes | Idem |
| `datas_fora_de_ordem` | ≤ 2% | Formato de data do perfil |
| `unidades_sem_prefixo` | ≤ 5% | Sigla `ORGAO` do perfil ou leitura da unidade |
| `documentos_sem_unidade` | ≤ 5% | Cabeçalho da tabela de documentos no perfil do SEI |
| `cobertura_texto` | ≥ 30% (média) | Separar restrição (limite) de falha (recoletar); PDF de imagem pede OCR |
| `falhas_download` | ≤ 10% | Recoletar com `--tentativas` maior |

Para trabalho fino, aperte os limiares (ex.: `--max-nao-reconhecidos 0.10`). Depois da trilha, a auditoria automática
([`scripts/auditoria.py`](../../scripts/auditoria.py)) refaz o cruzamento entre andamentos e conteúdo das peças em
escala: no caso, 12.306 peças cruzadas, com 0 divergência de unidade e de data e 1 de tipo
(`saida/auditoria/auditoria_automatica.json`).

## Armadilhas conhecidas

- **Viés de amostra.** A carteira de um gabinete só tem processos que chegaram à relatoria: cobre bem o núcleo
  finalístico e o rito decisório, não cobre suporte (pessoas, contratações) nem demandas que terminam sem decisão
  colegiada ([METODO.md](../METODO.md), seção 5). No caso, ouvidoria e sanção ficaram sem casos suficientes por isso.
  Escolha a lista de processos pensando nos tipos que quer mapear.
- **Processos migrados.** Andamentos anteriores à implantação do SEI não existem. No caso, 79 dos 251 processos eram
  físicos migrados, com trilha parcial: servem para conteúdo, não para tempo.
- **Processo só com peças.** Processo que aparece no conteúdo mas não nos andamentos não tem estadia nem posse; serve
  para fichas e classificação de atividade, não para espera entre unidades.
- **Cópia de processo migrado.** O mesmo caso pode reaparecer com número novo; a coorte retira cópias
  ([04](04_CLASSIFICACAO_COORTE.md)). No caso, 4 cópias foram retiradas ([RESULTADOS_FASE2.md](../RESULTADOS_FASE2.md)).
- **Data ambígua.** Data escrita na peça como `05-03-2024` tem de ser lida dia primeiro; a leitura implícita (mês
  primeiro) troca março por maio (teste `test_data_da_peca_le_dia_primeiro`).
- **Análise por peça diferente da original.** No caso, a análise vinha de outro sistema e de mais de uma versão de
  prompt; na replicação ela é refeita por `coleta/extrair.py`. Os números de terceiros dependem do campo `data`: confira
  numa amostra se ele está sendo lido (ver [VERIFICACAO_IA.md](VERIFICACAO_IA.md), item 3).

## O que muda em outro Estado

Parâmetros do perfil do órgão (nomes de [`perfis/modelo.py`](../../perfis/modelo.py)):

| Parâmetro | Para que serve | No caso AGENERSA |
|---|---|---|
| `ORGAO`, `DESCRICAO_BASE` | Separar peça própria de externa; dizer de onde vieram os processos | `AGENERSA`; carteira de um gabinete |
| `INICIO_SEI` | Separar processo nativo de migrado | novembro de 2019 |
| `FERIADOS_MOVEIS`, `FERIADOS_FIXOS`, `ANOS_FERIADOS` | Dias úteis | nacionais, estaduais do RJ, municipais da capital e Carnaval |
| `NATUREZA_UNIDADE`, `PREFIXO_GABINETE` | Agregar posse por tipo de unidade | secretaria, procuradoria, câmaras técnicas, gabinetes de conselheiro, ouvidoria |
| `SECRETARIA` | Hub: retorno a ela não é iteração | secretaria executiva |
| `RECEPCAO` | Quem junta correspondência externa (resposta de terceiro) | secretaria, protocolo, ouvidoria |
| `RAIA_ALIAS` | Sigla da unidade × nome da raia no modelo | — |
| `CATEGORIAS` | Natureza do trabalho e horas-base por tipo de documento (regex) | ver [03](03_CONTEUDO_ESFORCO.md) |
| `REGRAS_SUGESTAO`, `PECA_CARACTERISTICA`, `CODIGOS_NOVOS_FASE2`, `TIPOS_FORA_CATALOGO`, `ORDEM_CODIGOS` | Classificação, piloto e coorte | ver [04](04_CLASSIFICACAO_COORTE.md) |
| `CODIGOS_FASE3`, `FAMILIA_BENCHMARK`, `FAMILIAS_BENCHMARK` | Processos do TO-BE e família de benchmarking de cada um | reajuste tarifário, fiscalização de campo, ocorrência de usuário |
| `BASE_NORMAS`, `RUIDO_NORMA`, `VOLUME_REGRAS`, `VOLUME_ANOS` | Base normativa, normas a ignorar, volume anual | ver [07](07_CONFORMIDADE_LEGAL.md) e [DADOS_LEVANTADOS.md](DADOS_LEVANTADOS.md) |
| `HORAS_SEMANAIS`, `VENCIMENTO_BASE`, `CARGO_PADRAO`, `FATOR_CUSTO_TOTAL`, `FERIAS_DU` | Custo-hora e FTE (hipótese até o RH) | 40 h; vencimento base de edital; fator 1,0 / 1,6 / 2,2 |

No **RJ** (SEI-RJ), o perfil de instalação `RJ` está pronto e o do órgão pode partir de `rj_agenersa.py`, trocando
`ORGAO`, unidades, catálogo, códigos e custo-hora. Em **outro Estado**, o perfil do SEI e o do órgão são novos, assim
como o catálogo e a base normativa. Os nomes dos tipos de documento mudam de instalação para instalação: revise as
expressões de `CATEGORIAS` sobre os tipos mais frequentes de `protocolos.tsv` antes de rodar a trilha (tipo que cai em
`outro` recebe 0,2 h e natureza "juntada").

## Números do caso AGENERSA (ordem de grandeza)

| Item | Valor | Origem |
|---|---|---|
| Processos / andamentos / protocolos | 251 / 19.095 / 12.986 | [RESULTADOS_FASE0.md](../RESULTADOS_FASE0.md) |
| Metadados de peças no banco de conteúdo | 25.781 documentos de 398 processos | [RESULTADOS_PILOTO.md](../RESULTADOS_PILOTO.md) |
| Análises por peça | 25.390 | idem |
| Peças com ficha de trabalho (coorte) | 3.183 | [RESULTADOS_FASE2.md](../RESULTADOS_FASE2.md) |
