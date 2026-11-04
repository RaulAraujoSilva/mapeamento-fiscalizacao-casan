# 03 — Conteúdo e esforço

## Objetivo

Dizer, para cada peça produzida pelo órgão, **que trabalho ela contém**: natureza, entregável, insumos,
ferramentas, cálculos e testes próprios, competências, complexidade, fração autoral, horas estimadas, prazos
concedidos e sinais de perda. É o que transforma o metadado ("a câmara juntou um parecer em 12 dias") em mapa de
trabalho ("conferiu a fórmula paramétrica com dois índices, comparou com a tarifa vigente, apontou erro na base").

O SEI não registra horas. Toda hora aqui é **estimativa** e fica como **faixa** (piso–teto) até a calibração com
servidores.

## Entradas

- Texto integral das peças (`dados/relator/doc_text_piloto.parquet`) e análise por peça (`extractions.parquet`);
- metadados com MIME (`documentos.parquet`) para autoria;
- `saida/documentos.csv` (categoria e horas-base por tipo, da trilha);
- chave de API do provedor de LLM em variável de ambiente.

## Passos

1. **Autoria.** Antes de qualquer ficha, separe peça própria de peça externa (regra abaixo). Só peça própria
   recebe ficha.
2. **Ficha de trabalho por peça:** `cd scripts && python fichas_trabalho.py [--modelo <modelo>] [--workers 6]`
   (ou `python pipeline.py --fichas`). Cache por documento em `dados/fichas/`, por versão de prompt; a rodada é
   retomável.
3. **Ancoragem.** O próprio script confere, por código, se cada trecho de evidência está no texto da peça
   (`fichas_trabalho.ancorar`). Só item ancorado alimenta as etapas seguintes (`legado`).
4. **Esforço por conteúdo e AS-IS do piloto:** `python asis_piloto.py` → `saida/esforco_documentos.csv` (piso e
   teto por peça), `tarefas_piloto.csv`, planilha do piloto e `docs/ASIS_PILOTO.md`.
5. **Auditoria por amostra** (por lote): um auditor independente lê o texto e julga cada item de uma amostra de
   30 fichas ([VERIFICACAO_IA.md](VERIFICACAO_IA.md)).

## Regras de decisão

### 3.1 Autoria pelo MIME

O editor do SEI gera HTML. PDF é peça de fora juntada (ofício de terceiro, publicação, deliberação ou ata
copiadas), **exceto** relatórios técnicos e notificações, que as câmaras técnicas sobem em PDF. Peça externa conta
só como juntada (0,1 h) e não recebe ficha.

> **Falha real.** Sem o MIME, a secretaria aparecia "produzindo" cartas de concessionárias: a unidade que junta
> não é a autora ([RESULTADOS_PILOTO.md](../RESULTADOS_PILOTO.md)).

Quem assina não é necessariamente quem preparou a peça: o mapa é **por unidade**, não por pessoa.

### 3.2 Que peças recebem ficha

Peças substantivas e de comunicação produzidas pela agência (parecer, relatório, nota técnica, voto, informação,
relatório de fiscalização, ofício, despacho de mérito, minuta). Peças de tramitação (despacho de encaminhamento,
termo, recibo) não passam por IA: a categoria basta. Peças externas não recebem ficha.

### 3.3 Ficha v2 — regras do prompt (`fichas_trabalho.SISTEMA`)

1. **Só o que o texto diz.** Cada item traz `evidencia`: trecho copiado literalmente (10 a 160 caracteres, sem
   reticências no meio). Item sem trecho não entra.
2. **Trabalho próprio × reproduzido.** Cálculo ou análise que a peça só transcreve de outra peça (o voto que
   reproduz o cálculo da câmara) vai em `trabalho_reproduzido`. Na dúvida, é reproduzido.
3. **Fonte consultada × mencionada.** Só entra a base que o autor consultou para produzir a peça.
4. **Ferramenta só com prova** de uso, não pelo tema.
5. **Complexidade 1 a 5 por rubrica** (1 expediente; 2 comunicação ou instrução simples; 3 análise de poucas peças
   ou fórmula conhecida; 4 análise cruzada com cálculo próprio ou posições divergentes; 5 modelagem, cenários,
   auditoria com bases externas). Peça que só reproduz análise alheia tem a complexidade do trabalho próprio.
6. **Composição do texto** (autoral, transcrição, padrão, somando 100).
7. **Sinais de perda** com tipo fechado (pedido de complementação, devolução por vício, refazimento, reiteração,
   aguardando outra unidade, diligência externa, sobrestamento). **Prazo de rito (defesa, razões finais, recurso)
   não é perda.**
8. **Prazos** com dias, beneficiário e natureza (rito, diligência, prorrogação, cumprimento, interno). É daqui que
   a trilha tira o prazo de cada ofício (janela de terceiros) e a conformidade tira o prazo concedido.

Texto acima de 60.000 caracteres vai como início + fim (`MAX_CHARS`).

### 3.4 Travas determinísticas depois da ficha (`fichas_atividades.py`)

| Trava | Por quê |
|---|---|
| Ferramenta só com evidência que não seja fórmula de expediente e com nome não genérico (`EXPEDIENTE`, `GENERICAS`) | B3: "análise normativa" aparecia em despacho de encaminhamento |
| Peça própria que repete ≥ 60% de outra anterior da mesma categoria no mesmo caso vira sinal de perda | B4: refazimento e reiteração ficavam invisíveis peça a peça (11 casos achados) |
| Limpeza de nome de usuário, endereço, CPF, e-mail e telefone nas evidências e em tudo o que vai ao site | B5 |

### 3.5 Esforço: piso e teto

| Estimativa | Como | Papel |
|---|---|---|
| **Piso** | `horas_estimadas` da ficha (servidor experiente, inclui leitura dos insumos que o autor examinou, sem espera) | limite inferior |
| **Teto** | `horas_base(categoria) + laudas_autorais × H_LAUDA[complexidade] + docs_analisados × 0,25 h + fontes_externas × 1 h` (`comum.horas_modelo`) | limite superior |

Lauda = 1.250 caracteres com espaços, só a fração autoral. `H_LAUDA` = 0,05 / 0,25 / 0,5 / 0,9 / 1,5 h por lauda
para complexidade 1 a 5. Horas-base por tipo (0,1 h despacho de encaminhamento, 0,75 h ofício, 6 h parecer ou voto,
8 h relatório de fiscalização ou nota técnica) estão em `CATEGORIAS` do perfil do órgão; os coeficientes por lauda,
em `scripts/comum.py`. **Todos esses coeficientes são hipótese inicial**, explícita no código, para calibrar.

A calibração prevista é um estudo de tempo curto com cerca de 20 peças-tipo (parecer, relatório técnico, voto,
ofício, relatório de fiscalização), não uma entrevista aberta ([RESULTADOS_PILOTO.md](../RESULTADOS_PILOTO.md)).

## Saídas e formato

| Arquivo | Conteúdo |
|---|---|
| `saida/fichas_trabalho.jsonl` | Ficha completa por peça (com `modelo` que a gerou e itens com `ancorado`) |
| `saida/fichas_trabalho.csv` | Uma linha por peça (natureza, complexidade, horas, sinais) |
| `saida/esforco_documentos.csv` | Piso e teto por peça, laudas, autoria |
| `saida/bpmn/fichas_<cod>.json` | Ficha de cada atividade do modelo (tempos, entradas, ferramentas, competências, base normativa, cargos, perdas, lacunas) |

## Portão de qualidade

- `test_ancoragem_aceita_trecho_literal_e_recusa_inventado`, `test_legado_so_leva_item_ancorado_e_ignora_prazo_de_prorrogacao`,
  `test_expediente_nao_vira_ferramenta`, `test_limpeza_de_dados_pessoais`, `test_repeticao_de_peca_da_mesma_categoria`
  (regras) e `test_fichas_sao_v2_e_legado_so_ancorado` (saídas).
- Auditoria automática ([`scripts/auditoria.py`](../../scripts/auditoria.py), camada B): todo número citado na ficha
  tem de aparecer no texto da peça. Critério: números sem âncora ≤ 1% (`test_auditoria_automatica_dentro_dos_limites`).
- Auditoria por amostra: alucinação (sem lastro + contradito) ≤ 2%, imprecisão ≤ 10%
  ([PLANO_AUDITORIA_E_AMPLIACAO.md](../PLANO_AUDITORIA_E_AMPLIACAO.md)). Falhou: corrija o prompt ou a trava, refaça
  as fichas (a mudança de versão do prompt invalida o cache) e reaudite.

## Armadilhas conhecidas

- **Trocar de modelo no meio da rodada.** No caso, o crédito do primeiro modelo acabou e as fichas restantes foram
  feitas com outro. Na mesma peça, o segundo deu horas 1,42 vez as do primeiro (mediana), natureza igual em 78% e
  complexidade igual em 76% (`saida/fase2/comparacao_modelos_fichas.json`). Cada ficha registra o modelo; o
  procedimento conta fichas por modelo; e o efeito tem de ser declarado. **Prefira um único modelo por rodada** e
  orce o crédito antes.
- **Confundir piso e teto com intervalo de confiança.** São duas estimativas diferentes que ordenam as peças do mesmo
  jeito (correlação 0,91 no piloto) mas diferem em escala; a ficha deu cerca de 40% das horas do modelo
  ([METODO.md](../METODO.md)).
- **Usar horas para dimensionar equipe antes da calibração.** A faixa é larga demais para isso.
- **Peça restrita sem texto.** Entra pela categoria, sem ficha; afirmação sobre ela se apoia em peças posteriores que
  a relatam.

## O que muda em outro Estado

- Regra de autoria: confira numa amostra se, no seu SEI, as unidades sobem relatórios em PDF e quais. Ajuste a
  exceção.
- Rótulos de insumo, área de competência e ferramenta em `fichas_trabalho.py` refletem o setor regulado (gás,
  saneamento). Para energia, transporte ou outro setor, revise as listas fechadas antes da rodada e dê nova versão
  ao prompt.
- O nome do órgão, do Estado e dos setores regulados está escrito no texto do prompt de `fichas_trabalho.py` (e também
  em `classificar_atividades.py` e `classificar_novos.py`): troque e dê nova versão ao prompt, para que o cache antigo
  não seja reaproveitado.

## Números do caso AGENERSA (ordem de grandeza)

| Item | Valor | Origem |
|---|---|---|
| Piloto: documentos / externos / com ficha | 669 / 155 / 326 | [RESULTADOS_PILOTO.md](../RESULTADOS_PILOTO.md) |
| Piloto: horas piso / teto (total) | 588 h / 1.421 h (mediana por processo 34 h / 91 h) | idem |
| Custo da rodada de fichas do piloto | cerca de US$ 3 | idem |
| Parecer mediano (14 laudas) | entre 4 h e 14 h | idem |
| Despachos de encaminhamento | 41% dos documentos produzidos e menos de 5% das horas | idem |
| Fichas v1 → v2: sem lastro + contradito | 0,9% → 0% | [AUDITORIA.md](../AUDITORIA.md) |
| Fichas v1 → v2: incoerência | 25% → 7,8% | idem |
| Itens ancorados na v2 | 97,3% (o resto descartado) | idem |
| Coorte: fichas por modelo | 2.769 + 414 (dois modelos) | [RESULTADOS_FASE2.md](../RESULTADOS_FASE2.md) |
| Números das fichas sem âncora no texto (3.183 fichas, 9.722 números) | 30 (0,3%) | `saida/auditoria/auditoria_automatica.json` |
| Horas por caso nativo (piso; mediana) | reajuste 24,9 h; fiscalização 22,3 h; ocorrência 26,1 h | `saida/fase3/linha_base_*.json` |

Horas são hipótese até a calibração com servidores.
