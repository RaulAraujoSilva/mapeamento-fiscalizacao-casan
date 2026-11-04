# Especificação do modelo canônico (entrada do gerador BPMN)

Um arquivo `saida/bpmn/modelo_<Pxx>.json` por processo organizacional. O gerador
(`scripts/gerar_bpmn.py`) calcula o layout e escreve o BPMN 2.0 — o modelo só diz O QUE existe e
COMO se liga, nunca coordenadas.

```json
{
  "codigo": "P06",
  "nome": "Fiscalização técnica de campo",
  "escopo": "Do início da fiscalização à ciência da deliberação e arquivamento",
  "raias": [
    {"id": "CAENE", "nome": "Câmara de Energia (CAENE)"},
    {"id": "SCEXEC", "nome": "Secretaria Executiva"},
    {"id": "EXT", "nome": "Concessionária e terceiros"}
  ],
  "elementos": [
    {"id": "s1", "tipo": "inicio", "raia": "CAENE", "nome": "Fiscalização programada ou demanda recebida"},
    {"id": "t1", "tipo": "tarefa", "raia": "CAENE", "nome": "Vistoriar instalação e emitir relatório",
     "gatilho": "Programação anual ou demanda de usuário", "saida": "Relatório de fiscalização e termo de notificação"},
    {"id": "g1", "tipo": "xor", "raia": "PROC", "nome": "Instrução suficiente?"},
    {"id": "g2", "tipo": "xor_juncao", "raia": "PROC"},
    {"id": "e1", "tipo": "evento_tempo", "raia": "EXT", "nome": "Prazo da concessionária decorrido"},
    {"id": "f1", "tipo": "fim", "raia": "SCEXEC", "nome": "Processo arquivado"}
  ],
  "fluxos": [
    {"de": "s1", "para": "t1"},
    {"de": "g1", "para": "t5", "rotulo": "Sim", "principal": true},
    {"de": "g1", "para": "t9", "rotulo": "Não"}
  ],
  "fontes": "Casos SEI-480002/007520/2025 (típico) e SEI-480002/005546/2024 (crítico); 32 processos do código."
}
```

## Campos

- `raias`: de cima para baixo, na ordem em que as unidades entram no fluxo. Use só unidades que
  de fato atuam. Concessionária e órgãos externos podem ser uma raia `EXT` (última). O `id` ou o
  `nome` da raia tem de conter a sigla SEI exata de cada unidade que ela representa (ex.: "Câmara
  técnica (CAENE ou CASAN)"): é por ela que as peças são ligadas à raia (`fatos.na_raia`).
- `tipo`: `inicio`, `fim`, `tarefa`, `xor` (decisão, nome em pergunta com "?"), `xor_juncao`
  (sem nome), `paralelo` / `paralelo_juncao`, `evento_tempo` (espera de prazo), `evento_mensagem`
  (resposta/peça externa recebida).
- Tarefa: `nome` = verbo no infinitivo + objeto, até ~7 palavras. `gatilho` e `saida` (fase 2,
  obrigatórios nos tipos sem vínculos do piloto): o que dispara a atividade e a peça que ela produz,
  em até 12 palavras cada — é o que o classificador de atividade usa para reconhecer a peça.
- Nenhum número no modelo: frequência, dias, horas e status saem do código (`fatos.py`,
  `procedimento.py`); `freq`, `du`, `horas`, `nota` e `status` são recusados pelos testes.
- `fluxos`: `principal: true` marca a saída do caminho feliz de um `xor` (segue reto à direita);
  as demais saem por baixo. Laços (voltar a uma tarefa anterior) são permitidos: o gerador roteia
  por baixo da piscina.

## Regras de modelagem

1. **Canônico, não transcrição.** Consolidar típico + crítico (+ trilhas dos demais processos do
   código) num fluxo que um servidor reconheça. Variações observadas viram `xor` com laço; o que
   só aparece em parte dos casos entra como ramo alternativo.
2. **Máximo de 25 elementos.** Encaminhamentos puros da Secretaria (despacho de encaminhamento)
   não viram tarefa: a passagem pela Secretaria só vira tarefa quando ela faz algo (sortear relator,
   oficiar, publicar, certificar, encerrar). A fila que a Secretaria gera vai para a `nota` da
   tarefa seguinte.
3. **Sem invenção.** Toda tarefa, decisão e laço tem que estar nas evidências (`saida/bpmn/
   evidencias_<Pxx>.md`) ou em `docs/ASIS_PILOTO.md`. Não modelar etapas do escopo teórico do
   inventário que não aparecem nos processos.
4. Português com acentuação correta.
