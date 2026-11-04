# Especificação dos vínculos atividade → documentos

Um arquivo `saida/bpmn/vinculos_<Pxx>.json` por processo organizacional. Liga cada **tarefa** do
modelo canônico (`modelo_<Pxx>.json`) aos documentos reais dos casos-piloto
(`docs_<Pxx>.csv`, campo `ref` = `processo:sei_doc_id`) e descreve a atividade.

```json
{
  "codigo": "P06",
  "atividades": {
    "t1": {
      "docs": ["SEI-480002/007520/2025:112233445", "SEI-480002/005546/2024:99887766"],
      "docs_entrada": ["SEI-480002/007520/2025:112233400"],
      "descritivo": "A câmara técnica vistoria a instalação ...",
      "gatilho": "Fiscalização programada no plano anual ou demanda da Ouvidoria",
      "saida": "Relatório de fiscalização e termo de notificação enviados à concessionária",
      "observacoes": "No caso crítico a vistoria foi motivada por acidente; no típico, por plano anual."
    }
  }
}
```

- `docs`: documentos **produzidos pela AGENERSA** nessa atividade (autoria `agenersa`), dos dois casos.
  Um documento entra em no máximo uma atividade. Despachos de encaminhamento entram na atividade
  cuja passagem eles encerram ou abrem, quando fizer sentido; os que não se encaixam ficam fora.
- `docs_entrada`: peças externas (autoria `externa`: petições, ofícios e cartas da concessionária,
  respostas de órgãos) que são o insumo direto da atividade.
- `descritivo`: 2 a 4 frases sobre o trabalho real observado nas peças: o que a unidade faz, a partir
  de quê, com que finalidade, e o que varia entre casos. Sem adjetivos de avaliação, sem inventar.
- `gatilho`: o que dispara a atividade. `saida`: o que ela entrega e para quem.
- `observacoes`: ressalvas (atividade só em um caso, documentos restritos, inferência).
- Toda tarefa do modelo deve ter entrada; se não houver documento que a sustente, `docs` vazio e
  explicar em `observacoes`.
