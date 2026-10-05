export const METRICS = [
  { id: 'market-price', name: 'Bitcoin price', short: 'Price', unit: 'USD', color: '#4acda5' },
  { id: 'n-transactions', name: 'Daily transactions', short: 'Transactions', unit: 'transactions', color: '#7798ff' },
  { id: 'hash-rate', name: 'Network hash rate', short: 'Hash rate', unit: 'TH/s', color: '#b199f4' },
  { id: 'transaction-fees-usd', name: 'Network fees', short: 'Fees', unit: 'USD', color: '#e2b26a' },
];

export function quantile(sorted, q) {
  if (!sorted.length) return null;
  const pos = (sorted.length - 1) * q, lo = Math.floor(pos), hi = Math.ceil(pos);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
}

export function summarize(points) {
  const values = points.map(p => p.y).filter(Number.isFinite).sort((a,b) => a-b);
  const n = values.length;
  if (!n) return { count: 0, mean: null, median: null, min: null, max: null, std: null, q1: null, q3: null, lower: null, upper: null, outliers: 0, change: null };
  const mean = values.reduce((a,b) => a+b, 0)/n;
  const q1 = quantile(values, .25), q3 = quantile(values, .75), iqr = q3-q1;
  const lower = q1-1.5*iqr, upper = q3+1.5*iqr;
  const first = points[0]?.y, last = points.at(-1)?.y;
  return { count: n, mean, median: quantile(values,.5), min: values[0], max: values.at(-1), q1, q3, lower, upper,
    std: n > 1 ? Math.sqrt(values.reduce((s,v) => s+(v-mean)**2,0)/(n-1)) : null,
    outliers: values.filter(v => v<lower || v>upper).length,
    change: first !== 0 && Number.isFinite(first) && Number.isFinite(last) ? (last-first)/Math.abs(first)*100 : null };
}

export function normalizeChart(raw, metric) {
  if (!raw || typeof raw !== 'object' || !Array.isArray(raw.values)) throw new Error('Unexpected response: expected a values array.');
  if (raw.status && raw.status !== 'ok') throw new Error('The provider returned an unsuccessful chart status.');
  let missing=0, invalid=0, duplicates=0;
  const byTime=new Map();
  for (const p of raw.values) {
    if (!p || p.x == null || p.y == null) { missing++; continue; }
    if (typeof p.x !== 'number' || typeof p.y !== 'number' || !Number.isFinite(p.x) || !Number.isFinite(p.y) || p.x <= 0 || p.x > 8640000000000) { invalid++; continue; }
    if (byTime.has(p.x)) duplicates++;
    byTime.set(p.x, {x:p.x,y:p.y});
  }
  const values=[...byTime.values()].sort((a,b)=>a.x-b.x);
  const stats=summarize(values);
  const gaps=values.slice(1).reduce((s,p,i)=>s+Math.max(0,Math.round((p.x-values[i].x)/86400)-1),0);
  const schema=Object.entries(raw).map(([field,v])=>({field,type:Array.isArray(v)?'array':v===null?'null':typeof v}));
  return {...metric,unit:typeof raw.unit==='string'?raw.unit:metric.unit,period:typeof raw.period==='string'?raw.period:'unknown',description:typeof raw.description==='string'?raw.description:'',values,stats,
    quality:{received:raw.values.length,valid:values.length,missing,invalid,duplicates,gaps},schema};
}

export function rollingMean(points, window=7) {
  return points.map((p,i)=>{
    const group=points.slice(Math.max(0,i-window+1),i+1);
    const complete=group.length===window && group.every((v,j)=>j===0 || v.x-group[j-1].x===86400);
    return {...p,average:complete?group.reduce((s,v)=>s+v.y,0)/window:null};
  });
}

export function histogram(points, count=10) {
  const values=points.map(p=>p.y).filter(Number.isFinite);
  if (!values.length) return [];
  const min=Math.min(...values), max=Math.max(...values);
  if (min===max) return [{lo:min,hi:max,count:values.length}];
  const width=(max-min)/count;
  const bins=Array.from({length:count},(_,i)=>({lo:min+i*width,hi:min+(i+1)*width,count:0}));
  for (const v of values) bins[Math.min(count-1,Math.floor((v-min)/width))].count++;
  return bins;
}

export function correlate(a,b) {
  const index=new Map(b.map(p=>[p.x,p.y]));
  const pairs=a.filter(p=>index.has(p.x)).map(p=>({x:p.y,y:index.get(p.x),timestamp:p.x}));
  if (pairs.length<3) return {r:null,count:pairs.length,pairs};
  const mx=pairs.reduce((s,p)=>s+p.x,0)/pairs.length, my=pairs.reduce((s,p)=>s+p.y,0)/pairs.length;
  let cross=0,xx=0,yy=0;
  for(const p of pairs){cross+=(p.x-mx)*(p.y-my);xx+=(p.x-mx)**2;yy+=(p.y-my)**2;}
  return {r:xx&&yy?Math.max(-1,Math.min(1,cross/Math.sqrt(xx*yy))):null,count:pairs.length,pairs};
}

export function csvFor(series) {
  const quote=v=>'"'+String(v??'').replaceAll('"','""')+'"';
  return ['timestamp_utc,metric,value,unit',...series.flatMap(s=>s.values.map(p=>[new Date(p.x*1000).toISOString(),s.id,p.y,s.unit].map(quote).join(',')))].join('\n');
}
