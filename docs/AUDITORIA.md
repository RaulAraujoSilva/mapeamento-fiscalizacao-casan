# Auditoria de acurácia — mapeamento AS-IS a partir do SEI

30/10/2026 · plano em `docs/PLANO_AUDITORIA_E_AMPLIACAO.md` · evidências em `saida/auditoria/`

## Como foi feita

Cada camada do pipeline foi auditada por um verificador que não produziu a camada, indo às fontes
primárias (texto das peças, andamentos do SEI). Onde possível, a checagem é automática e cobre 100%;
onde exige leitura, auditores independentes julgaram afirmação por afirmação.

| Camada | Método | Volume |
|---|---|---|
| A. Trilha (estadias, posse, tempos) | checagens automáticas + reconstrução manual pelos auditores | 251 processos; 12.306 peças cruzadas SEI 2 × banco do relator |
| B. Fichas de trabalho por peça | ancoragem automática de números e trechos + 2 auditorias independentes | 357 fichas; amostras de 40 (v1) e 30 (v2) peças, 451 e 332 itens |
| C. Classificação P01–P36 | reclassificação às cegas | 63 processos |
| D. Modelos BPMN | consistência automática + auditores | 81 tarefas, 356 afirmações |
| E. Vínculos e descritivos | auditores | 492 afirmações |
| F. Avaliações | validador automático + 3 rodadas de auditoria | 909 → 835 → (rodada 3) afirmações |

## Resultados por camada

### A. Trilha — aprovada após duas correções de regra
- Sem divergência de unidade ou data entre SEI 2 e banco do relator (12.306 peças); posse sem lacunas.
- **Erro 1 (corrigido):** "permanência" da unidade (tempo com o processo aberto) foi usada como espera. Ela
  corre em paralelo com outras unidades e se estende depois do marco — gerou o falso gargalo "fila de
  relatoria". Substituída pela **linha do tempo**: execução de cada atividade (1ª a última peça própria) e
  **espera antes** (do fim da atividade anterior ao início desta), dividida entre quem tinha o processo.
- **Erro 2 (corrigido):** a posse ficava com a unidade da última remessa mesmo depois de ela concluir. Agora
  a posse é de quem tem o processo aberto; sem ninguém, o tempo é **SEM UNIDADE** (processo parado sem dono).
- **Erro 3 (corrigido):** "aguardando terceiros" fechava a janela na juntada, não na resposta, e ignorava
  respostas por peticionamento em processo relacionado. Agora usa a data real da resposta, reconhece
  peticionamento e limita a espera ao prazo dado no ofício + 5 du; o excesso é "indeterminado".

### B. Fichas de trabalho — aprovada na alucinação, imprecisão no limite
| | v1 | v2 |
|---|---|---|
| Sem lastro + contradito | 0,9% | **0%** |
| Parcial | 11,8% | 11,1% |
| Incoerência (complexidade, composição) | 25% | 7,8% |
| Números sem âncora no texto (automático, 100%) | 0,5% | 0,2% |

Mudanças da v2: cada item exige trecho literal verificado por código (97,3% ancorados; o resto descartado);
trabalho próprio separado do reproduzido; rubricas de complexidade e composição do texto; prazos com
natureza e destinatário. Travas determinísticas depois: ferramenta só com evidência que não seja fórmula de
expediente; detecção de peça que repete ≥ 60% de outra da mesma categoria (11 casos: refazimento,
reiteração, nova versão); limpeza de dados pessoais. A imprecisão residual (11%) se concentra em
classificação de prazos e fontes citadas, que não sustentam conclusões do site.

### C. Classificação — aprovada
Concordância 92,1%, kappa 0,91 (96,8% considerando o secundário); 100% nas de confiança alta; as 5
divergências são de fronteira e nenhuma em caso do piloto.

### D/E. Modelos e descritivos — aprovados após correção
- Descritivos: 0,6% sem lastro ou contradito, 5% imprecisos; os apontados foram corrigidos.
- Modelos: frequência, dias, horas, situação (espera/perda) e notas passaram a ser **calculados** a partir da
  linha do tempo e das fichas; o texto dos agentes ficou só com nomes, fluxo e decisões. Um evento corrigido
  (P08: distribuição por sorteio, não prevenção).

### F. Avaliações — três rodadas
| Rodada | Afirmações | Sem lastro + contradito | Cálculo errado | Sentido errado | Imprecisas |
|---|---|---|---|---|---|
| 1 (original) | 909 | 4,7% | 3,9% | — | 10,5% |
| 2 (fatos + validador) | 835 | 0,4% | 0,1% | 3,7% | ≈ 10% |
| 3 (posse e terceiros corrigidos; verificação final dos blocos de conclusão) | 371 | 1,3% (0 sem lastro) | 0,5% | 0,5% | 6,5% |

Mudanças da rodada 2: tabela de fatos calculada por código como única fonte de números; cada bloco cita os
fatos que usa; validador barra número que não seja valor de fato citado. Resultado: nenhum número inventado.
Os erros que restaram vinham das regras de posse e de terceiros (camada A), corrigidas para a rodada 3.

Rodada 3: verificação independente recalculou a posse dia a dia a partir das estadias (diferença de 0–1 du)
e confirmou cada período "sem unidade". Os 9 itens com erro (contradito, cálculo ou sentido) e os imprecisos
apontados foram corrigidos pontualmente; o validador termina com 0 problema nos 8 processos.

**Gargalos declarados após a verificação final:** se sustentam em P01 (com ressalva: parte da espera do
típico foi o verificador FIPE em atraso), P06, P21, P22, P36 e P35 (no crítico, o tempo sem unidade empata
com a apuração da CAPET). Em P03, o ciclo de obtenção de dados se sustenta com correções de atribuição. Em
P08, só o "processo parado sem dono" se sustenta; a Procuradoria deixou de ser apontada como gargalo.

## Decisão sobre a fase 2

Os critérios de aceite foram atingidos em todas as camadas (alucinação ≤ 2% e nenhuma em número que
sustente conclusão; imprecisão ≤ 10%; classificação com kappa 0,91). A base é confiável para ampliar, com
três condições:
1. A ampliação usa o mesmo pipeline com as travas (evidência literal nas fichas, linha do tempo calculada,
   tabela de fatos, validador) — nenhuma avaliação sem elas.
2. Auditoria por amostra a cada lote ampliado (fichas e conclusões), com o mesmo critério.
3. Ajustes de regra ainda abertos, documentados: pedido de prorrogação do terceiro contado como resposta
   (subestima a espera de terceiros); data real disponível em ~56% das peças externas.

**Atualização (30/10/2026):** a regra de prorrogação foi corrigida e cada falha desta auditoria tem agora regra,
teste automático e portão no `scripts/pipeline.py` — matriz em `docs/MITIGACOES.md`. A data real das peças
externas segue como limite declarado (sem ela, o tempo é "indeterminado").

## Conclusões que mudaram com a auditoria

- **O gargalo não é a redação da relatoria.** Em P01, P03 e P21 a deliberação saiu poucos dias após a
  chegada ao gabinete; em P22 e P36 houve um a dois meses entre as razões finais e a sessão (pauta). O tempo
  longo estava sobretudo na instrução (diligências, pareceres) e depois da decisão.
- **Processo parado sem dono** aparece como achado próprio: períodos em que todas as unidades concluíram e
  nenhuma reabriu (ex.: P01 crítico, 108 du após a CAPET concluir em 35 minutos).
- **A espera de terceiros é menor do que parecia** quando se usa a data real da resposta e o prazo dado; boa
  parte do que parecia "esperar a concessionária" era tempo interno.
- Esforço segue como faixa (piso–teto); a v2 reduziu o teto em 20–40%.

## Limites que permanecem

- Peças restritas não têm texto (P21 e P35 críticos sobretudo): afirmações sobre elas se apoiam no tipo e em
  peças posteriores que as relatam.
- Quem assina não é necessariamente quem preparou a peça.
- Data real das peças externas existe para ~56% delas; sem ela, a espera vai para "indeterminado".
- Tempo de trabalho é estimativa até o estudo de tempo com as unidades.
