"""Etapa 5b — ficha de cada atividade do BPMN canônico, consolidada a partir dos documentos vinculados
(saida/bpmn/vinculos_<Pxx>.json), e métricas de fluxo do processo.

Por atividade: descritivo, gatilho e saída (vínculos); executor (unidade + cargos de quem assina);
tempo de trabalho (faixa piso–teto das fichas) e de espera (fila até a 1ª peça e permanência, da trilha
SEI); entradas (insumos e peças externas); ferramentas, cálculos e testes; competências; base normativa;
sinais de perda; lacunas de dados.

Saída: saida/bpmn/fichas_<Pxx>.json"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict

import pandas as pd

from comum import DADOS, RAIA_ALIAS, SAIDA, RUIDO_NORMA
from dados_processos import P as INVENTARIO  # catálogo do perfil (comum põe CATALOGO no sys.path)

DIR = SAIDA / "bpmn"
HORAS_DIA = 6.0
NIVEL = {"basico": 1, "intermediario": 2, "especialista": 3}
NOME_NIVEL = {1: "básico", 2: "intermediário", 3: "especialista"}
ROTULO_AREA = {
    "juridico_regulatoria": "Jurídico-regulatória", "economico_financeira_tarifaria": "Econômico-financeira e tarifária",
    "engenharia_saneamento": "Engenharia de saneamento", "engenharia_gas_seguranca": "Engenharia de gás e segurança",
    "auditoria_controle": "Auditoria e controle", "dados_estatistica": "Dados e estatística",
    "redacao_oficial": "Redação oficial", "gestao_processual": "Gestão processual",
    "atendimento_usuario": "Atendimento ao usuário", "ambiental": "Ambiental", "contabil": "Contábil",
}
ROTULO_INSUMO = {
    "documento_do_processo": "Documentos do próprio processo", "documento_da_regulada": "Documentos da regulada",
    "base_externa": "Bases externas", "norma_ou_contrato": "Normas e contratos", "vistoria_ou_campo": "Vistoria/campo",
    "sistema_ou_base_interna": "Sistemas e bases internas", "precedente_ou_jurisprudencia": "Precedentes e jurisprudência",
}
ROTULO_SINAL = {
    "pedido_complementacao": "Pedido de complementação", "devolucao_por_vicio": "Devolução por vício",
    "refazimento": "Refazimento", "diligencia_externa": "Diligência externa", "prazo_concedido": "Prazo concedido",
    "reiteracao": "Reiteração", "aguardando_outra_unidade": "Aguardando outra unidade", "sobrestamento": "Sobrestamento",
    "repeticao_de_peca": "Repetição de peça anterior",
}
ASSINATURA = re.compile(r"assinado eletronicamente por\s+(.{3,80}?),\s*(.{3,90}?),\s*em\s+\d", re.I | re.S)


EXPEDIENTE = re.compile(r"remet|encaminh|encerr|lavr|junt|à considera|para conhecimento|para ciência|segue|em anexo|"
                        r"cumpra-se|publique-se|arquive|restitu|devolv|ao gabinete|à secex|à scexec", re.I)
GENERICAS = {"análise técnica", "análise jurídica", "redação oficial", "análise", "análise documental"}
# Cargo ou categoria depois de "Sr."/"consumidor" não é nome de pessoa: fica no texto.
CARGOS = {"Conselheiro", "Conselheira", "Relator", "Relatora", "Diretor", "Diretora", "Presidente", "Secretário",
          "Secretária", "Procurador", "Procuradora", "Ouvidor", "Ouvidora", "Coordenador", "Coordenadora",
          "Superintendente", "Chefe", "Gerente", "Amplo", "Livre", "Cativo", "Parcialmente"}


def _nome(m):
    return m.group(0) if m.group(2).split()[0] in CARGOS else f"{m.group(1)} [nome]"


PESSOAIS = [
    (re.compile(r"\b(usu[aá]ri[oa]|[Rr]eclamante|[Cc]onsumidora?|[Rr]equerente|Sr\.?|Sra\.?|[Ss]enhora?)\s+"
                r"([A-ZÀ-Ú][a-zà-ú]+(?:\s+(?:d[aeo]s?\s+)?[A-ZÀ-Ú][a-zà-ú]+){1,5})"), _nome),
    # número da casa depois de vírgula ou "nº": "Rua X - 26/03/2022" (título de processo) não é endereço
    (re.compile(r"(?i)\b(rua|avenida|av\.|travessa|estrada|rodovia)\s+[^,;\n]{3,60}"
                r"(?:,\s*(?:n[ºo°.]?\s*)?|\s+n[ºo°.]\s*)\d+[^;\n]{0,40}"),
     "[endereço]"),
    (re.compile(r"\d{3}\.\d{3}\.\d{3}-\d{2}"), "[CPF]"),
    # domínio terminado em letras: não confunde com "pacote@17.11.1" de endereço de CDN
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[A-Za-z]{2,}\b"), "[e-mail]"),
    # só com DDD entre parênteses ou rótulo: "100043-2018" é número de processo, não telefone
    (re.compile(r"\(\d{2}\)\s?9?\d{4}-?\d{4}|(?i:\b(?:tel|telefone|cel|celular)\b)\.?:?\s*\d{2}\s?9?\d{4}-?\d{4}"),
     "[telefone]"),
]


def limpar_pessoais(obj):
    """Remove dados pessoais de terceiros (nome de usuário, endereço, CPF, e-mail, telefone) dos textos."""
    if isinstance(obj, str):
        for rx, rep in PESSOAIS:
            obj = rx.sub(rep, obj)
        return obj
    if isinstance(obj, list):
        return [limpar_pessoais(x) for x in obj]
    if isinstance(obj, dict):
        return {k: limpar_pessoais(v) for k, v in obj.items()}
    return obj


COMPARAVEIS = {"parecer", "relatorio", "relatorio_fiscalizacao", "nota_tecnica", "voto", "oficio", "minuta",
               "notificacao_autuacao"}


def repeticoes_por_caso(refs_por_caso: dict, texto: dict, esf) -> dict:
    """Peça própria que repete >= 60% do texto de uma peça ANTERIOR DA MESMA CATEGORIA no mesmo caso
    (parecer × parecer, ofício × ofício...): refazimento, nova versão ou reiteração que a leitura peça a peça
    não vê. Trechos de 6 palavras presentes em mais de 5% das peças (cabeçalho, assinatura, rodapé do SEI)
    são descartados antes de comparar; e-mails, despachos e termos não entram."""
    def sh(t):
        w = re.findall(r"\w+", (t or "").lower())
        return {" ".join(w[i:i + 6]) for i in range(max(len(w) - 5, 0))}
    todos = {r: sh(t) for r, t in texto.items() if t}
    df = Counter(x for s_ in todos.values() for x in s_)
    corte = max(3, 0.05 * len(todos))
    out = defaultdict(list)
    for refs in refs_por_caso.values():
        docs = sorted((r for r in refs if r in todos and esf.loc[r, "categoria"] in COMPARAVEIS),
                      key=lambda r: esf.loc[r, "data_inclusao"])
        S = {r: {x for x in todos[r] if df[x] <= corte} for r in docs}
        for j, b in enumerate(docs):
            if len(S[b]) < 40:
                continue
            for a in reversed(docs[:j]):
                if esf.loc[a, "categoria"] != esf.loc[b, "categoria"] or len(S[a]) < 40:
                    continue
                pct = len(S[a] & S[b]) / len(S[b])
                if pct >= 0.6:
                    out[b].append((f"{esf.loc[a, 'tipo']} de {str(esf.loc[a, 'data_inclusao'])[:10]}", pct))
                    break
    return out


def faixa(vals, fmt="{:.0f}", sufixo=""):
    v = [x for x in vals if pd.notna(x)]
    if not v:
        return None
    a, b = min(v), max(v)
    return (fmt.format(a) if abs(a - b) < 0.05 else f"{fmt.format(a)}–{fmt.format(b)}") + sufixo


def main():
    piloto = pd.read_csv(SAIDA / "piloto.csv")
    cls = pd.read_csv(SAIDA / "processos_classificados.csv")
    esf = pd.read_csv(SAIDA / "esforco_documentos.csv", dtype={"numero": str})
    esf["ref"] = esf.numero_processo + ":" + esf.numero
    esf = esf.set_index("ref")
    est = pd.read_csv(SAIDA / "estadias.csv")
    est = est.set_index(["numero", "idx"])
    posse = pd.read_csv(SAIDA / "posse.csv")
    fichas = {}
    with open(SAIDA / "fichas_trabalho.jsonl", encoding="utf-8") as f:
        for ln in f:
            d = json.loads(ln)
            fichas[f"{d['processo']}:{d['sei_doc_id']}"] = d["ficha"]
    txt = pd.read_parquet(DADOS / "relator" / "doc_text_piloto.parquet")
    texto = {f"{p}:{s}": t for p, s, t in zip(txt.processo, txt.sei_doc_id, txt.texto)}
    ext = pd.read_parquet(DADOS / "relator" / "extractions.parquet")
    ext = ext[ext.processo.isin(piloto.numero)]
    normas = {f"{p}:{s}": json.loads(j).get("dispositivos_citados") or []
              for p, s, j in zip(ext.processo, ext.sei_doc_id, ext.extraction_json)}
    inv = {p["id"]: p for p in INVENTARIO}

    for arq in sorted(DIR.glob("vinculos_*.json")):
        v = json.loads(arq.read_text(encoding="utf-8"))
        cod = v["codigo"]
        modelo = json.loads((DIR / f"modelo_{cod}.json").read_text(encoding="utf-8"))
        raias = {r["id"]: r["nome"] for r in modelo["raias"]}
        casos = piloto[piloto.processo_principal == cod]
        linha = json.loads((DIR / f"fatos_{cod}.json").read_text(encoding="utf-8"))["linha_do_tempo"]
        proprias = defaultdict(list)
        for a_ in v["atividades"].values():
            for r in a_.get("docs", []):
                if r in esf.index:
                    proprias[esf.loc[r, "numero_processo"]].append(r)
        repeticoes = repeticoes_por_caso(proprias, texto, esf)
        atividades = {}
        for e in modelo["elementos"]:
            if e["tipo"] != "tarefa":
                continue
            a = v["atividades"].get(e["id"], {})
            todos = [r for r in a.get("docs", []) if r in esf.index]
            # só as peças da unidade da raia medem a atividade; as de outras unidades (despachos que abrem
            # ou fecham a passagem) ficam como trâmite associado e não entram em tempo, horas e técnicas
            raia_txt = (e["raia"] + " " + raias.get(e["raia"], "")).upper()
            na_raia = lambda r: (esf.loc[r, "unidade"].split("/")[-1] in raia_txt  # noqa: E731
                                 or any(esf.loc[r, "unidade"].endswith(k) and v in raia_txt
                                        for k, v in RAIA_ALIAS.items()))
            refs = [r for r in todos if na_raia(r)]
            tramite = [r for r in todos if not na_raia(r)]
            sem_raia = not refs and bool(todos)
            if sem_raia:
                refs = todos
            entradas = [r for r in a.get("docs_entrada", []) if r in esf.index]
            d = esf.loc[refs] if refs else esf.iloc[0:0]
            fs = [fichas[r] for r in refs if r in fichas]
            # trabalho por caso (piso = horas da ficha; teto = modelo por laudas)
            por_caso = d.groupby("numero_processo").agg(piso=("horas_llm", "sum"), teto=("horas_modelo", "sum"),
                                                        laudas=("laudas", "sum"))
            # espera: estadias em que os documentos foram juntados
            # tempos pela linha do tempo do caso (fatos.py): espera antes de cada ocorrência e execução
            esp, exe, noc, por_un, detalhe = [], [], [], defaultdict(float), []
            for proc, ocs in linha.items():
                mine = [o for o in ocs if o["atividade"] == e["id"]]
                if not mine:
                    continue
                esp.append(sum(o["espera_antes_du"] for o in mine))
                exe.append(sum(o["execucao_du"] for o in mine))
                noc.append(len(mine))
                papel = "típico" if casos.set_index("numero").loc[proc, "papel"].startswith("t") else "crítico"
                for o in mine:
                    for u, x in o["espera_antes_por_unidade"].items():
                        por_un[u] += x
                    detalhe.append(f"{papel}: {o['inicio']} a {o['fim']} — espera antes {o['espera_antes_du']:.0f} du, "
                                   f"execução {o['execucao_du']:.0f} du")
            insumos = defaultdict(list)
            for f in fs:
                for i in f.get("insumos") or []:
                    if i.get("descricao") and i["descricao"] not in insumos[i.get("tipo")]:
                        insumos[i.get("tipo")].append(i["descricao"])
            # ferramenta só com prova de uso: evidência que não seja fórmula de expediente, nome não genérico
            ferramentas = Counter(
                (x.get("nome") or "").strip().lower() for f in fs
                for x in ((f.get("trabalho_proprio") or {}).get("ferramentas") or [])
                if isinstance(x, dict) and x.get("ancorado") and not EXPEDIENTE.search(x.get("evidencia") or "")
                and (x.get("nome") or "").strip().lower() not in GENERICAS)
            comp = {}
            for f in fs:
                for c in f.get("competencias") or []:
                    ar = c.get("area")
                    comp.setdefault(ar, {"nivel": 0, "n": 0, "evidencias": []})
                    comp[ar]["nivel"] = max(comp[ar]["nivel"], NIVEL.get(c.get("nivel"), 1))
                    comp[ar]["n"] += 1
                    if c.get("evidencia") and len(comp[ar]["evidencias"]) < 2:
                        comp[ar]["evidencias"].append(c["evidencia"])
            nrm = Counter()
            for r in refs:
                for x in normas.get(r, []):
                    if not RUIDO_NORMA.search(x):
                        nrm[re.sub(r"\s+", " ", x).strip()] += 1
            cargos = Counter()
            for r in refs:
                for _, cargo in ASSINATURA.findall(texto.get(r) or ""):
                    cargo = re.sub(r"\s+", " ", cargo).strip()
                    if "externo" not in cargo.lower():
                        cargos[cargo] += 1
            sinais = defaultdict(list)
            for r in refs:
                for anterior, pct in repeticoes.get(r, []):
                    sinais["repeticao_de_peca"].append(f"{esf.loc[r, 'tipo']} repete {pct:.0%} do texto de {anterior}")
            for f in fs:
                for s in f.get("sinais_perda") or []:
                    sinais[s.get("tipo")].append(s.get("descricao", ""))
            sem_texto = [r for r in refs if r not in fichas]
            lacunas = []
            if not refs:
                lacunas.append("Sem documento vinculado: atividade inferida da trilha ou do outro caso")
            if sem_raia:
                lacunas.append("Nenhuma peça da própria unidade: tempos medidos pelas peças de trâmite de outras unidades")
            if sem_texto:
                lacunas.append(f"{len(sem_texto)} documento(s) sem texto disponível (restritos ou não baixados)")
            if refs and not cargos:
                lacunas.append("Cargo de quem executa não identificado nas assinaturas")
            lacunas.append("Tempo de trabalho estimado pelo conteúdo, não medido")
            atividades[e["id"]] = dict(
                id=e["id"], nome=e["nome"], unidade=raias.get(e["raia"], e["raia"]), status=e.get("status", "normal"),
                nota=None, freq=None,
                descritivo=a.get("descritivo"), gatilho=a.get("gatilho"), saida=a.get("saida"),
                # frases com tempo em dias úteis saem: os tempos vêm da linha do tempo, não do texto do vínculo
                observacoes=" ".join(x for x in re.split(r"(?<=[.;])\s+", a.get("observacoes") or "")
                                     if not re.search(r"\d+\s*(?:du\b|dias úteis)", x)) or None,
                casos_com_evidencia=int(d.numero_processo.nunique()), n_docs=len(refs),
                tramite_associado=sorted({f"{esf.loc[r, 'tipo']} ({esf.loc[r, 'unidade'].split('/')[-1]})" for r in tramite}),
                documentos=sorted(set(d.tipo.astype(str))) if len(d) else [],
                entradas_externas=sorted(set(esf.loc[entradas].tipo.astype(str))) if entradas else [],
                laudas=faixa(por_caso.laudas, "{:.0f}"),
                trabalho_h=dict(piso=faixa(por_caso.piso, "{:.1f}"), teto=faixa(por_caso.teto, "{:.1f}"),
                                modelo=e.get("horas")),
                espera_du=dict(antes=faixa(esp), execucao=faixa(exe), ocorrencias=faixa(noc),
                               posse_na_espera=[f"{u} {v:.0f} du" for u, v in sorted(por_un.items(), key=lambda kv: -kv[1])][:5],
                               detalhe=detalhe),
                insumos={ROTULO_INSUMO.get(k, k): vs[:6] for k, vs in insumos.items()},
                fontes_externas=sorted({x for f in fs for x in f.get("fontes_externas") or []})[:8],
                ferramentas=[k for k, _ in ferramentas.most_common(8)],
                calculos=[x for f in fs for x in f.get("calculos") or []][:5],
                testes=[x for f in fs for x in f.get("testes_auditoria") or []][:5],
                competencias=[dict(area=ROTULO_AREA.get(k, k), nivel=NOME_NIVEL[c["nivel"]], evidencias=c["evidencias"])
                              for k, c in sorted(comp.items(), key=lambda kv: (-kv[1]["nivel"], -kv[1]["n"]))],
                base_normativa=[k for k, _ in nrm.most_common(8)],
                cargos=[f"{k} ({n})" for k, n in cargos.most_common(5)],
                sinais_perda={ROTULO_SINAL.get(k, k): vs[:3] for k, vs in sinais.items()},
                prazos_citados=sorted({f"{x.get('dias')} dias ({x.get('natureza')}, {x.get('beneficiario')})" for f in fs
                                       for x in f.get("prazos") or [] if isinstance(x, dict) and x.get("ancorado")
                                       and x.get("dias")}),
                conclusoes_de_merito=[f["conclusao_de_merito"] for f in fs if f.get("conclusao_de_merito")][:5],
                trabalho_reproduzido=sorted({f"{x.get('autor_ou_unidade')}: {x.get('descricao')}"
                                             for f in fs for x in f.get("trabalho_reproduzido") or []})[:5],
                lacunas=lacunas,
            )

        # métricas de fluxo do processo (casos-piloto e carteira)
        casos_m = []
        for r in casos.itertuples():
            de = esf[esf.numero_processo == r.numero]
            po = posse[posse.numero == r.numero]
            seq = [s for s in str(r.sequencia_ativa).split(" → ")]
            piso, teto = de.horas_llm.sum(), de.horas_modelo.sum()
            casos_m.append(dict(
                numero=r.numero, papel=r.papel, lead_du=r.lead_du, trabalho_piso_h=round(piso, 1),
                trabalho_teto_h=round(teto, 1),
                pce_pct=f"{100 * piso / (r.lead_du * HORAS_DIA):.1f}–{100 * teto / (r.lead_du * HORAS_DIA):.1f}",
                passagens=len(seq), retornos=int(r.retornos_iteracao), aguardando_terceiros_du=r.espera_externa_du,
                pct_tempo_espera_dominante=round(100 * po.loc[po.espera_dominante, "du"].sum() / max(po.du.sum(), 1), 0),
            ))
        cart = cls[cls.processo_principal == cod]
        nat = cart[cart.nativo_sei]
        ano = pd.to_datetime(cart.data_geracao).dt.year.value_counts().sort_index()
        it = inv.get(cod, {})
        processo = dict(
            codigo=cod, nome=modelo["nome"], escopo=modelo.get("escopo"), fontes=modelo.get("fontes"),
            casos=casos_m,
            carteira=dict(processos=len(cart), nativos=len(nat), lead_mediano_du=nat.lead_du.median(),
                          com_deliberacao_pct=round(100 * cart.tem_deliberacao.mean()),
                          retornos_medio=round(cart.retornos_iteracao.mean(), 1),
                          por_ano={int(k): int(v) for k, v in ano.items() if pd.notna(k)}),
            inventario=dict(volume=it.get("volume"), dores=it.get("dores"), base=it.get("base"),
                            unidades=it.get("unidades")),
            n_atividades=len(atividades),
        )
        atividades = limpar_pessoais(atividades)
        (DIR / f"fichas_{cod}.json").write_text(json.dumps(dict(processo=processo, atividades=atividades),
                                                           ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        cob = sum(1 for a in atividades.values() if a["n_docs"])
        print(cod, f"{len(atividades)} atividades, {cob} com documentos")


if __name__ == "__main__":
    main()
