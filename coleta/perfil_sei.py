"""Perfil de uma instalação do SEI: tudo o que muda de um Estado para outro na Pesquisa Pública.

Por que existe: o SEI é o mesmo software em todo o país, mas cada órgão instala uma versão, liga ou desliga módulos e
às vezes personaliza rótulos ("Data de Geração" × "Data de Autuação"), cabeçalhos de tabela ("Unidade" × "Setor") e a
redação dos andamentos ("Processo remetido pela unidade" × "Processo enviado pela unidade"). O parser e o validador
leem essas diferenças daqui; o código do coletor não muda de Estado para Estado.

Frases canônicas dos andamentos
-------------------------------
O pipeline reconstrói a trilha (entrada e saída de cada unidade) a partir da descrição de cada andamento, em
`scripts/comum.py::tipo_andamento`, que espera a redação do SEI padrão:

    remetido    "Processo remetido pela unidade ORGAO/UNIDADE"   (a unidade de ORIGEM vem na frase)
    recebido    "Processo recebido na unidade"
    conclusao   "Conclusão do processo na unidade"  (ou "Conclusão automática ...")
    reabertura  "Reabertura do processo na unidade"
    gerado      "Processo público gerado" / "Processo restrito gerado" / "Processo gerado"

Quando a instalação do seu Estado escreve diferente, NÃO mude `scripts/comum.py`: acrescente uma `RegraAndamento` ao
perfil que traduza a frase local para a canônica. O coletor grava a frase canônica em `andamentos.tsv` e guarda a
original em `dados/coleta/andamentos_original.csv`, para auditoria. Cada regra traz um `exemplo`; o teste
`tests/test_coleta.py` confere que o exemplo, normalizado, é reconhecido por `tipo_andamento` com o evento declarado.

Para criar o perfil do seu Estado: copie `MODELO` (no fim deste arquivo), preencha e registre em `PERFIS`, ou salve os
campos num JSON e passe `--perfil caminho/do/perfil.json`. Passo a passo em `docs/adaptacao/COLETA_SEI.md`.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, fields, replace
from pathlib import Path

# Frase canônica de cada evento que o pipeline usa (ver docstring). {unidade} = unidade de origem com prefixo do órgão.
FRASES_CANONICAS = {
    "remetido": "Processo remetido pela unidade {unidade}",
    "recebido": "Processo recebido na unidade",
    "conclusao": "Conclusão do processo na unidade",
    "reabertura": "Reabertura do processo na unidade",
    "gerado": "Processo público gerado",
}
# Eventos sem os quais a trilha não fecha: se algum some da coleta inteira, o perfil está errado
EVENTOS_ESSENCIAIS = ("gerado", "remetido", "recebido", "conclusao")


@dataclass(frozen=True)
class RegraAndamento:
    """Traduz uma redação local de andamento para a frase canônica.

    `padrao` é uma regex aplicada à descrição já com espaços normalizados (use `^` para ancorar no início).
    Grupos nomeados viram campos do `canonica`: `(?P<unidade>...)` é tratado como unidade (recebe o prefixo do órgão
    se faltar) e `(?P<resto>...)` costuma carregar o complemento da frase. Grupo ausente vira texto vazio."""
    evento: str
    padrao: str
    canonica: str
    exemplo: str = ""

    def compilada(self) -> re.Pattern:
        return re.compile(self.padrao, re.I)


# Regras do SEI padrão. A redação já é a canônica; a regra de remessa existe para completar o prefixo do órgão
# quando a página mostra só a sigla da unidade.
REGRAS_SEI_PADRAO = (
    RegraAndamento("remetido", r"^Processo remetido pela unidade (?P<unidade>\S+)(?P<resto>.*)$",
                   "Processo remetido pela unidade {unidade}{resto}",
                   "Processo remetido pela unidade AGENERSA/SCEXEC"),
    RegraAndamento("recebido", r"^Processo recebido na unidade(?P<resto>.*)$", "Processo recebido na unidade{resto}",
                   "Processo recebido na unidade"),
    RegraAndamento("conclusao", r"^Conclusão do processo na unidade(?P<resto>.*)$",
                   "Conclusão do processo na unidade{resto}", "Conclusão do processo na unidade"),
    RegraAndamento("reabertura", r"^Reabertura do processo na unidade(?P<resto>.*)$",
                   "Reabertura do processo na unidade{resto}", "Reabertura do processo na unidade"),
)


@dataclass(frozen=True)
class PerfilSEI:
    """Configuração de uma instalação do SEI (uma por Estado/órgão)."""
    uf: str
    orgao: str                      # sigla que prefixa as unidades: "AGENERSA" em "AGENERSA/SCEXEC"
    nome_orgao: str = ""
    # endereço do módulo de pesquisa pública; base para resolver links relativos
    url_pesquisa: str = ""
    # se a instalação aceitar abrir o processo pelo número (raro: o normal é o link com hash da pesquisa pública).
    # Ex.: "https://sei.exemplo.gov.br/sei/modulos/pesquisa/md_pesq_processo_exibir.php?numero={numero}"
    modelo_url_processo: str | None = None
    # rótulos aceitos na tabela de autuação, por campo canônico (comparação sem acento, sem caixa e sem ":")
    rotulos_autuacao: dict = field(default_factory=lambda: {
        "numero": ["Processo", "Número", "Número do Processo"],
        "tipo": ["Tipo", "Tipo do Processo", "Espécie"],
        "data_geracao": ["Data de Geração", "Data de Autuação", "Data"],
        "interessado": ["Interessados", "Interessado", "Requerente", "Solicitante"],
    })
    # títulos (caption, atributo summary ou cabeçalho anterior) que identificam cada tabela
    titulos_protocolos: tuple = ("Lista de Protocolos", "Protocolos", "Lista de Documentos")
    titulos_andamentos: tuple = ("Lista de Andamentos", "Histórico de Andamentos", "Andamentos", "Histórico")
    # cabeçalhos aceitos por coluna canônica (exato primeiro, depois "contém")
    colunas_protocolos: dict = field(default_factory=lambda: {
        "numero": ["Processo / Documento", "Processo/Documento", "Documento", "Processo"],
        "tipo": ["Tipo"],
        "data": ["Data", "Data do Documento"],
        "data_inclusao": ["Data de Inclusão", "Inclusão"],
        "unidade": ["Unidade"],
    })
    colunas_andamentos: dict = field(default_factory=lambda: {
        "data_hora": ["Data/Hora", "Data / Hora", "Data"],
        "unidade": ["Unidade"],
        "descricao": ["Descrição", "Descricao"],
    })
    # link público do documento no href/onclick da âncora do protocolo (absoluto ou relativo)
    padrao_link_documento: str = (r"(?:https?://[^\s\"'()]+/)?md_pesq_documento_consulta_externa\.php\?"
                                  r"[^\s\"'\\)]+")
    formatos_data: tuple = ("%d/%m/%Y",)
    formatos_data_hora: tuple = ("%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S")
    completar_prefixo_unidade: bool = True  # "SCEXEC" → "AGENERSA/SCEXEC"
    regras_andamento: tuple = REGRAS_SEI_PADRAO
    # sinais na página: processo inteiro restrito; documento restrito (linha da lista ou página do documento);
    # bloqueio (captcha/limite de acesso) — o coletor PARA, nunca tenta contornar
    marca_processo_restrito: str = r"Processo ou Documento de Acesso Restrito"
    marca_documento_restrito: str = r"restrit|sigilos"
    marca_bloqueio: str = r"captcha|acesso bloqueado|excesso de requisi"

    # -------------------------------------------------------------- utilidades
    def normalizar_unidade(self, u: str | None) -> str | None:
        """Sigla da unidade com o prefixo do órgão; vazio vira None."""
        u = re.sub(r"\s+", "", u or "")
        if not u:
            return None
        if "/" not in u and self.completar_prefixo_unidade and self.orgao:
            return f"{self.orgao}/{u}"
        return u

    def normalizar_andamento(self, descricao: str) -> tuple[str, str | None]:
        """(descrição canônica, evento da regra aplicada ou None). Sem regra que case, devolve a original."""
        s = re.sub(r"\s+", " ", (descricao or "").replace("\xa0", " ")).strip()
        for r in self.regras_andamento:
            m = r.compilada().search(s)
            if not m:
                continue
            g = {k: (v or "") for k, v in m.groupdict().items()}
            if "unidade" in g:
                g["unidade"] = self.normalizar_unidade(g["unidade"]) or ""
            try:
                return r.canonica.format(**g).strip(), r.evento
            except (KeyError, IndexError):
                raise ValueError(f"regra '{r.padrao}': o modelo '{r.canonica}' usa grupo que a regex não tem")
        return s, None

    def para_json(self) -> dict:
        d = {f.name: getattr(self, f.name) for f in fields(self)}
        d["regras_andamento"] = [dict(vars(r)) for r in self.regras_andamento]
        return d


def perfil_de_dict(d: dict) -> PerfilSEI:
    """Monta um perfil a partir de um dicionário (JSON). Campos ausentes ficam com o padrão do SEI."""
    d = dict(d)
    if "regras_andamento" in d:
        d["regras_andamento"] = tuple(RegraAndamento(**r) for r in d["regras_andamento"])
    for k in ("titulos_protocolos", "titulos_andamentos", "formatos_data", "formatos_data_hora"):
        if k in d:
            d[k] = tuple(d[k])
    conhecidos = {f.name for f in fields(PerfilSEI)}
    desconhecidos = set(d) - conhecidos
    if desconhecidos:
        raise ValueError(f"campos desconhecidos no perfil: {sorted(desconhecidos)}")
    return PerfilSEI(**d)


# ---------------------------------------------------------------------------------------------- RJ (referência)
# SEI-RJ (sei.rj.gov.br), AGENERSA. É a instalação de onde vieram os dados do projeto original: rótulos, cabeçalhos e
# redação dos andamentos são os do SEI padrão.
RJ = PerfilSEI(
    uf="RJ",
    orgao="AGENERSA",
    nome_orgao="Agência Reguladora de Energia e Saneamento Básico do Estado do Rio de Janeiro",
    url_pesquisa="https://sei.rj.gov.br/sei/modulos/pesquisa/",
)

# ---------------------------------------------------------------------------------------------- MODELO para copiar
# Copie este bloco, troque o nome (ex.: SP = replace(MODELO, uf="SP", ...)) e registre em PERFIS.
# Os valores abaixo são EXEMPLOS de variações já vistas entre instalações; apague o que não se aplicar.
MODELO = replace(
    RJ,
    uf="XX",                                   # sigla do Estado
    orgao="ORGAO",                             # prefixo das unidades no SEI do seu órgão ("ARSESP", "AGR", ...)
    nome_orgao="Nome da agência reguladora",
    url_pesquisa="https://sei.exemplo.gov.br/sei/modulos/pesquisa/",
    # rótulos: inclua os do seu SEI ANTES dos padrões (o primeiro que casar vence)
    rotulos_autuacao={
        "numero": ["Nº do Processo", "Processo", "Número"],
        "tipo": ["Espécie", "Tipo", "Tipo do Processo"],
        "data_geracao": ["Data de Autuação", "Data de Geração", "Data"],
        "interessado": ["Interessado", "Interessados", "Requerente"],
    },
    titulos_protocolos=("Documentos do Processo", "Lista de Protocolos", "Protocolos"),
    titulos_andamentos=("Histórico de Tramitação", "Lista de Andamentos", "Andamentos"),
    colunas_protocolos={
        "numero": ["Nº SEI", "Processo / Documento", "Documento"],
        "tipo": ["Tipo de Documento", "Tipo"],
        "data": ["Data do Documento", "Data"],
        "data_inclusao": ["Registrado em", "Data de Inclusão", "Inclusão"],
        "unidade": ["Setor", "Unidade"],
    },
    colunas_andamentos={
        "data_hora": ["Data", "Data/Hora"],
        "unidade": ["Setor", "Unidade"],
        "descricao": ["Andamento", "Descrição"],
    },
    formatos_data_hora=("%d/%m/%Y às %H:%M", "%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S"),
    # regras: primeiro as redações locais, depois as do SEI padrão
    regras_andamento=(
        RegraAndamento("remetido", r"^Processo enviado (?:pela|da) unidade (?P<unidade>\S+)(?P<resto>.*)$",
                       "Processo remetido pela unidade {unidade}{resto}", "Processo enviado pela unidade DIRAD"),
        RegraAndamento("recebido", r"^Processo recebido (?:pelo setor|no setor)(?P<resto>.*)$",
                       "Processo recebido na unidade{resto}", "Processo recebido pelo setor"),
        RegraAndamento("conclusao", r"^Processo conclu[ií]do na unidade(?P<resto>.*)$",
                       "Conclusão do processo na unidade{resto}", "Processo concluído na unidade"),
        RegraAndamento("reabertura", r"^Processo reaberto na unidade(?P<resto>.*)$",
                       "Reabertura do processo na unidade{resto}", "Processo reaberto na unidade"),
        RegraAndamento("gerado", r"^Processo autuado(?P<resto>.*)$", "Processo público gerado{resto}",
                       "Processo autuado"),
    ) + REGRAS_SEI_PADRAO,
)

PERFIS = {"RJ": RJ, "MODELO": MODELO}


def carregar_perfil(nome_ou_caminho: str) -> PerfilSEI:
    """Perfil registrado em PERFIS (pela sigla) ou arquivo JSON com os campos do PerfilSEI."""
    if nome_ou_caminho.upper() in PERFIS:
        return PERFIS[nome_ou_caminho.upper()]
    p = Path(nome_ou_caminho)
    if p.suffix.lower() == ".json" and p.exists():
        return perfil_de_dict(json.loads(p.read_text(encoding="utf-8")))
    raise SystemExit(f"perfil '{nome_ou_caminho}' não encontrado: use {sorted(PERFIS)} ou um arquivo .json")
