"""Perfil do caso de estudo: processo SEI-480002/001314/2024 (AGENERSA, Fiscalização da Iguá Rio de Janeiro S.A.),
indicado por colega do curso como exemplo. Mesmo órgão do caso de referência: herda calendário, unidades, tipos de
documento, catálogo e custo-hora de `rj_agenersa.py` e troca só o que é específico da base deste caso."""
import importlib.util as _ilu
from pathlib import Path as _Path

_spec = _ilu.spec_from_file_location("perfil_rj_agenersa_base", _Path(__file__).with_name("rj_agenersa.py"))
_base = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_base)
globals().update({k: v for k, v in vars(_base).items() if not k.startswith("_")})

DESCRICAO_BASE = "processo SEI-480002/001314/2024 (Pesquisa Pública do SEI-RJ)"
DADOS = "dados"
ORDEM_CODIGOS = ["P06"]
CODIGOS_FASE3 = ["P06"]  # um único processo: conformidade, linha de base, TO-BE e controles de P06
FAMILIA_BENCHMARK = {"P06": "fiscalizacao"}
# piloto designado pelo aluno (processo indicado como exemplo, ainda em andamento na data de corte)
PILOTO_DESIGNADO = {"SEI-480002/001314/2024": "processo indicado como caso de estudo"}
# coorte da fase 2 com o único caso (procedimento.py mantém o rótulo "estudo_de_caso" abaixo de 5 casos)
MIN_CASOS_COORTE = 1
