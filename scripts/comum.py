"""Funções compartilhadas: caminhos, carga do dump SEI 2, calendário de dias úteis e
categorização de documentos e andamentos do SEI.

O que é específico do órgão (feriados, unidades, tipos de documento, catálogo, base normativa, custo-hora, códigos
do piloto) vem do perfil em perfis/<nome>.py, escolhido pela variável de ambiente PERFIL (padrão rj_agenersa, o caso
de referência). Este módulo carrega o perfil e reexporta os nomes: os demais scripts importam só de `comum`."""
from __future__ import annotations

import importlib.util
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]


def _carregar_perfil():
    """Perfil por nome (perfis/<PERFIL>.py) ou por caminho de arquivo .py."""
    nome = os.environ.get("PERFIL") or "rj_agenersa"
    arq = Path(nome) if nome.endswith(".py") else RAIZ / "perfis" / f"{nome}.py"
    if not arq.exists():
        raise SystemExit(f"perfil não encontrado: {arq} (variável PERFIL)")
    spec = importlib.util.spec_from_file_location(f"perfil_{arq.stem}", arq)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PERFIL = _carregar_perfil()


def _caminho(var: str, valor: str, base: Path = RAIZ) -> Path:
    """Variável de ambiente, se definida; senão o valor do perfil, relativo a `base` quando não for absoluto."""
    p = Path(os.environ.get(var) or valor)
    return p if p.is_absolute() else base / p


# ---------------------------------------------------------------- caminhos
DADOS = _caminho("SEI_DADOS", PERFIL.DADOS)  # fora do git: dump, banco do relator, caches
DUMP = DADOS / "sei2_dump"
SAIDA = RAIZ / "saida"
SAIDA.mkdir(exist_ok=True)
CATALOGO = _caminho("SEI_CATALOGO", PERFIL.CATALOGO)
# o catálogo (dados_processos.py, oficina_dados.py) é importado por nome; oficina_dados importa dados_processos
if str(CATALOGO) not in sys.path:
    sys.path.insert(0, str(CATALOGO))

# ---------------------------------------------------------------- identidade e unidades (perfil)
ORGAO = PERFIL.ORGAO
DESCRICAO_BASE = PERFIL.DESCRICAO_BASE
DESCRICAO_ORGAO = PERFIL.DESCRICAO_ORGAO  # apresentação do órgão nos prompts dos LLM
SETORES_ORGAO = PERFIL.SETORES_ORGAO
NATUREZA_UNIDADE = PERFIL.NATUREZA_UNIDADE
PREFIXO_GABINETE = PERFIL.PREFIXO_GABINETE
SECRETARIA = PERFIL.SECRETARIA
RECEPCAO = PERFIL.RECEPCAO
RAIA_ALIAS = PERFIL.RAIA_ALIAS

# Início do SEI no órgão: andamentos anteriores não existem no dump (processos físicos migrados)
INICIO_SEI = pd.Timestamp(PERFIL.INICIO_SEI)


def _tsv(nome: str, **kw) -> pd.DataFrame:
    return pd.read_csv(DUMP / nome, sep="\t", na_values="NULL", quoting=3, keep_default_na=False, **kw)


def carregar():
    """Retorna (processos, andamentos, protocolos) do dump SEI 2."""
    p = _tsv("processos.tsv", parse_dates=["data_geracao", "data_ultimo_andamento"])
    a = _tsv("andamentos.tsv", parse_dates=["data_hora"])
    d = _tsv("protocolos.tsv", parse_dates=["data", "data_inclusao"])
    for df in (p, a, d):
        for c in df.columns:
            if df[c].dtype == object:
                # inerte de propósito: r"\\n" com regex=False procura barra dupla + n, que o dump não tem (o "\n"
                # literal fica). Corrigir mudaria textos e números do caso de referência.
                df[c] = df[c].replace("", np.nan).str.replace(r"\\n", "\n", regex=False)
    return p, a, d


# ---------------------------------------------------------------- calendário
def _pascoa(ano: int) -> date:
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    mes = (h + l_ - 7 * m + 114) // 31
    dia = ((h + l_ - 7 * m + 114) % 31) + 1
    return date(ano, mes, dia)


def feriados(anos=PERFIL.ANOS_FERIADOS) -> list[date]:
    """Feriados que fecham o expediente do órgão (perfil): móveis contados da Páscoa e fixos (mês, dia)."""
    out = []
    for y in anos:
        p = _pascoa(y)
        out += [p + timedelta(days=k) for k in PERFIL.FERIADOS_MOVEIS]
        for m, d in PERFIL.FERIADOS_FIXOS:
            out.append(date(y, m, d))
    return out


_FERIADOS = np.array(feriados(), dtype="datetime64[D]")


def somar_du(ini, n: float) -> pd.Timestamp:
    """Data n dias úteis depois de ini."""
    d = np.busday_offset(np.datetime64(pd.Timestamp(ini).date(), "D"), int(n), roll="forward", holidays=_FERIADOS)
    return pd.Timestamp(d)


def dias_uteis(ini, fim) -> float:
    """Dias úteis entre dois instantes (fração do dia ignorada; NaN se faltar algum)."""
    if pd.isna(ini) or pd.isna(fim):
        return np.nan
    a = np.datetime64(pd.Timestamp(ini).date(), "D")
    b = np.datetime64(pd.Timestamp(fim).date(), "D")
    if b < a:
        return 0.0
    return float(np.busday_count(a, b, holidays=_FERIADOS))


# ---------------------------------------------------------------- andamentos
_RE_REMETIDO = re.compile(r"^Processo remetido pela unidade (\S+)")


def tipo_andamento(descr: str) -> tuple[str, str | None]:
    """Classifica a descrição do andamento. Retorna (evento, unidade_origem)."""
    s = (descr or "").strip()
    m = _RE_REMETIDO.match(s)
    if m:
        return "remetido", m.group(1)
    if s.startswith("Processo recebido na unidade"):
        return "recebido", None
    if s.startswith("Conclusão do processo na unidade") or s.startswith("Conclusão automática"):
        return "conclusao", None
    if s.startswith("Reabertura do processo na unidade"):
        return "reabertura", None
    if re.match(r"^Processo (público|restrito|sigiloso)? ?gerado", s):
        return "gerado", None
    if s.startswith("Disponibilizado acesso externo"):
        return "acesso_externo", None
    if s.startswith("Cancelada disponibilização"):
        return "acesso_externo_cancelado", None
    if s.startswith("Liberada assinatura externa"):
        return "assinatura_externa", None
    if re.search(r"\b(anexado|apensado|desanexado|desapensado)\b", s):
        return "anexacao", None
    if re.search(r"sobrestad", s, re.I):
        return "sobrestamento", None
    if re.search(r"relacionamento", s, re.I):
        return "relacionamento", None
    return "outro", None


def motivo_acesso_externo(descr: str) -> str:
    """Finalidade declarada da disponibilização de acesso externo (texto livre após o prazo)."""
    s = (descr or "").lower()
    if "peticionamento" in s:
        return "peticionamento"
    for chave, rot in [("razões finais", "razoes_finais"), ("razoes finais", "razoes_finais"),
                       ("vista", "vista"), ("manifesta", "manifestacao"), ("defesa", "defesa"),
                       ("recurso", "recurso"), ("reunião", "reuniao"), ("reuniao", "reuniao"),
                       ("ciência", "ciencia"), ("ciencia", "ciencia"), ("notifica", "notificacao"),
                       ("intima", "notificacao"), ("ofício", "oficio"), ("oficio", "oficio")]:
        if chave in s:
            return rot
    return "outro"


# ---------------------------------------------------------------- documentos
# (regex sobre o "tipo" do protocolo, categoria, natureza do trabalho, horas-base de esforço) — do perfil:
# cada órgão configura no SEI os seus tipos de documento. Horas-base são HIPÓTESE a calibrar (Fase 3 do método).
CATEGORIAS = PERFIL.CATEGORIAS
_CAT_RE = [(re.compile(rx, re.I), c, n, h) for rx, c, n, h in CATEGORIAS]

# Modelo de esforço por conteúdo (HIPÓTESE a calibrar com o estudo de tempo da Fase 2):
# horas = horas_base + laudas_autorais × H_LAUDA[complexidade] + docs_analisados × H_LEITURA + fontes_externas × H_FONTE
CARACTERES_LAUDA = 1250
H_LAUDA = {1: 0.05, 2: 0.25, 3: 0.5, 4: 0.9, 5: 1.5}
H_LEITURA = 0.25
H_FONTE = 1.0


def horas_modelo(horas_base: float, n_chars: float, fracao_autoral: float, complexidade, n_analisados, n_fontes) -> float:
    try:
        c = int(round(float(complexidade)))
    except (TypeError, ValueError):
        return horas_base
    laudas = (n_chars or 0) / CARACTERES_LAUDA * min(max(float(fracao_autoral or 0), 0.0), 1.0)
    return (horas_base + laudas * H_LAUDA.get(min(max(c, 1), 5), 0.5)
            + float(n_analisados or 0) * H_LEITURA + float(n_fontes or 0) * H_FONTE)


def categoria_documento(tipo: str, numero: str) -> tuple[str, str, float]:
    """(categoria, natureza_do_trabalho, horas_base) de um protocolo."""
    if not str(numero).isdigit():  # protocolo que é outro processo (anexado/relacionado)
        return "processo_relacionado", "tramitacao", 0.0
    t = (tipo or "").strip()
    for rx, c, n, h in _CAT_RE:
        if rx.search(t):
            return c, n, h
    return "outro", "juntada", 0.2


def natureza_unidade(u: str) -> str:
    if not isinstance(u, str):
        return "?"
    if u == "SEM UNIDADE":
        return "Sem unidade (processo parado)"
    org, _, sigla = u.partition("/")
    if org != ORGAO:
        return "Externo (" + org + ")"
    if sigla.startswith(PREFIXO_GABINETE):
        return "Gabinete de conselheiro"
    return NATUREZA_UNIDADE.get(sigla, "Apoio/assessoria")


def sigla(u: str) -> str:
    """'AGENERSA/CAPET' → 'CAPET' (órgão do perfil); externos mantêm o órgão."""
    if not isinstance(u, str):
        return "?"
    return u.split("/", 1)[1] if u.startswith(ORGAO + "/") else u


# ---------------------------------------------------------------- peças: SEI 2 + processos só do relator
def documentos(**kw) -> pd.DataFrame:
    """Peças do SEI 2 (saida/documentos.csv, com trilha) e, se gerado, das peças dos processos que só existem no
    banco do relator (saida/fase2/documentos_relator.csv, sem trilha: sem estadia, posse nem andamentos)."""
    kw.setdefault("low_memory", False)
    kw.setdefault("dtype", {"numero": str})
    d = pd.read_csv(SAIDA / "documentos.csv", **kw)
    arq = SAIDA / "fase2" / "documentos_relator.csv"
    if arq.exists():
        d = pd.concat([d, pd.read_csv(arq, **kw)], ignore_index=True)
    return d


# ---------------------------------------------------------------- fase 3: base normativa e volume (perfil)
# sqlite da base normativa (só leitura), relativo a DADOS; textos integrais em caminhos relativos à pasta-avó do
# sqlite (convenção da base do Especialista AGENERSA: <raiz>/data/base.sqlite + data/txt/...). Esquema mínimo e
# montagem a partir de textos e da planilha de deliberações: docs/adaptacao/BASE_NORMATIVA.md, montar_base_normas.py
BASE_NORMAS = _caminho("BASE_NORMAS", PERFIL.BASE_NORMAS, DADOS)
TEXTOS_NORMAS = _caminho("TEXTOS_NORMAS", str(BASE_NORMAS.parents[1]))

RUIDO_NORMA = PERFIL.RUIDO_NORMA  # normas citadas em toda peça (SEI, assinatura eletrônica): não são base da atividade
VOLUME_REGRAS = PERFIL.VOLUME_REGRAS  # código → (tipos de decisão, regex no tema/ementa); volume é piso
VOLUME_ANOS = PERFIL.VOLUME_ANOS  # anos completos usados na média

# códigos do piloto do TO-BE e família de benchmarking de cada um
CODIGOS_FASE3 = list(PERFIL.CODIGOS_FASE3)
FAMILIA_BENCHMARK = PERFIL.FAMILIA_BENCHMARK
FAMILIAS_BENCHMARK = PERFIL.FAMILIAS_BENCHMARK

# catálogo: sugestão por palavras-chave, peça característica, tipos da coorte, ordem de apresentação
REGRAS_SUGESTAO = PERFIL.REGRAS_SUGESTAO
PECA_CARACTERISTICA = PERFIL.PECA_CARACTERISTICA
CODIGOS_NOVOS_FASE2 = set(PERFIL.CODIGOS_NOVOS_FASE2)
TIPOS_FORA_CATALOGO = PERFIL.TIPOS_FORA_CATALOGO
ORDEM_CODIGOS = list(PERFIL.ORDEM_CODIGOS)

# Custo-hora do trabalho (R$/h) = vencimento base inicial do cargo ÷ horas do mês (fonte e ressalvas no perfil). Não
# inclui gratificações, progressão nem encargos: por isso o fator de custo total, que é HIPÓTESE até os dados do RH.
HORAS_MES = PERFIL.HORAS_SEMANAIS * 52 / 12
VENCIMENTO_BASE_2022 = PERFIL.VENCIMENTO_BASE  # nome histórico: é a chave gravada na linha de base (carimbo)
CUSTO_HORA_BASE = {k: round(v / HORAS_MES, 2) for k, v in VENCIMENTO_BASE_2022.items()}
CARGO_PADRAO = PERFIL.CARGO_PADRAO  # peças técnicas e jurídicas de nível superior
FATOR_CUSTO_TOTAL = PERFIL.FATOR_CUSTO_TOTAL
# Horas de trabalho de um servidor em tempo integral no ano: 8 h × (dias úteis do ano − férias em du)
FERIAS_DU = PERFIL.FERIAS_DU


def horas_ano_fte(ano: int = 2025) -> float:
    return 8 * (dias_uteis(pd.Timestamp(f"{ano}-01-01"), pd.Timestamp(f"{ano + 1}-01-01")) - FERIAS_DU)


# ---------------------------------------------------------------- fase 4: priorização da automação
# Critérios (peso em %) e régua 1 → 5: cortes da métrica para as notas 2, 3, 4 e 5 (abaixo do 1º corte = nota 1).
PRIORIZACAO_CRITERIOS = {
    "volume": (25, (5, 10, 25, 50)),            # processos por ano na agência (estimativa a partir do piso)
    "analise": (15, (0.2, 0.35, 0.5, 0.65)),    # fração das horas do tipo em peças de análise
    "dados": (15, (0.3, 0.45, 0.6, 0.75)),      # peças de análise com dado estruturado e com não estruturado (média)
    "regras": (20, (0.4, 0.55, 0.7, 0.85)),     # peças de análise com norma/contrato e com teste contra padrão (média)
    "padrao": (15, (0.3, 0.4, 0.5, 0.6)),       # texto padronizado e caminho mais frequente (média)
    "completude": (10, (0.2, 0.35, 0.5, 0.65)),  # fração das horas em atividades de potencial de IA alto
}
# naturezas de trabalho (ficha por peça) que são análise; encaminhamento, comunicação e registro não entram
NATUREZAS_ANALISE = {"analise_juridica", "analise_tecnica_engenharia", "analise_economico_financeira",
                     "auditoria_conferencia", "fiscalizacao_campo", "relatoria_decisao"}
# portões do candidato a piloto de automação completa: nota mínima e confiança mínima da coorte
PORTOES_PILOTO = dict(nota_volume=3, nota_regras=3, casos_coorte=8, revocacao_volume=0.75)
CENARIOS_AUTOMACAO = ("conservador", "esperado", "otimista")
# HIPÓTESES até a medição no piloto (a calibrar com o sistema rodando): fração das horas da atividade que a automação
# tira, por potencial de IA da avaliação AS-IS, e esforço de construção em horas de desenvolvimento.
FRACAO_AUTOMATIZAVEL = {"alto": (0.4, 0.6, 0.8), "médio": (0.15, 0.3, 0.45), "baixo": (0.0, 0.05, 0.1)}
HORAS_CAPACIDADE = {  # construir a capacidade uma vez (motor, prompts-base, testes)
    "automação de tramitação (RPA no SEI)": 40, "monitoramento de prazos e alertas": 24, "painel e indicadores": 24,
    "classificação e triagem": 60, "extração de dados de documentos": 80, "sumarização e linha do tempo": 40,
    "busca de precedentes e normas": 60, "verificação de conformidade": 100, "cálculo e conferência automática": 80,
    "redação assistida de minuta": 80}
HORAS_PLATAFORMA = 160       # integração com o SEI, ambiente, trilha de auditoria (uma vez para a carteira)
HORAS_CONFIG_ATIVIDADE = 16  # regra, modelo de documento e teste por atividade automatizada
VARIABILIDADE_FATOR = 0.5    # acréscimo na configuração por caminho distinto/caso (exceções a tratar)
CASOS_VALIDACAO, HORAS_VALIDACAO_CASO = 30, 2  # conjunto de referência rotulado por servidor
CUSTO_HORA_DEV = (220, 150, 100)  # R$/h por cenário (conservador = mais caro); hipótese, trocar pelo contrato
PRECO_LLM_MCHAR = (10, 5, 2)      # R$ por milhão de caracteres lidos pelo modelo, já com a saída; hipótese
MANUTENCAO_ANUAL = 0.2            # fração do custo de construção por ano
HORIZONTE_ANOS = 5

# O perfil do órgão pode trocar qualquer premissa da fase 4 (ex.: CUSTO_HORA_DEV do contrato, réguas, portões).
for _nome in ("PRIORIZACAO_CRITERIOS", "NATUREZAS_ANALISE", "PORTOES_PILOTO", "FRACAO_AUTOMATIZAVEL", "HORAS_CAPACIDADE",
              "HORAS_PLATAFORMA", "HORAS_CONFIG_ATIVIDADE", "VARIABILIDADE_FATOR", "CASOS_VALIDACAO",
              "HORAS_VALIDACAO_CASO", "CUSTO_HORA_DEV", "PRECO_LLM_MCHAR", "MANUTENCAO_ANUAL", "HORIZONTE_ANOS"):
    globals()[_nome] = getattr(PERFIL, _nome, globals()[_nome])

# ---------------------------------------------------------------- fase 5: especificação do motor de cálculo (P01)
TOL_RECALCULO_PP = 0.01  # pontos percentuais entre o IR escrito e o recalculado
# textos integrais dos contratos e aditivos (convenção da base do Especialista: <TEXTOS_NORMAS>/data/txt/biblioteca/...)
TEXTOS_CONTRATOS = _caminho("TEXTOS_CONTRATOS",
                            str(TEXTOS_NORMAS / "data" / "txt" / "biblioteca" / "contratos-de-concessao-e-documentos-associados"))
SERIES_CACHE = DADOS / "series"  # cache das séries públicas (fora do git)
# Fonte de cada componente das fórmulas de reajuste: (padrão no nome do índice, disponibilidade, onde buscar).
# A ordem importa: o primeiro padrão que casa decide. Subíndices da FGV não estão na base aberta do IPEA.
FONTES_COMPONENTE = [
    (r"(?i)acordo coletivo|ACT\b", "documento", "cláusula de reajuste salarial do acordo coletivo juntado ao pleito"),
    (r"(?i)pre[cç]o da [aá]gua|venda da [aá]gua|CEDAE", "outro reajuste",
     "deliberação do reajuste do preço da água no atacado (processo próprio da CEDAE)"),
    (r"(?i)energia|tarifa .*(Light|Enel)|Grupo A", "pública com regra", "ANEEL, tarifas homologadas (REH) e bandeiras; a regra de composição é do contrato"),
    (r"(?i)m[aã]o de obra|IPA|deriva|qu[ií]mic", "assinatura", "FGV Dados (série paga; o pleito anexa a série)"),
    (r"(?i)IPCA-E|especial", "pública", "IBGE SIDRA, tabela 3065 (número-índice do IPCA-15)"),
    (r"(?i)IPCA|amplo", "pública", "IBGE SIDRA, tabela 1737 (número-índice)"),
    (r"(?i)INCC|constru[cç][aã]o civil", "pública", "IPEADATA IGP12_INCC12 (INCC-DI geral)"),
    (r"(?i)IGP-M|mercado", "pública", "IPEADATA IGP12_IGPM12"),
    (r"(?i)IPC", "pública", "IPEADATA IGP12_IPC12 (IPC-Brasil)"),
    (r"(?i)liminar|judicial", "decisão", "percentual fixado por decisão judicial"),
    (r"(?i)IDG|desempenho", "verificador", "índice apurado pelo verificador independente"),
    (r"(?i)tarifa social|ITS", "concessionária", "bases de economias da concessionária, validadas pelo verificador"),
]
# Séries públicas usadas para procurar os números-índice citados nos pareceres (cache em dados/series/).
SERIES_PUBLICAS = {
    "IPEADATA IGP12_INCC12": ("ipeadata", "IGP12_INCC12"),
    "IPEADATA IGP12_IGPM12": ("ipeadata", "IGP12_IGPM12"),
    "IPEADATA IGP12_IPC12": ("ipeadata", "IGP12_IPC12"),
    "IBGE SIDRA, tabela 1737": ("sidra", "1737/n1/all/v/2266"),
    "IBGE SIDRA, tabela 3065": ("sidra", "3065/n1/all/v/1117"),
}
# O perfil pode trocar as fontes e séries (outro órgão, outros índices).
for _nome in ("TOL_RECALCULO_PP", "FONTES_COMPONENTE", "SERIES_PUBLICAS"):
    globals()[_nome] = getattr(PERFIL, _nome, globals()[_nome])
