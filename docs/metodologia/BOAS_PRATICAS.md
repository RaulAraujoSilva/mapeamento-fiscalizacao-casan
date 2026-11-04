# Boas práticas

Os princípios que fizeram o resultado do caso de referência ser confiável. Cada um tem a **regra**, o **porquê** (quase
sempre uma falha real) e **como é imposto** no código. Ao replicar, não relaxe nenhum deles para ganhar tempo: foi
relaxando que o caso errou, e cada correção custou uma rodada inteira de auditoria.

## A. Números

### A1. Toda métrica sai de código reprodutível
- **Regra.** Nenhum número é digitado à mão em planilha, texto, modelo ou site. Se um número aparece num entregável, há
  um script que o produz a partir dos dados.
- **Porquê.** Número digitado não se refaz quando a regra muda, e ninguém sabe de onde veio.
- **Como.** Planilhas, relatórios de resultado ([RESULTADOS_FASE2.md](../RESULTADOS_FASE2.md), [AVALIACAO_ASIS.md](../AVALIACAO_ASIS.md),
  [BENCHMARKING.md](../BENCHMARKING.md)) e o site são gerados por script (`gerar_planilha.py`, `resumo_fase2.py`,
  `gerar_site.py`, `benchmark_md.py`). Parâmetros e regras ficam só em `scripts/comum.py` (ou no perfil do órgão).

### A2. O agente escreve texto; o código escreve números
- **Regra.** Modelo, vínculo e avaliação feitos por agente não carregam frequência, dias, horas nem situação calculados
  por ele.
- **Porquê.** Na primeira versão, os agentes escreveram números nos modelos e erraram (falha D1); na avaliação v1, 3,9%
  das afirmações tinham cálculo errado ([AUDITORIA.md](../AUDITORIA.md)).
- **Como.** `test_modelo_sem_numeros_dos_agentes` recusa `freq`, `du`, `horas`, `nota`, `status` no modelo;
  `gerar_bpmn.py` calcula os números das tarefas.

### A3. Número em texto só de fato citado
- **Regra.** Todo número de uma avaliação, melhoria ou controle é o valor de um fato da tabela de fatos (ou de uma ficha
  ou do procedimento), e o bloco cita o id do fato. Dias úteis nunca se recalculam.
- **Porquê.** Com a tabela de fatos e o validador, as afirmações sem lastro caíram de 4,7% para 0,4%
  ([AUDITORIA.md](../AUDITORIA.md)).
- **Como.** `fatos.py` gera a tabela; `validar_avaliacao.py`, `validar_tobe.py` e `validar_controles.py` barram número,
  data, fato, requisito ou meta sem lastro.

### A4. Diga de que é a estatística e quantos casos tem
- **Regra.** Mediana é dita como mediana, de quê e em quantas observações. Não se somam nem se dividem medianas. Mediana
  de nativos e de todos são fatos diferentes.
- **Porquê.** Migrados distorcem a mediana da carteira (falha F3); soma de medianas não é a mediana da soma.
- **Como.** `test_validador_barra[mediana]`; regra 1 da versão 3 da especificação da avaliação.

### A5. Mediana é instável com poucos casos
- **Regra.** Tipo com menos de 5 casos é "estudo de caso" (nada de "padrão"); % de ramo de decisão exige ao menos 3
  transições; todo resultado mostra o n.
- **Porquê.** Com 7 encerrados, um caso a mais ou a menos muda a mediana de forma visível; percentuais de TO-BE com 11
  a 18 casos são ordem de grandeza.
- **Como.** `MIN_CASOS = 5` em `coorte_fase2.py` e `procedimento.py`; situação do código no procedimento;
  `test_probabilidade_dos_ramos_pela_transicao_observada`.

### A6. Medir a coisa certa
- **Regra.** Espera é medida pela linha do tempo repartida pela posse, nunca pela estadia. Tempo sem data real de resposta
  é "indeterminado", não "terceiros".
- **Porquê.** A estadia produziu o gargalo falso "fila de relatoria" (A1); a juntada usada como resposta inflava a
  espera de terceiros (A3).
- **Como.** `fatos.linha_do_tempo`, `trilhas.montar_posse`, `trilhas.janelas_espera_externa` e os testes sintéticos de
  cada regra ([02](02_TRILHA_TEMPO_POSSE.md)).

## B. Portões e versões

### B1. Portões que param o pipeline
- **Regra.** Checagem é portão: não gera nada, e se falha a sequência para. Nada é publicado de saída que não passou.
- **Porquê.** Uma checagem que só avisa vira aviso ignorado.
- **Como.** `pipeline.py` roda em ordem fixa e para no primeiro portão: testes das regras, `verificar_normas`,
  `validar_tobe`, `validar_controles`, `validar_avaliacoes --exigir-carimbo`, testes das saídas. Cada portão imprime uma
  dica do que corrigir.

### B2. Carimbo dos fatos e da linha de base
- **Regra.** A avaliação validada guarda a impressão digital dos fatos; a linha de base guarda o sha-256 das entradas; o
  resultado do TO-BE guarda o carimbo da linha de base.
- **Porquê.** Regeneração concorrente e regra de tempo alterada deixaram números velhos nas avaliações (F4).
- **Como.** `validar_avaliacao.py --carimbar` e `--exigir-carimbo`; `linha_base.py`; `test_carimbo_invalida_quando_fato_muda`,
  `test_resultado_tobe_atual_e_coerente`.

### B3. Não carimbar sem revisar
- **Regra.** Quando o portão do carimbo falha, revise o que o validador aponta, valide até 0 problema e só então carimbe.
  Recarimbar sem revisar é proibido. Quando os fatos novos só se somam aos antigos, confira que nenhum valor antigo
  mudou.
- **Porquê.** O carimbo existe para forçar a revisão; carimbar direto anula a trava.
- **Como.** Disciplina documentada no `CLAUDE.md` do projeto e na dica do pipeline; a conferência de "0 fatos antigos
  alterados" foi registrada no caso ([MITIGACOES.md](../MITIGACOES.md)).

### B4. Teste sintético para cada falha encontrada
- **Regra.** Toda falha achada em auditoria vira (1) regra corrigida no código e (2) teste com caso sintético mínimo que
  reproduz a falha. A matriz falha → mitigação → teste fica em [MITIGACOES.md](../MITIGACOES.md).
- **Porquê.** Sem o teste, a falha volta na próxima mudança.
- **Como.** [`tests/test_regras.py`](../../tests/test_regras.py) roda como primeira etapa do pipeline. Exemplos: posse
  de quem já concluiu, prorrogação como resposta, ofício sem prazo, prazo máximo com origem posterior ao ato, cauda de
  caso aberto, teto que cortava resposta de terceiro.

### B5. Determinismo e desempate estável
- **Regra.** Mesma entrada, mesma saída: semente fixa nas amostras, desempate pelo nome nas listas de frequência, ordem
  determinística dos candidatos.
- **Porquê.** A ordem de itens empatados mudava a cada rodada (conjuntos), e a impressão digital dos fatos mudava sem
  mudança real.
- **Como.** Semente fixa em `auditoria_classificador.py` e `comparar_modelos_fichas.py`; desempate em `procedimento.py`
  e `normas_processo.py`; duas rodadas com o mesmo hash como verificação.

### B6. Trava de execução e registro
- **Regra.** Uma execução do pipeline por vez; cada execução registra etapas, duração, commit e impressão digital dos fatos.
- **Porquê.** Duas regenerações simultâneas deixaram números velhos (F4).
- **Como.** `saida/.pipeline.lock` (expira em 2 h) e `saida/pipeline_execucao.json` em `pipeline.py`.

## C. Agentes e LLM

### C1. Especificação escrita antes do agente
- **Regra.** Nenhuma etapa de julgamento começa sem um `ESPECIFICACAO_*.md` com formato JSON, regras, fontes permitidas e
  como será validada.
- **Porquê.** Sem especificação, cada agente inventa um formato e um critério; não há como validar nem comparar rodadas.
- **Como.** Especificações em `saida/bpmn/` (modelo, vínculos, avaliação) e `saida/fase3/` (conformidade, benchmark,
  TO-BE); versões numeradas quando a regra muda (avaliação v1 → v2 → v3).

### C2. Saída estruturada, com lista fechada
- **Regra.** Saída de LLM em JSON com esquema; categorias por lista fechada (enum); valor fora da lista é descartado.
- **Porquê.** Rótulo livre não se agrega; rótulo fora das candidatas era atribuído a atividade de outra unidade.
- **Como.** Esquemas em `fichas_trabalho.py`, `classificar_atividades.py`, `classificar_novos.py`;
  `test_atribuicao_so_com_rotulo_valido_e_na_raia`.

### C3. Evidência literal conferida por código
- **Regra.** Todo item extraído por LLM traz um trecho literal do documento, e o código confere o trecho; item não
  ancorado não segue.
- **Porquê.** Reduziu a alucinação das fichas de 0,9% para 0% ([AUDITORIA.md](../AUDITORIA.md)).
- **Como.** `fichas_trabalho.ancorar`, `legado`; `test_ancoragem_*`; auditoria automática de números (camada B).

### C4. Auditoria às cegas por outro agente
- **Regra.** Classificação, rótulo de atividade, conclusões da avaliação e benchmarking são conferidos por um agente que
  não produziu a saída e não vê a resposta; ele recebe o mesmo insumo.
- **Porquê.** O agente que produz tende a confirmar a si mesmo; a avaliação contra o piloto deu 98% (otimista), a cega
  fora do piloto deu 88% no total ([RESULTADOS_FASE2.md](../RESULTADOS_FASE2.md)).
- **Como.** `auditoria_classificador.py --preparar/--comparar`; reclassificação cega das classificações; verificação
  independente do benchmarking (`verificacao.json`); verificação final dos blocos de conclusão.

### C5. Critério de aceite fixado antes
- **Regra.** Alucinação ≤ 2% e nenhuma em número que sustente conclusão; imprecisão ≤ 10%; classificação com concordância
  ≥ 85% e kappa ≥ 0,8. Fixado antes de olhar o resultado.
- **Porquê.** Critério escolhido depois do resultado sempre passa.
- **Como.** [PLANO_AUDITORIA_E_AMPLIACAO.md](../PLANO_AUDITORIA_E_AMPLIACAO.md); `CRITERIO = 0.85` em `procedimento.py`;
  `test_auditoria_do_classificador_atinge_criterio`, `test_auditoria_automatica_dentro_dos_limites`.

### C6. Um modelo por rodada, registrado
- **Regra.** Cada saída de LLM guarda o modelo e a versão do prompt; cache por versão; não troque de modelo no meio de
  uma rodada sem medir a diferença.
- **Porquê.** No caso, a troca forçada de modelo deu horas 1,42 vez maiores na mesma peça
  (`saida/fase2/comparacao_modelos_fichas.json`).
- **Como.** `PROMPT_VERSAO` e campo `modelo` em `fichas_trabalho.py`; `comparar_modelos_fichas.py`; fichas por modelo
  no procedimento.

### C7. IA não decide
- **Regra.** Nas propostas, decisão colegiada, juízo jurídico final e assinatura ficam com servidores; toda melhoria com IA
  tem controle humano e controle de qualidade com indicador.
- **Porquê.** Responsabilidade e devido processo; e a saída de IA tem taxa de erro que precisa ser medida.
- **Como.** Regra 3 da especificação da avaliação; `validar_tobe.py` (controle humano na fase 3);
  `validar_controles.py` (controle de qualidade para toda melhoria de fase 3).

## D. Fontes e lei

### D1. Trecho de norma literal, conferido contra o texto integral
- **Regra.** Todo trecho de norma é copiado do texto integral lido, até 60 palavras, e conferido por código; fonte externa
  à base vai para conferência manual com URL.
- **Porquê.** Artigo, prazo e número escritos de memória pelo LLM são o erro mais perigoso num entregável regulatório.
- **Como.** `verificar_normas.py` (portão); `test_requisitos_testam_atividades_do_modelo`.

### D2. Citação científica conferida
- **Regra.** DOI conferido no Crossref, trecho literal achado na fonte, resultado e parâmetro sem exagero; nunca de memória.
- **Porquê.** 13 de 64 casos precisaram de correção na verificação independente, quase sempre por dizer mais do que a fonte.
- **Como.** [08](08_BENCHMARKING.md); `test_benchmark_verificado_sem_caso_excluido`.

### D3. Rito legal e tempo de terceiro protegidos
- **Regra.** Prazo concedido à parte é requisito `prazo_min` e não pode ser cortado; resposta de terceiro não é espera da
  agência; razões finais e publicação são "necessárias sem valor", não desperdício.
- **Porquê.** Sem a trava, o TO-BE "ganharia" cortando defesa e cobrando da agência o tempo da concessionária.
- **Como.** `validar_tobe.py`; `simular_tobe.aplicar`; `test_tobe_teto_e_reducao_nao_cortam_resposta_de_terceiro`.

## E. Hipóteses, dados e entregáveis

### E1. Hipótese marcada como hipótese
- **Regra.** Horas, custo-hora, fator de custo total, 6 h produtivas por dia e coeficientes do modelo de esforço são
  hipótese até a calibração; melhoria sem benchmark é `hipotese: true`. O entregável diz isso onde o número aparece.
- **Porquê.** O SEI não registra horas; um número de horas sem ressalva vira dimensionamento de equipe.
- **Como.** Comentários "HIPÓTESE" em `comum.py`; `ressalvas` em `linha_base_<cod>.json`; regra de hipótese em
  `validar_tobe.py`; especificação da avaliação (regra 4 da versão 3).

### E2. Dados pessoais fora do git
- **Regra.** Tabelas do SEI, textos e pacotes de auditoria (que têm nomes, e-mails, endereços) ficam em `dados/`, fora do
  versionamento. O que vai ao site passa por limpeza.
- **Porquê.** As peças trazem dados de terceiros; o repositório é compartilhado.
- **Como.** `.gitignore`; `fichas_atividades.limpar_pessoais` (nome de usuário, endereço, CPF, e-mail, telefone);
  `test_limpeza_de_dados_pessoais`, `test_site_sem_dados_pessoais_nem_campos_antigos`.

### E3. Credenciais só por variável de ambiente
- **Regra.** URL de banco e chaves de API são lidas do ambiente e nunca impressas.
- **Porquê.** Log e arquivo versionado vazam segredo.
- **Como.** `exportar_relator.py` (no caso) lê `DATABASE_URL` e não imprime; scripts de LLM leem a chave do ambiente.

### E4. Entregável institucional sem IA e sem caminho local
- **Regra.** Relatório para o órgão não menciona IA, nomes de modelo nem caminhos locais de arquivo; acentuação correta.
  (Material didático do curso pode e deve falar de IA.)
- **Porquê.** O entregável é do órgão, não do método; caminho local não diz nada ao leitor e expõe a máquina.
- **Como.** Regra do projeto; o site não expõe o modelo de linguagem de cada ficha (`fichas_por_modelo` sai dos dados do
  site, `gerar_site.py`).

### E5. Validação humana é etapa
- **Regra.** Há paradas obrigatórias com servidores: trilha de um caso, lacunas do catálogo, perguntas de validação do
  modelo, gargalo, matriz de requisitos, melhorias de maior peso e metas ([ROTEIRO_REPLICACAO.md](ROTEIRO_REPLICACAO.md)).
- **Porquê.** O método reconstrói do registro; quem executa confirma o que o registro não mostra (critério de decisão,
  trabalho fora do SEI, tempo real de uma peça).
- **Como.** `perguntas_validacao` em cada avaliação; pontos a validar em [BPMN_PILOTO.md](../BPMN_PILOTO.md).
