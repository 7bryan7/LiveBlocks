import { METRICS, normalizeChart } from './analytics.mjs';
export const BASE_URL = 'https://api.blockchain.info/explorer-gateway-kt';
export const RANGES = [7,30,90,365];
export function gatewayBase(value=BASE_URL) {
  const url=new URL(value || BASE_URL);
  if(url.protocol!=='https:' || url.hostname!=='api.blockchain.info' || url.port || url.username || url.password || url.search || url.hash || url.pathname.replace(/\/$/,'')!=='/explorer-gateway-kt') throw new Error('Use the Blockchain.com Explorer Gateway HTTPS base URL.');
  return url.href.replace(/\/$/,'');
}
export async function fetchMetric(metric, days, config, fetcher=fetch) {
  const base=gatewayBase(config.base);
  const headers={'Content-Type':'application/json','Accept':'application/json'};
  if(config.key) headers['X-Explorer-Auth-Key']=config.key;
  const response=await fetcher(`${base}/charts/${metric.id}`,{
    method:'POST',headers,redirect:'manual',signal:AbortSignal.timeout(15000),
    body:JSON.stringify({timespan:`${days}days`,sampled:false,metadata:true,rollingAverage:'24h',cors:false,format:'json'})
  });
  if(!response.ok){
    const messages={401:'API key was not accepted.',403:'Access denied. Check your Explorer API key and plan.',429:'Provider rate limit reached. Retry after a minute.'};
    throw new Error(messages[response.status] || `Provider request failed (HTTP ${response.status}).`);
  }
  const text=await response.text();
  if(text.length>2000000) throw new Error('Provider response exceeded the supported size.');
  let raw;
  try{raw=JSON.parse(text);}catch{throw new Error('Provider returned a non-JSON response.');}
  return normalizeChart(raw,metric);
}
export async function fetchSnapshot(days, config, fetcher=fetch) {
  if(!RANGES.includes(days)) throw new Error('Unsupported time range.');
  gatewayBase(config.base);
  const settled=await Promise.allSettled(METRICS.map(m=>fetchMetric(m,days,config,fetcher)));
  const series=[],errors=[];
  settled.forEach((r,i)=>{
    if(r.status==='fulfilled') series.push(r.value);
    else errors.push({id:METRICS[i].id,message:r.reason?.name==='TimeoutError'?'Provider request timed out.':r.reason instanceof Error && /^(Provider|API key|Access denied|Unexpected response|The provider)/.test(r.reason.message)?r.reason.message:'Unable to reach the provider.'});
  });
  return {fetchedAt:new Date().toISOString(),days,source:gatewayBase(config.base),authenticated:Boolean(config.key),series,errors};
}
