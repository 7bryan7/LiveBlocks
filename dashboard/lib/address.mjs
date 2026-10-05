import { gatewayBase } from './gateway.mjs';
import { summarize } from './analytics.mjs';
export const DEFAULT_ADDRESS='bc1qq8dxdalmj3f89v5xm5f3y70sec9s0fa7qpesl7';
export const PAGE_SIZE=50;
const safeAmount=v=>Number.isSafeInteger(v)&&v>=0;
export function validAddress(address){return typeof address==='string'&&/^(bc1[a-z0-9]{20,87}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})$/.test(address);}
export function normalizeAddress(raw,address){
  if(!raw || raw.address!==address || !['confirmed','unconfirmed','utxo','txCount','received'].every(k=>Number.isSafeInteger(raw[k])))throw new Error('Unexpected response: address summary schema changed.');
  if(['confirmed','utxo','txCount','received'].some(k=>raw[k]<0))throw new Error('Unexpected response: invalid address summary values.');
  return Object.fromEntries(['address','confirmed','unconfirmed','utxo','txCount','received'].map(k=>[k,raw[k]]));
}
export function normalizeTransactions(raw,address){
  if(!raw||!Array.isArray(raw.transactions))throw new Error('Unexpected response: transactions array missing.');
  const seen=new Set(), rows=[];
  let invalid=0,duplicates=0,missing=0;
  for(const tx of raw.transactions){
    if(!tx||typeof tx.txId!=='string'||!/^[a-fA-F0-9]{64}$/.test(tx.txId)||tx.deleted===true){invalid++;continue;}
    if(seen.has(tx.txId)){duplicates++;continue;}seen.add(tx.txId);
    const validTime=t=>Number.isSafeInteger(t)&&t>0&&t<8640000000000;
    const timestamp=validTime(tx.time)?tx.time:validTime(tx.mempoolTime)?tx.mempoolTime:null;
    function total(items){
      if(!Array.isArray(items))return null;
      // A missing address could belong to the target; don't invent a zero flow.
      // Zero-value outputs (e.g. OP_RETURN) cannot alter an address amount.
      if(items.some(i=>!i||(!i.coinbase&&typeof i.address!=='string'&&i.value!==0)))return null;
      const matching=items.filter(i=>i.address===address);
      if(matching.some(i=>!safeAmount(i.value)))return null;
      const sum=matching.reduce((s,i)=>s+i.value,0);return Number.isSafeInteger(sum)?sum:null;
    }
    const incoming=total(tx.outputs),outgoing=total(tx.inputs);
    const net=incoming==null||outgoing==null?null:incoming-outgoing;
    const fee=safeAmount(tx.fee)?tx.fee:null,size=safeAmount(tx.size)&&tx.size>0?tx.size:null;
    const vbytes=safeAmount(tx.weight)&&tx.weight>0?Math.ceil(tx.weight/4):null;
    if(timestamp==null||net==null||fee==null||size==null)missing++;
    rows.push({hash:tx.txId,timestamp,incoming,outgoing,net,fee,size,vbytes,feeRate:fee!=null&&vbytes?fee/vbytes:null,confirmed:typeof tx.mempool==='boolean'?!tx.mempool:null,blockHeight:Number.isSafeInteger(tx.blockHeight)?tx.blockHeight:null});
  }
  const fees=rows.filter(r=>r.fee!==null).map((r,i)=>({x:i,y:r.fee}));
  return {rows,quality:{received:raw.transactions.length,valid:rows.length,invalid,duplicates,missing},feeStats:summarize(fees),schema:Object.entries(raw.transactions[0]??{}).map(([field,v])=>({field,type:Array.isArray(v)?'array':v===null?'null':typeof v}))};
}
export async function fetchAddress(address,offset,config,fetcher=fetch){
  if(!validAddress(address))throw new Error('Invalid Bitcoin address format.');
  const base=gatewayBase(config.base),headers={'Content-Type':'application/json','Accept':'application/json'};
  if(config.key)headers['X-Explorer-Auth-Key']=config.key;
  async function post(path,body){
    const res=await fetcher(base+path,{method:'POST',headers,redirect:'manual',body:JSON.stringify(body),signal:AbortSignal.timeout(20000)});
    if(!res.ok)throw new Error(res.status===429?'Provider rate limit reached. Try again in a minute.':res.status===401||res.status===403?'Explorer API key rejected or insufficient access.':`Provider request failed (HTTP ${res.status}).`);
    const text=await res.text();if(text.length>8000000)throw new Error('Provider response is too large.');
    try{return JSON.parse(text);}catch{throw new Error('Provider returned invalid JSON.');}
  }
  const [summary,transactions]=await Promise.allSettled([
    post('/btc/address',{network:'BTC',address,page:0}).then(r=>normalizeAddress(r,address)),
    post('/btc/address/transactions',{address,limit:PAGE_SIZE,offset}).then(r=>normalizeTransactions(r,address))
  ]);
  function message(r){return r.reason?.name==='TimeoutError'?'Provider request timed out.':r.reason instanceof Error&&/^(Provider|Explorer|Unexpected)/.test(r.reason.message)?r.reason.message:'Unable to reach the provider.';}
  return {address,offset,limit:PAGE_SIZE,fetchedAt:new Date().toISOString(),authenticated:Boolean(config.key),source:base,
    summary:summary.status==='fulfilled'?summary.value:null,
    transactions:transactions.status==='fulfilled'?transactions.value:null,
    errors:[...(summary.status==='rejected'?[{part:'summary',message:message(summary)}]:[]),...(transactions.status==='rejected'?[{part:'transactions',message:message(transactions)}]:[])]};
}
