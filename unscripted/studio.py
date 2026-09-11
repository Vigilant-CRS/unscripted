"""Unscripted Studio — the world-pack editor.

Self-contained HTML/CSS/JS served by the runtime, like the demo page and by the
same rules: no external requests, no build step, no framework. It drives the same
authoring endpoints any other tool would.

What it is for: a narrative designer building a world without knowing that a
protected proposition is identified by a canonical core key, that slot order
determines that key, or that a routine block runs until the next one starts.

The three things it does that a text editor cannot:

- **The day is a picture.** A routine is a grid of hours, and where two characters
  overlap is visible rather than inferred. "Do these two ever meet" is the question
  behind every rumour in the world, and it was previously unanswerable without
  running the game.
- **Consequences are live.** Every edit re-runs the authoring report against the
  unsaved document, so "nobody can answer this topic" and "this secret is
  decorative" appear while you are typing, not after a playtest.
- **Propositions are pickers.** Predicate from a list, slots as fields. The
  canonical key is never shown because it is never typed.

Raw JSON stays available for everything else. This is an editor for the parts
that need one, not a wrapper that hides the format from people who know it.
"""
from __future__ import annotations

#: Placeholder the service replaces with the configured bearer token (or "").
AUTH_TOKEN_PLACEHOLDER = "__UNSCRIPTED_AUTH_TOKEN__"


def studio_html(auth_token: str | None = None) -> str:
    """The editor page, wired for this deployment's authentication."""
    return STUDIO_HTML.replace(AUTH_TOKEN_PLACEHOLDER, auth_token or "")


STUDIO_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Unscripted Studio</title>
<style>
  :root{
    --bg:#0c1014; --panel:#141b22; --panel2:#1b242d; --line:#26323d;
    --ink:#e7eef5; --dim:#8aa0b2; --accent:#4ea1ff; --good:#39d98a; --warn:#ffb454; --bad:#ff5d6c;
    --mono:"SFMono-Regular",ui-monospace,Menlo,Consolas,monospace;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
    font:14px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
  header{padding:10px 16px;border-bottom:1px solid var(--line);display:flex;
    align-items:center;gap:14px;background:linear-gradient(180deg,#121a22,#0c1014)}
  header h1{font-size:14px;margin:0;letter-spacing:.3px}
  header .path{font:11.5px/1 var(--mono);color:var(--dim)}
  header .spacer{flex:1}
  button{background:var(--panel2);color:var(--ink);border:1px solid var(--line);
    border-radius:7px;padding:7px 13px;cursor:pointer;font-size:13px}
  button:hover{border-color:var(--accent)}
  button.primary{background:var(--accent);color:#06121f;border-color:var(--accent);font-weight:600}
  button.primary:disabled{opacity:.45;cursor:default}
  .status{font:11.5px/1 var(--mono);padding:6px 10px;border-radius:6px;border:1px solid var(--line)}
  .status.ok{color:var(--good);border-color:var(--good)}
  .status.bad{color:var(--bad);border-color:var(--bad)}
  .grid{display:grid;grid-template-columns:170px 1.45fr 1fr;gap:12px;padding:12px;
    height:calc(100vh - 49px)}
  .col{display:flex;flex-direction:column;gap:12px;min-height:0}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:10px;
    display:flex;flex-direction:column;min-height:0}
  .card>h2{font-size:10.5px;letter-spacing:1.3px;text-transform:uppercase;color:var(--dim);
    margin:0;padding:9px 12px;border-bottom:1px solid var(--line)}
  .card .body{padding:10px 12px;overflow:auto;min-height:0}
  nav button{display:block;width:100%;text-align:left;margin-bottom:5px;border-radius:6px}
  nav button.sel{background:var(--accent);color:#06121f;border-color:var(--accent);font-weight:600}
  label{display:block;font-size:11px;color:var(--dim);margin:9px 0 3px;
    text-transform:uppercase;letter-spacing:.7px}
  input,select,textarea{width:100%;background:#0a0f14;border:1px solid var(--line);
    color:var(--ink);border-radius:6px;padding:7px 9px;font-size:13px;font-family:inherit}
  textarea{font:12px/1.5 var(--mono);min-height:220px;resize:vertical}
  input:focus,select:focus,textarea:focus{outline:none;border-color:var(--accent)}
  .row{display:flex;gap:8px}.row>*{flex:1}
  .hint{font-size:11.5px;color:var(--dim);margin-top:4px}
  .empty{color:var(--dim);font-style:italic;padding:8px 0}
  /* day grid */
  .day{overflow-x:auto}
  .dayrow{display:flex;align-items:center;gap:6px;margin:3px 0}
  .dayrow .who{width:112px;font:11.5px/1 var(--mono);color:var(--ink);
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .slots{display:flex;gap:1px;flex:1}
  .slot{flex:1;height:17px;border-radius:2px;background:#0a0f14;position:relative}
  .slot.meet{outline:1px solid var(--good);outline-offset:-1px}
  .hours{display:flex;gap:1px;margin-left:118px;font:9px/1 var(--mono);color:var(--dim)}
  .hours span{flex:1;text-align:center}
  .legend{display:flex;flex-wrap:wrap;gap:9px;margin-top:8px;font:10.5px/1 var(--mono)}
  .legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:4px;
    vertical-align:-1px}
  /* map */
  .place{padding:6px 0;border-bottom:1px solid var(--line);font:12px/1.5 var(--mono)}
  .place .ex{color:var(--dim)}
  .place.unreach{color:var(--warn)}
  /* findings */
  .find{padding:7px 0;border-bottom:1px solid var(--line)}
  .find .lv{font:9.5px/1 var(--mono);padding:2px 6px;border-radius:9px;border:1px solid;
    margin-right:6px;text-transform:uppercase}
  .lv.blocker{color:var(--bad);border-color:var(--bad)}
  .lv.problem{color:var(--warn);border-color:var(--warn)}
  .lv.hint{color:var(--dim);border-color:var(--line)}
  .find .fix{font-size:11.5px;color:var(--dim);margin-top:3px;padding-left:2px}
  .meet{font:11.5px/1.6 var(--mono);color:var(--dim)}
  .meet b{color:var(--ink);font-weight:500}
  .num{flex:0 0 42px;text-align:right;font:11px/1 var(--mono);color:var(--dim);align-self:center}
  input[type=range]{padding:0;height:22px}
</style>
</head>
<body>
<header>
  <h1>Unscripted Studio</h1>
  <span class="path" id="packpath">…</span>
  <span class="spacer"></span>
  <span class="status" id="status">loading</span>
  <button id="revert">Revert</button>
  <button class="primary" id="save" disabled>Save</button>
</header>

<div class="grid">
  <div class="col">
    <div class="card" style="flex:1">
      <h2>Pack</h2>
      <div class="body"><nav id="nav"></nav></div>
    </div>
  </div>

  <div class="col">
    <div class="card" style="flex:1">
      <h2 id="edithead">Editor</h2>
      <div class="body" id="editor"></div>
    </div>
  </div>

  <div class="col">
    <div class="card" style="flex:0 0 auto">
      <h2>The day — where everyone is</h2>
      <div class="body">
        <div class="day" id="day"><div class="empty">—</div></div>
        <div class="legend" id="legend"></div>
        <div class="sub"></div>
        <div class="meet" id="meetings"></div>
      </div>
    </div>
    <div class="card" style="flex:0 0 auto">
      <h2>The map</h2>
      <div class="body" id="map"><div class="empty">—</div></div>
    </div>
    <div class="card" style="flex:1">
      <h2>What to look at — <span id="verdict">—</span></h2>
      <div class="body" id="findings"><div class="empty">—</div></div>
    </div>
  </div>
</div>

<script>
const $ = s => document.querySelector(s);
const esc = s => String(s==null?'':s).replace(/[&<>"]/g,
  c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const UNSCRIPTED_TOKEN = "__UNSCRIPTED_AUTH_TOKEN__";
function headers(extra){ const h=Object.assign({},extra||{});
  if(UNSCRIPTED_TOKEN) h['Authorization']='Bearer '+UNSCRIPTED_TOKEN; return h; }
async function get(u){ const r=await fetch(u,{headers:headers()}); return r.json(); }
async function post(u,b){ const r=await fetch(u,{method:'POST',
  headers:headers({'Content-Type':'application/json'}),body:JSON.stringify(b)}); return r.json(); }

let PACK=null, SAVED=null, PREDS=[], SECTION='places', DIRTY=false, PLAYER_ID='';
const PLACE_COLOURS=['#4ea1ff','#39d98a','#ffb454','#ff5d6c','#b98cff','#4fd6d2','#f07fb8','#9aa7b4'];
let placeColour={};

function setStatus(text, cls){ const el=$('#status'); el.textContent=text;
  el.className='status'+(cls?' '+cls:''); }
function markDirty(){ DIRTY=true; $('#save').disabled=false; setStatus('unsaved changes','bad'); }

// ---------------------------------------------------------------- loading --
async function load(){
  const data = await get('/authoring/pack');
  if(data.error){ setStatus(data.error,'bad'); return; }
  PACK = data.pack; PREDS = data.predicates; PLAYER_ID = data.player_id || '';
  SAVED = JSON.stringify(PACK);
  $('#packpath').textContent = PACK.path;
  const places = Object.keys(PACK.world.places||{});
  placeColour = {}; places.forEach((p,i)=> placeColour[p]=PLACE_COLOURS[i%PLACE_COLOURS.length]);
  DIRTY=false; $('#save').disabled=true; setStatus('loaded','ok');
  renderNav(); renderEditor(); renderReport(data.report);
}

async function preview(){
  const data = await post('/authoring/preview', {pack: PACK});
  if(data.report) renderReport(data.report);
}

async function save(){
  setStatus('saving…');
  const data = await post('/authoring/save', {pack: PACK});
  if(data.error){ setStatus(data.error,'bad'); return; }
  SAVED = JSON.stringify(PACK); DIRTY=false; $('#save').disabled=true;
  const errs = (data.issues||[]).filter(i=>i.severity==='error');
  setStatus(errs.length? `saved · ${errs.length} validation error(s)` : 'saved · valid',
            errs.length? 'bad':'ok');
  renderReport(data.report);
}

// ------------------------------------------------------------------- nav --
function sections(){
  const out=[['places','Places'],['topics','Topics'],['knowledge','Who knows what'],
             ['scenario','Scenario'],['canon','Facts this world defines'],['world','World (raw)']];
  Object.keys(PACK.characters||{}).forEach(fn=>out.push(['char:'+fn, (PACK.characters[fn].names||{}).public || fn]));
  return out;
}
function renderNav(){
  $('#nav').innerHTML='';
  sections().forEach(([key,label])=>{
    const b=document.createElement('button');
    b.textContent=label; b.className = key===SECTION?'sel':'';
    b.onclick=()=>{ SECTION=key; renderNav(); renderEditor(); };
    $('#nav').appendChild(b);
  });
}

// ---------------------------------------------------------------- editor --
function renderEditor(){
  const host=$('#editor');
  if(SECTION.startsWith('char:')) return renderCharacter(SECTION.slice(5), host);
  if(SECTION==='topics')    return renderTopics(host);
  if(SECTION==='places')    return renderPlaces(host);
  if(SECTION==='knowledge') return renderKnowledge(host);
  $('#edithead').textContent = SECTION;
  host.innerHTML='';
  host.appendChild(jsonEditor(SECTION==='world'?'world':SECTION, PACK[SECTION]));
}

function slider(label, value, oninput, min, max, step){
  const l=document.createElement('label'); l.textContent=label;
  const wrap=document.createElement('div'); wrap.className='row';
  const i=document.createElement('input'); i.type='range';
  i.min=min==null?0:min; i.max=max==null?1:max; i.step=step||0.05;
  i.value=value==null?0:value;
  const out=document.createElement('span'); out.className='num'; out.textContent=(+i.value).toFixed(2);
  i.oninput=()=>{ out.textContent=(+i.value).toFixed(2); oninput(parseFloat(i.value));
                  markDirty(); preview(); };
  wrap.appendChild(i); wrap.appendChild(out);
  const box=document.createElement('div'); box.appendChild(l); box.appendChild(wrap);
  return box;
}

// -- places: the map, and what a place is like to be in --------------------
function renderPlaces(host){
  $('#edithead').textContent='Places';
  host.innerHTML='';
  const places = PACK.world.places || (PACK.world.places={});
  Object.keys(places).forEach(pid=>{
    const p = places[pid];
    const head=document.createElement('div');
    head.style.cssText='margin:12px 0 2px;border-top:1px solid var(--line);padding-top:10px';
    head.innerHTML=`<b>${esc(p.label||pid)}</b> <span class="hint">${esc(pid)}</span>`;
    host.appendChild(head);
    host.appendChild(field('name players see', p.label, v=>p.label=v));
    host.appendChild(field('words players might type (comma separated)',
      (p.aliases||[]).join(', '),
      v=>p.aliases=v.split(',').map(x=>x.trim()).filter(Boolean)));

    const el=document.createElement('label'); el.textContent='you can walk from here to';
    host.appendChild(el);
    const exits = p.exits || (p.exits=[]);
    Object.keys(places).filter(o=>o!==pid).forEach(other=>{
      const line=document.createElement('div'); line.style.cssText='display:flex;gap:7px;align-items:center';
      const cb=document.createElement('input'); cb.type='checkbox'; cb.style.width='auto';
      cb.checked = exits.includes(other);
      cb.onchange=()=>{ const i=exits.indexOf(other);
        if(cb.checked && i<0) exits.push(other); if(!cb.checked && i>=0) exits.splice(i,1);
        markDirty(); preview(); };
      const lab=document.createElement('span'); lab.style.fontSize='13px';
      lab.textContent=(places[other]||{}).label||other;
      line.appendChild(cb); line.appendChild(lab); host.appendChild(line);
    });

    host.appendChild(slider('how loud it is', p.noise_level, v=>p.noise_level=v));
    host.appendChild(slider('how watched it is', p.surveillance_level, v=>p.surveillance_level=v));
    host.appendChild(slider('how private it is', p.privacy_level, v=>p.privacy_level=v));
    host.appendChild(slider('how formally people speak here', p.formality, v=>p.formality=v));
    host.appendChild(slider('how much gossip spreads here', p.gossip_factor==null?1:p.gossip_factor,
                            v=>p.gossip_factor=v, 0, 2, 0.1));
    const note=document.createElement('div'); note.className='hint';
    note.textContent='0 means nothing is ever passed on here. A market square is above 1, a chapel below.';
    host.appendChild(note);

    const del=document.createElement('button'); del.textContent='remove this place';
    del.style.marginTop='8px';
    del.onclick=()=>{ delete places[pid];
      Object.values(places).forEach(o=>{ if(o.exits) o.exits=o.exits.filter(e=>e!==pid); });
      markDirty(); renderPlaces(host); preview(); };
    host.appendChild(del);
  });
  const add=document.createElement('button'); add.textContent='+ add a place';
  add.style.marginTop='14px';
  add.onclick=()=>{ let n=1; while(places['place:new_'+n]) n++;
    places['place:new_'+n]={label:'New place',aliases:[],exits:[],noise_level:0.3,
      surveillance_level:0.3,privacy_level:0.4,formality:0.4,gossip_factor:1.0};
    markDirty(); renderPlaces(host); preview(); };
  host.appendChild(add);
}

// -- who knows what at the start, and from which source --------------------
function renderKnowledge(host){
  $('#edithead').textContent='Who knows what at the start';
  host.innerHTML='';
  const state = PACK.initial_state || (PACK.initial_state={beliefs:[]});
  const beliefs = state.beliefs || (state.beliefs=[]);
  const agents = Object.values(PACK.characters||{}).map(c=>c.id).filter(Boolean);
  const intro=document.createElement('div'); intro.className='hint';
  intro.textContent='A character can only answer a question if somebody seeded them the '
    + 'knowledge. Every belief needs a source, because "how do you know that" is the '
    + 'question this runtime exists to answer.';
  host.appendChild(intro);

  beliefs.forEach((b,idx)=>{
    const head=document.createElement('div');
    head.style.cssText='margin:12px 0 2px;border-top:1px solid var(--line);padding-top:10px';
    head.innerHTML=`<b>${esc(b.agent||'(nobody)')}</b>`;
    host.appendChild(head);
    const l=document.createElement('label'); l.textContent='who knows it'; host.appendChild(l);
    const sel=document.createElement('select');
    agents.forEach(a=>{ const o=document.createElement('option'); o.value=a; o.textContent=a;
      if(a===b.agent) o.selected=true; sel.appendChild(o); });
    sel.onchange=()=>{ b.agent=sel.value; markDirty(); renderKnowledge(host); preview(); };
    host.appendChild(sel);
    host.appendChild(propositionPicker('what they know', b.proposition, p=>{ b.proposition=p; }));
    host.appendChild(field('how they would describe it', b.summary, v=>b.summary=v));
    host.appendChild(field('where it came from (an id you invent, e.g. seed_mara_saw_it)',
      b.origin_event, v=>b.origin_event=v));
    host.appendChild(slider('how much they trust that source', b.trust==null?0.9:b.trust,
                            v=>b.trust=v));
    host.appendChild(slider('how much it matters to them', b.importance==null?0.6:b.importance,
                            v=>b.importance=v));
    const del=document.createElement('button'); del.textContent='remove'; del.style.marginTop='8px';
    del.onclick=()=>{ beliefs.splice(idx,1); markDirty(); renderKnowledge(host); preview(); };
    host.appendChild(del);
  });
  const add=document.createElement('button'); add.textContent='+ somebody knows something';
  add.style.marginTop='14px';
  add.onclick=()=>{ beliefs.push({agent:agents[0]||'', proposition:{predicate:'',slots:{},polarity:'+'},
    summary:'', origin_event:'seed_'+(beliefs.length+1), trust:0.9, competence:0.85, importance:0.6});
    markDirty(); renderKnowledge(host); preview(); };
  host.appendChild(add);
}

function jsonEditor(key, value){
  const wrap=document.createElement('div');
  const ta=document.createElement('textarea');
  ta.value=JSON.stringify(value,null,2); ta.style.minHeight='420px';
  const msg=document.createElement('div'); msg.className='hint';
  msg.textContent='Raw JSON. Structured editors exist for the parts that need one.';
  ta.oninput=()=>{
    try{ const parsed=JSON.parse(ta.value);
      if(key.startsWith('char:')) PACK.characters[key.slice(5)]=parsed; else PACK[key]=parsed;
      msg.textContent='valid JSON'; msg.style.color='var(--good)'; markDirty(); preview();
    }catch(e){ msg.textContent='invalid JSON: '+e.message; msg.style.color='var(--bad)'; }
  };
  wrap.appendChild(ta); wrap.appendChild(msg);
  return wrap;
}

function field(label, value, oninput, type){
  const l=document.createElement('label'); l.textContent=label;
  const i=document.createElement(type==='area'?'textarea':'input');
  if(type==='area') i.style.minHeight='60px';
  i.value=value==null?'':value;
  i.oninput=()=>{ oninput(i.value); markDirty(); preview(); };
  const box=document.createElement('div'); box.appendChild(l); box.appendChild(i);
  return box;
}

// -- character: the day is the hard part, so it gets a real editor ----------
function renderCharacter(filename, host){
  const c = PACK.characters[filename]; if(!c) return;
  $('#edithead').textContent = (c.names||{}).public || filename;
  host.innerHTML='';
  const places = Object.keys(PACK.world.places||{});

  host.appendChild(field('Public name', (c.names||{}).public,
    v=>{ c.names=c.names||{}; c.names.public=v; }));
  host.appendChild(field('Names players might type (comma separated)',
    ((c.names||{}).aliases||[]).join(', '),
    v=>{ c.names=c.names||{}; c.names.aliases=v.split(',').map(s=>s.trim()).filter(Boolean); }));

  const lbl=document.createElement('label'); lbl.textContent='Their day';
  host.appendChild(lbl);
  const routine = c.routine || (c.routine=[]);
  routine.forEach((block,idx)=>{
    const row=document.createElement('div'); row.className='row'; row.style.marginBottom='5px';
    const t=document.createElement('input'); t.value=block.from||''; t.placeholder='08:00';
    t.oninput=()=>{ block.from=t.value; markDirty(); preview(); };
    const sel=document.createElement('select');
    places.forEach(p=>{ const o=document.createElement('option'); o.value=p;
      o.textContent=(PACK.world.places[p]||{}).label||p;
      if(p===block.place) o.selected=true; sel.appendChild(o); });
    sel.onchange=()=>{ block.place=sel.value; markDirty(); preview(); };
    const act=document.createElement('input'); act.value=block.activity||'';
    act.placeholder='doing what?';
    act.oninput=()=>{ block.activity=act.value; markDirty(); preview(); };
    const del=document.createElement('button'); del.textContent='×'; del.style.flex='0 0 34px';
    del.onclick=()=>{ routine.splice(idx,1); markDirty(); renderCharacter(filename,host); preview(); };
    row.appendChild(t); row.appendChild(sel); row.appendChild(act); row.appendChild(del);
    host.appendChild(row);
  });
  const add=document.createElement('button'); add.textContent='+ add a block';
  add.onclick=()=>{ routine.push({from:'12:00',place:places[0]||'',activity:''});
                    markDirty(); renderCharacter(filename,host); preview(); };
  host.appendChild(add);
  const note=document.createElement('div'); note.className='hint';
  note.textContent='A block runs until the next one starts and wraps past midnight. '
    + 'Where the scene opens must match the block in force at that time.';
  host.appendChild(note);

  // -- relationships: who they trust decides who they believe --------------
  const rl=document.createElement('label'); rl.textContent='How they feel about people';
  host.appendChild(rl);
  const rels = c.relationships || (c.relationships={});
  const everyone = Object.values(PACK.characters||{}).map(x=>x.id)
    .filter(id=>id && id!==c.id).concat(PLAYER_ID?[PLAYER_ID]:[]);
  everyone.forEach(other=>{
    const r = rels[other];
    const line=document.createElement('div');
    line.style.cssText='border-top:1px solid var(--line);padding-top:7px;margin-top:7px';
    const head=document.createElement('div');
    head.style.cssText='display:flex;justify-content:space-between;align-items:center';
    head.innerHTML=`<span style="font:12px/1 var(--mono)">${esc(other)}</span>`;
    const tog=document.createElement('button'); tog.textContent = r? 'forget them':'they know them';
    tog.onclick=()=>{ if(r) delete rels[other];
      else rels[other]={trust:0.3,liking:0.0,familiarity:0.0};
      markDirty(); renderCharacter(filename,host); preview(); };
    head.appendChild(tog); line.appendChild(head);
    if(r){
      line.appendChild(slider('  trusts what they say', r.trust, v=>r.trust=v));
      line.appendChild(slider('  likes them', r.liking, v=>r.liking=v, -1, 1, 0.05));
      line.appendChild(slider('  knows them well', r.familiarity, v=>r.familiarity=v));
      const h=document.createElement('div'); h.className='hint';
      h.textContent='Trust decides how much a claim from them moves this belief. '
        + 'Liking and familiarity decide whether they chat at all.';
      line.appendChild(h);
    }
    host.appendChild(line);
  });

  // -- secrets: a proposition picker, never a core key ---------------------
  const sl=document.createElement('label'); sl.textContent='Secrets'; host.appendChild(sl);
  (c.secrets||[]).forEach((sec,idx)=>{
    if(typeof sec==='string'){ const d=document.createElement('div'); d.className='hint';
      d.textContent='"'+sec+'" — a bare string secret does nothing. Replace it.';
      host.appendChild(d); return; }
    host.appendChild(field('  id', sec.id, v=>sec.id=v));
    host.appendChild(field('  words that would give it away (comma separated)',
      (sec.surface_forms||[]).join(', '),
      v=>sec.surface_forms=v.split(',').map(s=>s.trim()).filter(Boolean)));
    host.appendChild(field('  topics they refuse to discuss (comma separated)',
      (sec.guards_topics||[]).join(', '),
      v=>sec.guards_topics=v.split(',').map(s=>s.trim()).filter(Boolean)));
    host.appendChild(field('  trust needed before they will talk', sec.min_trust,
      v=>sec.min_trust=parseFloat(v)||0));
    host.appendChild(propositionPicker('  what it hides', (sec.protects||[])[0],
      p=>{ sec.protects=[p]; }));
  });

  const raw=document.createElement('div'); raw.style.marginTop='14px';
  const toggle=document.createElement('button'); toggle.textContent='Everything else (raw JSON)';
  const holder=document.createElement('div'); holder.style.display='none';
  toggle.onclick=()=>{ holder.style.display = holder.style.display==='none'?'block':'none';
    if(!holder.childElementCount) holder.appendChild(jsonEditor('char:'+filename, c)); };
  raw.appendChild(toggle); raw.appendChild(holder); host.appendChild(raw);
}

// -- a proposition is a predicate plus fields. The core key is never shown. --
function propositionPicker(label, value, onchange){
  const box=document.createElement('div');
  const l=document.createElement('label'); l.textContent=label; box.appendChild(l);
  const current = (value && typeof value==='object' && value.predicate)
    ? JSON.parse(JSON.stringify(value)) : {predicate:'', slots:{}, polarity:'+'};
  const sel=document.createElement('select');
  const blank=document.createElement('option'); blank.value=''; blank.textContent='— pick a fact —';
  sel.appendChild(blank);
  PREDS.forEach(p=>{ const o=document.createElement('option'); o.value=p.predicate;
    o.textContent=`${p.predicate}  (${p.slots.join(', ')})  · ${p.source}`;
    if(p.predicate===current.predicate) o.selected=true; sel.appendChild(o); });
  const slotBox=document.createElement('div');
  function drawSlots(){
    slotBox.innerHTML='';
    const spec=PREDS.find(p=>p.predicate===current.predicate);
    if(!spec) return;
    spec.slots.forEach(name=>{
      slotBox.appendChild(field('    '+name, current.slots[name]||'',
        v=>{ current.slots[name]=v; onchange(current); }));
    });
    const pol=document.createElement('select');
    [['+','is true'],['-','is NOT true']].forEach(([v,t])=>{
      const o=document.createElement('option'); o.value=v; o.textContent=t;
      if(v===current.polarity) o.selected=true; pol.appendChild(o); });
    pol.onchange=()=>{ current.polarity=pol.value; onchange(current); markDirty(); preview(); };
    const pl=document.createElement('label'); pl.textContent='    and this fact';
    slotBox.appendChild(pl); slotBox.appendChild(pol);
  }
  sel.onchange=()=>{ current.predicate=sel.value; current.slots={};
    drawSlots(); onchange(current); markDirty(); preview(); };
  box.appendChild(sel); box.appendChild(slotBox); drawSlots();
  return box;
}

// -- topics ----------------------------------------------------------------
function renderTopics(host){
  $('#edithead').textContent='Topics';
  host.innerHTML='';
  const topics = (PACK.topics && PACK.topics.topics) || (PACK.topics={topics:[]}).topics;
  topics.forEach((t,idx)=>{
    const head=document.createElement('div'); head.style.cssText=
      'margin:12px 0 2px;border-top:1px solid var(--line);padding-top:10px';
    head.innerHTML=`<b>${esc(t.label||t.id||'(untitled)')}</b>`;
    host.appendChild(head);
    host.appendChild(field('id', t.id, v=>t.id=v));
    host.appendChild(field('label shown to authors', t.label, v=>t.label=v));
    host.appendChild(field('words players might type (comma separated)',
      (t.aliases||[]).join(', '),
      v=>t.aliases=v.split(',').map(s=>s.trim()).filter(Boolean)));
    host.appendChild(propositionPicker('what asking about it is asking',
      t.query, p=>{ t.query=p; }));
    const ph = t.phrasings || (t.phrasings={});
    ['affirm','deny'].forEach(stance=>{
      const set = ph[stance] || (ph[stance]={});
      ['formal','neutral','vernacular'].forEach(reg=>{
        host.appendChild(field(`saying "${stance}" — ${reg}`, set[reg], v=>set[reg]=v));
      });
    });
    const del=document.createElement('button'); del.textContent='remove this topic';
    del.style.marginTop='8px';
    del.onclick=()=>{ topics.splice(idx,1); markDirty(); renderTopics(host); preview(); };
    host.appendChild(del);
  });
  const add=document.createElement('button'); add.textContent='+ add a topic';
  add.style.marginTop='14px';
  add.onclick=()=>{ topics.push({id:'new_topic',label:'New topic',aliases:[],
    phrasings:{affirm:{},deny:{}}}); markDirty(); renderTopics(host); preview(); };
  host.appendChild(add);
}

// ---------------------------------------------------------------- report --
function renderReport(r){
  $('#verdict').textContent = r.ready ? 'playable' : 'not playable yet';
  $('#verdict').style.color = r.ready ? 'var(--good)' : 'var(--bad)';

  // the day
  const day = r.day || {};
  const ids = Object.keys(day);
  if(!ids.length){ $('#day').innerHTML='<div class="empty">no character has a routine yet</div>'; }
  else{
    const n = day[ids[0]].length;
    // where two or more characters coincide is what makes a society
    const meet = [];
    for(let i=0;i<n;i++){
      const counts={};
      ids.forEach(id=>{ const p=day[id][i].place; if(p) counts[p]=(counts[p]||0)+1; });
      meet.push(counts);
    }
    let html='';
    ids.forEach(id=>{
      const cells = day[id].map((s,i)=>{
        const col = placeColour[s.place] || '#33414d';
        const shared = s.place && meet[i][s.place]>1;
        return `<div class="slot${shared?' meet':''}" style="background:${col}"
                 title="${esc(s.clock)} · ${esc(s.place||'')}${s.activity?' · '+esc(s.activity):''}"></div>`;
      }).join('');
      html += `<div class="dayrow"><div class="who">${esc(id.replace('agent:',''))}</div>
               <div class="slots">${cells}</div></div>`;
    });
    html += '<div class="hours">'+[0,3,6,9,12,15,18,21].map(h=>`<span>${h}</span>`).join('')+'</div>';
    $('#day').innerHTML = html;
    $('#legend').innerHTML = Object.keys(placeColour).map(p=>
      `<span><i style="background:${placeColour[p]}"></i>${esc((PACK.world.places[p]||{}).label||p)}</span>`
    ).join('') + '<span><i style="outline:1px solid var(--good);background:transparent"></i>they meet</span>';
  }

  $('#meetings').innerHTML = (r.meetings||[]).length
    ? (r.meetings||[]).map(m=>`<div><b>${esc(m.a.replace('agent:',''))}</b> + `+
        `<b>${esc(m.b.replace('agent:',''))}</b> — ${m.hours_per_day}h/day</div>`).join('')
    : '<div class="empty">nobody ever meets, so nothing can spread</div>';

  $('#map').innerHTML = (r.map||[]).map(p=>
    `<div class="place${p.reachable?'':' unreach'}">${esc(p.label)}`+
    `<span class="ex"> → ${p.exits.length?p.exits.map(e=>esc(e)).join(', '):'nowhere'}</span></div>`
  ).join('') || '<div class="empty">no places yet</div>';

  const f = r.findings||[];
  $('#findings').innerHTML = f.length ? f.map(x=>
    `<div class="find"><span class="lv ${x.level}">${x.level}</span>${esc(x.message)}`+
    (x.fix?`<div class="fix">→ ${esc(x.fix)}</div>`:'')+`</div>`).join('')
    : '<div class="empty">nothing to fix</div>';
}

$('#save').onclick = save;
$('#revert').onclick = ()=>{ if(!DIRTY || confirm('Discard unsaved changes?')) load(); };
window.addEventListener('beforeunload', e=>{ if(DIRTY){ e.preventDefault(); e.returnValue=''; } });
load();
</script>
</body>
</html>"""
