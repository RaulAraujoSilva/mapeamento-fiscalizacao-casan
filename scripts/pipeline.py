"""Orquestrador das etapas determinísticas, com portões de qualidade entre elas.

Roda em ordem fixa e para no primeiro portão que falhar — nada é publicado a partir de saída que não passou.
Mitiga falhas achadas na auditoria (docs/MITIGACOES.md): regeneração concorrente deixando números velhos nas
avaliações (trava de execução + carimbo dos fatos), regra de tempo alterada sem rever conclusões (validador
com --exigir-carimbo antes do site), e regressão de regra (testes sintéticos antes de gerar).

Etapas com agente ou rede ficam fora e são chamadas à parte: classificação P01–P36, modelos e vínculos
(agentes); exportar_relator.py (banco do relator) e fichas_trabalho.py (LLM) — esta última entra com --fichas.

Uso:
  python pipeline.py                 # testes → trilha → … → site, com portões
  python pipeline.py --fichas        # inclui as fichas de trabalho por LLM (cache por versão de prompt)
  python pipeline.py --de fatos      # começa numa etapa (as anteriores já rodaram)
  python pipeline.py --sem-site      # para antes do site (ex.: avaliações ainda em revisão)
  python pipeline.py --ate procedimento   # para depois de uma etapa (inclusive)

Ordem fatos → procedimento: fatos.py lê saida/fase2/procedimento_<cod>.json gerado na rodada ANTERIOR (procedimento.py
usa funções de fatos.py e vem depois). Num órgão novo, a primeira rodada sai com fatos sem `coorte.*`; rode de novo
com --de fatos. O pipeline avisa quando procedimento.py muda os arquivos que fatos.py já tinha lido.

Fase 3 em órgão novo: sem base normativa, normas_<cod>.json, melhorias_<cod>.json ou controles_<cod>.json, as etapas
correspondentes saem com "aviso:" (mostrado aqui) e código 0, por código; erro de verdade continua barrando.
Perfil do órgão: variável PERFIL (perfis/<nome>.py); dados: SEI_DADOS; base normativa: BASE_NORMAS.
Registro: saida/pipeline_execucao.json (etapas, duração, commit, impressão digital dos fatos)."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SCRIPTS = RAIZ / "scripts"
TRAVA = RAIZ / "saida" / ".pipeline.lock"
PY = [sys.executable, "-W", "ignore"]

# (nome, comando, é portão?) — portão = checagem que não gera nada e barra a sequência
ETAPAS = [
    ("testes_regras", PY + ["-m", "pytest", "-q", "-p", "no:cacheprovider", str(RAIZ / "tests" / "test_regras.py")], True),
    ("trilhas", PY + [str(SCRIPTS / "trilhas.py")], False),
    ("fichas_trabalho", PY + [str(SCRIPTS / "fichas_trabalho.py")], False),
    ("asis_piloto", PY + [str(SCRIPTS / "asis_piloto.py")], False),
    ("fatos", PY + [str(SCRIPTS / "fatos.py")], False),
    ("fichas_atividades", PY + [str(SCRIPTS / "fichas_atividades.py")], False),
    ("gerar_bpmn", PY + [str(SCRIPTS / "gerar_bpmn.py")], False),
    ("auditoria", PY + [str(SCRIPTS / "auditoria.py")], False),
    ("procedimento", PY + [str(SCRIPTS / "procedimento.py")], False),
    ("resumo_fase2", PY + [str(SCRIPTS / "resumo_fase2.py")], False),
    ("volume_anual", PY + [str(SCRIPTS / "volume_anual.py")], False),
    ("normas_processo", PY + [str(SCRIPTS / "normas_processo.py")], False),
    ("verificar_normas", PY + [str(SCRIPTS / "verificar_normas.py")], True),
    ("conformidade", PY + [str(SCRIPTS / "conformidade.py")], False),
    ("linha_base", PY + [str(SCRIPTS / "linha_base.py")], False),
    ("benchmark_md", PY + [str(SCRIPTS / "benchmark_md.py")], False),
    ("insumo_tobe", PY + [str(SCRIPTS / "insumo_tobe.py")], False),
    ("validar_tobe", PY + [str(SCRIPTS / "validar_tobe.py")], True),
    ("simular_tobe", PY + [str(SCRIPTS / "simular_tobe.py")], False),
    ("validar_controles", PY + [str(SCRIPTS / "validar_controles.py")], True),
    ("priorizacao_automacao", PY + [str(SCRIPTS / "priorizacao_automacao.py")], False),
    ("validar_avaliacoes", PY + [str(SCRIPTS / "validar_avaliacao.py"), "--exigir-carimbo"], True),
    ("testes_saidas", PY + ["-m", "pytest", "-q", "-p", "no:cacheprovider", str(RAIZ / "tests" / "test_saidas.py")], True),
    ("site", PY + [str(SCRIPTS / "gerar_site.py")], False),
]
NOMES = [n for n, _, _ in ETAPAS]

DICA = {
    "validar_avaliacoes": "os fatos mudaram ou há afirmação sem lastro: revise as avaliações apontadas, rode "
                          "validar_avaliacao.py até 0 problema e então validar_avaliacao.py --carimbar",
    "testes_regras": "uma regra de tempo, ficha ou validação regrediu: veja o teste que falhou antes de gerar",
    "verificar_normas": "um trecho de norma não bate com o texto integral da base do Especialista: corrija o trecho em "
                        "saida/fase3/normas_<cod>.json (nunca escreva de memória)",
    "validar_tobe": "uma melhoria do TO-BE cita fato, requisito ou benchmark inexistente, ou corta prazo legal mínimo: "
                    "corrija saida/fase3/melhorias_<cod>.json",
    "validar_controles": "um indicador tem linha de base ou meta sem lastro (fato, simulação, norma ou benchmark), ou "
                         "uma melhoria de fase 3 está sem controle de qualidade: corrija saida/fase3/controles_<cod>.json",
    "testes_saidas": "a saída gerada viola uma propriedade (posse, fatos, modelo, site): não publique",
}


def travar():
    """Uma execução por vez: duas regenerações simultâneas deixaram números velhos nas avaliações."""
    TRAVA.parent.mkdir(parents=True, exist_ok=True)
    if TRAVA.exists() and time.time() - TRAVA.stat().st_mtime < 2 * 3600:
        raise SystemExit(f"outra execução em andamento ({TRAVA.read_text(encoding='utf-8')}); "
                         f"se não houver, apague {TRAVA}")
    TRAVA.write_text(f"pid {os.getpid()} desde {time.strftime('%Y-%m-%d %H:%M')}", encoding="utf-8")


def impressao_procedimentos() -> str:
    """Impressão digital de saida/fase2/procedimento_*.json, lidos por fatos.py."""
    h = hashlib.sha256()
    for a in sorted((RAIZ / "saida" / "fase2").glob("procedimento_*.json")):
        h.update(a.name.encode() + a.read_bytes())
    return h.hexdigest()


def commit_atual() -> str | None:
    r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=RAIZ, capture_output=True, text=True)
    sujo = subprocess.run(["git", "status", "--porcelain", "scripts"], cwd=RAIZ, capture_output=True, text=True).stdout
    return (r.stdout.strip() + ("+alterações" if sujo.strip() else "")) if r.returncode == 0 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--de", choices=NOMES, default=NOMES[0])
    ap.add_argument("--ate", choices=NOMES, default=NOMES[-1], help="última etapa a rodar (inclusive)")
    ap.add_argument("--fichas", action="store_true", help="inclui fichas_trabalho.py (chama o LLM)")
    ap.add_argument("--sem-site", action="store_true")
    args = ap.parse_args()
    if NOMES.index(args.ate) < NOMES.index(args.de):
        ap.error("--ate vem antes de --de")
    pular = {"fichas_trabalho"} - ({"fichas_trabalho"} if args.fichas else set())
    if args.sem_site:
        pular.add("site")
    travar()
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    registro = dict(inicio=time.strftime("%Y-%m-%d %H:%M:%S"), commit=commit_atual(), etapas=[])
    ok = True
    try:
        proc_lido = impressao_procedimentos()  # o que fatos.py lê nesta rodada
        for nome, cmd, portao in ETAPAS[NOMES.index(args.de):NOMES.index(args.ate) + 1]:
            if nome in pular:
                continue
            t0 = time.time()
            r = subprocess.run(cmd, cwd=SCRIPTS, env=env, capture_output=True, text=True, encoding="utf-8")
            dur = round(time.time() - t0, 1)
            registro["etapas"].append(dict(etapa=nome, portao=portao, ok=r.returncode == 0, segundos=dur))
            print(f"{'✔' if r.returncode == 0 else '✘'} {nome:<20} {dur:>6.1f}s")
            for linha in r.stdout.splitlines():
                if linha.startswith("aviso:"):
                    print("   ", linha)
            if (nome == "procedimento" and r.returncode == 0 and "fatos" in [e["etapa"] for e in registro["etapas"]]
                    and impressao_procedimentos() != proc_lido):
                print("    aviso: procedimento.py mudou o que fatos.py leu nesta rodada; rode de novo com --de fatos")
            if r.returncode != 0:
                print((r.stdout + r.stderr)[-3000:])
                if nome in DICA:
                    print("→", DICA[nome])
                ok = False
                break
        if ok:
            import validar_avaliacao as va
            registro["fatos_sha"] = {c: va.sha_fatos(c) for c in
                                     sorted(p.stem.split("_")[1] for p in va.DIR.glob("fatos_*.json"))}
    finally:
        registro.update(fim=time.strftime("%Y-%m-%d %H:%M:%S"), ok=ok)
        (RAIZ / "saida" / "pipeline_execucao.json").write_text(json.dumps(registro, ensure_ascii=False, indent=1),
                                                              encoding="utf-8")
        TRAVA.unlink(missing_ok=True)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
