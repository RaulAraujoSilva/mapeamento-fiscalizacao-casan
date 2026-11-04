# Coleta de dados do SEI para o seu Estado

Este guia é para o aluno e para o assistente de IA que o ajuda. Ele explica de onde vêm os dados que o pipeline usa,
como coletá-los da instalação do SEI do seu Estado, como ajustar o coletor quando o seu SEI é diferente do SEI-RJ e
como saber se a coleta ficou boa antes de rodar o mapeamento.

O pipeline (`scripts/`) não conversa com o SEI. Ele lê tabelas prontas:

| Pasta | Arquivos | Para quê |
|---|---|---|
| `dados/sei2_dump/` | `processos.tsv`, `andamentos.tsv`, `protocolos.tsv`, `observacoes.tsv` | a trilha: por onde o processo passou, quando, e que documentos cada unidade juntou |
| `dados/relator/` | `documentos.parquet`, `doc_text_piloto.parquet`, `extractions.parquet`, `cobertura_texto.csv` | o conteúdo das peças: texto e uma análise estruturada de cada documento |

O coletor (`coleta/`) produz exatamente essas tabelas. Quem é do Rio de Janeiro já tem os dados do projeto original;
quem é de outro Estado usa o coletor com um **perfil** da sua instalação do SEI.

## 1. De onde vêm os dados

### Pesquisa Pública do SEI (caminho principal)

Quase todo órgão que usa o SEI publica a **Pesquisa Pública** (módulo `modulos/pesquisa/`). Para cada processo
público ela mostra três blocos:

1. **Autuação**: número, tipo, data de geração e interessados;
2. **Lista de Protocolos**: cada documento juntado, com número SEI, tipo, data, data de inclusão e unidade;
3. **Lista de Andamentos**: cada movimento do processo, com data e hora, unidade e descrição
   ("Processo remetido pela unidade ...", "Processo recebido na unidade", "Conclusão do processo na unidade"...).

A página de um processo tem um endereço do tipo
`https://sei.<estado>.gov.br/sei/modulos/pesquisa/md_pesq_processo_exibir.php?<código>`. O código é gerado pelo SEI;
não dá para montá-lo a partir do número do processo. A busca por número, na tela de pesquisa, costuma ter
**captcha**, e o coletor **não** automatiza essa busca nem tenta contornar o captcha. Por isso a entrada do coletor é
a lista de links dos processos: pesquise cada processo no navegador e copie o link da página.

Cada documento público tem um link `md_pesq_documento_consulta_externa.php?<código>`, que o coletor usa para baixar o
conteúdo.

### Páginas salvas à mão (quando não há acesso automatizado)

Se a pesquisa pública do seu órgão bloqueia acesso automatizado, ou se você tem acesso aos processos pelo SEI interno,
abra cada processo no navegador e salve a página (Ctrl+S, "Página da Web, somente HTML" ou "completa"). Ponha os
arquivos `.html` numa pasta e rode o coletor com `--html-salvo pasta/`. Para os documentos, salve cada um com o
número SEI como nome (`12345678.pdf`, `12345678.html`) e use `coleta/documentos.py --pasta-docs pasta/ --sem-rede`.

### Alternativas que exigem o órgão (descritas, não implementadas)

- **Webservice do SEI (SeiWS, SOAP)**: o SEI tem um webservice nativo (`/sei/ws/SeiWS.php`) com operações para
  consultar processos, documentos e andamentos. Para usá-lo, o administrador do SEI do órgão precisa cadastrar um
  "sistema" e um "serviço", liberar as operações e o IP de origem. É o caminho mais completo (inclui processos
  restritos, se o órgão autorizar), mas depende de pedido formal à área de TI.
- **Módulo REST (mod-wssei)**: algumas instalações têm o módulo usado pelo aplicativo móvel do SEI, que expõe uma API
  REST autenticada com usuário e senha de servidor. Só use com autorização do órgão, nunca com a senha de outra
  pessoa.
- **Extração pela TI**: o órgão pode exportar direto do banco do SEI as tabelas de protocolo, atividade (andamentos) e
  documento.

Em qualquer desses casos, o que importa é gravar as mesmas tabelas da seção 6. As funções `coletar.gravar` e
`documentos.gravar` aceitam linhas montadas por outro meio.

## 2. Rodar a coleta

```bash
pip install -r requirements-coleta.txt

# 1) trilha: uma URL por linha em processos.txt (linhas com # são comentário)
python -m coleta.coletar --perfil RJ --lista processos.txt --intervalo 3 --contato seu.email@exemplo.edu.br

# 2) diagnóstico (portão): sai com código 1 se algo estiver fora do limiar
python -m coleta.validar_coleta --perfil RJ

# 3) documentos públicos: texto de HTML, PDF e DOCX
python -m coleta.documentos --perfil RJ

# 4) análise de cada peça por LLM (custa dinheiro: teste antes com --limite 20)
python -m coleta.extrair --limite 20
python -m coleta.extrair

# 5) diagnóstico de novo, agora com a cobertura de texto
python -m coleta.validar_coleta --perfil RJ
```

Boas práticas que o coletor já segue e que você não deve desligar:

- **Respeite o servidor.** O intervalo padrão é de 2 segundos entre requisições (`--intervalo`); em coletas grandes,
  use 3 a 5 segundos e rode fora do horário de expediente. O coletor tenta de novo só em erro temporário (429, 5xx,
  falha de rede), com espera crescente, e respeita o cabeçalho `Retry-After`.
- **Identifique-se.** O User-Agent diz que é um coletor acadêmico; passe um e-mail em `--contato` (ou na variável
  `COLETA_CONTATO`) para que o órgão possa falar com você.
- **Cache.** Cada página e cada documento baixados ficam em `dados/bruto/`; rodar de novo não baixa outra vez (use
  `--atualizar` para forçar). Assim você pode ajustar o perfil e reprocessar sem tocar no servidor.
- **Proxy** é opcional, pela variável `COLETA_PROXY` (`http://usuario:senha@host:porta`). O coletor nunca imprime a
  URL nem a senha do proxy. Use proxy só se a sua rede exigir, não para driblar bloqueio do órgão.
- **Captcha ou bloqueio**: o coletor para na hora e avisa. Não tente contornar; passe a usar páginas salvas à mão.

`coletar.py` também aceita números de processo no lugar das URLs, se você tiver um CSV `numero,url` (`--mapa-urls`) ou
se a sua instalação permitir abrir o processo pelo número (campo `modelo_url_processo` do perfil). Use `--acrescentar`
para juntar uma coleta nova às tabelas já gravadas.

## 3. Criar o perfil do seu Estado, passo a passo

O perfil fica em `coleta/perfil_sei.py`. Ele reúne tudo o que muda entre instalações: rótulos, cabeçalhos, formato de
data, prefixo das unidades e a redação dos andamentos. O código do coletor não muda.

1. **Salve duas ou três páginas de processo** do seu SEI (Ctrl+S) numa pasta de trabalho, de processos com
   bastante movimento. Escolha pelo menos um com documento restrito.
2. **Copie o `MODELO`** do fim de `coleta/perfil_sei.py`:
   ```python
   SP = replace(MODELO, uf="SP", orgao="ARSESP", nome_orgao="...",
                url_pesquisa="https://sei.sp.gov.br/sei/modulos/pesquisa/")
   PERFIS = {"RJ": RJ, "MODELO": MODELO, "SP": SP}
   ```
   Ou salve os campos num JSON (`python -c "from coleta.perfil_sei import MODELO; import json;
   print(json.dumps(MODELO.para_json(), ensure_ascii=False, indent=1))" > meu_perfil.json`, edite e use
   `--perfil meu_perfil.json`).
3. **Prefixo do órgão** (`orgao`): olhe a coluna Unidade. Se aparece `ARSESP/DIR`, o prefixo é `ARSESP`. Se aparece só
   `DIR`, deixe `completar_prefixo_unidade=True` e o coletor grava `ARSESP/DIR`. O pipeline separa peça própria de
   peça externa por esse prefixo (no pipeline, o mesmo valor vai em `ORGAO` do perfil do órgão em `perfis/`).
4. **Rótulos da autuação** (`rotulos_autuacao`): copie exatamente o texto das células da esquerda ("Nº do Processo:",
   "Data de Autuação:"). Acento, maiúscula e dois-pontos não importam.
5. **Tabelas** (`titulos_*` e `colunas_*`): copie o título de cada lista (o texto acima da tabela) e o cabeçalho de
   cada coluna. As colunas são achadas pelo cabeçalho, não pela posição.
6. **Datas** (`formatos_data`, `formatos_data_hora`): no formato do `strftime` do Python. Ex.: `22/04/2024 às 15:00`
   é `"%d/%m/%Y às %H:%M"`.
7. **Rode só a trilha das páginas salvas e o diagnóstico**:
   ```bash
   python -m coleta.coletar --perfil SP --sem-rede --html-salvo paginas/ --destino dados/teste_dump
   python -m coleta.validar_coleta --perfil SP --destino dados/teste_dump --min-andamentos-essenciais 1
   ```
8. **Ajuste os andamentos.** O pipeline reconstrói a passagem do processo por cada unidade a partir da descrição dos
   andamentos, com a função `tipo_andamento` de `scripts/comum.py`, que espera as frases do SEI padrão:

   | Evento | Frase canônica | Por que importa |
   |---|---|---|
   | `remetido` | `Processo remetido pela unidade ORGAO/UNIDADE` (unidade de origem na frase) | abre a estadia na unidade de destino e fecha a da origem |
   | `recebido` | `Processo recebido na unidade` | marca o recebimento |
   | `conclusao` | `Conclusão do processo na unidade` | fecha a estadia |
   | `reabertura` | `Reabertura do processo na unidade` | reabre a estadia |
   | `gerado` | `Processo público gerado` (ou restrito/sigiloso) | início do processo |

   Se o diagnóstico mostra muitas frases não reconhecidas, ou acusa evento essencial ausente, a sua instalação
   escreve diferente. **Não altere `scripts/comum.py`**: acrescente ao perfil uma `RegraAndamento` que traduz a frase
   local para a canônica. O relatório do validador lista as frases mais comuns com números e unidades trocados por
   `9` e `<UNIDADE>`, o que ajuda a escrever a regex:
   ```python
   RegraAndamento("remetido", r"^Processo enviado (?:pela|da) unidade (?P<unidade>\S+)(?P<resto>.*)$",
                  "Processo remetido pela unidade {unidade}{resto}",
                  exemplo="Processo enviado pela unidade DIRAD")
   ```
   O grupo `unidade` recebe o prefixo do órgão; o grupo `resto` carrega o complemento. O coletor grava a frase
   canônica em `andamentos.tsv` e guarda a original em `dados/coleta/andamentos_original.csv`. Todo `exemplo` é
   testado: `python -m pytest tests/test_coleta.py` confere que, normalizado, ele é reconhecido pelo pipeline com o
   evento declarado.
9. **Restrição** (`marca_documento_restrito`, `marca_processo_restrito`): confira, numa página com documento restrito,
   que texto ou ícone (atributo `title`/`alt`) o seu SEI usa, e ajuste a regex se necessário.
10. Repita os passos 7 e 8 até o validador aprovar. Só então colete a lista completa pela rede.

Para o assistente de IA: o roteiro acima é determinístico. Leia o relatório do `validar_coleta`, proponha a regra ou o
rótulo que falta, acrescente um `exemplo` real (anonimizado) e rode os testes. Não edite `scripts/` para acomodar o
Estado.

## 4. Diagnóstico com `validar_coleta.py`

O validador lê as tabelas exatamente como o pipeline lê (`comum.carregar`) e sai com código 1 se alguma checagem
reprova. Os limiares podem ser mudados na linha de comando (`--max-nao-reconhecidos 0.10`, etc.).

| Checagem | Limiar padrão | O que significa quando reprova |
|---|---|---|
| `esquema` | 0 falha | arquivo ausente, coluna errada, id repetido, data fora de AAAA-MM-DD |
| `processos_sem_andamento` | ≤ 5% | a tabela de andamentos não foi achada (título ou cabeçalho no perfil) ou o órgão não publica andamentos |
| `andamentos_nao_reconhecidos` | ≤ 25% | **principal sinal de perfil a ajustar**: a redação dos andamentos difere da canônica |
| `eventos_essenciais` | todos presentes | algum de geração, remessa, recebimento ou conclusão não aparece: falta regra no perfil |
| `datas_fora_de_ordem` | ≤ 2% | formato de data errado no perfil, andamento antes da geração ou no futuro |
| `unidades_sem_prefixo` | ≤ 5% | prefixo do órgão ausente: ajuste `orgao` ou `completar_prefixo_unidade` |
| `documentos_sem_unidade` | ≤ 5% | coluna Unidade não achada na lista de protocolos |
| `cobertura_texto` | ≥ 30% (média) | poucos documentos substantivos com texto: muitos restritos ou escaneados |
| `falhas_download` | ≤ 10% | erros de rede ou servidor: rode de novo mais devagar (o cache guarda o que já veio) |

Uma parcela de andamentos "não reconhecidos" é normal: o pipeline só precisa dos eventos da tabela da seção 3.
Acesso externo, anexação, sobrestamento e relacionamento também são reconhecidos; o resto é registrado como "outro"
e não atrapalha.

## 5. Limites, ética e LGPD

- **Só dados públicos.** O coletor lê o que a Pesquisa Pública mostra. Documento restrito ou sigiloso é registrado
  com tipo, data e unidade (o que a lista pública mostra), sem texto, e o coletor nunca tenta abri-lo. Processo
  inteiro restrito entra só com a trilha que a página exibir.
- **Viés de cobertura.** Processos restritos (sancionadores, por exemplo) ficam com pouca ou nenhuma peça com texto.
  Diga isso no relatório; não generalize a partir só dos processos públicos.
- **Andamentos podem estar ocultos.** Algumas instalações configuram a pesquisa pública para não mostrar a lista de
  andamentos ou só parte dela. Sem andamentos não há trilha: nesse caso peça os dados ao órgão (seção 1).
- **PDF escaneado** fica como `sem_texto`; o coletor não faz OCR.
- **Dados pessoais.** As páginas têm nomes de interessados, servidores e, nos documentos, CPF, endereço e e-mail.
  Mesmo públicos, são dados pessoais (LGPD, art. 7º, § 3º e § 4º: o uso deve respeitar a finalidade da publicação).
  Regras do projeto:
  - **nunca versione `dados/`** (o `.gitignore` já exclui a pasta): nem TSVs, nem `dados/bruto/`, nem parquets;
  - não republique tabelas brutas, listas de interessados nem trechos de documentos com dados pessoais;
  - nos entregáveis, use agregados (tempos, contagens, tipos de peça) e unidades, não pessoas;
  - apague `dados/bruto/` quando terminar o trabalho;
  - antes de publicar, rode `python scripts/sanear_saida.py`: ele tira nome de usuário, endereço, CPF, e-mail e
    telefone que as fichas e tabelas de `saida/` citam das peças; o teste `tests/test_dados_pessoais.py` e o CI
    (`.github/workflows/testes.yml`) reprovam a publicação se sobrar algum;
  - a análise por LLM envia o texto das peças ao provedor escolhido; use só documentos públicos e confira se o seu
    órgão permite.
- **Termos de uso.** Leia os termos da pesquisa pública do seu órgão. Se houver dúvida, peça autorização; muitos
  órgãos fornecem os dados diretamente quando o objetivo é pesquisa.

## 6. Esquema das tabelas canônicas

### `dados/sei2_dump/*.tsv`

Separador tabulação, primeira linha é o cabeçalho, nulo é `NULL`, sem aspas (o pipeline lê com `quoting=3`), UTF-8.
Quebra de linha dentro de um campo é gravada como `\n` literal (barra e n), como no dump original.

`processos.tsv` — um processo por linha

| Coluna | Conteúdo |
|---|---|
| `id` | UUID estável derivado do número do processo (o mesmo número gera sempre o mesmo id) |
| `numero` | número do processo como o SEI mostra (`SEI-220007/001234/2023`) |
| `tipo` | tipo do processo |
| `interessado` | interessados, separados por `; ` |
| `data_geracao` | `AAAA-MM-DD` |
| `ultima_unidade` | unidade do andamento mais recente |
| `data_ultimo_andamento` | `AAAA-MM-DD HH:MM:SS` |
| `assunto`, `tipo_custom`, `natureza`, `concessionaria`, `status` | campos do controle interno do gabinete no projeto original; a pesquisa pública não os tem: `NULL` |

`andamentos.tsv` — um movimento por linha

| Coluna | Conteúdo |
|---|---|
| `processo_id` | `id` do processo |
| `data_hora` | `AAAA-MM-DD HH:MM:SS` |
| `unidade` | unidade onde o andamento foi registrado, com prefixo (`AGENERSA/SCEXEC`) |
| `descricao` | frase canônica (seção 3); a original fica em `dados/coleta/andamentos_original.csv` |

`protocolos.tsv` — um documento (ou processo anexado/relacionado) por linha

| Coluna | Conteúdo |
|---|---|
| `processo_id` | `id` do processo |
| `numero` | número SEI do documento; protocolo que é outro processo tem número não numérico (`SEI-...`) |
| `tipo` | tipo do documento como na lista ("Parecer 12", "Ofício 15") |
| `data` | data do documento, `AAAA-MM-DD` |
| `data_inclusao` | data de inclusão no processo, `AAAA-MM-DD` |
| `unidade` | unidade que juntou o documento |
| `descricao` | `NULL` (a pesquisa pública não tem) |

`observacoes.tsv` (`processo_id`, `texto`, `criado_em`): notas internas do gabinete no projeto original; a coleta
grava só o cabeçalho.

### `dados/relator/`

| Arquivo | Colunas |
|---|---|
| `documentos.parquet` | `processo`, `sei_doc_id`, `tipo`, `data` e `data_inclusao` (`dd/mm/aaaa`), `unidade`, `download_status` (`ok`, `sem_texto`, `restricted`, `failed`, `pending`), `mime`, `n_chars` (inteiro), `restrito` (booleano), `motivo_restricao`, `origem_apenso` (nulo: a coleta não segue processos anexados) |
| `doc_text_piloto.parquet` | `processo`, `sei_doc_id`, `texto` — só documentos com texto extraído |
| `extractions.parquet` | `processo`, `sei_doc_id`, `model_id` (`stub` para peça sem texto), `prompt_version`, `extraction_json` (texto JSON: `data`, `acao_processual`, `pedidos_e_determinacoes`, `resumo_dos_fatos_relevantes`, `resumo_detalhado`, `pontos_chave`, `prazos_e_eventos`, `dispositivos_citados`, `entidades.documentos_referenciados`, `tier_relevancia` e demais campos) |
| `cobertura_texto.csv` | `processo`, `pecas`, `com_texto`, `restritas`, `substantivas`, `cobertura_substantivas` |

### Auxiliares do coletor (`dados/coleta/`)

`indice_documentos.csv` (link público e restrição de cada documento, entrada de `documentos.py`),
`andamentos_original.csv` (frase original × canônica de cada andamento) e `fontes.csv` (URL ou arquivo de origem de
cada processo e data da coleta).
