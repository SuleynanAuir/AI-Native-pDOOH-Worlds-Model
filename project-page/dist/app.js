const $=s=>document.querySelector(s);
const dialog=$('#lightbox');
document.querySelectorAll('.zoom').forEach(button=>button.addEventListener('click',()=>{
 dialog.querySelector('img').src=button.dataset.image;
 dialog.querySelector('img').alt=button.dataset.caption;
 dialog.querySelector('p').textContent=button.dataset.caption;
 dialog.showModal();
}));
dialog.querySelector('.close').addEventListener('click',()=>dialog.close());
dialog.addEventListener('click',e=>{if(e.target===dialog)dialog.close()});
const galleries={
 simulation:['simulation-scenes','Daily simulation · Two location-specific scenes share a playback clock, while their audience evidence remains separate.'],
 map:['investment-map','Investment geography · Screen coordinates, investment intensity, and regional summaries from the saved report.'],
 quote:['investment-quote','Screen-level quote · Campaign days, daily amount, total investment, cumulative Impression, and SOT.']
};
document.querySelectorAll('[data-gallery]').forEach(b=>b.addEventListener('click',()=>{
 document.querySelectorAll('[data-gallery]').forEach(x=>{x.classList.toggle('active',x===b);x.setAttribute('aria-pressed',String(x===b))});
 const [file,caption]=galleries[b.dataset.gallery];
 $('#gallery-image').src='assets/'+file+'.webp';$('#gallery-image').alt=caption;
 $('#gallery-caption').textContent=caption;
 $('#gallery-zoom').dataset.image='assets/'+file+'.webp';$('#gallery-zoom').dataset.caption=caption;
}));
const info={
 investment:['Balanced evidence','The integrated plan','Combine seven-dimensional importance with media cost, location, and investment constraints.'],
 sim_exposure:['Exposure efficiency','Prioritize viewing opportunity','Give greater weight to exposure potential and cost efficiency when redistributing the available budget.'],
 sim_interest:['Audience interest','Follow audience relevance','Emphasize simulated interest, favorability, and market match. These attitudes are not conversion probabilities.'],
 sim_coverage:['Regional dispersion','Spread the investment','Apply a stronger regional-concentration penalty to reduce the preference for densely represented location groups.']
};
const num=n=>Math.round(n).toLocaleString('en-US'),money=n=>'$'+n.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
const compact=n=>new Intl.NumberFormat('en',{notation:'compact',maximumFractionDigits:1}).format(n);
const ns='http://www.w3.org/2000/svg';
function svgEl(tag,attrs,text){const el=document.createElementNS(ns,tag);for(const [k,v]of Object.entries(attrs))el.setAttribute(k,v);if(text!==undefined)el.textContent=text;return el}
fetch('assets/results.json').then(r=>{if(!r.ok)throw Error('Report data unavailable');return r.json()}).then(data=>{
 const maxX=Math.max(...data.plans.flatMap(p=>p.items.map(i=>i.amount)))*1.06;
 const maxY=Math.max(...data.plans.flatMap(p=>p.items.map(i=>i.impressions)))*1.06;
 for(const p of data.plans){
  const b=document.createElement('button');b.textContent=info[p.strategy][0];b.dataset.strategy=p.strategy;b.addEventListener('click',()=>render(p));$('#result-tabs').append(b);
  const tr=document.createElement('tr');tr.dataset.plan=p.strategy;
  for(const v of [info[p.strategy][0],money(p.total),num(p.impressions),money(p.total*1000/p.impressions),p.screen_count]){
   const td=document.createElement('td');td.textContent=v;tr.append(td)
  }$('#comparison-body').append(tr);
 }
 function render(p){
  document.querySelectorAll('[data-strategy]').forEach(b=>{b.classList.toggle('active',b.dataset.strategy===p.strategy);b.setAttribute('aria-pressed',String(b.dataset.strategy===p.strategy))});
  document.querySelectorAll('[data-plan]').forEach(tr=>tr.classList.toggle('selected',tr.dataset.plan===p.strategy));
  const [label,title,description]=info[p.strategy];
  $('#strategy-label').textContent=label;$('#strategy-title').textContent=title;$('#strategy-description').textContent=description;
  $('#result-budget').textContent=money(p.total);$('#result-impressions').textContent=num(p.impressions);
  $('#result-cpm').textContent=money(p.total*1000/p.impressions);$('#result-screens').textContent=p.screen_count+' / '+data.coverage.total;
  const svg=$('#strategy-chart');svg.replaceChildren();
  svg.setAttribute('aria-label',label+': '+num(p.impressions)+' predicted cumulative Impression, '+money(p.total)+' investment.');
  svg.append(svgEl('text',{x:65,y:20},'Cumulative Impression'));
  for(let i=0;i<=4;i++){const t=i/4,y=335-t*285,x=65+t*580;
   svg.append(svgEl('line',{x1:65,x2:645,y1:y,y2:y,stroke:'#e0e9e3'}));
   svg.append(svgEl('text',{x:55,y:y+4,'text-anchor':'end'},compact(maxY*t)));
   svg.append(svgEl('text',{x,y:359,'text-anchor':'middle'},compact(maxX*t)));
  }
  for(const item of p.items){
   const dot=svgEl('circle',{cx:65+item.amount/maxX*580,cy:335-item.impressions/maxY*285,r:4.5,fill:'#26745a','fill-opacity':.65,stroke:'#fff','stroke-width':.7,tabindex:0});
   const text=item.address+' · '+money(item.amount)+' · '+num(item.impressions)+' Impression';
   dot.append(svgEl('title',{},text));dot.setAttribute('aria-label',text);
   dot.addEventListener('mouseenter',()=>$('#chart-note').textContent=text);dot.addEventListener('focus',()=>$('#chart-note').textContent=text);
   svg.append(dot);
  }
  svg.append(svgEl('text',{x:355,y:392,'text-anchor':'middle'},'Campaign investment (USD)'));
  $('#chart-note').textContent='Shared axes across all four plans. Hover or focus a point to inspect its allocation.';
 }
 render(data.plans[0]);
}).catch(()=>{$('#strategy-description').textContent='Report data could not be loaded. Please refresh the page.'});
document.querySelectorAll('[data-gallery]').forEach(b=>b.setAttribute('aria-pressed',String(b.classList.contains('active'))));
