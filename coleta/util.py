"""Peças comuns do coletor: caminhos, cliente HTTP educado, escrita das TSVs no formato que `scripts/comum.py` lê e
acesso, só para leitura, às regras do pipeline (`comum.tipo_andamento`, `comum.categoria_documento`).

Por que um cliente HTTP próprio: a Pesquisa Pública é um serviço do Estado, não uma API. O coletor identifica-se
(User-Agent), espera entre requisições, respeita `Retry-After`, tenta de novo com espera crescente só em erro
temporário (429, 5xx, rede) e nunca imprime a credencial do proxy."""
from __future__ import annotations

import hashlib
import os
import re
import sys
import time
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
# mesma pasta de dados do pipeline: variável SEI_DADOS (relativa à raiz do repositório) ou dados/
DADOS = Path(os.environ.get("SEI_DADOS") or "dados")
DADOS = DADOS if DADOS.is_absolute() else RAIZ / DADOS
DUMP = DADOS / "sei2_dump"          # tabelas canônicas da trilha (o que scripts/comum.py lê)
RELATOR = DADOS / "relator"         # conteúdo das peças (parquets que os scripts leem)
BRUTO = DADOS / "bruto"             # HTML/arquivos baixados, como vieram (cache)
TRABALHO = DADOS / "coleta"         # índices auxiliares do coletor (links dos documentos, frases originais)
EXTRACOES = DADOS / "extracoes"     # cache das análises por LLM

# namespace fixo: o id de um processo é o mesmo em qualquer máquina e em qualquer coleta
_NS = uuid.uuid5(uuid.NAMESPACE_URL, "processos-sei-regulacao/coleta")

COLUNAS = {
    "processos.tsv": ["id", "numero", "tipo", "interessado", "data_geracao", "ultima_unidade",
                      "data_ultimo_andamento", "assunto", "tipo_custom", "natureza", "concessionaria", "status"],
    "andamentos.tsv": ["processo_id", "data_hora", "unidade", "descricao"],
    "protocolos.tsv": ["processo_id", "numero", "tipo", "data", "data_inclusao", "unidade", "descricao"],
    "observacoes.tsv": ["processo_id", "texto", "criado_em"],
}


# ------------------------------------------------------------------------------------------------ texto
def limpar(s) -> str:
    """Espaços normalizados (inclui o espaço não separável que o SEI usa nas células)."""
    return re.sub(r"\s+", " ", str(s or "").replace("\xa0", " ")).strip()


def chave(s: str) -> str:
    """Forma de comparação de rótulos: sem acento, sem caixa, sem ':' e espaços finais."""
    s = unicodedata.normalize("NFKD", limpar(s)).encode("ascii", "ignore").decode()
    return re.sub(r"\s*:\s*$", "", s).lower().strip()


def numero_normalizado(numero: str) -> str:
    return re.sub(r"\s+", "", numero or "").upper()


def id_processo(numero: str) -> str:
    """UUID estável derivado do número do processo (o mesmo número gera sempre o mesmo id)."""
    return str(uuid.uuid5(_NS, numero_normalizado(numero)))


def slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s or "").strip("_") or "sem_nome"


def hash_curto(s: str, n: int = 20) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:n]


# ------------------------------------------------------------------------------------------------ TSV
def _celula(v) -> str:
    """Valor no formato do dump: nulo e vazio viram NULL; tab vira espaço; quebra de linha vira '\\n' literal
    (comum.carregar desfaz). Sem aspas: o pipeline lê com quoting=3 (QUOTE_NONE)."""
    if v is None:
        return "NULL"
    try:
        import pandas as pd
        if pd.isna(v):
            return "NULL"
    except (TypeError, ValueError):
        pass
    s = str(v).replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ").strip()
    return s.replace("\n", "\\n") if s else "NULL"


def escrever_tsv(linhas: list[dict], destino: Path, nome: str) -> Path:
    destino.mkdir(parents=True, exist_ok=True)
    cols = COLUNAS[nome]
    arq = destino / nome
    with open(arq, "w", encoding="utf-8", newline="\n") as f:
        f.write("\t".join(cols) + "\n")
        for r in linhas:
            f.write("\t".join(_celula(r.get(c)) for c in cols) + "\n")
    return arq


def ler_tsv(arq: Path) -> list[dict]:
    """Lê uma TSV do dump como texto (NULL → None), para mesclar coletas."""
    if not arq.exists():
        return []
    linhas = arq.read_text(encoding="utf-8").splitlines()
    if not linhas:
        return []
    cab = linhas[0].split("\t")
    out = []
    for ln in linhas[1:]:
        v = ln.split("\t")
        out.append({c: (None if x == "NULL" else x) for c, x in zip(cab, v)})
    return out


# ------------------------------------------------------------------------------------------------ pipeline
def comum():
    """O módulo scripts/comum.py, importado só para leitura das regras (fonte única do pipeline)."""
    pasta = str(RAIZ / "scripts")
    if pasta not in sys.path:
        sys.path.insert(0, pasta)
    import comum as _c  # noqa: PLC0415
    return _c


# ------------------------------------------------------------------------------------------------ HTTP
@dataclass
class Resposta:
    conteudo: bytes
    content_type: str
    status: int
    url: str


def sem_credencial(msg: str) -> str:
    """Apaga usuário:senha de URLs que apareçam em mensagens de erro (proxy autenticado)."""
    return re.sub(r"(\w+://)[^/@\s]+@", r"\1***@", str(msg))


class ClienteHTTP:
    """GET com intervalo mínimo entre requisições, timeout, retry com espera crescente e User-Agent identificável.

    Proxy: variável de ambiente COLETA_PROXY (ex.: http://usuario:senha@host:porta), opcional. As variáveis padrão
    HTTP_PROXY/HTTPS_PROXY também valem (requests as lê). A URL do proxy nunca é impressa."""

    def __init__(self, intervalo: float = 2.0, timeout: float = 30.0, tentativas: int = 3, espera_base: float = 2.0,
                 contato: str | None = None, sessao=None):
        import requests
        self.intervalo, self.timeout, self.tentativas, self.espera_base = intervalo, timeout, tentativas, espera_base
        self.sessao = sessao or requests.Session()
        contato = contato or os.environ.get("COLETA_CONTATO")
        ua = "processos-sei-regulacao-coletor/1.0 (mapeamento de processos; uso academico"
        self.sessao.headers["User-Agent"] = ua + (f"; contato: {contato})" if contato else ")")
        proxy = os.environ.get("COLETA_PROXY")
        if proxy:
            self.sessao.proxies.update({"http": proxy, "https": proxy})
        self.usa_proxy = bool(proxy)
        self._ultima = 0.0

    def _esperar_vez(self):
        falta = self.intervalo - (time.monotonic() - self._ultima)
        if falta > 0:
            time.sleep(falta)
        self._ultima = time.monotonic()

    def obter(self, url: str) -> Resposta:
        import requests
        erro = None
        for tentativa in range(self.tentativas + 1):
            self._esperar_vez()
            try:
                r = self.sessao.get(url, timeout=self.timeout)
            except requests.RequestException as e:
                erro = f"{type(e).__name__}: {sem_credencial(e)}"
                espera = self.espera_base * 2 ** tentativa
            else:
                if r.status_code < 400:
                    return Resposta(r.content, r.headers.get("Content-Type", ""), r.status_code, r.url)
                erro = f"HTTP {r.status_code}"
                if r.status_code != 429 and r.status_code < 500:
                    break  # 4xx definitivo (404, 403): insistir não ajuda e pesa no servidor
                ra = r.headers.get("Retry-After", "")
                espera = float(ra) if ra.isdigit() else self.espera_base * 2 ** tentativa
            if tentativa < self.tentativas:
                time.sleep(espera)
        raise RuntimeError(f"falha ao baixar ({erro})")
