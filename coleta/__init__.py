"""Coletor de dados do SEI para o mapeamento de processos.

Lê a Pesquisa Pública do SEI (ou páginas salvas à mão no navegador) e grava as tabelas canônicas que o pipeline de
`scripts/` consome: `dados/sei2_dump/*.tsv` (trilha) e `dados/relator/*` (conteúdo das peças). Cada instalação do SEI
tem rótulos, cabeçalhos e redação de andamentos um pouco diferentes; essas diferenças ficam num perfil por Estado
(`coleta/perfil_sei.py`), não espalhadas pelo código. Guia completo em `docs/adaptacao/COLETA_SEI.md`."""
