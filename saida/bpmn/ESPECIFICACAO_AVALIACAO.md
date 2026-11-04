# Especificação da avaliação AS-IS (melhoria e automação com IA)

Um arquivo `saida/bpmn/avaliacao_<Pxx>.json` por processo organizacional, apoiado SÓ nas evidências:
`fichas_<Pxx>.json` (atividades com tempos, entradas, ferramentas, competências, perdas; métricas dos
casos e da carteira), `modelo_<Pxx>.json` (fluxo) e, se precisar, `evidencias_<Pxx>.md`,
`saida/fichas_trabalho.jsonl` e `docs/ASIS_PILOTO.md`. Todo número citado tem que estar nessas fontes.

## Referenciais

| Lente | O que olhar |
|---|---|
| Lean — 8 desperdícios | Espera; Defeitos/retrabalho; Superprocessamento; Transporte (tramitações e passagens sem trabalho); Estoque (processos parados em fila); Movimentação (busca de informação, consultas entre unidades); Superprodução (peças além do necessário, transcrição de peças anteriores); Talento não aproveitado (especialista em tarefa de expediente) |
| Mapeamento do fluxo de valor (VSM) | lead time, tempo de trabalho (faixa), eficiência do ciclo (PCE), % do tempo em espera dominante, passagens, retornos, espera de terceiros |
| Teoria das Restrições | gargalo: onde o processo espera mais e por quê |
| Seis Sigma | variabilidade entre caso típico e crítico e suas causas |
| Análise de valor | cada atividade: agrega valor · necessária sem valor (exigência legal ou de controle) · não agrega valor |
| ECRS | eliminar, combinar, reordenar, simplificar/padronizar |
| IA | o que um sistema de IA faria concretamente na atividade, e o que continua com o servidor |

Tipos de aplicação de IA (use estes rótulos): extração de dados de documentos · classificação e triagem ·
sumarização e linha do tempo · redação assistida de minuta · cálculo e conferência automática ·
verificação de conformidade · monitoramento de prazos e alertas · busca de precedentes e normas ·
automação de tramitação (RPA no SEI) · painel e indicadores.

## Formato

```json
{
  "codigo": "P06",
  "sintese": "3 a 5 frases com o diagnóstico do AS-IS",
  "leitura_metricas": "2 a 4 frases interpretando lead time, trabalho, PCE, espera, passagens e retornos",
  "gargalo": {"onde": "...", "evidencia": "...", "atividades": ["t5"]},
  "variabilidade": "típico × crítico: o que varia e por quê",
  "desperdicios": [
    {"tipo": "Espera", "evidencia": "...", "atividades": ["t3", "t5"], "severidade": "alta"}
  ],
  "atividades": {
    "t1": {
      "valor": "agrega valor | necessária sem valor | não agrega valor",
      "justificativa_valor": "uma frase",
      "potencial_ia": "alto | médio | baixo",
      "tipos_ia": ["extração de dados de documentos"],
      "aplicacao_ia": "o que a IA faria nesta atividade, concreto",
      "ganho_esperado": "o que reduz (horas de trabalho e/ou dias de espera), em ordem de grandeza e com a base",
      "controle_humano": "o que continua com o servidor (decisão, assinatura, juízo técnico)",
      "melhoria_lean": "ação sem IA (ECRS, padronização, prazo, paralelização) ou vazio"
    }
  },
  "oportunidades": [
    {"titulo": "...", "categoria": "IA | Lean | IA + Lean", "descricao": "...", "atividades": ["t3"],
     "ganho_esperado": "...", "impacto": "alto | médio | baixo", "esforco": "alto | médio | baixo",
     "prerequisitos": "dados, integração com o SEI, norma interna...", "riscos": "..."}
  ],
  "indicadores_sugeridos": ["..."],
  "perguntas_validacao": ["o que confirmar com a unidade antes de redesenhar"]
}
```

## Regras

1. Toda tarefa do modelo tem entrada em `atividades`.
2. 4 a 7 oportunidades, priorizadas (impacto alto e esforço baixo primeiro). Espera é o desperdício
   dominante nos processos da agência: diga se a IA reduz a espera (ex.: triagem, alertas de prazo,
   minuta pronta na chegada) ou só o tempo de trabalho.
3. Não proponha IA para decidir: decisão colegiada, juízo jurídico final e assinatura ficam com servidores.
4. Respeite o rito legal: razões finais, publicação e prazos de defesa são necessários sem valor — a
   melhoria é fazê-los mais rápido, não suprimi-los.
5. Ganho com base: cite a faixa de horas ou de dias úteis da ficha que o sustenta. Sem base, "a medir".
6. Português com acentuação correta.

## Versão 2 — regras de ancoragem (obrigatórias, 30/10/2026)

A auditoria da versão 1 achou números recalculados errado e permanência de unidade lida como espera
(ex.: "103 du de relatoria" quando a deliberação saiu 10 du após a chegada ao gabinete). A partir daqui:

1. **Tempo só da tabela de fatos** `saida/bpmn/fatos_<Pxx>.json` (linha do tempo do caso calculada por código):
   - `<caso>.<tarefa>.<n>.espera_antes` — dias úteis entre o fim da atividade anterior e o início desta, e
     `...espera_antes.<UNIDADE>` com quem estava o processo nesse intervalo;
   - `<caso>.<tarefa>.<n>.execucao` — da 1ª à última peça própria da ocorrência n;
   - `<caso>.posse.<UNIDADE>`, `<caso>.lead`, `<caso>.cauda`, `<caso>.terceiros` (resposta com data real),
     `<caso>.indeterminado` (não separável de processo parado — diga isso), `<caso>.juntada` (atraso interno
     de juntar peça recebida), `carteira.lead_mediano_nativos` e `carteira.lead_mediano_todos` (diga qual).
   Não use duração de passagem/estadia nem calcule intervalos, somas ou proporções novas.
2. **Cada bloco cita os fatos** que usa: `fatos_sintese`, `fatos_leitura_metricas`, `fatos_variabilidade`
   (listas no topo do JSON) e `fatos_usados` em `gargalo`, em cada `desperdicios[i]`, `oportunidades[i]` e
   `atividades[tN]`. Horas, laudas e contagens podem vir de `fichas_<Pxx>.json` (nova versão).
3. **Validação:** `python scripts/validar_avaliacao.py <Pxx>` tem que terminar com 0 problema.
4. **Erros conhecidos:** `saida/auditoria/auditoria_claims_<Pxx>.json` lista as afirmações da versão 1 julgadas
   contraditas, sem lastro, com cálculo errado ou imprecisas, com a correção. Nenhuma delas pode reaparecer.
5. Datas de fatos do caso só se estiverem nos fatos (`.inicio`, `.fim`) ou numa peça (citar a peça).

## Versão 3 — avaliação pela coorte (fase 2, 30/10/2026)

Os tipos sem caso-piloto (N01, P04, P07, P18, P19) não têm `fichas_<Pxx>.json` nem `vinculos_<Pxx>.json`. A
avaliação deles se apoia na coorte: todos os processos do código, com cada peça atribuída a uma atividade do modelo
e auditada às cegas por amostra. Fontes: `modelo_<Pxx>.json`, `saida/fase2/procedimento_<Pxx>.json` (contagens,
ferramentas, insumos, competências, sinais de perda, caminhos), `fatos_<Pxx>.json` e `evidencias_<Pxx>.md`.

1. **Tempo só de fatos `coorte.*`** (todos com `.mediana`, `.q1`, `.q3`, `.max` e `.n`, este último = número de
   observações):
   - `coorte.<tN>.espera_antes`, `coorte.<tN>.execucao` (du) e `coorte.<tN>.horas_piso` / `horas_teto` (h, por
     ocorrência); `coorte.<tN>.casos`, `.pct_casos`, `.casos_com_laco`; `coorte.<tN>.perda.<sinal>` (casos);
   - por caso nativo: `coorte.caso.lead`, `coorte.caso.espera_entre_atividades`, `coorte.caso.execucao_atividades`,
     `coorte.caso.horas_piso`, `coorte.caso.terceiros`, `coorte.caso.indeterminado`, `coorte.caso.oficios`,
     `coorte.caso.retornos`, `coorte.caso.unidades_ativas`; `coorte.posse.<UNIDADE>` (posse total por caso em que a
     unidade aparece; `SEM UNIDADE` = processo parado sem dono); `coorte.lead_nativos_encerrados`;
   - `coorte.transicao.<de>.<para>` (passagens) e `.pct`; `coorte.casos`, `coorte.trilha.<tipo>`, `coorte.n_caminhos`,
     `coorte.auditoria.concordancia_substantivas` (%) e `carteira.*` quando houver.
   Ao citar uma mediana, diga que é mediana e de quê (ex.: "mediana de 19 du de espera antes da atividade, em 28
   ocorrências"). Não some nem divida medianas; não compare mediana de uma coisa com soma de outra.
2. **Situação do código**, dita na `sintese`: *procedimento* (≥ 5 casos e auditoria ≥ 85%), *indicativo* (números
   com ressalva) ou *estudo de caso* (menos de 5 casos: nada de "padrão" nem "tendência"). Processos sem trilha
   (`coorte.trilha.sem`) só têm datas de juntada das peças: a espera antes da 1ª atividade e o lead time deles não
   existem — diga isso quando forem a maioria.
3. **Variabilidade** = dispersão na coorte (q1 × q3, máximo, casos com laço, número de caminhos), não típico × crítico.
4. **Horas** são estimativa por peça (hipótese até a calibração com servidores); as fichas vieram de dois modelos e
   as do segundo tendem a ter horas maiores. Use horas como ordem de grandeza.
5. Mesmo formato, mesmas regras 1 a 6 e mesmo validador (`python scripts/validar_avaliacao.py <Pxx>`, 0 problema).
   O validador aceita números do procedimento da coorte no lugar das fichas.

Tipo do piloto com modelo revisado na fase 2 (P08): as tarefas novas não têm fatos do caso-piloto; use os fatos
`coorte.*` delas, que também estão em `fatos_P08.json`.
