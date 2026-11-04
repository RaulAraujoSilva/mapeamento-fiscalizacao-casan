"""Perfis de órgão: tudo o que é específico de um Estado/agência (calendário, unidades, tipos de documento, catálogo
de processos, base normativa, custo-hora, códigos do piloto). `scripts/comum.py` carrega o perfil indicado pela
variável de ambiente PERFIL (padrão `rj_agenersa`) e reexporta os nomes; os scripts só importam de `comum`.

Para adaptar a outro órgão: copie `modelo.py` para `<uf>_<orgao>.py`, preencha cada nome seguindo o comentário e rode
com PERFIL=<uf>_<orgao>. O perfil `rj_agenersa.py` é o caso de referência (saídas em saida/)."""
