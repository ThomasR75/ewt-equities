// EW Calibration Platform — client
let DATA=[], BYID={}, META=[], DEFAULTS={}, EXT=[];
let sortK="buy", sortDir=-1, onlySetups=false, sel=null, tf="D";
let maWin="50", zWin="50", CUR=null, FUND_ASOF=null;
const CHART={};                         // "engine:stock_id" -> {D,W,M} chart data (lazy)
let ENGINE="gbt_log", ENGINES=[];
let SMETA=[], SDEF={};
const $=s=>document.querySelector(s);
const tb=$("#tbl tbody");
const fmt=(v,d=2)=>v==null||isNaN(v)?"—":(+v).toFixed(d);
const gcls=g=>g=="A"?"gA":g=="B"?"gB":"gN";
const sgn=v=>v==null?"":(v>=0?"pos":"neg");
const T=d=>new Date(d).getTime();

async function init(){
  const [f,eng]=await Promise.all([
    fetch("api/factors").then(r=>r.json()),
    fetch("api/engines").then(r=>r.json()).catch(()=>({engines:[],default:null}))
  ]);
  META=f.meta; DEFAULTS=f.defaults; EXT=f.ext_ratios;
  ENGINES=eng.engines||[]; ENGINE=eng.default||(ENGINES[0]&&ENGINES[0].name)||"gbt_log";
  buildEngineSel();
  try{ const sf=await fetch("api/score_factors").then(r=>r.json()); SMETA=sf.meta||[]; SDEF=sf.defaults||{}; buildScoreControls(); }catch(e){}
  const d=await fetch("api/data?engine="+ENGINE).then(r=>r.json());
  setData(d);
  buildControls(); loadPresets();
  const cfg=await fetch("api/config").then(r=>r.json()).catch(()=>({hosted:false}));
  if(cfg.hosted){ applyHosted(); }
  else { refreshFitStatus(); refreshFundStatus(); }
}
function applyHosted(){
  // read-only cloud view: hide the buttons that mutate/compute server-side
  ["#fitBtn","#fitProg","#fundBtn","#fundProg","#btBtn"].forEach(id=>{const e=document.querySelector(id); if(e)e.style.display="none";});
  const s=document.querySelector("#subline"); if(s)s.innerHTML+=' <span class="chip">read-only cloud view</span>';
}
function buildScoreControls(){
  const body=document.querySelector("#sctlBody"); if(!body)return; body.innerHTML="";
  [...new Set(SMETA.map(m=>m.group))].forEach(g=>{
    const box=document.createElement("div"); box.className="grp"; box.innerHTML=`<h3>${g}</h3>`;
    SMETA.filter(m=>m.group===g).forEach(m=>{
      const v=SDEF[m.key];
      const row=document.createElement("div"); row.className="f"; row.dataset.key=m.key;
      row.innerHTML=`<label>${m.label}</label>
        <input type="range" min="${m.min}" max="${m.max}" step="${m.step}" value="${v}" data-skey="${m.key}">
        <span class="val">${(+v).toFixed(2)}</span>`;
      box.appendChild(row);
    });
    body.appendChild(box);
  });
  body.querySelectorAll('input[type=range]').forEach(i=>i.addEventListener("input",e=>{
    const row=e.target.closest(".f"); row.querySelector(".val").textContent=(+e.target.value).toFixed(2);
    row.classList.toggle("changed", Math.abs(+e.target.value-SDEF[e.target.dataset.skey])>1e-9);
    scheduleCalibrate();
  }));
}
function collectScore(){
  const o={}; document.querySelectorAll('#sctlBody input[type=range]').forEach(i=>o[i.dataset.skey]=+i.value); return o;
}
function scoreDirty(){
  return [...document.querySelectorAll('#sctlBody input[type=range]')]
    .some(i=>Math.abs(+i.value-SDEF[i.dataset.skey])>1e-9);
}
document.querySelector("#scoreReset").onclick=()=>{
  document.querySelectorAll('#sctlBody input[type=range]').forEach(i=>{
    i.value=SDEF[i.dataset.skey]; const row=i.closest(".f");
    row.querySelector(".val").textContent=(+i.value).toFixed(2); row.classList.remove("changed");
  });
  calibrate();
};
document.querySelector("#sctlHead").onclick=e=>{
  if(e.target.closest("button")||e.target.closest("input"))return;
  document.querySelector("#sctl").classList.toggle("collapsed");
};
function buildEngineSel(){
  const sel=document.querySelector("#engineSel"); if(!sel)return;
  sel.innerHTML="";
  ENGINES.forEach(e=>{const o=document.createElement("option");o.value=e.name;
    o.textContent=e.label+(e.n?` · ${e.n}`:"");o.selected=(e.name===ENGINE);sel.appendChild(o);});
  sel.disabled = ENGINES.length<2;
  sel.onchange=async ev=>{
    ENGINE=ev.target.value;
    for(const k in CHART)delete CHART[k];
    const d=await fetch("api/data?engine="+ENGINE).then(r=>r.json());
    setData(d); calibrate();
  };
}
function setData(d){
  DATA=d.records; BYID={}; DATA.forEach(x=>BYID[x.stock_id]=x);
  FUND_ASOF=d.fund_as_of||null;
  $("#subline").textContent=`${d.n} names · point-in-time as of ${d.as_of} · setups recompute live · state built ${d.built}`;
  updateSummary(d.summary); render();
}

/* ---------- control panel ---------- */
function buildControls(){
  const body=$("#ctlBody"); body.innerHTML="";
  [...new Set(META.map(m=>m.group))].forEach(g=>{
    const box=document.createElement("div"); box.className="grp"; box.innerHTML=`<h3>${g}</h3>`;
    META.filter(m=>m.group==g).forEach(m=>{
      const v=DEFAULTS[m.key];
      const row=document.createElement("div"); row.className="f"; row.dataset.key=m.key;
      row.innerHTML=`<label>${m.label}</label>
        <input type="range" min="${m.min}" max="${m.max}" step="${m.step}" value="${v}" data-key="${m.key}">
        <span class="val">${fmtFactor(m.key,v)}</span>`;
      box.appendChild(row);
    });
    body.appendChild(box);
  });
  const fb=document.createElement("div"); fb.className="grp";
  fb.innerHTML=`<h3>Fib target ratios</h3><div class="fib" id="fibRow"></div>`; body.appendChild(fb);
  const fr=fb.querySelector("#fibRow");
  EXT.forEach((r,i)=>{const inp=document.createElement("input");inp.type="number";inp.step="0.001";inp.value=r;inp.dataset.fib=i;fr.appendChild(inp);});
  body.querySelectorAll('input[type=range]').forEach(inp=>inp.addEventListener("input",e=>{
    const k=e.target.dataset.key,val=+e.target.value,row=e.target.closest(".f");
    row.querySelector(".val").textContent=fmtFactor(k,val);
    row.classList.toggle("changed",Math.abs(val-DEFAULTS[k])>1e-9);
    scheduleCalibrate();
  }));
  fr.querySelectorAll("input").forEach(inp=>inp.addEventListener("input",scheduleCalibrate));
}
function fmtFactor(k,v){
  if(k.endsWith("_pct")||k=="entry_offset"||k=="stop_extra"||k=="near_max")return (v*100).toFixed(1)+"%";
  return (+v).toFixed(2);
}
function collectCfg(){
  const cfg={};
  document.querySelectorAll('#ctlBody input[type=range]').forEach(i=>cfg[i.dataset.key]=+i.value);
  cfg.ext_ratios=[...document.querySelectorAll('#fibRow input')].map(i=>+i.value).filter(x=>x>0);
  return cfg;
}
let calibTimer=null;
function scheduleCalibrate(){clearTimeout(calibTimer);calibTimer=setTimeout(calibrate,160);}
async function calibrate(){
  $("#busy").style.display="inline-flex";
  const res=await fetch("api/calibrate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({...collectCfg(),engine:ENGINE,score:(scoreDirty()?collectScore():null)})}).then(r=>r.json());
  DATA.forEach(x=>{const r=res.results[x.stock_id]; if(!r)return; x.calib=r;
    if(r.long_score!=null)x.long_score=r.long_score;
    if(r.short_score!=null)x.short_score=r.short_score;
    if(r.d_structure)x.d_structure=r.d_structure;
    if(r.scenarios)x.scenarios_json=r.scenarios;});
  const sn=document.querySelector("#scoreNote"), ss=document.querySelector("#scoreState");
  if(sn){ if(res.score_note){sn.textContent=res.score_note;sn.style.display="inline-flex";} else sn.style.display="none"; }
  if(ss) ss.textContent = res.score_applied ? "custom (live)" : (scoreDirty()?"not applied":"defaults");
  updateSummary(res.summary); render();
  if(CUR&&BYID[CUR.stock_id]){CUR=BYID[CUR.stock_id]; drawSelected(); if($("#ovl").style.display!="none")refreshOverlayLevels();}
  $("#busy").style.display="none";
}
function updateSummary(s){$("#pA").textContent=s.A;$("#pB").textContent=s.B;$("#pL").textContent=s.long;$("#pS").textContent=s.short;$("#pG").textContent=s.with_geometry;$("#pT").textContent=s.total;}
$("#resetBtn").onclick=()=>applyFactors(null);
$("#ctlHead").onclick=e=>{if(e.target.closest("button")||e.target.closest("select"))return;$("#ctl").classList.toggle("collapsed");};

/* ---------- table ---------- */
function acc(x,k){
  const t=x.technicals,c=x.calib;
  switch(k){
    case "ticker":return x.ticker; case "buy":return x.long_score;
    case "grade":return c.grade=="A"?3:c.grade=="B"?2:(c.setup?1:0);
    case "rr":return c.setup?c.setup.rr:null; case "last":return x.last_price;
    case "maDist":return t.ma[maWin]?t.ma[maWin].dist_pct:null; case "z":return t.z[zWin];
    case "pos52":return t.pos52; case "rsi14":return t.rsi14; case "vol20":return t.vol20;
    case "slope50":return t.slope50;
    case "pe":return x.fund?x.fund.pe:null; case "pb":return x.fund?x.fund.pb:null;
    case "dy":return x.fund?x.fund.dy_ttm:null;
    case "d_structure":return x.d_structure||""; default:return null;
  }
}
function rows(){
  let r=DATA.slice();
  if(onlySetups)r=r.filter(x=>x.calib.signal!="none");
  const str=(sortK=="ticker"||sortK=="d_structure");
  r.sort((a,b)=>{let va=acc(a,sortK),vb=acc(b,sortK);
    if(str)return sortDir*String(va).localeCompare(String(vb));
    if(va==null)va=-1e12;if(vb==null)vb=-1e12;return sortDir*(va-vb);});
  return r;
}
function render(){
  const r=rows(); tb.innerHTML="";
  r.forEach((x,i)=>{
    const t=x.technicals,c=x.calib;
    const tr=document.createElement("tr"); tr.dataset.id=x.stock_id;
    if(sel==x.stock_id)tr.className="sel";
    const bw=Math.round(x.long_score*60);
    let g;
    if(c.grade)g=`<span class="badge ${gcls(c.grade)}">${c.grade}</span>`;
    else if(c.setup)g=`<span class="gN" title="${c.setup_reason||''}">·</span>`;
    else g=`<span class="gN">—</span>`;
    const ma=t.ma[maWin];
    const maCell=ma?`<span class="${sgn(ma.dist_pct)}">${ma.dist_pct>=0?"+":""}${ma.dist_pct.toFixed(1)}%</span>`:"—";
    const z=t.z[zWin];
    const zCell=z==null?"—":`<span class="${Math.abs(z)>=2?(z>0?"neg":"pos"):""}">${z>=0?"+":""}${z.toFixed(2)}</span>`;
    const rsi=t.rsi14;
    const rsiCell=rsi==null?"—":`<span class="${rsi>=70?"neg":rsi<=30?"pos":""}">${rsi.toFixed(0)}</span>`;
    tr.innerHTML=`<td>${i+1}</td><td class="tk tkr" title="${(x.name||x.ticker).replace(/"/g,'&quot;')}" style="cursor:help">${x.ticker}</td>
      <td><span class="bar" style="width:${bw}px"></span> ${(x.long_score*100).toFixed(0)}</td>
      <td>${g}</td><td>${c.setup?fmt(c.setup.rr):"—"}</td><td>${fmt(x.last_price)}</td>
      <td>${maCell}</td><td>${zCell}</td>
      <td>${t.pos52==null?"—":t.pos52.toFixed(2)}</td><td>${rsiCell}</td>
      <td>${t.vol20==null?"—":t.vol20.toFixed(0)}</td>
      <td><span class="${sgn(t.slope50)}">${t.slope50==null?"—":(t.slope50>=0?"+":"")+t.slope50.toFixed(1)}</span></td>
      <td>${x.fund&&x.fund.pe!=null?x.fund.pe.toFixed(1):"—"}</td>
      <td>${x.fund&&x.fund.pb!=null?x.fund.pb.toFixed(1):"—"}</td>
      <td>${x.fund&&x.fund.dy_ttm!=null?x.fund.dy_ttm.toFixed(2):"—"}</td>
      <td class="tk" style="color:#9db">${x.d_structure||"—"}</td>`;
    tr.onclick=()=>selectStock(x.stock_id);
    tb.appendChild(tr);
  });
  if((sel==null||!BYID[sel]||(onlySetups&&BYID[sel].calib.signal=="none"))&&r.length){
    selectStock(r[0].stock_id);
  }
}
document.querySelectorAll("#tbl th").forEach(th=>th.onclick=()=>{
  const k=th.dataset.k; if(k=="rank")return;
  if(sortK==k)sortDir*=-1; else{sortK=k;sortDir=(k=="ticker"||k=="d_structure")?1:-1;}
  document.querySelectorAll("#tbl th").forEach(h=>h.classList.remove("sorted")); th.classList.add("sorted");
  $("#sortlbl").textContent="sorted: "+th.textContent.trim(); render();
});
$("#onlySetups").onchange=e=>{onlySetups=e.target.checked;render();};
$("#maSel").onchange=e=>{maWin=e.target.value;$("#hMA").textContent="vs MA"+maWin;render();};
$("#zSel").onchange=e=>{zWin=e.target.value;$("#hZ").textContent="Z"+zWin;render();};
$("#tfBtns").querySelectorAll("button").forEach(b=>b.onclick=()=>{
  tf=b.dataset.tf; $("#tfBtns").querySelectorAll("button").forEach(x=>x.classList.remove("on")); b.classList.add("on");
  drawSelected();
});

/* ---------- selection + charts (on demand) ---------- */
async function ensureChart(sid){
  const k=ENGINE+":"+sid;
  if(!CHART[k]) CHART[k]=(await fetch("api/chart/"+sid+"?engine="+ENGINE).then(r=>r.json())).charts;
  return CHART[k];
}
async function selectStock(sid){
  sel=sid; CUR=BYID[sid];
  [...tb.children].forEach(tr=>tr.classList.toggle("sel",+tr.dataset.id===sid));
  await drawSelected();
}
async function drawSelected(){
  if(!CUR)return;
  const charts=await ensureChart(CUR.stock_id);
  drawMini(CUR, charts[tf]||{series:[],pivots:[],labels:[]});
  if($("#ovl").style.display!=="none") buildOverlay();   // keep overlay in sync
}

/* ---------- mini SVG chart ---------- */
function drawMini(x,ch){
  const c=x.calib, su=c.setup;
  $("#cTkr").textContent=x.ticker;
  $("#cPx").textContent=`last ${fmt(x.last_price)} · as of ${x.as_of} · ${tf==="D"?"daily":tf==="W"?"weekly":"monthly"} · ${ch.structure||"—"} / ${ch.degree||"—"}`;
  $("#cSig").innerHTML=c.signal!="none"?`<span class="badge ${gcls(c.grade)}">${c.grade} ${c.signal.toUpperCase()}</span>`:`<span class="gN">no gated setup${c.setup?" (R/R "+c.setup.rr+")":""}</span>`;
  const S=ch.series,W=900,H=420,mL=48,mR=64,mT=16,mB=28;
  if(!S.length){$("#chart").innerHTML="";return;}
  const xs=S.map(p=>T(p.d)); let xmin=Math.min(...xs),xmax=Math.max(...xs);
  let ys=S.map(p=>p.c);
  const piv=(ch.pivots||[]).filter(p=>T(p.ts)>=xmin&&T(p.ts)<=xmax); piv.forEach(p=>ys.push(p.price));
  if(su)["entry","stop","t1","invalidation_level"].forEach(k=>{if(su[k])ys.push(su[k]);});
  let ymin=Math.min(...ys),ymax=Math.max(...ys);
  const lpad=(Math.log(ymax)-Math.log(ymin))*0.06||0.05,lymin=Math.log(ymin)-lpad,lymax=Math.log(ymax)+lpad;
  const X=v=>mL+(T(v)-xmin)/(xmax-xmin)*(W-mL-mR), Y=v=>mT+(lymax-Math.log(v))/(lymax-lymin)*(H-mT-mB);
  let g=`<rect x="0" y="0" width="${W}" height="${H}" fill="#111a29"/>`;
  for(let i=0;i<=4;i++){const lv=Math.exp(lymin+(lymax-lymin)*i/4),yy=Y(lv);
    g+=`<line x1="${mL}" y1="${yy}" x2="${W-mR}" y2="${yy}" stroke="#22314d"/><text x="${W-mR+6}" y="${yy+4}" fill="#6a7a96" font-size="11">${lv.toFixed(lv<10?2:0)}</text>`;}
  const y0=new Date(xmin).getFullYear(),y1=new Date(xmax).getFullYear();
  for(let yr=y0;yr<=y1;yr++){const xx=X(`${yr}-01-01`);if(xx<mL||xx>W-mR)continue;
    g+=`<line x1="${xx}" y1="${mT}" x2="${xx}" y2="${H-mB}" stroke="#1a2740"/><text x="${xx}" y="${H-8}" fill="#6a7a96" font-size="11" text-anchor="middle">${yr}</text>`;}
  g+=`<path d="${S.map((p,i)=>`${i?"L":"M"}${X(p.d).toFixed(1)},${Y(p.c).toFixed(1)}`).join("")}" fill="none" stroke="#5aa0ff" stroke-width="1.6"/>`;
  if(piv.length){
    g+=`<path d="${piv.map((p,i)=>`${i?"L":"M"}${X(p.ts).toFixed(1)},${Y(p.price).toFixed(1)}`).join("")}" fill="none" stroke="#f4c04d" stroke-width="1.4" opacity=".85"/>`;
    piv.forEach((p,i)=>{const px=X(p.ts),py=Y(p.price);g+=`<circle cx="${px}" cy="${py}" r="3.2" fill="#f4c04d"/><text x="${px}" y="${py-7}" fill="#f4c04d" font-size="12" font-weight="700" text-anchor="middle">${(ch.labels&&ch.labels[i])!=null?ch.labels[i]:""}</text>`;});
  }
  const hl=(v,color,label,dash)=>{if(!v)return;const yy=Y(v);if(yy<mT||yy>H-mB)return;
    g+=`<line x1="${mL}" y1="${yy}" x2="${W-mR}" y2="${yy}" stroke="${color}" stroke-width="1.2" ${dash?'stroke-dasharray="5,4"':''} opacity=".9"/><text x="${mL+4}" y="${yy-4}" fill="${color}" font-size="11" font-weight="600">${label} ${(+v).toFixed(2)}</text>`;};
  if(su){hl(su.entry,"#28c07a","Entry");hl(su.t1,"#1f9e63","T1",1);hl(su.t2,"#1f9e63","T2",1);hl(su.stop,"#f0644b","Stop");hl(su.invalidation_level,"#c23a28","Invalid",1);}
  $("#chart").innerHTML=g;
  renderDetail(x,ch,su);
}
function renderDetail(x,ch,su){
  const nr=x.nested_read||{},cw=nr.current_wave||{};
  let m=`<span class="kv">Buy <b>${(x.long_score*100).toFixed(0)}</b></span><span class="kv">Short <b>${(x.short_score*100).toFixed(0)}</b></span><span class="kv">Alignment <b>${nr.alignment??"—"}</b></span><span class="kv">Wave D/W/M <b>${cw.D??"—"}/${cw.W??"—"}/${cw.M??"—"}</b></span>`;
  if(su)m+=`<span class="kv">Entry <b>${fmt(su.entry)}</b></span><span class="kv">Stop <b>${fmt(su.stop)}</b></span><span class="kv">T1 <b>${fmt(su.t1)}</b></span><span class="kv">R/R <b>${fmt(su.rr)}</b></span>`;
  $("#cMeta").innerHTML=m;
  const tc=x.technicals;
  const maList=["20","50","100","200"].map(w=>{const a=tc.ma[w];return a?`${w}d ${a.above?"▲":"▼"} ${a.dist_pct>=0?"+":""}${a.dist_pct.toFixed(1)}%`:`${w}d —`;}).join(" · ");
  const zList=["20","50","100"].map(w=>tc.z[w]==null?`${w}d —`:`${w}d ${tc.z[w]>=0?"+":""}${tc.z[w].toFixed(2)}σ`).join(" · ");
  $("#cTech").innerHTML=`<div class="kv" style="grid-column:1/3"><b>vs MA:</b> ${maList}</div><div class="kv" style="grid-column:1/3"><b>Z-score:</b> ${zList}</div><div class="kv">52w range pos <b>${tc.pos52==null?"—":tc.pos52.toFixed(2)}</b></div><div class="kv">RSI(14) <b>${tc.rsi14??"—"}</b></div><div class="kv">50d slope <b>${tc.slope50==null?"—":(tc.slope50>=0?"+":"")+tc.slope50.toFixed(1)+"%"}</b></div><div class="kv">Vol 20/60d <b>${tc.vol20??"—"}% / ${tc.vol60??"—"}%</b></div>`;
  const sc=(x.scenarios_json||[]).filter(s=>!s.is_residual);
  let sz=`<h4>Scenario field (weighted)</h4>`;
  sc.forEach(s=>{const col=s.direction>0?"#28c07a":s.direction<0?"#f0644b":"#8090aa",arrow=s.direction>0?"▲":s.direction<0?"▼":"·";
    sz+=`<div class="scrow"><span class="w">${(s.weight*100).toFixed(0)}%</span><span class="sbar" style="width:${Math.round(s.weight*150)}px;background:${col}"></span><span style="color:${col}">${arrow}</span><span style="color:#b9c6dc">${s.path}</span></div>`;});
  const resid=(x.scenarios_json||[]).find(s=>s.is_residual);
  if(resid)sz+=`<div class="scrow"><span class="w">${(resid.weight*100).toFixed(0)}%</span><span class="sbar" style="width:${Math.round(resid.weight*150)}px;background:#3a4a63"></span><span style="color:#8090aa">· no clean structure</span></div>`;
  $("#cScz").innerHTML=sz;
  renderFund(x);
}
function renderFund(x){
  const el=$("#cFund"); const f=x.fund;
  if(!f){el.innerHTML=`<div class="kv" style="grid-column:1/3;color:#6a7a96"><b>Fundamentals:</b> none loaded — click “Update fundamentals”.</div>`;return;}
  const n=(v,d=2,suf="")=>v==null?"—":(+v).toFixed(d)+suf;
  const cap=f.mktcap==null?"—":(f.mktcap>=1e12?(f.mktcap/1e12).toFixed(2)+"T":f.mktcap>=1e9?(f.mktcap/1e9).toFixed(1)+"B":(f.mktcap/1e6).toFixed(0)+"M");
  el.innerHTML=`
   <div class="kv" style="grid-column:1/3;border-top:1px solid var(--line);padding-top:7px"><b>Fundamentals</b> <span style="color:#6a7a96">${FUND_ASOF?("as of "+FUND_ASOF):""}</span></div>
   <div class="kv">P/E (ttm) <b>${n(f.pe,1)}</b> · fwd <b>${n(f.pe_fwd,1)}</b></div>
   <div class="kv">P/B <b>${n(f.pb,1)}</b></div>
   <div class="kv">EPS (ttm) <b>${n(f.eps,2)}</b> · fwd <b>${n(f.eps_fwd,2)}</b></div>
   <div class="kv">Market cap <b>${cap}</b></div>
   <div class="kv" style="grid-column:1/3">Div yield — ttm <b>${n(f.dy_ttm,2,"%")}</b> · prior yr <b>${n(f.dy_prev,2,"%")}</b> · forward <b>${n(f.dy_fwd,2,"%")}</b></div>`;
}

/* ---------- uPlot zoomable overlay ---------- */
let U=null, OVX={pivots:[],labels:[],levels:[],x0:0,x1:0};
$("#chart").onclick=()=>{ if(!CUR)return;
  if(typeof uPlot==="undefined"){alert("Zoom view needs the uPlot library (from CDN). Check your connection and reload.");return;}
  $("#ovl").style.display="flex"; buildOverlay(); };
$("#ovClose").onclick=()=>{ $("#ovl").style.display="none"; if(U){U.destroy();U=null;} };
$("#ovl").addEventListener("click",e=>{ if(e.target.id==="ovl"){$("#ovClose").onclick();} });
document.addEventListener("keydown",e=>{ if(e.key==="Escape"&&$("#ovl").style.display!=="none")$("#ovClose").onclick(); });
$("#ovTf").querySelectorAll("button").forEach(b=>b.onclick=()=>{
  tf=b.dataset.tf; $("#ovTf").querySelectorAll("button").forEach(x=>x.classList.remove("on")); b.classList.add("on");
  $("#tfBtns").querySelectorAll("button").forEach(x=>x.classList.toggle("on",x.dataset.tf===tf));
  drawSelected();
});
$("#ovRefit").onclick=refitCurrent;

function yRange(u){
  const xs=u.data[0],ys=u.data[1],xmin=u.scales.x.min,xmax=u.scales.x.max;
  let lo=Infinity,hi=-Infinity;
  for(let i=0;i<xs.length;i++)if(xs[i]>=xmin&&xs[i]<=xmax){const v=ys[i];if(v!=null){if(v<lo)lo=v;if(v>hi)hi=v;}}
  OVX.pivots.forEach(pv=>{if(pv.t>=xmin&&pv.t<=xmax){if(pv.price<lo)lo=pv.price;if(pv.price>hi)hi=pv.price;}});
  OVX.levels.forEach(L=>{if(L.v){if(L.v<lo)lo=L.v;if(L.v>hi)hi=L.v;}});
  if(!isFinite(lo)){lo=Math.min(...ys.filter(v=>v!=null));hi=Math.max(...ys.filter(v=>v!=null));}
  const pad=(Math.log(hi)-Math.log(lo))*0.06||0.02;
  return [Math.exp(Math.log(lo)-pad),Math.exp(Math.log(hi)+pad)];
}
function wheelZoomPlugin(){
  return {hooks:{ready:u=>{
    const over=u.over;
    over.addEventListener("wheel",e=>{
      e.preventDefault();
      const rect=over.getBoundingClientRect(), curX=(e.clientX-rect.left)/rect.width;
      const min=u.scales.x.min,max=u.scales.x.max,range=max-min;
      const nRange=range*(e.deltaY<0?0.82:1/0.82);
      const at=min+curX*range;
      let nMin=at-curX*nRange,nMax=at+(1-curX)*nRange;
      nMin=Math.max(OVX.x0,nMin); nMax=Math.min(OVX.x1,nMax);
      if(nMax-nMin>10) u.setScale("x",{min:nMin,max:nMax});
    },{passive:false});
    let panning=false,px=0,pmin=0,pmax=0;
    over.addEventListener("mousedown",e=>{if(e.button!==0)return;panning=true;px=e.clientX;pmin=u.scales.x.min;pmax=u.scales.x.max;over.style.cursor="grabbing";});
    window.addEventListener("mousemove",e=>{if(!panning)return;
      const rect=over.getBoundingClientRect(),perPx=(pmax-pmin)/rect.width,dx=(e.clientX-px)*perPx;
      let nMin=pmin-dx,nMax=pmax-dx;
      if(nMin<OVX.x0){nMax+=OVX.x0-nMin;nMin=OVX.x0;} if(nMax>OVX.x1){nMin-=nMax-OVX.x1;nMax=OVX.x1;}
      u.setScale("x",{min:Math.max(OVX.x0,nMin),max:Math.min(OVX.x1,nMax)});});
    window.addEventListener("mouseup",()=>{panning=false;over.style.cursor="grab";});
    over.addEventListener("dblclick",()=>u.setScale("x",{min:OVX.x0,max:OVX.x1}));
  }}};
}
function overlayDrawPlugin(){
  const dpr=(window.uPlot&&uPlot.pxRatio)||window.devicePixelRatio||1;
  return {hooks:{draw:u=>{
    const c=u.ctx,L=u.bbox.left,Tp=u.bbox.top,Wp=u.bbox.width,Hp=u.bbox.height; c.save();
    OVX.levels.forEach(l=>{if(!l.v)return;const y=u.valToPos(l.v,"y",true);if(y<Tp||y>Tp+Hp)return;
      c.strokeStyle=l.color;c.lineWidth=1*dpr;c.setLineDash(l.dash?[5*dpr,4*dpr]:[]);
      c.beginPath();c.moveTo(L,y);c.lineTo(L+Wp,y);c.stroke();c.setLineDash([]);
      c.fillStyle=l.color;c.font=`${11*dpr}px sans-serif`;c.textAlign="left";c.fillText(`${l.label} ${l.v.toFixed(2)}`,L+4*dpr,y-3*dpr);});
    const pv=OVX.pivots.filter(p=>p.t>=u.scales.x.min&&p.t<=u.scales.x.max);
    if(pv.length){c.strokeStyle="#f4c04d";c.globalAlpha=.85;c.lineWidth=1.3*dpr;c.beginPath();
      pv.forEach((p,i)=>{const x=u.valToPos(p.t,"x",true),y=u.valToPos(p.price,"y",true);i?c.lineTo(x,y):c.moveTo(x,y);});c.stroke();c.globalAlpha=1;
      pv.forEach(p=>{const x=u.valToPos(p.t,"x",true),y=u.valToPos(p.price,"y",true);
        c.fillStyle="#f4c04d";c.beginPath();c.arc(x,y,3.2*dpr,0,7);c.fill();
        c.font=`bold ${12*dpr}px sans-serif`;c.textAlign="center";c.fillText(p.label||"",x,y-8*dpr);});}
    c.restore();
  }}};
}
function buildOverlay(){
  const x=CUR,ch=(CHART[ENGINE+":"+x.stock_id]||{})[tf]; if(!ch)return;
  $("#ovTkr").textContent=x.ticker+(x.name?` · ${x.name}`:"");
  $("#ovMeta").textContent=`${tf==="D"?"daily":tf==="W"?"weekly":"monthly"} · ${ch.structure||"—"} / ${ch.degree||"—"} · last ${fmt(x.last_price)} · as of ${x.as_of}`;
  $("#ovTf").querySelectorAll("button").forEach(b=>b.classList.toggle("on",b.dataset.tf===tf));
  const S=ch.series; if(!S.length){return;}
  const xs=S.map(p=>T(p.d)/1000), ys=S.map(p=>p.c);
  OVX.x0=xs[0]; OVX.x1=xs[xs.length-1];
  OVX.pivots=(ch.pivots||[]).map((p,i)=>({t:T(p.ts)/1000,price:p.price,label:(ch.labels&&ch.labels[i])||""})).filter(p=>p.t>=OVX.x0&&p.t<=OVX.x1);
  const su=x.calib.setup;
  OVX.levels=su?[{v:su.entry,color:"#28c07a",label:"Entry"},{v:su.t1,color:"#1f9e63",label:"T1",dash:1},{v:su.t2,color:"#1f9e63",label:"T2",dash:1},{v:su.stop,color:"#f0644b",label:"Stop"},{v:su.invalidation_level,color:"#c23a28",label:"Invalid",dash:1}]:[];
  const wrap=$("#uwrap"), w=wrap.clientWidth-4, h=wrap.clientHeight-4;
  const opts={width:w,height:h,padding:[10,14,4,8],
    scales:{x:{time:true},y:{distr:3,range:yRange}},
    axes:[{stroke:"#8a9ab5",grid:{stroke:"#1a2740"},ticks:{stroke:"#2a3852"}},
          {stroke:"#8a9ab5",grid:{stroke:"#22314d"},ticks:{stroke:"#2a3852"},size:60}],
    cursor:{drag:{x:false,y:false},points:{size:5}},
    legend:{show:false},
    series:[{value:(u,v)=>v==null?"":new Date(v*1000).toISOString().slice(0,10)},
            {label:"close",stroke:"#5aa0ff",width:1.6,points:{show:false},value:(u,v)=>v==null?"":v.toFixed(2)}],
    plugins:[wheelZoomPlugin(),overlayDrawPlugin()]};
  if(U)U.destroy();
  U=new uPlot(opts,[xs,ys],$("#uchart"));
}
function refreshOverlayLevels(){ if(U&&CUR){buildOverlay();} }
window.addEventListener("resize",()=>{ if(U&&$("#ovl").style.display!=="none"){const wr=$("#uwrap");U.setSize({width:wr.clientWidth-4,height:wr.clientHeight-4});} });

/* ---------- fitter ---------- */
async function refreshFundStatus(){
  const s=await fetch("api/fundamentals/status").then(r=>r.json());
  const b=$("#fundBtn");
  if(!s.yfinance_available){b.title="Updating needs yfinance in the server env"; }
  if(s.running)pollFund();
}
async function refreshFitStatus(){
  const s=await fetch("api/fit/status").then(r=>r.json());
  const btn=$("#fitBtn");
  if(!s.weigher_available){ btn.disabled=true; btn.title=s.weigher_msg||"fitter deps missing"; btn.textContent="Run fit (needs joblib+lightgbm)"; }
  if(s.running){ pollFit(); }
}
$("#fundBtn").onclick=async()=>{
  const st=await fetch("api/fundamentals/status").then(r=>r.json());
  if(!st.yfinance_available){alert("Updating fundamentals needs yfinance in the server env (pip install yfinance).");return;}
  if(!confirm("Refresh fundamentals (P/E, P/B, dividend yields) from yfinance for the whole universe? Takes a few minutes."))return;
  const r=await fetch("api/fundamentals/update",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"}).then(x=>x.json());
  if(r.error){alert(r.error);return;}
  pollFund();
};
let fundTimer=null;
function pollFund(){
  $("#fundBtn").disabled=true; $("#fundProg").style.display="inline-flex";
  clearTimeout(fundTimer);
  const tick=async()=>{
    const s=await fetch("api/fundamentals/status").then(r=>r.json());
    $("#fundProg").textContent=`fundamentals ${s.done}/${s.total||"…"}`;
    if(s.running){fundTimer=setTimeout(tick,1500);}
    else{
      $("#fundProg").style.display="none"; $("#fundBtn").disabled=false;
      if(s.error){alert("Fundamentals update error: "+s.error);return;}
      const d=await fetch("api/data?engine="+ENGINE).then(r=>r.json()); setData(d); calibrate();
    }
  };
  tick();
}
$("#fitBtn").onclick=async()=>{
  if($("#fitBtn").disabled)return;
  if(!confirm("Re-run the wave fitter for the whole universe? This can take several minutes for a large universe."))return;
  const r=await fetch("api/fit/universe",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"}).then(x=>x.json());
  if(r.error){alert(r.error);return;}
  pollFit();
};
let fitTimer=null;
function pollFit(){
  $("#fitBtn").disabled=true; $("#fitProg").style.display="inline-flex";
  clearTimeout(fitTimer);
  const tick=async()=>{
    const s=await fetch("api/fit/status").then(r=>r.json());
    $("#fitProg").textContent=`fitting ${s.done}/${s.total||"…"}`;
    if(s.running){ fitTimer=setTimeout(tick,1200); }
    else{
      $("#fitProg").style.display="none"; $("#fitBtn").disabled=false;
      if(s.phase==="error"){alert("Fit error: "+s.error);return;}
      for(const k in CHART)delete CHART[k];               // charts changed
      const d=await fetch("api/data?engine="+ENGINE).then(r=>r.json()); setData(d); calibrate();
    }
  };
  tick();
}
async function refitCurrent(){
  if(!CUR)return;
  const btn=$("#ovRefit"); btn.disabled=true; btn.textContent="Re-fitting…";
  const r=await fetch("api/fit/stock",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({stock_id:CUR.stock_id})}).then(x=>x.json());
  btn.disabled=false; btn.textContent="Re-fit ⟳";
  if(r.error){alert(r.error);return;}
  const sid=CUR.stock_id; delete CHART[ENGINE+":"+sid];
  await calibrate();                                       // refresh table under current cfg
  CUR=BYID[sid]; await drawSelected();
}

/* ---------- presets ---------- */
let PRESETS={builtin:[],user:[]};
async function loadPresets(selv){
  PRESETS=await fetch("api/presets").then(r=>r.json());
  const s=$("#presetSel"); s.innerHTML='<option value="">Presets…</option>';
  const add=(arr,label)=>{if(!arr.length)return;const og=document.createElement("optgroup");og.label=label;
    arr.forEach(p=>{const o=document.createElement("option");o.value=(p.builtin?"b:":"u:")+p.name;o.textContent=p.name;og.appendChild(o);});s.appendChild(og);};
  add(PRESETS.builtin,"Built-in"); add(PRESETS.user,"Saved"); if(selv)s.value=selv;
}
function applyFactors(factors){
  document.querySelectorAll('#ctlBody input[type=range]').forEach(i=>{
    const k=i.dataset.key,v=(factors&&k in factors)?factors[k]:DEFAULTS[k];
    i.value=v;const row=i.closest(".f");row.querySelector(".val").textContent=fmtFactor(k,+v);
    row.classList.toggle("changed",Math.abs(+v-DEFAULTS[k])>1e-9);});
  const ext=(factors&&factors.ext_ratios)?factors.ext_ratios:EXT;
  document.querySelectorAll('#fibRow input').forEach((i,idx)=>i.value=ext[idx]!=null?ext[idx]:EXT[idx]);
  calibrate();
}
$("#presetSel").onchange=e=>{const v=e.target.value;if(!v)return;const [kind,...rest]=v.split(":");const name=rest.join(":");
  const p=(kind=="b"?PRESETS.builtin:PRESETS.user).find(x=>x.name==name);if(p)applyFactors(p.factors);};
$("#saveBtn").onclick=async()=>{const name=prompt("Save calibration preset as:");if(!name)return;
  await fetch("api/presets",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name:name.trim(),factors:collectCfg()})});await loadPresets("u:"+name.trim());};
$("#delBtn").onclick=async()=>{const v=$("#presetSel").value;if(!v.startsWith("u:")){alert("Pick a saved preset to delete.");return;}
  const name=v.slice(2);if(!confirm(`Delete preset “${name}”?`))return;await fetch("api/presets/"+encodeURIComponent(name),{method:"DELETE"});await loadPresets();};

/* ---------- backtest ---------- */
$("#btBtn").onclick=runBacktest;
function card(lab,num,ci,delta){return `<div class="btcard"><div class="lab">${lab}</div><div class="num mono">${num}</div>${ci?`<div class="ci mono">${ci}</div>`:""}${delta?`<div class="delta">${delta}</div>`:""}</div>`;}
function dcol(v){return v>0?"pos":v<0?"neg":"";}
function fmtDelta(cur,base,d=2,pct=false){if(cur==null||base==null)return "";const x=cur-base;return `<span class="${dcol(x)}">Δ ${(x>=0?"+":"")+x.toFixed(d)+(pct?" pts":"")} vs baseline</span>`;}
async function runBacktest(){
  $("#btPanel").style.display="block"; $("#btBusy").style.display="inline-flex"; $("#btBtn").textContent="Backtest ⏳";
  const r=await fetch("api/backtest",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({...collectCfg(),cutoff:(document.querySelector("#btCutoff")||{}).value||null})}).then(x=>x.json());
  $("#btBusy").style.display="none"; $("#btBtn").textContent="Backtest ▶";
  if(r.error){$("#btBody").innerHTML=`<div class="btnote">${r.error}</div>`;return;}
  renderBacktest(r.result,r.baseline,r.span);
}
function renderBacktest(res,base,span){
  $("#btSpan").innerHTML=`${span.n_stocks} stocks · walk-forward ${span.start}+ step ${span.step}`;
  if(res.resolved===0){$("#btBody").innerHTML=`<div class="btnote">No resolved setups under this calibration — loosen the gate to generate trades to score.</div>`;return;}
  const w=res,wr=w.win_rate,ex=w.expectancy;
  const wrCI=`Wilson95 ${w.wilson95[0]}–${w.wilson95[1]}%`, exCI=`boot95 ${w.boot95[0]>=0?"+":""}${w.boot95[0]} … ${w.boot95[1]>=0?"+":""}${w.boot95[1]}`;
  let g=`<div class="btgrid">`;
  g+=card("Resolved setups",`${w.resolved}`,`of ${w.graded_setups} graded`,"");
  g+=card("Win rate",`${wr}%`,wrCI,fmtDelta(wr,base.win_rate,1,true));
  g+=card("Expectancy (R/trade)",`${ex>=0?"+":""}${ex}`,`${exCI} · p=${w.p_mean_ne_0}`,fmtDelta(ex,base.expectancy,3));
  g+=card("Total R",`${w.total_r>=0?"+":""}${w.total_r}`,`${w.won}W / ${w.lost}L / ${w.invalidated}inv / ${w.expired}exp`,"");
  g+=card("Engine vs coin-flip",`p=${w.p_engine_ge_random}`,`null mean ${w.null_mean>=0?"+":""}${w.null_mean}`,"");
  const A=w.grade.A,B=w.grade.B;
  g+=card("Grade A",A?`${A.win_pct}% · ${A.mean_r>=0?"+":""}${A.mean_r}R`:"—",A?`n=${A.n}`:"no A setups","");
  g+=card("Grade B",B?`${B.win_pct}% · ${B.mean_r>=0?"+":""}${B.mean_r}R`:"—",B?`n=${B.n}`:"no B setups","");
  g+=`</div>`;
  const notes=[];
  if(w.boot95[0]<=0&&w.boot95[1]>=0)notes.push("Expectancy CI spans 0 — no statistically detectable edge.");
  else if(w.boot95[0]>0)notes.push("Expectancy CI entirely positive — a detectable edge on this sample (caution: in-sample tuning).");
  else notes.push("Expectancy CI entirely negative — this calibration loses.");
  if(w.p_engine_ge_random>0.10)notes.push(`Direction no better than a coin flip (p=${w.p_engine_ge_random}).`);
  if(A&&B&&A.mean_r<B.mean_r)notes.push("Grade A underperforms B — calibration inverted (same as the reliability study).");
  notes.push("Tuning and scoring on the same history overstates edge; a real edge must survive out-of-sample.");
  if(w.splits){
    const sp=w.splits, mk=(t,m)=>{
      if(!m||!m.resolved)return card(t,"—",m&&m.note?m.note:"no setups","");
      return card(t,`${m.expectancy>=0?"+":""}${m.expectancy} R`,
        `n=${m.resolved} · win ${m.win_rate}% · boot95 ${m.boot95[0]} … ${m.boot95[1]}`,"");
    };
    g+=`<div class="rgrp" style="margin-top:14px"><h3>Train / holdout split @ ${sp.cutoff}</h3><div class="btgrid">`;
    g+=mk("Train (before cutoff)",sp.train)+mk("Holdout (on/after cutoff)",sp.holdout)+`</div></div>`;
    const ho=sp.holdout||{};
    if(ho.resolved){
      notes.push(ho.boot95 && ho.boot95[0]>0
        ? "Holdout expectancy CI is positive — the only result here worth anything."
        : "Holdout expectancy is not positive — a tuned set that only wins in train is overfit.");
    } else notes.push("No resolved setups in the holdout window — the split tells you nothing yet.");
  }
  g+=`<div class="btnote">${notes.join(" ")}</div>`;
  $("#btBody").innerHTML=g;
}

init();


/* ---------- EWT rules modal ---------- */
let RULES=null;
document.querySelector("#rulesBtn").onclick=openRules;
document.querySelector("#rulesClose").onclick=()=>{document.querySelector("#rovl").style.display="none";};
document.querySelector("#rovl").addEventListener("click",e=>{if(e.target.id==="rovl")document.querySelector("#rovl").style.display="none";});
async function openRules(){
  if(!RULES) RULES=await fetch("api/rules").then(r=>r.json());
  renderRules(RULES);
  document.querySelector("#rovl").style.display="flex";
}
function esc(t){return (t||"").replace(/&/g,"&amp;").replace(/</g,"&lt;");}
function renderRules(R){
  const rule=(name,cond,desc,extra)=>`<div class="rrule"><span class="rn">${esc(name)}</span>${cond?`<span class="rc">${esc(cond)}</span>`:""}${extra?` <span class="rw">${esc(extra)}</span>`:""}<div class="rd">${esc(desc)}</div></div>`;
  let h=`<div class="rgrp"><p class="note">${esc(R.scale_note)}</p></div>`;
  h+=`<div class="rgrp"><h3>Cardinal rules</h3><p class="note">${esc(R.cardinal_note)}</p>`;
  R.cardinal.forEach(r=>h+=rule(r.name,r.condition,r.description)); h+=`</div>`;
  h+=`<div class="rgrp"><h3>Classification</h3>`;
  (R.classification||[]).forEach(r=>h+=rule(r.name,r.condition,"")); h+=`</div>`;
  h+=`<div class="rgrp"><h3>Corrective structures</h3>`;
  R.corrective.forEach(r=>h+=rule(r.name,r.condition,r.description)); h+=`</div>`;
  h+=`<div class="rgrp"><h3>Guidelines (soft scores)</h3><p class="note">${esc(R.guideline_note)}</p>`;
  R.guidelines.forEach(r=>h+=rule(r.name,"",r.description,`weight ${r.weight} (${r.weight_pct}%)`)); h+=`</div>`;
  document.querySelector("#rulesBody").innerHTML=h;
}
