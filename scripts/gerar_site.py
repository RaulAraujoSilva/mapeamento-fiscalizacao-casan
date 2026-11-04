"""Etapa 6 — site do mapeamento AS-IS: visão geral do portfólio, página por processo (BPMN com zoom e camadas,
ficha de cada atividade, avaliação Lean e potencial de IA) e página de método e lacunas de dados.

Entradas: saida/bpmn/<Pxx>.bpmn, modelo_<Pxx>.json, fichas_<Pxx>.json (piloto) e/ou
saida/fase2/procedimento_<Pxx>.json (coorte), avaliacao_<Pxx>.json (opcional)
Saída: docs/site/index.html (arquivo único; bpmn-js pelo CDN)"""
from __future__ import annotations

import json

from comum import ORDEM_CODIGOS, ORGAO, RAIZ, SAIDA
from fichas_atividades import limpar_pessoais

DIR = SAIDA / "bpmn"
DEST = RAIZ / "docs" / "site"
ORDEM = ORDEM_CODIGOS  # ordem de apresentação (perfil)

# disponibilidade de cada campo da ficha de atividade
LACUNAS = [
    ("Sequência de unidades e atividades", "disponível", "Andamentos e documentos do SEI (trilha real)",
     "Todos os processos da base; anteriores a nov/2019 com trilha parcial", "—"),
    ("Tempo de espera", "disponível", "Datas de entrada, 1ª juntada e saída de cada unidade no SEI",
     "Todos os processos nativos do SEI", "—"),
    ("Tempo de trabalho", "estimado", "Conteúdo das peças: laudas autorais × complexidade (teto) e leitura da peça (piso)",
     "Peças com texto (≈ 85% das peças substantivas do piloto)",
     "Estudo de tempo curto com as unidades (~20 peças-tipo) para calibrar a faixa"),
    ("Descritivo, gatilho e saída", "disponível", "Leitura das peças vinculadas a cada atividade", "12 casos-piloto",
     "Validar redação com a unidade"),
    ("Entradas (insumos)", "disponível", "Fichas de trabalho: documentos do processo, da regulada, bases externas, normas",
     "Peças com texto", "—"),
    ("Ferramentas, cálculos e testes", "disponível", "Fichas de trabalho", "Peças com texto",
     "Sistemas e planilhas fora do SEI não aparecem nas peças — confirmar com a unidade"),
    ("Competências", "inferido", "Fichas de trabalho (área e nível exigidos pela peça)", "Peças com texto",
     "Validar com a gestão de pessoas e cruzar com a matriz de competências da agência"),
    ("Base normativa", "disponível", "Dispositivos citados nas peças (análise do relator)", "≈ 40% das peças citam norma",
     "—"),
    ("Executor (cargo)", "parcial", "Bloco de assinatura eletrônica das peças", "≈ 40% das peças",
     "Quem prepara a peça nem sempre assina: confirmar equipe com a unidade"),
    ("Volume por ano", "parcial", "Carteira do gabinete CONS-02 + estatísticas de deliberações do diagnóstico",
     "Só processos que chegam à relatoria", "Extrair a lista completa de processos por tipo no SEI de todas as unidades"),
    ("Custo da atividade (R$)", "ausente — possível", "—", "—",
     "Remuneração por cargo (Portal da Transparência RJ) × horas calibradas"),
    ("Força de trabalho por unidade (FTE)", "ausente — possível", "—", "—", "Dados de RH da agência"),
    ("Qualidade percebida pelo usuário/regulado", "ausente — possível", "—", "—", "Pesquisa ou dados da Ouvidoria"),
    ("Peças restritas", "ausente — limitado", "Documentos com restrição de acesso no SEI", "Ex.: acidentes e sanções",
     "Upload pelo gabinete (o relator já aceita PDF) ou acesso interno"),
]

HTML = r"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Processos AS-IS __ORGAO__</title>
<style>
:root{--bg:#f7f8fa;--card:#fff;--fg:#1c1f23;--mut:#5c6670;--line:#dde1e6;--acc:#1f5f99;--acc2:#e8f0f8;
--alto:#1b7f4b;--alto-bg:#dff3e7;--medio:#9a6a00;--medio-bg:#fff1cc;--baixo:#6b7280;--baixo-bg:#eceef1;
--ruim:#b02a37;--ruim-bg:#f8d7da;--sel:#1f5f99}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#121417;--card:#1b1e22;--fg:#e6e8eb;--mut:#a0a8b1;--line:#30353b;--acc:#7fb3e6;--acc2:#1f2a36;--alto-bg:#163a28;--alto:#7fd3a3;--medio-bg:#3a3017;--medio:#e7c36a;--baixo-bg:#2a2e33;--baixo:#b2b8bf;--ruim-bg:#3d1c20;--ruim:#f08f99}}
:root[data-theme="dark"]{--bg:#121417;--card:#1b1e22;--fg:#e6e8eb;--mut:#a0a8b1;--line:#30353b;--acc:#7fb3e6;--acc2:#1f2a36;--alto-bg:#163a28;--alto:#7fd3a3;--medio-bg:#3a3017;--medio:#e7c36a;--baixo-bg:#2a2e33;--baixo:#b2b8bf;--ruim-bg:#3d1c20;--ruim:#f08f99}
*{box-sizing:border-box}html,body{margin:0}body{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,"Segoe UI",Roboto,sans-serif}
a{color:var(--acc)}button{font:inherit}
header.top{position:sticky;top:0;z-index:20;background:var(--card);border-bottom:1px solid var(--line);display:flex;flex-wrap:wrap;align-items:center;gap:8px 16px;padding:10px 16px}
header.top h1{font-size:17px;margin:0;font-weight:650}
nav.main{display:flex;flex-wrap:wrap;gap:4px}
nav.main button{border:1px solid transparent;background:none;color:var(--fg);padding:5px 9px;border-radius:6px;cursor:pointer;font-size:14px}
nav.main button[aria-current="page"]{background:var(--acc2);border-color:var(--acc);color:var(--acc);font-weight:600}
main{max-width:1500px;margin:0 auto;padding:16px}
h2{font-size:21px;margin:4px 0 6px}h3{font-size:16px;margin:18px 0 8px}h4{font-size:14px;margin:12px 0 4px}
p.lead{color:var(--mut);margin:0 0 12px;max-width:980px}
.grid{display:grid;gap:12px}.g4{grid-template-columns:repeat(auto-fill,minmax(260px,1fr))}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px}
.card.click{cursor:pointer}.card.click:hover{border-color:var(--acc)}
.kpis{display:flex;flex-wrap:wrap;gap:8px 18px;margin:8px 0}
.kpi b{display:block;font-size:20px;font-variant-numeric:tabular-nums}.kpi span{font-size:12px;color:var(--mut)}
.chip{display:inline-block;padding:1px 8px;border-radius:999px;font-size:12px;font-weight:600;border:1px solid transparent;white-space:nowrap}
.alto{background:var(--alto-bg);color:var(--alto)}.medio,.média,.médio{background:var(--medio-bg);color:var(--medio)}.baixo,.baixa{background:var(--baixo-bg);color:var(--baixo)}
.alta{background:var(--ruim-bg);color:var(--ruim)}
.va{background:var(--alto-bg);color:var(--alto)}.nvn{background:var(--medio-bg);color:var(--medio)}.nva{background:var(--ruim-bg);color:var(--ruim)}
table{border-collapse:collapse;width:100%;font-size:13.5px}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:12px;color:var(--mut);font-weight:600;background:var(--card);position:sticky;top:0}
tr.sel td{background:var(--acc2)}tbody tr.click{cursor:pointer}tbody tr.click:hover td{background:var(--acc2)}
.tablewrap{overflow-x:auto;border:1px solid var(--line);border-radius:10px;background:var(--card)}
.proc-layout{display:grid;grid-template-columns:minmax(0,1fr) 400px;gap:12px;align-items:start}
.proc-layout>*{min-width:0}
@media (max-width:1100px){.proc-layout{grid-template-columns:minmax(0,1fr)}aside.painel{position:static;max-height:none}}
.diagram{background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
.toolbar{display:flex;flex-wrap:wrap;align-items:center;gap:6px;padding:8px;border-bottom:1px solid var(--line)}
.toolbar button,.toolbar select{border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:6px;padding:4px 9px;cursor:pointer;font-size:13px;min-width:32px}
.toolbar button:hover{border-color:var(--acc)}.toolbar .sep{width:1px;height:22px;background:var(--line);margin:0 4px}
.toolbar .zoomv{font-variant-numeric:tabular-nums;font-size:12px;color:var(--mut);min-width:44px;text-align:center}
#canvas{height:62vh;min-height:420px;background:#fff}
.diagram:fullscreen #canvas{height:calc(100vh - 92px)}
.legend{display:flex;flex-wrap:wrap;gap:6px 14px;padding:6px 10px;font-size:12px;color:var(--mut);border-top:1px solid var(--line)}
.legend i{display:inline-block;width:12px;height:12px;border:1px solid #888;vertical-align:-2px;margin-right:5px;border-radius:2px}
aside.painel{background:var(--card);border:1px solid var(--line);border-radius:10px;position:sticky;top:64px;max-height:calc(100vh - 80px);overflow:auto}
aside.painel,#diagram{scroll-margin-top:70px}
aside.painel .hd{padding:12px 14px;border-bottom:1px solid var(--line)}
aside.painel .hd h3{margin:0 0 4px}aside.painel .bd{padding:4px 14px 14px}
.tabs{display:flex;flex-wrap:wrap;gap:4px;margin:10px 0 4px}.tabs button{border:1px solid var(--line);background:none;color:var(--fg);border-radius:6px;padding:3px 8px;font-size:12.5px;cursor:pointer}
.tabs button[aria-selected="true"]{background:var(--acc2);border-color:var(--acc);color:var(--acc);font-weight:600}
dl{margin:0}dt{font-size:12px;color:var(--mut);margin-top:10px;font-weight:600}dd{margin:2px 0 0}
ul.tight{margin:4px 0;padding-left:18px}ul.tight li{margin:2px 0}
.muted{color:var(--mut)}.small{font-size:12.5px}
.tempo{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px}.tempo div{background:var(--bg);border-radius:8px;padding:8px}
.tempo b{font-size:18px;display:block}
.warn{background:var(--medio-bg);color:var(--fg);border-left:3px solid var(--medio);padding:6px 9px;border-radius:4px;font-size:12.5px;margin-top:8px}
.matriz{display:grid;grid-template-columns:110px repeat(3,1fr);gap:6px}
.matriz .cel{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px;min-height:80px}
.matriz .eixo{font-size:12px;color:var(--mut);display:flex;align-items:center;justify-content:center;text-align:center}
.matriz .cel .op{font-size:12.5px;margin:3px 0;cursor:pointer}.matriz .cel .op:hover{text-decoration:underline}
.matriz .q1{border-color:var(--alto)}
.dw{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:10px}
.oport td:first-child{min-width:220px}
.empty{padding:30px 14px;color:var(--mut);text-align:center}
.djs-element.sel-act .djs-visual>rect,.djs-element.sel-act .djs-visual>polygon,.djs-element.sel-act .djs-visual>circle{stroke:#1f5f99!important;stroke-width:4px!important}
.djs-element.lay-alto .djs-visual>rect{fill:#c9ecd6!important;stroke:#1b7f4b!important}
.djs-element.lay-medio .djs-visual>rect{fill:#ffe9b0!important;stroke:#9a6a00!important}
.djs-element.lay-baixo .djs-visual>rect{fill:#eceef1!important;stroke:#6b7280!important}
.djs-element.lay-ruim .djs-visual>rect{fill:#f5c2c7!important;stroke:#b02a37!important}
.djs-element.lay-neutro .djs-visual>rect{fill:#ffffff!important;stroke:#9aa1a9!important}
.djs-element.djs-shape[data-element-id^="t"]{cursor:pointer}
.djs-element.cam-on .djs-visual>rect{stroke:#1b7f4b!important;stroke-width:4px!important}
.djs-element.cam-off{opacity:.3}
.dist{font-variant-numeric:tabular-nums}.barra{height:6px;background:var(--line);border-radius:3px;margin-top:3px}
.barra i{display:block;height:6px;border-radius:3px;background:var(--acc)}
</style></head><body>
<header class="top"><h1>Processos AS-IS · __ORGAO__</h1><nav class="main" id="nav"></nav></header>
<main id="app"></main>
<script src="https://unpkg.com/bpmn-js@17.11.1/dist/bpmn-navigated-viewer.production.min.js"></script>
<script>
const DADOS = __DADOS__;
const LACUNAS = __LACUNAS__;
const $ = (s, el=document) => el.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const nivelCls = v => ({'alto':'alto','alta':'alta','médio':'medio','média':'medio','medio':'medio','baixo':'baixo','baixa':'baixa'}[String(v||'').toLowerCase()] || 'baixo');
const valorCls = v => /^agrega/.test(v||'') ? 'va' : /necess/.test(v||'') ? 'nvn' : /não agrega/.test(v||'') ? 'nva' : 'baixo';
const lista = (xs, vazio='—') => (xs && xs.length) ? '<ul class="tight">' + xs.map(x=>'<li>'+esc(x)+'</li>').join('') + '</ul>' : '<span class="muted">'+vazio+'</span>';
const ativs = d => d.fichas ? d.fichas.atividades : Object.fromEntries(d.tarefas.map(t => [t.id,
  {espera_du:{}, trabalho_h:{}, insumos:{}, sinais_perda:{}, competencias:[], cargos:[], documentos:[], ...t}]));
const num = v => String(v).replace('.', ',');
const dist = (x, un='du') => x ? `${num(x.mediana)} ${un} <span class="small muted">(q1 ${num(x.q1)}–q3 ${num(x.q3)}; n ${x.n})</span>` : '<span class="muted">—</span>';
const SIT = {procedimento:['procedimento','alto'], indicativo:['indicativo, com ressalva','medio'], estudo_de_caso:['estudo de caso','baixo']};
const sitChip = p => p ? `<span class="chip ${SIT[p.situacao][1]}">${SIT[p.situacao][0]}</span>` : '<span class="chip baixo">casos-piloto</span>';
let viewer = null, cam = null, estado = {pagina:'geral', proc:null, ativ:null, camada:'status', aba:'atividade'};
try { Object.assign(estado, JSON.parse(localStorage.getItem('asis_estado')||'{}')) } catch(e){}
function salvar(){ try{ localStorage.setItem('asis_estado', JSON.stringify({pagina:estado.pagina, proc:estado.proc, camada:estado.camada})) }catch(e){} }

function navegar(pagina, proc){ estado.pagina = pagina; if (proc) estado.proc = proc; estado.ativ = null; salvar(); render(); window.scrollTo(0,0); }
function renderNav(){
  const itens = [['geral','Visão geral'], ...DADOS.map(d=>['proc:'+d.codigo, d.codigo]), ['metodo','Método e dados']];
  $('#nav').innerHTML = itens.map(([k,t]) => {
    const atual = k === estado.pagina || (k === 'proc:'+estado.proc && estado.pagina === 'proc');
    const tit = k.startsWith('proc:') ? esc(DADOS.find(d=>'proc:'+d.codigo===k).nome) : '';
    return `<button data-k="${k}" title="${tit}" ${atual?'aria-current="page"':''}>${t}</button>`}).join('');
  $('#nav').querySelectorAll('button').forEach(b => b.onclick = () => { const k=b.dataset.k; k.startsWith('proc:') ? navegar('proc', k.slice(5)) : navegar(k) });
}
function render(){ renderNav(); if (estado.pagina === 'proc' && estado.proc) renderProc(); else if (estado.pagina === 'metodo') renderMetodo(); else renderGeral(); }

// ---------------------------------------------------------------- visão geral
function metricasProc(d){
  const av = d.avaliacao || {}, ativ = Object.values(ativs(d));
  const alto = Object.values(av.atividades||{}).filter(a => nivelCls(a.potencial_ia)==='alto').length;
  const nva = Object.values(av.atividades||{}).filter(a => valorCls(a.valor)==='nva').length;
  if (!d.fichas) { const l = d.proc.lead_nativos_encerrados;
    return {lead: l ? Math.round(l.mediana) : '—', esp: null, pce: null, n: ativ.length, alto, nva}; }
  const c = d.fichas.processo.casos;
  const lead = c.map(x=>x.lead_du), esp = c.map(x=>x.pct_tempo_espera_dominante);
  const rng = xs => xs.length ? (Math.min(...xs)===Math.max(...xs) ? Math.round(xs[0]) : Math.round(Math.min(...xs))+'–'+Math.round(Math.max(...xs))) : '—';
  return {lead: rng(lead), esp: rng(esp), pce: c.map(x=>x.pce_pct).join(' / '), n: ativ.length, alto, nva};
}
function renderGeral(){
  const ops = [];
  DADOS.forEach(d => (d.avaliacao?.oportunidades||[]).forEach(o => ops.push({...o, codigo:d.codigo})));
  const cel = (imp, esf) => ops.filter(o => nivelCls(o.impacto)===imp && nivelCls(o.esforco)===esf)
      .map(o => `<div class="op" data-p="${o.codigo}" title="${esc(o.descricao)}"><b>${o.codigo}</b> · ${esc(o.titulo)} <span class="chip ${o.categoria && o.categoria.includes('IA')?'alto':'baixo'}">${esc(o.categoria||'')}</span></div>`).join('') || '<span class="muted small">—</span>';
  const tiposD = ['Espera','Defeitos/retrabalho','Superprocessamento','Transporte','Estoque','Movimentação','Superprodução','Talento não aproveitado'];
  const sev = (d, t) => { const x = (d.avaliacao?.desperdicios||[]).find(w => (w.tipo||'').trim().toLowerCase() === t.toLowerCase()); return x ? `<span class="chip ${nivelCls(x.severidade)}" title="${esc(x.evidencia)}">${esc(x.severidade)}</span>` : '<span class="muted">·</span>'; };
  $('#app').innerHTML = `
  <h2>Mapeamento AS-IS a partir do SEI</h2>
  <p class="lead">${DADOS.length} processos organizacionais reconstruídos da trilha real de processos SEI do gabinete CONS-02. Cada fluxo foi desenhado a partir de casos típicos e críticos e, em ${DADOS.filter(d=>d.proc).length} deles, conferido numa coorte de processos do mesmo tipo (${DADOS.reduce((s,d)=>s+(d.proc?.casos||0),0)} processos), que dá a frequência de cada atividade, os caminhos e a distribuição dos tempos. Os processos-piloto têm ainda ficha detalhada de cada atividade, avaliação pelos referenciais Lean e potencial de automação com IA. Tempos de trabalho são estimativas pelo conteúdo das peças, a calibrar com as unidades.</p>
  <div class="grid g4">${DADOS.map(d => { const m = metricasProc(d); return `
    <div class="card click" data-p="${d.codigo}">
      <div class="small muted">${d.codigo} · ${sitChip(d.proc)}</div><h3 style="margin:2px 0 6px">${esc(d.nome)}</h3>
      <div class="kpis">${d.proc?`<div class="kpi"><b>${d.proc.casos}</b><span>casos na coorte</span></div><div class="kpi"><b>${d.proc.lead_nativos_encerrados?Math.round(d.proc.lead_nativos_encerrados.mediana):'—'}</b><span>lead time mediano (du)</span></div>`:`<div class="kpi"><b>${m.lead}</b><span>lead time (du)</span></div>`}
      ${m.esp!=null?`<div class="kpi"><b>${m.esp}%</b><span>tempo em espera (piloto)</span></div>`:''}<div class="kpi"><b>${m.n}</b><span>atividades</span></div></div>
      ${d.fichas?`<div class="small">Eficiência do ciclo: ${esc(m.pce)}% · <span class="chip alto">${m.alto} com alto potencial de IA</span> ${m.nva?`<span class="chip nva">${m.nva} sem valor</span>`:''}</div>`:d.avaliacao?`<div class="small">Avaliação pela coorte · <span class="chip alto">${m.alto} com alto potencial de IA</span> ${m.nva?`<span class="chip nva">${m.nva} sem valor</span>`:''}</div>`:'<div class="small muted">Sem casos-piloto: ficha detalhada e avaliação ainda não feitas.</div>'}
      <p class="small muted" style="margin:8px 0 0">${esc((d.avaliacao?.sintese||'').split('. ').slice(0,2).join('. '))}</p></div>`}).join('')}</div>
  ${(() => { const at = DADOS.flatMap(d => Object.values(d.avaliacao?.atividades||{})); const n = f => at.filter(f).length;
    return `<div class="card" style="margin-top:12px"><div class="kpis">
      <div class="kpi"><b>${at.length}</b><span>atividades mapeadas</span></div>
      <div class="kpi"><b>${n(a=>nivelCls(a.potencial_ia)==='alto')}</b><span>com alto potencial de IA</span></div>
      <div class="kpi"><b>${n(a=>nivelCls(a.potencial_ia)==='medio')}</b><span>com potencial médio</span></div>
      <div class="kpi"><b>${n(a=>valorCls(a.valor)==='va')}</b><span>agregam valor</span></div>
      <div class="kpi"><b>${n(a=>valorCls(a.valor)==='nvn')}</b><span>necessárias sem valor (rito, controle)</span></div>
      <div class="kpi"><b>${n(a=>valorCls(a.valor)==='nva')}</b><span>não agregam valor</span></div>
      <div class="kpi"><b>${ops.length}</b><span>oportunidades</span></div></div>
      <p class="small muted" style="margin:4px 0 0">A espera domina: na maior parte do ciclo o processo está parado em fila entre unidades, aguardando terceiros ou a pauta. IA reduz horas de leitura, cálculo e redação e encurta a espera quando elimina uma passagem, antecipa a triagem ou dispara alertas de prazo; as filas maiores pedem gestão (prazos internos, painel de estoque, paralelização).</p></div>` })()}
  <h3>Oportunidades: impacto × esforço</h3>
  <div class="matriz">
    <div></div><div class="eixo">esforço baixo</div><div class="eixo">esforço médio</div><div class="eixo">esforço alto</div>
    ${['alto','medio','baixo'].map(imp => `<div class="eixo">impacto ${imp==='medio'?'médio':imp}</div>` + ['baixo','medio','alto'].map(esf => `<div class="cel ${imp==='alto'&&esf==='baixo'?'q1':''}">${cel(imp,esf)}</div>`).join('')).join('')}
  </div>
  <h3>Desperdícios Lean por processo</h3>
  <div class="tablewrap"><table><thead><tr><th>Processo</th>${tiposD.map(t=>`<th>${t}</th>`).join('')}</tr></thead>
  <tbody>${DADOS.filter(d=>d.avaliacao).map(d=>`<tr class="click" data-p="${d.codigo}"><td><b>${d.codigo}</b> ${esc(d.nome)}</td>${tiposD.map(t=>`<td>${sev(d,t)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  $('#app').querySelectorAll('[data-p]').forEach(el => el.onclick = () => navegar('proc', el.dataset.p));
}

// ---------------------------------------------------------------- processo
async function renderProc(){
  const d = DADOS.find(x => x.codigo === estado.proc) || DADOS[0];
  estado.proc = d.codigo;
  const P = d.fichas ? d.fichas.processo : {escopo: d.escopo}, av = d.avaliacao || {}, A = ativs(d), PR = d.proc;
  const linhas = Object.values(A), pa = id => PR?.atividades?.[id];
  cam = null;
  $('#app').innerHTML = `
  <h2>${d.codigo} · ${esc(d.nome)}</h2>
  <p class="lead">${esc(P.escopo||'')}</p>
  <div class="proc-layout">
    <div>
      <div class="diagram" id="diagram">
        <div class="toolbar" role="toolbar" aria-label="Zoom e camadas">
          <button id="zmenos" title="Diminuir (−)">−</button><span class="zoomv" id="zval">100%</span><button id="zmais" title="Aumentar (+)">+</button>
          <button id="zfit" title="Ajustar ao quadro (0)">Ajustar</button><button id="zlarg" title="Ajustar à largura">Largura</button><button id="z100" title="Tamanho real (1)">100%</button>
          <button id="zsel" title="Centralizar a atividade selecionada">Ir à seleção</button><button id="zfull" title="Tela cheia (F)">Tela cheia</button>
          <span class="sep"></span><label class="small muted" for="camada">Camada</label>
          <select id="camada"><option value="status">Situação AS-IS</option>${PR?'<option value="freq">Frequência na coorte</option>':''}${d.avaliacao?'<option value="ia">Potencial de IA</option><option value="valor">Valor agregado</option>':''}<option value="espera">Tempo de espera</option></select>
          ${PR&&PR.caminhos.length?`<span class="sep"></span><label class="small muted" for="caminho">Caminho</label><select id="caminho"><option value="">todos</option>${PR.caminhos.map((c,i)=>`<option value="${i}">${i+1}º · ${c.casos} caso${c.casos>1?'s':''} (${c.pct}%)</option>`).join('')}</select>`:''}
        </div>
        <div id="canvas"></div>
        <div class="legend" id="legenda"></div>
      </div>
      <p class="small muted">Arraste para mover · Ctrl + roda do mouse para zoom · clique numa atividade para ver a ficha · teclas + − 0 1 F.</p>
      <h3>Atividades</h3>
      ${PR?`<p class="small muted" style="margin:0 0 6px">Números da coorte de ${PR.casos} processos: % dos casos em que a atividade ocorre e medianas (quartis no painel). Clique na linha para a ficha.</p>`:''}
      <div class="tablewrap"><table><thead><tr><th>Atividade</th><th>Unidade</th>${PR?'<th>Casos</th><th>Espera antes (du)</th><th>Execução (du)</th><th>Trabalho (h, piso)</th>':'<th>Espera antes (du)</th><th>Execução (du)</th><th>Trabalho (h, piso–teto)</th>'}<th>Valor</th><th>IA</th></tr></thead>
      <tbody id="tab-ativ">${linhas.map(a => { const x = (av.atividades||{})[a.id] || {}, c = pa(a.id); return `<tr class="click" data-a="${a.id}">
        <td>${esc(a.nome)}</td><td class="small">${esc(a.unidade)}</td>${PR ? (c ? `<td>${c.pct_casos}%</td><td>${c.espera_antes_du?num(c.espera_antes_du.mediana):'—'}</td><td>${c.execucao_du?num(c.execucao_du.mediana):'—'}</td><td>${c.horas_piso?num(c.horas_piso.mediana):'—'}</td>` : '<td>—</td><td>—</td><td>—</td><td>—</td>')
        : `<td>${esc(a.espera_du.antes||'—')}</td><td>${esc(a.espera_du.execucao||'—')}</td><td>${esc(a.trabalho_h.piso||'—')} / ${esc(a.trabalho_h.teto||'—')}</td>`}
        <td>${x.valor?`<span class="chip ${valorCls(x.valor)}">${esc(x.valor)}</span>`:'—'}</td><td>${x.potencial_ia?`<span class="chip ${nivelCls(x.potencial_ia)}">${esc(x.potencial_ia)}</span>`:'—'}</td></tr>`}).join('')}</tbody></table></div>
      ${renderCoorte(d)}
      ${renderAvaliacao(d)}
    </div>
    <aside class="painel" id="painel"><div class="empty">Clique numa atividade do diagrama ou da tabela para ver a ficha: descritivo, tempos de espera e de trabalho, entradas, ferramentas e técnicas, saída, competências, avaliação e potencial de IA.</div></aside>
  </div>`;
  $('#tab-ativ').querySelectorAll('tr').forEach(tr => tr.onclick = () => selecionar(tr.dataset.a, true));
  $('#camada').value = estado.camada;
  if (![...$('#camada').options].some(o => o.value === estado.camada)) estado.camada = 'status';
  $('#camada').onchange = e => { estado.camada = e.target.value; salvar(); aplicarCamada(d); };
  if ($('#caminho')) $('#caminho').onchange = e => marcarCaminho(d, e.target.value);
  document.querySelectorAll('[data-cam]').forEach(b => b.onclick = () => { $('#caminho').value = b.dataset.cam; marcarCaminho(d, b.dataset.cam); $('#diagram').scrollIntoView({behavior:'smooth'}); });
  if (viewer) viewer.destroy();
  viewer = new BpmnJS({container: '#canvas'});
  await viewer.importXML(d.xml);
  const canvas = viewer.get('canvas');
  canvas.zoom('fit-viewport');
  const atualizaZoom = () => $('#zval').textContent = Math.round(canvas.zoom()*100) + '%';
  viewer.get('eventBus').on('canvas.viewbox.changed', atualizaZoom); atualizaZoom();
  const passo = f => { const z = canvas.zoom(); canvas.zoom(Math.max(0.15, Math.min(4, z*f)), 'auto'); };
  $('#zmenos').onclick = () => passo(1/1.2); $('#zmais').onclick = () => passo(1.2);
  $('#zfit').onclick = () => canvas.zoom('fit-viewport', 'auto');
  $('#z100').onclick = () => canvas.zoom(1, 'auto');
  $('#zlarg').onclick = () => { const vb = canvas.viewbox(); const s = vb.outer.width / (vb.inner.width + 20); canvas.viewbox({x: vb.inner.x - 10, y: vb.inner.y - 10, width: vb.outer.width / s, height: vb.outer.height / s}); };
  $('#zsel').onclick = () => estado.ativ && focar(estado.ativ);
  $('#zfull').onclick = () => { const el = $('#diagram'); document.fullscreenElement ? document.exitFullscreen() : el.requestFullscreen && el.requestFullscreen().then(() => setTimeout(() => { canvas.resized(); canvas.zoom('fit-viewport') }, 100)); };
  document.onkeydown = e => { if (estado.pagina !== 'proc' || /input|select|textarea/i.test(e.target.tagName)) return;
    if (e.key === '+' || e.key === '=') passo(1.2); else if (e.key === '-') passo(1/1.2); else if (e.key === '0') canvas.zoom('fit-viewport','auto'); else if (e.key === '1') canvas.zoom(1,'auto'); else if (e.key.toLowerCase() === 'f') $('#zfull').click(); };
  viewer.get('eventBus').on('element.click', e => { if (A[e.element.id]) selecionar(e.element.id, false); });
  if (!d.fichas && !['atividade','coorte','melhoria'].includes(estado.aba)) estado.aba = 'atividade';
  aplicarCamada(d);
  if (estado.ativ && A[estado.ativ]) selecionar(estado.ativ, true);
}
function focar(id){
  const canvas = viewer.get('canvas'), el = viewer.get('elementRegistry').get(id); if (!el) return;
  const vb = canvas.viewbox(); const z = Math.max(canvas.zoom(), 0.9);
  const w = vb.outer.width / z, h = vb.outer.height / z;
  canvas.viewbox({x: el.x + el.width/2 - w/2, y: el.y + el.height/2 - h/2, width: w, height: h});
}
function selecionar(id, centralizar){
  const d = DADOS.find(x => x.codigo === estado.proc), canvas = viewer.get('canvas');
  if (estado.ativ) try { canvas.removeMarker(estado.ativ, 'sel-act') } catch(e){}
  estado.ativ = id; canvas.addMarker(id, 'sel-act');
  if (centralizar) focar(id);
  document.querySelectorAll('#tab-ativ tr').forEach(tr => tr.classList.toggle('sel', tr.dataset.a === id));
  renderPainel(d, id);
}
function aplicarCamada(d){
  const canvas = viewer.get('canvas'), av = d.avaliacao || {}, A = ativs(d), PR = d.proc;
  const cls = ['lay-alto','lay-medio','lay-baixo','lay-ruim','lay-neutro'];
  const numF = s => { const m = String(s||'').match(/(\d+)(?:–(\d+))?/); return m ? +(m[2]||m[1]) : null; };
  const leg = {
    status: '<span><i style="background:#f8d7da;border-color:#b02a37"></i>espera dominante</span><span><i style="background:#fff3cd;border-color:#b58105"></i>sinal de perda</span><span><i style="background:#fff"></i>trabalho efetivo</span>',
    ia: '<span><i style="background:#c9ecd6;border-color:#1b7f4b"></i>alto potencial de IA</span><span><i style="background:#ffe9b0;border-color:#9a6a00"></i>médio</span><span><i style="background:#eceef1"></i>baixo</span>',
    valor: '<span><i style="background:#c9ecd6;border-color:#1b7f4b"></i>agrega valor</span><span><i style="background:#ffe9b0;border-color:#9a6a00"></i>necessária sem valor</span><span><i style="background:#f5c2c7;border-color:#b02a37"></i>não agrega valor</span>',
    freq: '<span><i style="background:#c9ecd6;border-color:#1b7f4b"></i>em 75% dos casos ou mais</span><span><i style="background:#ffe9b0;border-color:#9a6a00"></i>25–74%</span><span><i style="background:#eceef1"></i>menos de 25%</span>',
    espera: '<span><i style="background:#c9ecd6;border-color:#1b7f4b"></i>até 10 du de espera antes</span><span><i style="background:#ffe9b0;border-color:#9a6a00"></i>11–30 du</span><span><i style="background:#f5c2c7;border-color:#b02a37"></i>mais de 30 du</span><span><i style="background:#fff"></i>sem dado</span>'};
  $('#legenda').innerHTML = leg[estado.camada] + (PR ? '<span>· tarefa: [% dos casos da coorte · espera mediana antes, em du · horas-piso medianas] · ramos de decisão: % das passagens observadas</span>' : '<span>· tarefa: [casos · espera antes em du · horas piso–teto]</span>');
  Object.keys(A).forEach(id => {
    cls.forEach(c => { try { canvas.removeMarker(id, c) } catch(e){} });
    let c = null; const x = (av.atividades||{})[id] || {};
    if (estado.camada === 'ia') c = {alto:'lay-alto', medio:'lay-medio', baixo:'lay-baixo'}[nivelCls(x.potencial_ia)] || 'lay-neutro';
    else if (estado.camada === 'valor') c = {va:'lay-alto', nvn:'lay-medio', nva:'lay-ruim'}[valorCls(x.valor)] || 'lay-neutro';
    else if (estado.camada === 'freq') { const p = PR?.atividades?.[id]?.pct_casos; c = p == null ? 'lay-neutro' : p >= 75 ? 'lay-alto' : p >= 25 ? 'lay-medio' : 'lay-baixo'; }
    else if (estado.camada === 'espera') { const e_ = PR?.atividades?.[id]?.espera_antes_du; const v = PR ? (e_ ? e_.mediana : null) : numF(A[id].espera_du.antes); c = v == null ? 'lay-neutro' : v <= 10 ? 'lay-alto' : v <= 30 ? 'lay-medio' : 'lay-ruim'; }
    if (c) try { canvas.addMarker(id, c) } catch(e){}
  });
}
function renderPainel(d, id){
  const a = ativs(d)[id], x = (d.avaliacao?.atividades||{})[id] || {};
  const abas = d.fichas ? [['atividade','Atividade'],['tempos','Tempos'],['entradas','Entradas e saída'],['tecnicas','Técnicas e competências'],['melhoria','Melhoria e IA'],['lacunas','Lacunas']] : [['atividade','Atividade'], ...(d.avaliacao ? [['melhoria','Melhoria e IA']] : [])];
  if (d.proc) abas.splice(1, 0, ['coorte','Na coorte']);
  if (!abas.some(([k]) => k === estado.aba)) estado.aba = 'atividade';
  const corpo = {
    coorte: painelCoorte(d, id),
    atividade: !d.fichas ? `<dl><dt>Gatilho</dt><dd>${esc(a.gatilho||'—')}</dd><dt>Saída</dt><dd>${esc(a.saida||'—')}</dd><dt>Executor</dt><dd>${esc(a.unidade)}</dd></dl><div class="warn">Processo sem casos-piloto: o descritivo, as entradas e as técnicas por atividade não foram levantados caso a caso. A aba “Na coorte” mostra o que os processos do tipo registram${d.avaliacao ? ' e a aba “Melhoria e IA” traz a avaliação feita a partir dela' : ''}.</div>` : `<dl><dt>Descritivo</dt><dd>${esc(a.descritivo||'—')}</dd><dt>Gatilho</dt><dd>${esc(a.gatilho||'—')}</dd>
      <dt>Executor</dt><dd>${esc(a.unidade)}${a.cargos.length?'<div class="small muted">Quem assina: '+esc(a.cargos.join(' · '))+'</div>':''}</dd>
      <dt>Evidência</dt><dd class="small">${a.n_docs} peça(s) em ${a.casos_com_evidencia} caso(s) · frequência no modelo ${esc(a.freq||'—')}${a.documentos.length?'<br>'+esc(a.documentos.slice(0,8).join(' · ')):''}</dd>
      ${a.observacoes?`<dt>Observações</dt><dd class="small">${esc(a.observacoes)}</dd>`:''}${a.nota?`<dt>Nota do fluxo</dt><dd class="small">${esc(a.nota)}</dd>`:''}</dl>`,
    tempos: `<div class="tempo"><div><span class="small muted">Espera antes da atividade</span><b>${esc(a.espera_du.antes||'—')} du</b></div>
      <div><span class="small muted">Execução</span><b>${esc(a.espera_du.execucao||'—')} du</b></div>
      <div><span class="small muted">Trabalho — piso</span><b>${esc(a.trabalho_h.piso||'—')} h</b></div><div><span class="small muted">Trabalho — teto</span><b>${esc(a.trabalho_h.teto||'—')} h</b></div></div>
      <dl>${(a.espera_du.posse_na_espera||[]).length?`<dt>Com quem o processo estava durante a espera</dt><dd>${esc(a.espera_du.posse_na_espera.join(' · '))}</dd>`:''}
      ${(a.espera_du.detalhe||[]).length?`<dt>Ocorrências</dt><dd class="small">${lista(a.espera_du.detalhe)}</dd>`:''}
      <dt>Laudas produzidas</dt><dd>${esc(a.laudas||'—')}</dd>${(a.prazos_citados||[]).length?`<dt>Prazos citados nas peças</dt><dd class="small">${lista(a.prazos_citados)}</dd>`:''}</dl>
      <div class="warn">Espera antes = dias úteis entre o fim da atividade anterior e a 1ª peça desta, com a unidade que tinha o processo; execução = da 1ª à última peça própria. Faixa entre os casos. Trabalho é estimado pelo conteúdo das peças (piso = leitura; teto = laudas autorais × complexidade), a calibrar com a unidade.</div>`,
    entradas: `<dl><dt>Insumos</dt><dd>${Object.keys(a.insumos).length ? Object.entries(a.insumos).map(([k,v])=>'<div class="small"><b>'+esc(k)+'</b>'+lista(v)+'</div>').join('') : '—'}</dd>
      <dt>Peças externas que alimentam a atividade</dt><dd>${lista(a.entradas_externas)}</dd><dt>Fontes externas consultadas</dt><dd>${lista(a.fontes_externas)}</dd>
      <dt>Saída</dt><dd>${esc(a.saida||'—')}</dd>${(a.conclusoes_de_merito||[]).length?`<dt>Conclusões de mérito nas peças</dt><dd>${lista(a.conclusoes_de_merito)}</dd>`:''}
      <dt>Base normativa citada</dt><dd>${lista(a.base_normativa)}</dd></dl>`,
    tecnicas: `<dl><dt>Ferramentas e técnicas</dt><dd>${lista(a.ferramentas)}</dd><dt>Cálculos</dt><dd>${lista(a.calculos)}</dd><dt>Testes e verificações</dt><dd>${lista(a.testes)}</dd>
      ${(a.trabalho_reproduzido||[]).length?`<dt>Trabalho de outras unidades apenas reproduzido</dt><dd class="small">${lista(a.trabalho_reproduzido)}</dd>`:''}
      <dt>Competências necessárias</dt><dd>${a.competencias.length ? '<ul class="tight">'+a.competencias.map(c=>'<li><b>'+esc(c.area)+'</b> — '+esc(c.nivel)+(c.evidencias.length?'<div class="small muted">'+esc(c.evidencias[0])+'</div>':'')+'</li>').join('')+'</ul>' : '—'}</dd></dl>`,
    melhoria: `<dl><dt>Classificação de valor</dt><dd>${x.valor?`<span class="chip ${valorCls(x.valor)}">${esc(x.valor)}</span> <span class="small">${esc(x.justificativa_valor||'')}</span>`:'—'}</dd>
      <dt>Potencial de IA</dt><dd>${x.potencial_ia?`<span class="chip ${nivelCls(x.potencial_ia)}">${esc(x.potencial_ia)}</span> `:''}${(x.tipos_ia||[]).map(t=>'<span class="chip baixo">'+esc(t)+'</span> ').join('')}</dd>
      <dt>O que a IA faria</dt><dd>${esc(x.aplicacao_ia||'—')}</dd><dt>Ganho esperado</dt><dd>${esc(x.ganho_esperado||'—')}</dd>
      <dt>Continua com o servidor</dt><dd>${esc(x.controle_humano||'—')}</dd><dt>Melhoria sem IA (Lean)</dt><dd>${esc(x.melhoria_lean||'—')}</dd>
      <dt>Sinais de perda nas peças</dt><dd>${Object.keys(a.sinais_perda).length ? Object.entries(a.sinais_perda).map(([k,v])=>'<div class="small"><b>'+esc(k)+'</b>'+lista(v)+'</div>').join('') : '<span class="muted">nenhum</span>'}</dd></dl>`,
    lacunas: lista(a.lacunas)
  };
  $('#painel').innerHTML = `<div class="hd"><div class="small muted">${d.codigo} · ${esc(a.unidade)}</div><h3>${esc(a.nome)}</h3>
    <div class="tabs" role="tablist">${abas.map(([k,t])=>`<button role="tab" data-k="${k}" aria-selected="${k===estado.aba}">${t}</button>`).join('')}</div></div>
    <div class="bd">${corpo[estado.aba] || corpo.atividade}</div>`;
  $('#painel').querySelectorAll('.tabs button').forEach(b => b.onclick = () => { estado.aba = b.dataset.k; renderPainel(d, id) });
}
function painelCoorte(d, id){
  const PR = d.proc, c = PR?.atividades?.[id]; if (!c) return '<p class="muted">Sem dados da coorte.</p>';
  const nomes = ativs(d), nm = t => t === 'fim' ? 'fim do processo' : t === 'início' ? 'início' : (nomes[t]?.nome || t);
  const fq = xs => xs && xs.length ? xs.map(i => `<div class="small">${esc(i.item.replace(/_/g,' '))} <span class="muted">· ${i.casos} caso${i.casos>1?'s':''}</span><div class="barra"><i style="width:${Math.round(100*i.casos/Math.max(c.casos,1))}%"></i></div></div>`).join('') : '<span class="muted">—</span>';
  const sai = (PR.transicoes[id] || []).filter(t => t.para !== id);
  return `<p class="small" style="margin:8px 0">Em <b>${c.casos} de ${PR.casos}</b> casos (${c.pct_casos}%)${c.casos_com_laco?` · repetida em ${c.casos_com_laco} caso${c.casos_com_laco>1?'s':''}`:''}.</p>
    <dl class="dist"><dt>Espera antes da atividade</dt><dd>${dist(c.espera_antes_du)}</dd><dt>Execução</dt><dd>${dist(c.execucao_du)}</dd>
    <dt>Trabalho por ocorrência (piso)</dt><dd>${dist(c.horas_piso, 'h')}</dd><dt>Trabalho por ocorrência (teto)</dt><dd>${dist(c.horas_teto, 'h')}</dd>
    <dt>Depois desta atividade</dt><dd>${sai.length ? '<ul class="tight">' + sai.map(t => `<li>${esc(nm(t.para))} <span class="muted">· ${t.pct}%</span></li>`).join('') + '</ul>' : '—'}</dd>
    <dt>Ferramentas e técnicas (casos com a atividade)</dt><dd>${fq(c.ferramentas)}</dd><dt>Insumos de referência</dt><dd>${fq(c.insumos)}</dd>
    <dt>Competências</dt><dd>${fq(c.competencias)}</dd><dt>Sinais de perda</dt><dd>${fq(c.sinais_perda)}</dd></dl>
    <div class="warn">Medianas e quartis entre as ocorrências da atividade nos processos da coorte. Espera antes = dias úteis desde a atividade anterior; em processo sem trâmite registrado, a primeira espera não é medida. Trabalho estimado pelo conteúdo das peças, a calibrar.</div>`;
}
function marcarCaminho(d, i){
  const canvas = viewer.get('canvas'), A = ativs(d);
  Object.keys(A).forEach(id => ['cam-on','cam-off'].forEach(c => { try { canvas.removeMarker(id, c) } catch(e){} }));
  if (i === '' || i == null) return;
  const seq = new Set(d.proc.caminhos[+i].sequencia.split(' → '));
  Object.keys(A).forEach(id => { try { canvas.addMarker(id, seq.has(id) ? 'cam-on' : 'cam-off') } catch(e){} });
}
function renderCoorte(d){
  const PR = d.proc; if (!PR) return '';
  const nomes = ativs(d), au = PR.auditoria_classificador, t = PR.trilha, l = PR.lead_nativos_encerrados;
  const nuc = Object.entries(PR.atividades).filter(([,a]) => a.pct_casos >= 50).map(([k]) => nomes[k]?.nome || k);
  return `<h3>Procedimento na coorte ${sitChip(PR)}</h3>
    <div class="card"><div class="kpis"><div class="kpi"><b>${PR.casos}</b><span>processos (${t.nativa||0} com trâmite completo, ${t.migrada||0} migrados, ${t.sem||0} só com as peças)</span></div>
      <div class="kpi"><b>${l?Math.round(l.mediana):'—'}</b><span>lead time mediano dos encerrados (du${l?`; n ${l.n}`:''})</span></div>
      <div class="kpi"><b>${PR.n_caminhos}</b><span>caminhos distintos</span></div>
      ${au?`<div class="kpi"><b>${Math.round(100*au.concordancia_substantivas)}%</b><span>conferência independente por amostra (${au.substantivas} peças)</span></div>`:''}</div>
      <p class="small muted" style="margin:6px 0 0">${PR.situacao==='procedimento'?'Frequências e tempos representam o procedimento do tipo.':PR.situacao==='indicativo'?'A conferência por amostra ficou abaixo de 85%: números indicativos até a revisão do modelo.':'Menos de 5 casos: leitura de estudo de caso, não de procedimento.'} Núcleo comum (em metade dos casos ou mais): ${esc(nuc.join(' → ') || '—')}.</p></div>
    <h4>Caminhos mais frequentes</h4><div class="tablewrap"><table><thead><tr><th>#</th><th>Casos</th><th>Atividades, na ordem da primeira ocorrência</th></tr></thead><tbody>
    ${PR.caminhos.slice(0,6).map((c,i)=>`<tr class="click" data-cam="${i}"><td>${i+1}</td><td>${c.casos} (${c.pct}%)</td><td class="small">${esc(c.sequencia.split(' → ').map(x=>nomes[x]?.nome||x).join(' → '))}</td></tr>`).join('')}</tbody></table></div>
    <p class="small muted">Clique num caminho para destacá-lo no diagrama.</p>`;
}
function metricasCoorte(d){
  const pc = d.proc?.por_caso_nativo || {}, L = [['lead','Lead time','du'],['espera_entre_atividades','Esperas entre atividades (soma por caso)','du'],
    ['execucao_atividades','Execução das atividades (soma por caso)','du'],['horas_piso','Trabalho nas peças mapeadas (piso)','h'],['horas_teto','Trabalho nas peças mapeadas (teto)','h'],
    ['terceiros','Aguardando terceiros (confirmado)','du'],['oficios','Ofícios','ofícios'],['retornos','Retornos a unidade já visitada','retornos']].filter(([k]) => pc[k]);
  if (!L.length) return '<p class="small muted">Nenhum processo da coorte tem trâmite completo no SEI: lead time, posse e esperas por caso não são medidos.</p>';
  return `<div class="tablewrap"><table><thead><tr><th>Por processo com trâmite completo</th><th>Mediana</th><th>q1–q3</th><th>Máximo</th><th>Processos</th></tr></thead><tbody>
    ${L.map(([k,t,u])=>`<tr><td>${t}</td><td>${num(pc[k].mediana)} ${u}</td><td>${num(pc[k].q1)}–${num(pc[k].q3)}</td><td>${num(pc[k].max)}</td><td>${pc[k].n}</td></tr>`).join('')}</tbody></table></div>`;
}
function renderAvaliacao(d){
  const av = d.avaliacao, nomeA = i => esc(ativs(d)[i]?.nome || i);
  if (!d.fichas && !av) return '';
  const P = d.fichas?.processo;
  const casos = !P ? metricasCoorte(d) : `<div class="tablewrap"><table><thead><tr><th>Caso</th><th>Lead time (du)</th><th>Trabalho (h, piso–teto)</th><th>Eficiência do ciclo (%)</th><th>Tempo em espera dominante</th><th>Passagens</th><th>Retornos</th><th>Aguardando terceiros (du)</th></tr></thead><tbody>
    ${P.casos.map(c=>`<tr><td>${esc(c.numero)} <span class="small muted">${esc(c.papel)}</span></td><td>${Math.round(c.lead_du)}</td><td>${c.trabalho_piso_h}–${c.trabalho_teto_h}</td><td>${esc(c.pce_pct)}</td><td>${c.pct_tempo_espera_dominante}%</td><td>${c.passagens}</td><td>${c.retornos}</td><td>${Math.round(c.aguardando_terceiros_du)}</td></tr>`).join('')}</tbody></table></div>
    <p class="small muted">Carteira do código: ${P.carteira.processos} processos SEI (${P.carteira.nativos} nativos), lead time mediano ${Math.round(P.carteira.lead_mediano_du||0)} du, ${P.carteira.com_deliberacao_pct}% com deliberação, ${P.carteira.retornos_medio} retornos em média. ${P.inventario.volume?'Volume (diagnóstico): '+esc(P.inventario.volume)+'.':''}</p>`;
  if (!av) return `<h3>Avaliação AS-IS</h3>${casos}<p class="muted">Avaliação ainda não gerada.</p>`;
  const titulo = P ? 'Métricas do fluxo de valor' : 'Métricas do fluxo de valor na coorte';
  return `<h3>Avaliação AS-IS</h3><div class="card"><p style="margin:0">${esc(av.sintese)}</p></div>
    <h4>${titulo}</h4>${casos}<p>${esc(av.leitura_metricas||'')}</p>
    <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(300px,1fr))">
      <div class="card"><h4 style="margin-top:0">Gargalo (Teoria das Restrições)</h4><p style="margin:0"><b>${esc(av.gargalo?.onde||'—')}</b></p><p class="small" style="margin:4px 0 0">${esc(av.gargalo?.evidencia||'')}</p></div>
      <div class="card"><h4 style="margin-top:0">Variabilidade (Seis Sigma)</h4><p class="small" style="margin:0">${esc(av.variabilidade||'—')}</p></div></div>
    <h4>Desperdícios (Lean)</h4><div class="dw">${(av.desperdicios||[]).map(w=>`<div class="card"><div><b>${esc(w.tipo)}</b> <span class="chip ${nivelCls(w.severidade)}">${esc(w.severidade)}</span></div><p class="small" style="margin:6px 0 0">${esc(w.evidencia)}</p>${(w.atividades||[]).length?`<p class="small muted" style="margin:4px 0 0">Atividades: ${w.atividades.map(i=>'<a href="#" data-a="'+i+'">'+nomeA(i)+'</a>').join(' · ')}</p>`:''}</div>`).join('')}</div>
    <h4>Oportunidades priorizadas</h4><div class="tablewrap"><table class="oport"><thead><tr><th>Oportunidade</th><th>Tipo</th><th>Impacto</th><th>Esforço</th><th>Ganho esperado</th><th>Pré-requisitos e riscos</th></tr></thead><tbody>
    ${(av.oportunidades||[]).map(o=>`<tr><td><b>${esc(o.titulo)}</b><div class="small">${esc(o.descricao)}</div>${(o.atividades||[]).length?`<div class="small muted">${o.atividades.map(i=>'<a href="#" data-a="'+i+'">'+nomeA(i)+'</a>').join(' · ')}</div>`:''}</td><td>${esc(o.categoria)}</td><td><span class="chip ${nivelCls(o.impacto)}">${esc(o.impacto)}</span></td><td><span class="chip ${nivelCls(o.esforco)==='alto'?'alta':nivelCls(o.esforco)==='baixo'?'alto':'medio'}">${esc(o.esforco)}</span></td><td class="small">${esc(o.ganho_esperado)}</td><td class="small">${esc(o.prerequisitos)}<br><span class="muted">${esc(o.riscos)}</span></td></tr>`).join('')}</tbody></table></div>
    <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(300px,1fr));margin-top:12px">
      <div class="card"><h4 style="margin-top:0">Indicadores para acompanhar</h4>${lista(av.indicadores_sugeridos)}</div>
      <div class="card"><h4 style="margin-top:0">Validar com a unidade</h4>${lista(av.perguntas_validacao)}</div></div>`;
}
document.addEventListener('click', e => { const a = e.target.closest('a[data-a]'); if (a && estado.pagina==='proc'){ e.preventDefault(); selecionar(a.dataset.a, true); $('#diagram').scrollIntoView({behavior:'smooth'}); } });

// ---------------------------------------------------------------- método
function renderMetodo(){
  const st = s => s.startsWith('disponível') ? 'alto' : s.startsWith('ausente') ? 'alta' : 'medio';
  $('#app').innerHTML = `<h2>Método e dados</h2>
  <p class="lead">O mapa nasce do registro do que aconteceu no SEI, não de entrevistas: a unidade que juntou cada documento, as datas de entrada e saída de cada unidade e o conteúdo das peças. Entrevistas entram depois, para validar o desenho e calibrar o tempo de trabalho.</p>
  <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(300px,1fr))">
    <div class="card"><h4 style="margin-top:0">1 · Trilha</h4><p class="small" style="margin:0">Estadias de cada unidade (remessa, recebimento, conclusão) e posse do processo, que divide o tempo sem dupla contagem. Espera dominante = passagem ≥ 20 du com trabalho estimado abaixo de 5% da capacidade.</p></div>
    <div class="card"><h4 style="margin-top:0">2 · Conteúdo</h4><p class="small" style="margin:0">Leitura de cada peça produzida pela agência (gerada no SEI): tarefa, insumos, ferramentas, cálculos, testes, competências, complexidade e sinais de perda. Peças externas contam como insumo.</p></div>
    <div class="card"><h4 style="margin-top:0">3 · Modelo</h4><p class="small" style="margin:0">Fluxo canônico por processo (casos típico e crítico + trilhas dos demais processos do código), em BPMN 2.0, com cada atividade ligada às peças que a sustentam.</p></div>
    <div class="card"><h4 style="margin-top:0">4 · Avaliação</h4><p class="small" style="margin:0">Lean (8 desperdícios), fluxo de valor (lead time, trabalho, eficiência do ciclo), Teoria das Restrições (gargalo), Seis Sigma (variabilidade), análise de valor agregado, ECRS e potencial de IA por atividade.</p></div>
    <div class="card"><h4 style="margin-top:0">5 · Coorte</h4><p class="small" style="margin:0">Cada peça própria dos processos do mesmo tipo é ligada a uma atividade do fluxo (ou marcada fora do fluxo), com conferência independente por amostra fora dos casos-piloto. Daí saem a frequência de cada atividade, os caminhos, a probabilidade de cada ramo de decisão e a distribuição dos tempos (mediana e quartis). Tipo com conferência abaixo de 85% é apresentado como indicativo; com menos de 5 casos, como estudo de caso. Tipos sem casos-piloto são avaliados pelas medianas e quartis da coorte.</p></div></div>
  <h3>Disponibilidade dos dados da ficha de atividade</h3>
  <div class="tablewrap"><table><thead><tr><th>Campo</th><th>Situação</th><th>Fonte</th><th>Cobertura</th><th>Como completar</th></tr></thead><tbody>
  ${LACUNAS.map(l=>`<tr><td><b>${esc(l[0])}</b></td><td><span class="chip ${st(l[1])}">${esc(l[1])}</span></td><td class="small">${esc(l[2])}</td><td class="small">${esc(l[3])}</td><td class="small">${esc(l[4])}</td></tr>`).join('')}</tbody></table></div>
  <h3>Limites</h3><ul class="small"><li>Base do gabinete CONS-02: só processos que chegam à relatoria; Ouvidoria (1 caso) ficou fora e o processo sancionador (3 casos) é estudo de caso.</li><li>Processos que existem só como conjunto de peças, sem trâmite registrado, entram na frequência das atividades e no trabalho, mas não na espera entre unidades.</li><li>Processos físicos anteriores a nov/2019 têm trilha parcial.</li><li>Peças restritas não têm texto; entram pelo tipo.</li><li>Quem assina nem sempre é quem prepara a peça.</li></ul>`;
}
render();
</script></body></html>"""


def resumo_md(dados):
    """docs/AVALIACAO_ASIS.md — síntese da avaliação por processo, gerada dos mesmos JSON do site."""
    prio = {"alto": 0, "médio": 1, "baixo": 2}
    at = [a for d in dados for a in (d["avaliacao"] or {}).get("atividades", {}).values()]
    n = lambda chave, val: sum(1 for a in at if a.get(chave) == val)  # noqa: E731
    md = ["# Avaliação AS-IS — melhoria e automação com IA", "",
          "Gerado por `scripts/gerar_site.py` a partir de `saida/bpmn/avaliacao_<código>.json`; navegação completa no "
          "site `docs/site/index.html`.", "",
          f"**Portfólio:** {len(at)} atividades em {len(dados)} processos — {n('potencial_ia', 'alto')} com alto potencial "
          f"de IA, {n('potencial_ia', 'médio')} com potencial médio; {n('valor', 'agrega valor')} agregam valor, "
          f"{n('valor', 'necessária sem valor')} são necessárias sem valor (rito legal e controle) e "
          f"{n('valor', 'não agrega valor')} não agregam valor.", ""]
    for d in dados:
        av = d["avaliacao"]
        if not av:
            continue
        md += [f"## {d['codigo']} — {d['nome']}", "", av["sintese"], ""]
        if d["fichas"]:
            casos = d["fichas"]["processo"]["casos"]
            md += ["| Caso | Lead time (du) | Trabalho (h) | Eficiência do ciclo | Espera dominante |", "|---|---|---|---|---|"]
            md += [f"| {c['numero']} ({c['papel']}) | {c['lead_du']:.0f} | {c['trabalho_piso_h']}–{c['trabalho_teto_h']} | "
                   f"{c['pce_pct']}% | {c['pct_tempo_espera_dominante']:.0f}% |" for c in casos]
        else:  # tipo sem caso-piloto: métricas por processo nativo da coorte
            pc = (d["proc"] or {}).get("por_caso_nativo") or {}
            nomes = {"lead": "Lead time (du)", "espera_entre_atividades": "Esperas entre atividades (du)",
                     "execucao_atividades": "Execução das atividades (du)", "horas_piso": "Trabalho, piso (h)",
                     "horas_teto": "Trabalho, teto (h)"}
            md += [f"Coorte de {d['proc']['casos']} processos; medidas por processo com trâmite completo no SEI:", "",
                   "| Medida | Mediana | q1–q3 | Processos |", "|---|---|---|---|"]
            md += [f"| {t} | {pc[k]['mediana']:g} | {pc[k]['q1']:g}–{pc[k]['q3']:g} | {pc[k]['n']} |"
                   for k, t in nomes.items() if pc.get(k)] or ["| sem trâmite completo | — | — | 0 |"]
        md += ["", f"**Gargalo:** {av['gargalo']['onde']} — {av['gargalo']['evidencia']}", "",
               "**Desperdícios:** " + "; ".join(f"{w['tipo']} ({w['severidade']})" for w in av["desperdicios"]) + ".", "",
               "**Oportunidades prioritárias:**", ""]
        ops = sorted(av["oportunidades"], key=lambda o: (prio.get(o["impacto"], 3), -prio.get(o["esforco"], 3)))
        md += [f"{k}. **{o['titulo']}** ({o['categoria']}; impacto {o['impacto']}, esforço {o['esforco']}) — "
               f"{o['ganho_esperado']}" for k, o in enumerate(ops[:3], 1)]
        md.append("")
    md += ["## Dados: o que existe e o que falta", "", "| Campo | Situação | Como completar |", "|---|---|---|"]
    md += [f"| {c} | {s} | {como} |" for c, s, _, _, como in LACUNAS]
    (RAIZ / "docs" / "AVALIACAO_ASIS.md").write_text("\n".join(md) + "\n", encoding="utf-8")


def main():
    dados = []
    for cod in ORDEM:
        f, pr = DIR / f"fichas_{cod}.json", SAIDA / "fase2" / f"procedimento_{cod}.json"
        if not f.exists() and not pr.exists():
            continue
        av = DIR / f"avaliacao_{cod}.json"
        modelo = json.loads((DIR / f"modelo_{cod}.json").read_text(encoding="utf-8"))
        raias = {r["id"]: r["nome"] for r in modelo["raias"]}
        proc = json.loads(pr.read_text(encoding="utf-8")) if pr.exists() else None
        if proc:  # o site não expõe qual modelo de linguagem gerou cada ficha
            proc.pop("fichas_por_modelo", None)
            for a in proc["atividades"].values():
                a.pop("fichas_por_modelo", None)
        # dados pessoais de terceiros saem de tudo o que vai para o site, não só das fichas
        dados.append(dict(codigo=cod, nome=modelo["nome"], escopo=modelo.get("escopo", ""),
                          xml=(DIR / f"{cod}.bpmn").read_text(encoding="utf-8"),
                          fichas=limpar_pessoais(json.loads(f.read_text(encoding="utf-8"))) if f.exists() else None,
                          proc=limpar_pessoais(proc),
                          tarefas=[dict(id=e["id"], nome=e["nome"], unidade=raias[e["raia"]], gatilho=e.get("gatilho"),
                                        saida=e.get("saida")) for e in modelo["elementos"] if e["tipo"] == "tarefa"],
                          avaliacao=limpar_pessoais(json.loads(av.read_text(encoding="utf-8"))) if av.exists() else None))
    DEST.mkdir(parents=True, exist_ok=True)
    js = lambda o: json.dumps(o, ensure_ascii=False).replace("</", "<\\/")  # noqa: E731
    (DEST / "index.html").write_text(HTML.replace("__ORGAO__", ORGAO).replace("__DADOS__", js(dados)).replace("__LACUNAS__", js(LACUNAS)),
                                     encoding="utf-8")
    resumo_md(dados)
    print("site:", DEST / "index.html", "|", len(dados), "processos,",
          sum(1 for d in dados if d["avaliacao"]), "com avaliação,", sum(1 for d in dados if d["proc"]), "com coorte")


if __name__ == "__main__":
    main()
