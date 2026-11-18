"""M01: панель «Мировой рынок» — товары, страны, динамика (один автономный HTML-файл).

Вход: канонический CSV (country,year,product_code,indicator,value,unit,flag).
Выход: HTML, который открывается двойным щелчком, без интернета и установки.
Данные встраиваются в файл; неполные наблюдения показываются отдельно и нулями не заполняются.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from m01_surplus_report import build_report

TEMPLATE = r'''<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>M01 · Товарный баланс</title>
<style>
:root{--bg:#f4f5f2;--panel:#fff;--ink:#1d2421;--mute:#5f6b66;--line:#d9ddd8;--accent:#2f6f5e;--pos:#2f7d4f;--neg:#b5532f;--chip:#e8ece8}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#121a17;--panel:#1b2622;--ink:#e6ece8;--mute:#9aa8a1;--line:#2e3b36;--accent:#6fbfa5;--pos:#5fc08a;--neg:#e08a63;--chip:#25322d}}
:root[data-theme=dark]{--bg:#121a17;--panel:#1b2622;--ink:#e6ece8;--mute:#9aa8a1;--line:#2e3b36;--accent:#6fbfa5;--pos:#5fc08a;--neg:#e08a63;--chip:#25322d}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,Segoe UI,Arial,sans-serif}
.wrap{max-width:1100px;margin:0 auto;padding:16px}
h1{font-size:20px;margin:0 0 2px}.sub{color:var(--mute);font-size:13px;margin-bottom:12px}
.bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:10px 0}
.tabs{display:flex;gap:6px}.tab{border:1px solid var(--line);background:var(--panel);color:var(--ink);padding:7px 14px;border-radius:8px;cursor:pointer;font:inherit}
.tab[aria-selected=true]{background:var(--accent);color:#fff;border-color:var(--accent)}
select{background:var(--panel);color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:6px 8px;font:inherit}
label{color:var(--mute);font-size:13px;display:flex;gap:6px;align-items:center}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px;overflow-x:auto}
table{border-collapse:collapse;width:100%;min-width:700px}th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
th{color:var(--mute);font-weight:600;font-size:13px;cursor:pointer;user-select:none}th:first-child,td:first-child{text-align:left}
td.good{font-weight:600}td.rec{white-space:normal;min-width:190px;line-height:1.3}.u{color:var(--mute);font-size:12px;font-weight:400}
.bal{position:relative;width:150px;height:32px;margin-left:auto}
.bal .mid{position:absolute;left:50%;top:0;bottom:0;border-left:1px solid var(--mute)}
.bal .fill{position:absolute;top:19px;height:9px;border-radius:2px}
.bal .t{position:absolute;right:0;left:0;top:0;text-align:center;font-size:12px;line-height:16px}
.pos{color:var(--pos)}.neg{color:var(--neg)}.ok{color:var(--pos)}.bad{color:var(--neg)}
.chip{display:inline-block;background:var(--chip);border-radius:999px;padding:1px 8px;font-size:12px}
.note{color:var(--mute);font-size:13px;margin-top:10px}
.warn{background:var(--chip);border-left:4px solid var(--accent);padding:8px 12px;border-radius:6px;font-size:13px;margin:10px 0}
#tm{position:relative;width:100%;height:340px;border-radius:8px;overflow:hidden}
#tm div{position:absolute;color:#fff;padding:6px 8px;overflow:hidden;border:2px solid var(--panel);border-radius:4px;font-size:13px}
#tm b{display:block}.empty{padding:30px;text-align:center;color:var(--mute)}
svg text{fill:var(--ink);font-size:12px}svg .ax{stroke:var(--line)}svg .gl{stroke:var(--line);stroke-dasharray:3 4}
.leg{display:flex;flex-wrap:wrap;gap:12px;margin-top:6px;font-size:13px}.leg span{display:flex;align-items:center;gap:6px}
</style></head><body><div class="wrap">
<h1>Товарный баланс (M01)</h1>
<div class="sub" id="src"></div>
<div class="warn" id="warn"></div>
<div class="bar"><div class="tabs" role="tablist">
<button class="tab" role="tab" data-t="goods" aria-selected="true">Товары</button>
<button class="tab" role="tab" data-t="map" aria-selected="false">Страны</button>
<button class="tab" role="tab" data-t="trend" aria-selected="false">Динамика</button></div>
<label class="tab" style="cursor:pointer">Открыть CSV<input type="file" id="file" accept=".csv,.tsv,.txt" hidden></label>
<label id="lc">Страна <select id="country"></select></label>
<label id="lp">Товар <select id="product"></select></label>
<label id="ly">Год <select id="year"></select></label>
<label id="lm">Показатель <select id="metric"><option value="production">Производство</option><option value="exports">Экспорт</option><option value="imports">Импорт</option><option value="apparent_consumption">Потребление</option></select></label>
</div>
<div id="err" class="bad" role="alert" style="margin:6px 0"></div>
<div class="card" id="view"></div>
<div class="note" id="inc"></div>
</div>
<script>
let D,R,INC,countries,products,years;
const $=s=>document.querySelector(s);
const uniq=a=>[...new Set(a)];
const fmt=(x,d=1)=>{if(x==null)return'—';const a=Math.abs(x);return Number(x).toLocaleString('ru-RU',a>0&&a<1&&d<3?{maximumSignificantDigits:2}:{maximumFractionDigits:d,minimumFractionDigits:0})};
const pct=x=>x==null?'—':(x*100).toLocaleString('ru-RU',{maximumFractionDigits:0})+' %';
function fill(sel,vals){sel.innerHTML=vals.map(v=>`<option>${v}</option>`).join('')}
function load(d){D=d;R=d.rows;INC=d.incomplete;
 countries=uniq(R.map(r=>r.country)).sort();products=uniq(R.map(r=>r.product_code)).sort();years=uniq(R.map(r=>r.year)).sort((a,b)=>b-a);
 fill($('#country'),countries);fill($('#product'),products);fill($('#year'),years);
 $('#src').textContent=R.length||INC.length?`Источник: ${D.source}. Сформировано ${D.generated}. Строк: ${R.length}, неполных: ${INC.length}.`:'Данные не загружены.';
 $('#warn').textContent=D.warning+' «Баланс» = экспорт − импорт: плюс — избыток (страна производит больше, чем потребляет), минус — дефицит. Цены: нужны стоимостные данные, в этой версии их нет.';
 render()}

function parseCsv(t){t=t.replace(/^﻿/,'');const first=t.split(/\r?\n/,1)[0];
 const d=(first.match(/;/g)||[]).length>(first.match(/,/g)||[]).length?';':(first.includes('\t')&&!first.includes(',')?'\t':',');
 const rows=[];let row=[],f='',q=false;
 for(let i=0;i<t.length;i++){const ch=t[i];
  if(q){if(ch==='"'){if(t[i+1]==='"'){f+='"';i++}else q=false}else f+=ch}
  else if(ch==='"')q=true;else if(ch===d){row.push(f);f=''}
  else if(ch==='\n'||ch==='\r'){if(ch==='\r'&&t[i+1]==='\n')i++;row.push(f);f='';if(row.some(x=>x!==''))rows.push(row);row=[]}
  else f+=ch}
 row.push(f);if(row.some(x=>x!==''))rows.push(row);return rows}
function buildFromCsv(text,name,tol=0.01){
 const rows=parseCsv(text);if(rows.length<2)throw new Error('в файле нет данных');
 const h=rows[0].map(x=>x.trim()),ix=n=>h.indexOf(n),SEP='\u0001',MISS=['C','U',':','-'];
 for(const n of ['country','year','product_code','indicator','value','unit'])if(ix(n)<0)throw new Error(`нет столбца «${n}». Нужен формат: country,year,product_code,indicator,value,unit,flag`);
 const G=new Map(),REP=new Map();
 rows.slice(1).forEach((r,k)=>{const g=n=>ix(n)<0?'':(r[ix(n)]??'').trim();
  if(!Number.isInteger(Number(g('year')))||g('year')==='')throw new Error(`строка ${k+2}: некорректный год «${g('year')}»`);
  const key=[g('country'),g('year'),g('product_code'),g('unit')].join(SEP),ind=g('indicator').toUpperCase(),raw=g('value'),flag=g('flag').toUpperCase();
  if(!G.has(key))G.set(key,{});
  const miss=MISS.includes(flag)||['','..',':','-'].includes(raw);let v=null;
  if(!miss){v=Number(raw);if(!Number.isFinite(v)||(v<0&&ind!=='CONSQNT'))throw new Error(`строка ${k+2}: недопустимое значение «${raw}»`)}
  if(ind==='CONSQNT'){REP.set(key,v);return}
  if(!['PRODQNT','IMPQNT','EXPQNT'].includes(ind))return;
  const o=G.get(key);if(ind in o)throw new Error(`строка ${k+2}: повтор ${ind} для ${key.split(SEP).join(' / ')}`);o[ind]=v});
 const out=[],inc=[];
 [...G.entries()].sort((a,b)=>a[0]<b[0]?-1:1).forEach(([key,o])=>{const [country,year,product,unit]=key.split(SEP);
  const miss=['PRODQNT','IMPQNT','EXPQNT'].filter(i=>o[i]==null);
  if(miss.length){inc.push({country,year:+year,product_code:product,unit,missing_indicators:miss});return}
  const p=o.PRODQNT,im=o.IMPQNT,ex=o.EXPQNT,c=p+im-ex,row={country,year:+year,product_code:product,unit,production:p,imports:im,exports:ex,apparent_consumption:c,net_exports:ex-im,self_sufficiency:c>0?p/c:null};
  const rep=REP.get(key);if(rep!=null){const res=c-rep;row.reported_consumption=rep;row.residual=res;row.residual_rel=rep>0?res/rep:null;row.converges=rep>0?Math.abs(res)<=tol*rep:null}
  out.push(row)});
 return{rows:out,incomplete:inc,warning:'Проданная продукция + импорт - экспорт — кажущееся потребление. Не является полным балансом запасов, потерь и промежуточного использования.',source:name,generated:new Date().toISOString().slice(0,16).replace('T',' ')+' (загружено в браузере)'}}
window.__buildFromCsv=buildFromCsv;
let tab='goods',sortKey='net_exports',sortDir=-1;
const COLS=[['product_code','Товар'],['production','Производство'],['imports','Импорт'],['exports','Экспорт'],['apparent_consumption','Потребление'],['net_exports','Баланс'],['self_sufficiency','Самообеспечение'],['residual','Сверка с источником']];
function balBar(v,max){const w=max?Math.min(50,Math.abs(v)/max*50):0;const cls=v>=0?'pos':'neg';
 const st=v>=0?`left:50%;width:${w}%;background:var(--pos)`:`right:50%;width:${w}%;background:var(--neg)`;
 return `<div class="bal" title="${v>=0?'избыток':'дефицит'}"><div class="mid"></div><div class="fill" style="${st}"></div><div class="t ${cls}">${v>0?'+':''}${fmt(v)}</div></div>`}
function goods(){
 const c=$('#country').value,y=+$('#year').value;
 const rows=R.filter(r=>r.country===c&&r.year===y);
 if(!rows.length)return `<div class="empty">Нет полных данных для ${c}, ${y}. См. список неполных ниже.</div>`;
 rows.sort((a,b)=>sortKey==='product_code'?sortDir*String(a[sortKey]).localeCompare(String(b[sortKey])):sortDir*((a[sortKey]??-Infinity)-(b[sortKey]??-Infinity)));
 const max=Math.max(...rows.map(r=>Math.abs(r.net_exports)))||1;
 const head=COLS.map(([k,t])=>`<th data-k="${k}">${t}${k===sortKey?(sortDir>0?' ▲':' ▼'):''}</th>`).join('');
 const body=rows.map(r=>`<tr><td class="good">${r.product_code} <span class="u">${r.unit}</span></td><td>${fmt(r.production)}</td><td>${fmt(r.imports)}</td><td>${fmt(r.exports)}</td><td>${fmt(r.apparent_consumption)}</td><td>${balBar(r.net_exports,max)}</td><td>${pct(r.self_sufficiency)}</td><td class="rec">${r.residual==null?'<span class="u">нет заявленного потребления</span>':`<span class="${r.converges==null?'u':r.converges?'ok':'bad'}">${r.converges==null?'не проверяется (источник ≤ 0)':r.converges?'✓ совпадает':'✕ расходится'}</span> <span class="u">источник ${fmt(r.reported_consumption,3)}, разница ${r.residual>0?'+':''}${fmt(r.residual,3)} (${pct(r.residual_rel)})</span>`}</td></tr>`).join('');
 return `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table><div class="note"><b>Потребление</b> = производство + импорт − экспорт (расчёт). <b>Сверка с источником</b>: если источник сам сообщает потребление, сравниваем его с расчётом; «совпадает», когда разница не больше допуска (1 %). Разница — это запасы, потери и прочее, что в этих трёх показателях не видно.</div>`}
function squarify(items,W,H){const tot=items.reduce((s,i)=>s+i.v,0),k=W*H/tot,its=items.map(i=>({...i,a:i.v*k}));
 let x=0,y=0,w=W,h=H,row=[],out=[];
 const worst=(r,s)=>{const sm=r.reduce((p,i)=>p+i.a,0),mx=Math.max(...r.map(i=>i.a)),mn=Math.min(...r.map(i=>i.a));return Math.max(s*s*mx/(sm*sm),sm*sm/(s*s*mn))};
 const lay=r=>{const sm=r.reduce((p,i)=>p+i.a,0);if(w>=h){const cw=sm/h;let cy=y;r.forEach(i=>{const ch=i.a/cw;out.push({i,x,y:cy,w:cw,h:ch});cy+=ch});x+=cw;w-=cw}else{const rh=sm/w;let cx=x;r.forEach(i=>{const cw=i.a/rh;out.push({i,x:cx,y,w:cw,h:rh});cx+=cw});y+=rh;h-=rh}};
 its.forEach(i=>{const s=Math.min(w,h);if(!row.length||worst(row.concat(i),s)<=worst(row,s))row.push(i);else{lay(row);row=[i]}});
 if(row.length)lay(row);return out}
function map(){
 const p=$('#product').value,y=+$('#year').value,m=$('#metric').value,mt=$('#metric').selectedOptions[0].text;
 const rows=R.filter(r=>r.product_code===p&&r.year===y&&r[m]>0).sort((a,b)=>b[m]-a[m]);
 if(!rows.length)return `<div class="empty">Нет данных по товару ${p} за ${y}.</div>`;
 const tot=rows.reduce((s,r)=>s+r[m],0);
 const head=`<div class="u" style="margin-bottom:6px">${mt}: ${p}, ${y}. Площадь плитки пропорциональна значению (${rows[0].unit}).</div>`;
 const tbl=`<table style="margin-top:12px"><thead><tr><th>Страна</th><th>${mt}</th><th>Доля</th><th>Баланс</th></tr></thead><tbody>${rows.map(r=>`<tr><td class="good">${r.country}</td><td>${fmt(r[m])}</td><td>${pct(r[m]/tot)}</td><td class="${r.net_exports>=0?'pos':'neg'}">${r.net_exports>0?'+':''}${fmt(r.net_exports)}</td></tr>`).join('')}</tbody></table>`;
 return head+'<div id="tm"></div>'+tbl}
function drawTm(){const el=$('#tm');if(!el)return;const p=$('#product').value,y=+$('#year').value,m=$('#metric').value;
 const rows=R.filter(r=>r.product_code===p&&r.year===y&&r[m]>0).sort((a,b)=>b[m]-a[m]);
 const W=el.clientWidth,H=el.clientHeight,tot=rows.reduce((s,r)=>s+r[m],0);
 el.innerHTML=squarify(rows.map(r=>({v:r[m],r})),W,H).map((t,n)=>`<div style="left:${t.x}px;top:${t.y}px;width:${t.w}px;height:${t.h}px;background:hsl(${(n*47+150)%360} 38% 30%)"><b>${t.i.r.country}</b>${fmt(t.i.v)} · ${pct(t.i.v/tot)}</div>`).join('')}
function trend(){
 const c=$('#country').value,p=$('#product').value;
 const rows=R.filter(r=>r.country===c&&r.product_code===p).sort((a,b)=>a.year-b.year);
 if(rows.length<2)return `<div class="empty">Для динамики нужно минимум два полных года (${c}, ${p}: ${rows.length}).</div>`;
 const S=[['production','Производство','#2f7d4f','0'],['apparent_consumption','Потребление','#3b6ea5','0'],['exports','Экспорт','#b5532f','6 3'],['imports','Импорт','#8a6bb0','2 3']];
 const W=700,H=280,L=52,B=28,T=10,Rr=14,xs=rows.map(r=>r.year),x0=xs[0],x1=xs[xs.length-1];
 const vals=rows.flatMap(r=>S.map(s=>r[s[0]])),hi0=Math.max(0,...vals),lo0=Math.min(0,...vals),hi=hi0>0?hi0*1.08:1,lo=lo0<0?lo0*1.08:0;
 const X=v=>L+(v-x0)/(x1-x0)*(W-L-Rr),Y=v=>T+(hi-v)/(hi-lo)*(H-T-B),dec=hi>=100?0:hi>=10?1:hi>=1?2:4;
 let g='';for(let i=0;i<=4;i++){const v=lo+(hi-lo)*i/4;g+=`<line class="gl" x1="${L}" x2="${W-Rr}" y1="${Y(v)}" y2="${Y(v)}"/><text x="${L-6}" y="${Y(v)+4}" text-anchor="end">${fmt(v,dec)}</text>`}
 if(lo<0)g+=`<line class="ax" x1="${L}" x2="${W-Rr}" y1="${Y(0)}" y2="${Y(0)}" stroke-width="1.5"/><text x="${W-Rr}" y="${Y(0)-4}" text-anchor="end">0</text>`;
 xs.forEach(v=>g+=`<text x="${X(v)}" y="${H-8}" text-anchor="middle">${v}</text>`);
 const lines=S.map(s=>`<polyline fill="none" stroke="${s[2]}" stroke-width="2.4" stroke-dasharray="${s[3]}" points="${rows.map(r=>X(r.year)+','+Y(r[s[0]])).join(' ')}"/>`+rows.map(r=>`<circle cx="${X(r.year)}" cy="${Y(r[s[0]])}" r="3" fill="${s[2]}"><title>${s[1]} ${r.year}: ${fmt(r[s[0]],3)} ${r.unit}</title></circle>`).join('')).join('');
 return `<div class="u">${c} · ${p} · ${rows[0].unit}. Наведите на точку, чтобы увидеть значение.</div><svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Динамика ${p}, ${c}">${g}${lines}</svg><div class="leg">${S.map(s=>`<span><svg width="26" height="8"><line x1="0" x2="26" y1="4" y2="4" stroke="${s[2]}" stroke-width="2.4" stroke-dasharray="${s[3]}"/></svg>${s[1]}</span>`).join('')}</div>`}
function render(){
 if(!R.length&&!INC.length){$('#view').innerHTML='<div class="empty">Данные не загружены. Нажмите «Открыть CSV» и выберите файл в формате country, year, product_code, indicator, value, unit, flag.</div>';$('#inc').innerHTML='';return}
 $('#lc').style.display=tab==='map'?'none':'';$('#lp').style.display=tab==='goods'?'none':'';
 $('#ly').style.display=tab==='trend'?'none':'';$('#lm').style.display=tab==='map'?'':'none';
 $('#view').innerHTML=tab==='goods'?goods():tab==='map'?map():trend();
 if(tab==='map')drawTm();
 document.querySelectorAll('th[data-k]').forEach(th=>th.onclick=()=>{const k=th.dataset.k;if(sortKey===k)sortDir*=-1;else{sortKey=k;sortDir=k==='product_code'?1:-1}render()});
 const c=$('#country').value,y=$('#year').value;
 const inc=INC.filter(x=>tab==='map'?String(x.year)===y:(x.country===c&&(tab==='trend'||String(x.year)===y)));
 $('#inc').innerHTML=inc.length?`<b>Неполные или скрытые данные (не заполнены нулями):</b> `+inc.map(x=>`<span class="chip">${x.country} ${x.product_code} ${x.year}: нет ${x.missing_indicators.join(', ')}</span>`).join(' '):''}
document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>{tab=b.dataset.t;document.querySelectorAll('.tab').forEach(x=>x.setAttribute('aria-selected',x===b));render()});
['#country','#product','#year','#metric'].forEach(s=>$(s).onchange=render);
addEventListener('resize',()=>{if(tab==='map')drawTm()});
$('#file').onchange=async e=>{const f=e.target.files[0];if(!f)return;
 try{load(buildFromCsv(await f.text(),f.name));$('#err').textContent=''}catch(x){$('#err').textContent='Ошибка файла: '+x.message}e.target.value=''};
load(__DATA__);
</script></body></html>'''

def build_html(csv_path, out_path, tolerance=0.01):
    if csv_path is None:   # пустая панель: данные загружаются кнопкой «Открыть CSV»
        rep = {'rows': [], 'incomplete': [], 'warning': 'Проданная продукция + импорт - экспорт — кажущееся потребление. Не является полным балансом запасов, потерь и промежуточного использования.', 'n_rows': 0, 'n_incomplete': 0}
    else:
        rep = build_report(csv_path, tolerance)
    data = {'rows': rep['rows'], 'incomplete': rep['incomplete'], 'warning': rep['warning'],
            'source': Path(csv_path).name if csv_path else '', 'generated': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
    payload = json.dumps(data, ensure_ascii=False).replace('</', '<\\/')
    Path(out_path).write_text(TEMPLATE.replace('__DATA__', payload), encoding='utf-8')
    return rep

def main():
    import argparse
    a = argparse.ArgumentParser(description='M01: панель «Товары / Страны / Динамика» (HTML)')
    a.add_argument('csv', nargs='?', default=None, help='CSV; без него создаётся пустая панель с кнопкой «Открыть CSV»'); a.add_argument('--out', default='m01_dashboard.html'); a.add_argument('--tolerance', type=float, default=0.01)
    x = a.parse_args(); rep = build_html(x.csv, x.out, x.tolerance)
    print(f"Готово: {x.out} (строк {rep['n_rows']}, неполных {rep['n_incomplete']})")

if __name__ == '__main__':
    main()
