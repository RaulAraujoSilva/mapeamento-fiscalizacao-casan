# Avaliação AS-IS — melhoria e automação com IA

Gerado por `scripts/gerar_site.py` a partir de `saida/bpmn/avaliacao_<código>.json`; navegação completa no site `docs/site/index.html`.

**Portfólio:** 8 atividades em 1 processos — 5 com alto potencial de IA, 3 com potencial médio; 2 agregam valor, 6 são necessárias sem valor (rito legal e controle) e 0 não agregam valor.

## P06 — Fiscalização técnica de campo (programada e por demanda)

Estudo de caso de 1 processo, o único do código na carteira, com trilha nativa do SEI: nada aqui é padrão nem tendência, e toda mediana citada é a de um único caso nativo, portanto instável. O processo está aberto e o último ato coletado, o ofício de ciência do parecer jurídico, é um fim provisório: o lead time de 636 du vai do início ao último andamento e ainda pode crescer. O trabalho está concentrado no ciclo de vistorias e relatórios da CASAN, e o tempo está nas esperas depois do ciclo, de 106 du antes do parecer técnico e de 205 du antes do parecer jurídico; no caso nativo, a espera entre atividades tem mediana de 552 du e a execução das atividades, mediana de 84 du. As horas (de 319,2 h a 477 h no caso nativo, piso e teto da mediana) são estimativa pelo conteúdo das peças, hipótese a calibrar com os servidores. Nenhuma peça da concessionária foi coletada e o rótulo de atividade das peças veio dos vínculos do próprio caso, sem classificador nem auditoria às cegas de rótulo fora do piloto (as fichas de trabalho, estas sim, tiveram amostra auditada), o que limita a leitura das esperas.

| Caso | Lead time (du) | Trabalho (h) | Eficiência do ciclo | Espera dominante |
|---|---|---|---|---|
| SEI-480002/001314/2024 (designado) | 636 | 320.0–477.6 | 8.4–12.5% | 89% |

**Gargalo:** Nas esperas entre o fim do ciclo de vistorias e os atos de conclusão, sobretudo antes do parecer jurídico e antes do parecer técnico, e não na vistoria nem na redação dos pareceres. Trata-se de uma restrição de fluxo (falta de marco e de responsável pela etapa seguinte), a confirmar com as unidades, e não de falta de capacidade de uma unidade: a posse registrada no SEI não prova que a unidade estava trabalhando nem que havia fila. — A maior espera antes de uma atividade é a do parecer jurídico, de 205 du, dos quais 203 du com a Procuradoria e 2 du com a Secretaria Executiva. Isso é posse no SEI: o Parecer 759 leva número de 2025, mas sua data no SEI é o mesmo dia do ofício de ciência, de modo que não se sabe se a Procuradoria analisava, aguardava distribuição ou só juntou a peça depois, e não se conclui fila da Procuradoria. A segunda maior é a do parecer técnico, de 106 du sem nenhuma unidade com o processo aberto, intervalo que provavelmente inclui o prazo de resposta da concessionária, cujas respostas não foram coletadas (a confirmar). Depois do parecer técnico vêm mais 55 du com a Secretaria Executiva antes da comunicação de ciência, peça estimada em 0,4 h, e 26 du antes da reanálise da CASAN. O trabalho estimado das atividades de conclusão é pequeno diante dessas esperas: 24,2 h no piso do parecer técnico e de 6 h a 12,7 h no parecer jurídico, hipótese a calibrar com os servidores.

**Desperdícios:** Espera (alta); Estoque (média); Defeitos/retrabalho (média); Movimentação (média); Talento não aproveitado (média); Transporte (baixa); Superprodução (baixa).

**Oportunidades prioritárias:**

1. **Painel de etapa seguinte e alerta de processo parado** (IA + Lean; impacto alto, esforço baixo) — Ataca a espera, não o trabalho: no caso, 306 du sem nenhuma unidade com o processo aberto, 106 du antes do parecer técnico e 55 du antes da ciência. A redução depende de a gestão agir sobre o alerta e de quanto dessas esperas é prazo da concessionária (a medir; estudo de caso de 1 processo).
2. **Matriz de não conformidades e de cumprimento por unidade vistoriada** (IA + Lean; impacto alto, esforço médio) — Trabalho: parte das 24,2 h (piso) e 11,9 h (teto) estimadas para o parecer técnico, hipótese a calibrar. Espera: com a matriz viva, o parecer pode sair logo depois do último prazo de resposta, em vez dos 106 du sem unidade observados no caso (redução a medir).
3. **Comunicação padronizada e automática com a concessionária** (IA + Lean; impacto médio, esforço baixo) — Espera curta e repetida: mediana de 6 du antes de cada encaminhamento de lote e de 8,5 du antes de cada agendamento (único caso nativo), além de 55 du antes da ciência do parecer técnico. Trabalho: mediana de 0,8 h no piso e de 1,1 h no teto por encaminhamento (caso nativo).

## Dados: o que existe e o que falta

| Campo | Situação | Como completar |
|---|---|---|
| Sequência de unidades e atividades | disponível | — |
| Tempo de espera | disponível | — |
| Tempo de trabalho | estimado | Estudo de tempo curto com as unidades (~20 peças-tipo) para calibrar a faixa |
| Descritivo, gatilho e saída | disponível | Validar redação com a unidade |
| Entradas (insumos) | disponível | — |
| Ferramentas, cálculos e testes | disponível | Sistemas e planilhas fora do SEI não aparecem nas peças — confirmar com a unidade |
| Competências | inferido | Validar com a gestão de pessoas e cruzar com a matriz de competências da agência |
| Base normativa | disponível | — |
| Executor (cargo) | parcial | Quem prepara a peça nem sempre assina: confirmar equipe com a unidade |
| Volume por ano | parcial | Extrair a lista completa de processos por tipo no SEI de todas as unidades |
| Custo da atividade (R$) | ausente — possível | Remuneração por cargo (Portal da Transparência RJ) × horas calibradas |
| Força de trabalho por unidade (FTE) | ausente — possível | Dados de RH da agência |
| Qualidade percebida pelo usuário/regulado | ausente — possível | Pesquisa ou dados da Ouvidoria |
| Peças restritas | ausente — limitado | Upload pelo gabinete (o relator já aceita PDF) ou acesso interno |
