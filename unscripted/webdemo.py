"""Self-contained web demo UI for Unscripted.

A single dependency-free HTML/CSS/JS page served by the runtime's own HTTP
service. It drives the REAL runtime through the same JSON endpoints a studio
would integrate against (/turn, /state/*, /avatar/*), so the demo is also a live
integration reference -- not a mock. Its job is to make the moat *visible*:
who knows what and why, how belief carries provenance, how memory fades, how
affect drives a face, and why an NPC said what it said.
"""

#: Placeholder the service replaces with the configured bearer token (or "").
AUTH_TOKEN_PLACEHOLDER = "__UNSCRIPTED_AUTH_TOKEN__"


def demo_html(auth_token: str | None = None) -> str:
    """The demo page, wired for this deployment's authentication."""
    return DEMO_HTML.replace(AUTH_TOKEN_PLACEHOLDER, auth_token or "")


DEMO_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Unscripted — Live Demo</title>
<style>
  :root{
    --bg:#0c1014; --panel:#141b22; --panel2:#1b242d; --line:#26323d;
    --ink:#e7eef5; --dim:#8aa0b2; --accent:#4ea1ff; --good:#39d98a; --warn:#ffb454; --bad:#ff5d6c;
    --mono:"SFMono-Regular",ui-monospace,Menlo,Consolas,monospace;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
    font:14px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
  header{padding:12px 18px;border-bottom:1px solid var(--line);
    display:flex;align-items:center;gap:16px;background:linear-gradient(180deg,#121a22,#0c1014)}
  header h1{font-size:15px;margin:0;letter-spacing:.3px}
  header .tag{color:var(--dim);font-style:italic;font-size:12.5px}
  header .spacer{flex:1}
  .clock{font:12px/1 var(--mono);color:var(--dim);border:1px solid var(--line);
    padding:6px 9px;border-radius:7px}
  .grid{display:grid;grid-template-columns:1.05fr 1.25fr 1fr;gap:12px;padding:12px;
    height:calc(100vh - 50px)}
  .col{display:flex;flex-direction:column;gap:12px;min-height:0}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:10px;
    display:flex;flex-direction:column;min-height:0}
  .card>h2{font-size:11px;letter-spacing:1.4px;text-transform:uppercase;color:var(--dim);
    margin:0;padding:10px 12px;border-bottom:1px solid var(--line)}
  .card .body{padding:10px 12px;overflow:auto;min-height:0}
  .scene .place{font-size:17px;font-weight:600}
  .attrs{display:flex;gap:14px;color:var(--dim);font:12px/1 var(--mono);margin:6px 0 10px}
  .chips{display:flex;flex-wrap:wrap;gap:7px}
  .chip{background:var(--panel2);border:1px solid var(--line);border-radius:20px;
    padding:5px 12px;cursor:pointer;font-size:13px;transition:.12s}
  .chip:hover{border-color:var(--accent)}
  .chip.sel{background:var(--accent);color:#06121f;border-color:var(--accent);font-weight:600}
  .chip.exit{border-style:dashed;color:var(--dim)}
  .sub{color:var(--dim);font-size:11px;text-transform:uppercase;letter-spacing:1px;margin:12px 0 6px}
  #transcript{flex:1;overflow:auto;display:flex;flex-direction:column;gap:8px}
  .line{padding:8px 10px;border-radius:8px;background:var(--panel2);border:1px solid var(--line)}
  .line.you{background:#13212e}
  .line .who{font-size:11px;color:var(--accent);font-weight:600;margin-bottom:2px}
  .line.you .who{color:var(--good)}
  .line .why{font:11px/1.4 var(--mono);color:var(--dim);margin-top:5px;
    border-top:1px dashed var(--line);padding-top:5px;display:none;white-space:pre-wrap}
  .line .why.show{display:block}
  .line .whybtn{font-size:11px;color:var(--accent);cursor:pointer;user-select:none}
  form{display:flex;gap:8px;margin-top:8px}
  input[type=text]{flex:1;background:#0a0f14;border:1px solid var(--line);color:var(--ink);
    border-radius:8px;padding:9px 11px;font-size:14px}
  input[type=text]:focus{outline:none;border-color:var(--accent)}
  button.send{background:var(--accent);color:#06121f;border:0;border-radius:8px;
    padding:0 16px;font-weight:600;cursor:pointer}
  .hint{color:var(--dim);font-size:11px;margin-top:6px}
  .hint b{color:var(--ink);cursor:pointer;font-weight:500}
  .empty{color:var(--dim);font-style:italic;padding:8px 0}
  /* affect */
  .affectrow{display:flex;gap:14px;align-items:center}
  .bars{flex:1}
  .bar{display:flex;align-items:center;gap:8px;margin:4px 0;font:11px/1 var(--mono)}
  .bar .lbl{width:74px;color:var(--dim)}
  .track{flex:1;height:8px;background:#0a0f14;border-radius:5px;position:relative;overflow:hidden}
  .fill{position:absolute;top:0;bottom:0;border-radius:5px}
  .emo{display:inline-block;padding:3px 9px;border-radius:14px;background:var(--panel2);
    border:1px solid var(--line);font-size:12px;margin-right:6px}
  /* belief table */
  table{width:100%;border-collapse:collapse;font-size:12.5px}
  td,th{text-align:left;padding:6px 6px;border-bottom:1px solid var(--line);vertical-align:top}
  th{color:var(--dim);font-size:10.5px;text-transform:uppercase;letter-spacing:.6px}
  .prop{font:12px/1.4 var(--mono)}
  .pbar{height:7px;background:#0a0f14;border-radius:4px;overflow:hidden;margin-top:3px}
  .pbar>i{display:block;height:100%;background:var(--accent)}
  .prov{font:10.5px/1.4 var(--mono);color:var(--dim)}
  .badge{font-size:10px;padding:1px 6px;border-radius:8px;border:1px solid var(--line);margin-left:4px}
  .badge.confl{color:var(--warn);border-color:var(--warn)}
  .mem{padding:6px 0;border-bottom:1px solid var(--line)}
  .mem .meta{font:10.5px/1.3 var(--mono);color:var(--dim)}
  .tag-vivid{color:var(--good)} .tag-faint{color:var(--warn)} .tag-lost{color:var(--bad)}
  .trace{font:11px/1.5 var(--mono);white-space:pre-wrap}
  .trace .code{color:var(--accent)}
  .fac{margin:6px 0}
  .fac .name{display:flex;justify-content:space-between;font:12px/1 var(--mono)}
  .heat{height:7px;background:#0a0f14;border-radius:4px;overflow:hidden;margin-top:3px}
  .heat>i{display:block;height:100%;background:linear-gradient(90deg,var(--good),var(--warn),var(--bad))}
  .clk{font:10.5px/1.4 var(--mono);color:var(--dim)}
  svg.face{background:#0a0f14;border:1px solid var(--line);border-radius:10px}
  /* knowledge spread */
  .fact{padding:7px 0;border-bottom:1px solid var(--line)}
  .fact .prop{font:11.5px/1.4 var(--mono);color:var(--ink)}
  .fact .reach{display:flex;align-items:center;gap:8px;margin:4px 0 5px;
    font:10.5px/1 var(--mono);color:var(--dim)}
  .fact .rbar{flex:1;height:6px;background:#0a0f14;border-radius:4px;overflow:hidden;display:flex}
  .rbar>i{display:block;height:100%}
  .rbar>i.w{background:var(--good)} .rbar>i.h{background:var(--warn)}
  .holders{display:flex;flex-wrap:wrap;gap:4px}
  .hop{font:10.5px/1 var(--mono);padding:3px 7px;border-radius:10px;border:1px solid var(--line)}
  .hop.h0{color:var(--good);border-color:var(--good)}
  .hop.h1{color:var(--warn);border-color:var(--warn)}
  .hop.h2{color:var(--bad);border-color:var(--bad)}
  .hop .n{opacity:.65;margin-left:4px}
  .flow{font:10.5px/1.6 var(--mono);color:var(--dim)}
  .flow b{color:var(--ink);font-weight:500}
  .flow .d{color:var(--bad)}
  .origins{font:10px/1.4 var(--mono);color:var(--dim);margin-top:3px}
</style>
</head>
<body>
<header>
  <h1>Unscripted</h1>
  <span class="tag">The world remembers — and every character remembers differently.</span>
  <span class="spacer"></span>
  <span class="clock" id="clock">t = —</span>
</header>

<div class="grid">
  <!-- LEFT: scene + conversation -->
  <div class="col">
    <div class="card scene" style="flex:0 0 auto">
      <h2>The Scene</h2>
      <div class="body">
        <div class="place" id="place">…</div>
        <div class="attrs" id="attrs"></div>
        <div class="sub">People here — click to read their mind</div>
        <div class="chips" id="npcs"></div>
        <div class="sub">Exits</div>
        <div class="chips" id="exits"></div>
      </div>
    </div>
    <div class="card" style="flex:1">
      <h2>Conversation</h2>
      <div class="body" style="display:flex;flex-direction:column">
        <div id="transcript"><div class="empty">Ask a question, accuse, promise, threaten, or move.</div></div>
        <form id="cmd">
          <input type="text" id="inp" placeholder="ask Vee about Milan" autocomplete="off">
          <button class="send" type="submit">Send</button>
        </form>
        <div class="hint">Try:
          <b data-c="ask Vee about Milan">ask Vee about Milan</b> ·
          <b data-c="ask Honce about clinic">ask Honce about clinic</b> ·
          <b data-c="listen radio">listen radio</b> ·
          <b data-c="wait 20">wait 20</b>
        </div>
      </div>
    </div>
  </div>

  <!-- MIDDLE: the mind -->
  <div class="col">
    <div class="card" style="flex:0 0 auto">
      <h2>Inside the mind — <span id="who2">select an NPC</span></h2>
      <div class="body">
        <div class="affectrow">
          <svg class="face" id="face" width="120" height="120" viewBox="0 0 120 120"></svg>
          <div class="bars">
            <div id="emos"></div>
            <div class="bar"><span class="lbl">valence</span><div class="track" id="t-val"></div></div>
            <div class="bar"><span class="lbl">arousal</span><div class="track" id="t-aro"></div></div>
            <div class="bar"><span class="lbl">dominance</span><div class="track" id="t-dom"></div></div>
            <div class="bar"><span class="lbl">stress</span><div class="track" id="t-str"></div></div>
          </div>
        </div>
        <div class="prov" id="tend" style="margin-top:8px"></div>
      </div>
    </div>
    <div class="card" style="flex:1">
      <h2>Subjective knowledge &amp; provenance</h2>
      <div class="body"><div id="beliefs"><div class="empty">—</div></div></div>
    </div>
    <div class="card" style="flex:0 0 36%">
      <h2>Memory (with forgetting)</h2>
      <div class="body"><div id="memory"><div class="empty">—</div></div></div>
    </div>
  </div>

  <!-- RIGHT: why + world -->
  <div class="col">
    <div class="card" style="flex:1">
      <h2>Why did they say that — reason trace</h2>
      <div class="body"><div id="trace" class="trace"><div class="empty">Ask an NPC something.</div></div></div>
    </div>
    <div class="card" style="flex:0 0 auto">
      <h2>Relationships</h2>
      <div class="body"><div id="rels"><div class="empty">—</div></div></div>
    </div>
    <div class="card" style="flex:0 0 auto">
      <h2>How knowledge travels — <span id="ktime">—</span></h2>
      <div class="body">
        <div id="knowledge"><div class="empty">—</div></div>
        <div class="sub">Who told whom</div>
        <div id="flows" class="flow"><div class="empty">nothing has been passed on yet</div></div>
      </div>
    </div>
    <div class="card" style="flex:0 0 auto">
      <h2>Society — factions react off-screen</h2>
      <div class="body"><div id="world"><div class="empty">—</div></div></div>
    </div>
  </div>
</div>

<script>
const $ = s => document.querySelector(s);
let selected = null;
// escape model-/player-derived text before innerHTML (NPC lines, memories, props)
const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g,
  c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

// When the service runs with --auth-token, it substitutes the token here so the
// same-origin demo page can authenticate like any other client would.
const UNSCRIPTED_TOKEN = "__UNSCRIPTED_AUTH_TOKEN__";
function authHeaders(extra){
  const h = Object.assign({}, extra || {});
  if(UNSCRIPTED_TOKEN) h['Authorization'] = 'Bearer ' + UNSCRIPTED_TOKEN;
  return h;
}
async function getJSON(u){ const r = await fetch(u,{headers:authHeaders()}); return r.json(); }
async function postJSON(u,b){ const r = await fetch(u,{method:'POST',headers:authHeaders({'Content-Type':'application/json'}),body:JSON.stringify(b)}); return r.json(); }

function signedFill(el, v, color){ // v in [-1,1]
  const pct = Math.abs(v)*50; const left = v>=0 ? 50 : 50-pct;
  el.innerHTML = `<i class="fill" style="left:${left}%;width:${pct}%;background:${color}"></i>
                  <i style="position:absolute;left:50%;top:-2px;bottom:-2px;width:1px;background:#33414d"></i>`;
}
function unitFill(el, v, color){ el.innerHTML = `<i class="fill" style="left:0;width:${Math.max(0,Math.min(1,v))*100}%;background:${color}"></i>`; }

function bs(face, key){ // average L/R blendshape
  const b = face.blendshapes||{};
  if(b[key]!==undefined) return b[key];
  const l=b[key+'Left']||0, r=b[key+'Right']||0; return (l+r)/2;
}
function drawFace(face){
  const smile=bs(face,'mouthSmile'), frown=bs(face,'mouthFrown'), open=bs(face,'jawOpen');
  const wide=bs(face,'eyeWide'), browDown=bs(face,'browDown'), browInner=bs(face,'browInnerUp');
  const curve=(smile-frown); // +up smile, -down frown
  const eyeH=6+wide*6-browDown*1.5, mouthY=84+open*4;
  const mc=mouthY - curve*16; // control point of mouth quadratic
  const browL_y=44 - browInner*4 + browDown*5, browL_iny=44 - browInner*7 + browDown*2;
  const g='#cfe0ee';
  $('#face').innerHTML = `
    <ellipse cx="60" cy="60" rx="40" ry="46" fill="#10171e" stroke="#26323d"/>
    <line x1="34" y1="${browL_iny}" x2="48" y2="${browL_y}" stroke="${g}" stroke-width="2.4" stroke-linecap="round"/>
    <line x1="86" y1="${browL_iny}" x2="72" y2="${browL_y}" stroke="${g}" stroke-width="2.4" stroke-linecap="round"/>
    <ellipse cx="44" cy="56" rx="6" ry="${eyeH}" fill="#0a0f14" stroke="${g}"/>
    <ellipse cx="76" cy="56" rx="6" ry="${eyeH}" fill="#0a0f14" stroke="${g}"/>
    <circle cx="${44+ (face.gaze&&face.gaze.aversion>0.4?-3:0)}" cy="56" r="2.3" fill="${g}"/>
    <circle cx="${76+ (face.gaze&&face.gaze.aversion>0.4?-3:0)}" cy="56" r="2.3" fill="${g}"/>
    <path d="M40 ${mouthY} Q60 ${mc} 80 ${mouthY}" fill="none" stroke="${g}" stroke-width="2.6" stroke-linecap="round"/>
    ${open>0.1?`<ellipse cx="60" cy="${mouthY+2}" rx="10" ry="${open*5}" fill="#0a0f14" stroke="${g}"/>`:''}`;
}

function renderScene(s){
  $('#clock').textContent = 't = '+s.world_time;
  $('#place').textContent = s.label;
  $('#attrs').innerHTML = `<span>noise ${s.attributes.noise}</span><span>surveillance ${s.attributes.surveillance}</span><span>privacy ${s.attributes.privacy}</span>`;
  $('#npcs').innerHTML = s.npcs.length? '' : '<span class="empty">no one here</span>';
  s.npcs.forEach(n=>{
    const c=document.createElement('span'); c.className='chip'+(n.id===selected?' sel':'');
    c.textContent=n.name; c.onclick=()=>selectAgent(n.id); $('#npcs').appendChild(c);
  });
  $('#exits').innerHTML='';
  s.exits.forEach(e=>{
    const c=document.createElement('span'); c.className='chip exit'; c.textContent='→ '+e.label;
    c.onclick=()=>send('go '+e.label.toLowerCase()); $('#exits').appendChild(c);
  });
}

function renderAgent(a){
  $('#who2').textContent = a.name;
  drawFace(a.face);
  const em = a.affect;
  const others = Object.entries(em.active_emotions)
    .filter(([k])=>k.split('@')[0]!==em.dominant_emotion).slice(0,3);
  $('#emos').innerHTML = `<span class="emo">${em.dominant_emotion} ${(em.intensity*100|0)}%</span>`+
    others.map(([k,v])=>`<span class="emo">${k.split('@')[0]} ${(v*100|0)}%</span>`).join('');
  signedFill($('#t-val'), em.valence, em.valence>=0?'var(--good)':'var(--bad)');
  signedFill($('#t-aro'), em.arousal, 'var(--accent)');
  signedFill($('#t-dom'), em.dominance, 'var(--accent)');
  unitFill($('#t-str'), em.stress, 'var(--warn)');
  const tend = Object.entries(em.action_tendencies||{}).sort((a,b)=>Math.abs(b[1])-Math.abs(a[1])).slice(0,5);
  $('#tend').textContent = tend.length? 'action tendencies: '+tend.map(([k,v])=>`${k} ${v>0?'+':''}${v}`).join('  ·  ') : '';

  // beliefs
  if(!a.beliefs.length){ $('#beliefs').innerHTML='<div class="empty">No beliefs yet — ask, claim or wait.</div>'; }
  else{
    let h='<table><tr><th>Proposition</th><th style="width:90px">Belief</th><th>Provenance</th></tr>';
    a.beliefs.forEach(b=>{
      const conf=b.conflict>0.15?`<span class="badge confl">conflict ${b.conflict.toFixed(2)}</span>`:'';
      const prov=b.provenance.map(p=>p.claim_id||p.origin_event||'?').join(', ')||'—';
      h+=`<tr><td class="prop">${esc(b.text)}${conf}</td>
        <td>${(b.prob*100|0)}%<div class="pbar"><i style="width:${b.prob*100}%"></i></div></td>
        <td class="prov">${esc(prov)}</td></tr>`;
    });
    $('#beliefs').innerHTML=h+'</table>';
  }
  // memory
  if(!a.memory.length){ $('#memory').innerHTML='<div class="empty">No memories yet.</div>'; }
  else{
    $('#memory').innerHTML = a.memory.map(m=>`<div class="mem">
      <div>${esc(m.content)}</div>
      <div class="meta">[${m.type}] <span class="tag-${m.status}">${m.status}</span> ·
        act ${m.activation} · importance ${m.importance} · valence ${m.valence>=0?'+':''}${m.valence}</div></div>`).join('');
  }
  // relationships
  const rels=Object.entries(a.relationships||{});
  $('#rels').innerHTML = rels.length? rels.map(([id,r])=>`
    <div class="bar"><span class="lbl">${esc(r.name)}</span><div class="track">${''}</div></div>`).join('') : '<div class="empty">none</div>';
  rels.forEach(([id,r],i)=>{ const tr=$('#rels').querySelectorAll('.track')[i]; signedFill(tr, r.trust, r.trust>=0?'var(--good)':'var(--bad)'); });
  // reason trace
  if(!a.reason_trace.length){ $('#trace').innerHTML='<div class="empty">No trace this turn — ask this NPC something.</div>'; }
  else{
    $('#trace').innerHTML = a.reason_trace.map(t=>{
      let d=t.detail; try{ d=typeof d==='string'?d:JSON.stringify(d); }catch(e){ d=String(d); }
      return `<div><span class="code">${t.code}</span> ${t.magnitude>=0?'+':''}${t.magnitude}\n  ${d}</div>`;
    }).join('');
  }
}

function hopClass(h){ return h===0?'h0':(h<=2?'h1':'h2'); }

function renderKnowledge(k){
  $('#ktime').textContent = k.time_of_day;
  const facts = (k.facts||[]).filter(f=>f.reach>0).slice(0,5);
  if(!facts.length){ $('#knowledge').innerHTML='<div class="empty">nobody knows anything yet</div>'; }
  else{
    $('#knowledge').innerHTML = facts.map(f=>{
      const w = f.first_hand, h = f.hearsay, tot = Math.max(1, w+h);
      const chips = f.holders.slice(0,9).map(x=>
        `<span class="hop ${hopClass(x.hops)}" title="${esc(x.origin||'')} · p=${x.prob}">`+
        `${esc(x.name)}<span class="n">${x.hops===0?'witness':x.hops+'\u00b7hop'}</span></span>`).join('');
      // several distinct origins means several INDEPENDENT sources -- the thing
      // that makes a belief actually well-founded rather than merely repeated
      const orig = f.origins.length>1
        ? `${f.origins.length} independent sources`
        : `1 source: ${esc(f.origins[0]||'—')}`;
      return `<div class="fact">
        <div class="prop">${esc(f.text)}</div>
        <div class="reach"><span>${f.reach} know</span>
          <div class="rbar"><i class="w" style="width:${100*w/tot}%"></i><i class="h" style="width:${100*h/tot}%"></i></div>
          <span>${w} saw · ${h} heard</span></div>
        <div class="holders">${chips}</div>
        <div class="origins">${orig}</div>
      </div>`;
    }).join('');
  }
  const flows = (k.transmissions||[]).slice(-7).reverse();
  $('#flows').innerHTML = flows.length ? flows.map(t=>
    `<div><b>${esc(t.from_name||t.from)}</b> → <b>${esc(t.to_name||t.to)}</b>`+
    ` <span>@ ${esc(t.place_label||'')}</span> <span>${t.hops}\u00b7hop</span>`+
    (t.distorted?` <span class="d">${esc(t.distortion_note||'distorted')}</span>`:'')+`</div>`).join('')
    : '<div class="empty">nothing has been passed on yet</div>';
}

function renderWorld(w){
  const f=Object.entries(w.factions||{});
  $('#world').innerHTML = f.length? f.map(([id,fa])=>`
    <div class="fac"><div class="name"><span>${id.replace('faction:','')}</span>
      <span>heat ${fa.heat} · infl ${fa.influence}</span></div>
      <div class="heat"><i style="width:${Math.min(1,fa.heat)*100}%"></i></div>
      ${fa.clocks.map(c=>`<div class="clk">⏱ ${c.name} ${c.filled}/${c.size}</div>`).join('')}
    </div>`).join('') : '<div class="empty">no factions</div>';
}

async function selectAgent(id){ selected=id; await refresh(); }

async function refresh(){
  const [scene,world,knowledge] = await Promise.all([
    getJSON('/state/scene'), getJSON('/state/world'), getJSON('/state/knowledge')]);
  // preselect from ?npc=... (shareable demo links), else auto-select the first NPC here
  if(!selected || !scene.npcs.find(n=>n.id===selected)){
    const param = new URLSearchParams(location.search).get('npc');
    if(param && scene.npcs.find(n=>n.id===param)) selected = param;
    else if(scene.npcs.length) selected = scene.npcs[0].id;
  }
  renderScene(scene); renderWorld(world); renderKnowledge(knowledge);
  if(selected && scene.npcs.find(n=>n.id===selected)){
    renderAgent(await getJSON('/state/agent?agent_id='+encodeURIComponent(selected)));
  }
}

function addLine(who, text, cls){
  const empty=$('#transcript').querySelector('.empty'); if(empty) empty.remove();
  const d=document.createElement('div'); d.className='line '+(cls||'');
  d.innerHTML=`<div class="who">${esc(who)}</div><div>${esc(text)}</div>`;
  $('#transcript').appendChild(d); $('#transcript').scrollTop=1e9; return d;
}

async function send(text){
  if(!text.trim()) return;
  addLine('You', text, 'you');
  const res = await postJSON('/avatar/turn', {text});
  const msg = res.message || '';
  const npc = res.npc_response;
  const av = res.avatar;
  const line = addLine(npc? (av?av.speaker_id.replace('agent:',''):'NPC') : 'World', msg || '(no response)');
  if(av){
    selected = av.speaker_id;
    const why=document.createElement('div'); why.className='why';
    const btn=document.createElement('span'); btn.className='whybtn'; btn.textContent='▸ why?';
    btn.onclick=()=>{ why.classList.toggle('show'); btn.textContent=why.classList.contains('show')?'▾ why?':'▸ why?'; };
    let reasons=(av.reasons||[]).map(r=>Array.isArray(r)?`${r[0]}  ${r[1]}`:JSON.stringify(r)).join('\n');
    why.textContent='act='+av.act+'  verdict='+av.verdict+'\n'+reasons;
    line.appendChild(btn); line.appendChild(why);
  }
  await refresh();
}

$('#cmd').addEventListener('submit', async e=>{ e.preventDefault(); const v=$('#inp').value; $('#inp').value=''; await send(v); });
document.querySelectorAll('.hint b').forEach(b=> b.onclick=()=>send(b.dataset.c));
refresh();
</script>
</body>
</html>"""
