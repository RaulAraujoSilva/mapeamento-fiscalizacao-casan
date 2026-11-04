# Base normativa da fase 3

A fase 3 (conformidade legal, linha de base e TO-BE) consulta uma base normativa em SQLite. Na AGENERSA essa base é a do
Especialista AGENERSA, um projeto à parte com milhares de normas, deliberações e dispositivos já mapeados. Outro órgão
não precisa reproduzir aquele projeto: basta uma base com as tabelas e colunas abaixo, que é o que
`scripts/montar_base_normas.py` monta a partir de duas fontes que todo órgão tem — os textos das normas e a lista das
suas deliberações (ou decisões).

## Onde a base fica e como o pipeline a encontra

| Nome | Origem | Padrão |
|---|---|---|
| `BASE_NORMAS` | perfil (relativo à pasta de dados) ou variável de ambiente `BASE_NORMAS` | `dados/normas/base_normas.sqlite` |
| `TEXTOS_NORMAS` | variável de ambiente `TEXTOS_NORMAS` | pasta-avó do sqlite (`dados/`) |

A coluna `txt` das tabelas de normas guarda o caminho do texto integral **relativo a `TEXTOS_NORMAS`**. Com o padrão, o
sqlite fica em `dados/normas/` e os textos em `dados/normas/txt/`, de modo que `txt` vale `normas/txt/LEI-4556-2005.txt`.
(Na base do Especialista a convenção é a mesma: `<raiz>/data/base_conhecimento.sqlite` e `txt = data/txt/...`.)

A base é aberta só para leitura. Ela fica fora do git, como o resto de `dados/`.

## Quem lê o quê

| Script | Tabelas e colunas |
|---|---|
| `volume_anual.py` | `deliberacoes(numero, ano, processo, tipo_decisao, tema, ementa_catalogo)` |
| `normas_processo.py` | `dispositivo_map(string_original, disp_id)`; `dispositivos_canonicos(disp_id, rotulo, tipo, pai_id)`; `normativo(id_canonico, titulo, txt)`; `legislacao_externa(id_canonico, titulo, txt)`; `deliberacoes(numero, processo, tipo_decisao, tema, ementa_catalogo)`; `dispositivos_legais(numero, dispositivo_legal)`; `contratos_concessao(concessionaria_canonica, id_canonico, tipo, vigente)` |
| `verificar_normas.py` | só os arquivos de texto, em `TEXTOS_NORMAS / fonte.txt` de cada norma de `saida/fase3/normas_<cod>.json` |

Sem a base (arquivo ausente), `volume_anual.py`, `normas_processo.py` e `verificar_normas.py` saem com um aviso e
código 0; `linha_base.py` segue sem volume nem custo anual. Com a base presente, um trecho que não bate com o texto
continua barrando o pipeline.

## Esquema mínimo

| Tabela | Coluna | Conteúdo |
|---|---|---|
| `normativo` | `id_canonico` | `TIPO-NNN/AAAA` (ex.: `IN-001/2007`, `LEI-4556/2005`) — `normas_processo.py` procura a norma-raiz `IN:1/2007` como `IN-001/2007` e `IN-1/2007` |
| | `titulo`, `tipo`, `numero_norma`, `ano`, `url_documento` | título, tipo canônico, `N/AAAA`, ano, URL oficial |
| | `txt` | caminho do texto integral relativo a `TEXTOS_NORMAS` |
| `legislacao_externa` | as mesmas, mais `disp_id` | normas de outros entes (federais, de outro órgão); mesma busca por `id_canonico` |
| `dispositivos_canonicos` | `disp_id` | `SIGLA:numero/ano` para a norma (`LEI:5619/2009`) e `SIGLA:numero/ano:artN` para o artigo (`LEI:5619/2009:art5`) |
| | `rotulo` | forma legível: `Lei nº 5.619/2009, art. 5º` |
| | `tipo` | `lei`, `decreto`, `resolucao`, `instrucao_normativa`, `deliberacao`, `portaria`… |
| | `pai_id` | dispositivo-pai (o artigo aponta para a norma; a norma tem `pai_id` nulo) |
| | `nivel` | 0 = norma, 1 = artigo |
| `dispositivo_map` | `string_original`, `disp_id`, `metodo` | citação livre, já com espaços normalizados, → dispositivo |
| `deliberacoes` | `numero`, `data`, `ano`, `processo`, `tema`, `tipo_decisao`, `ementa_catalogo` | uma linha por deliberação/decisão do órgão; `processo` é o número SEI (só os dígitos são comparados) |
| `dispositivos_legais` | `numero`, `dispositivo_legal` | dispositivos citados em cada deliberação |
| `contratos_concessao` | `concessionaria_canonica`, `id_canonico`, `tipo`, `vigente` | contratos e aditivos; pode ficar vazia |

Siglas reconhecidas por `montar_base_normas.py`: `LC` (lei complementar), `LEI`, `DEC`, `IN`, `RES`, `DELIB`, `PORT`.
Contrato de concessão, norma técnica e outros tipos ficam como citação não mapeada (aparecem como `BRUTO` nos
candidatos e a curadoria decide); quem precisar deles pode acrescentar linhas às tabelas por fora.

## Montagem com `montar_base_normas.py`

```
cd scripts
python montar_base_normas.py --textos ../dados/normas/brutos --deliberacoes ../dados/normas/deliberacoes.csv \
       --citacoes ../dados/relator/extractions.parquet
```

Insumos:

1. `--textos`: uma pasta com um arquivo por norma, em `.txt`, `.pdf` (precisa de `pypdf`) ou `.html`. O nome do arquivo
   identifica a norma: `LEI-5619-2009.txt`, `DEC_48209_2022.pdf`, `IN-001-2007.html` (sigla, número, ano). Para nomes
   fora do padrão, título e URL, use um índice `--normas` (CSV com `arquivo, tipo, numero, ano, titulo, tabela, url`;
   `tabela` é `normativo` ou `legislacao_externa`). Os textos são copiados — PDF e HTML convertidos — para
   `<pasta do sqlite>/txt/`. Prefira o texto oficial consolidado: é contra ele que os trechos literais serão conferidos.
   PDF digitalizado sem camada de texto não serve; passe antes por OCR.
2. `--deliberacoes`: planilha `.csv` ou `.xlsx` com `numero`, `data` (ou `ano`), `processo`, `tipo_decisao`, `tema`,
   `ementa` e, opcional, `dispositivos` (citações separadas por `;` ou `|`). `tipo_decisao` é livre, mas tem de bater
   com os tipos usados em `VOLUME_REGRAS` do perfil (o script põe em minúsculas). A fonte costuma ser o portal de
   deliberações do órgão ou o diário oficial.
3. `--citacoes` (opcional, repetível): citações livres para o mapa — o `extractions.parquet` das análises das peças
   (campo `dispositivos_citados`), um `.csv` (1ª coluna) ou um `.txt` (uma por linha). Sem isso, o mapa só tem as
   citações da planilha de deliberações, e `normas_processo.py` acha menos normas nas peças.
4. `--contratos` (opcional): CSV com `concessionaria_canonica, id_canonico, tipo, vigente`.

A base é sempre remontada do zero. O script informa quantas citações não reconheceu e quais arquivos não identificou.

## Depois da base: curadoria e conferência

`normas_processo.py` gera `saida/fase3/candidatos_normas_<cod>.json` (normas-raiz por frequência de citação, com o
caminho do texto). A curadoria (`saida/fase3/ESPECIFICACAO_CONFORMIDADE.md`) escolhe as normas, lê o texto e transcreve
o trecho literal em `saida/fase3/normas_<cod>.json`; ali, `fonte.txt` é o valor da coluna `txt` (relativo a
`TEXTOS_NORMAS`), não o caminho absoluto dos candidatos. `verificar_normas.py` confere cada trecho contra o texto, depois
de normalizar espaços, aspas, travessões, caixa e hifenização de quebra de linha; trecho de fonte fora da base vai para
conferência manual com a URL.
