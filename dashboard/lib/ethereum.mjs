import { gatewayBase } from './gateway.mjs';
import { summarize } from './analytics.mjs';
import { validEthAddress } from './chains.mjs';

// Keep base-unit integers as strings for lossless exports. Only chart/EDA
// values are converted to floating point ETH or gwei.
const wei=v=>typeof v==='string'&&/^\d{1,78}$/.test(v)?BigInt(v):null;
const units=(v,divisor)=>v===null?null:Number(v)/divisor;
const count=v=>typeof v==='string'&&/^\d+$/.test(v)&&Number.isSafeInteger(Number(v))?Number(v):null;
const safeTime=v=>Number.isSafeInteger(v)&&v>0&&v<8640000000000;
export function normalizeEthereum(raw,address){
  if(!raw||typeof raw.address!=='string'||raw.address.toLowerCase()!==address.toLowerCase()||wei(raw.balance)===null||!Array.isArray(raw.transactions))throw new Error('Unexpected response: Ethereum address schema changed.');
  const target=address.toLowerCase(),seen=new Set(),rows=[];
  let invalid=0,duplicates=0,missing=0,excludedInternal=0;
  for(const tx of raw.transactions){
    // The live wallet response mixes external transactions with internal calls.
    // Filter calls before hash deduplication so they cannot replace the parent.
    if(tx?.type==='INTERNAL'){excludedInternal++;continue;}
    if(tx?.type!=='EXTERNAL'){invalid++;continue;}
    if(!tx||typeof tx.hash!=='string'||!/^0x[0-9a-fA-F]{64}$/.test(tx.hash)){invalid++;continue;}
    const hash=tx.hash.toLowerCase();if(seen.has(hash)){duplicates++;continue;}seen.add(hash);
    const value=wei(tx.value),fee=wei(tx.fee),gasPrice=wei(tx.gasPrice);
    const from=validEthAddress(tx.from)?tx.from.toLowerCase():null,to=validEthAddress(tx.to)?tx.to.toLowerCase():null;
    // External value transfers only. Reverted execution transfers no ETH.
    // Missing execution status cannot be treated as a successful transfer.
    let incoming=null,outgoing=null;
    if(tx.success===false){incoming=BigInt(0);outgoing=BigInt(0);}
    else if(tx.success===true&&value!==null&&from&&(to||tx.to===null)){
      incoming=to===target?value:BigInt(0);outgoing=from===target?value:BigInt(0);
    }
    const net=incoming===null||outgoing===null?null:incoming-outgoing;
    const timestamp=safeTime(tx.timestamp)?tx.timestamp:null;
    const gasUsed=Number.isSafeInteger(tx.gasUsed)&&tx.gasUsed>0?tx.gasUsed:null;
    const confirmed=Number.isSafeInteger(tx.blockNumber)&&tx.blockNumber>0?true:['PENDING','MEMPOOL','UNCONFIRMED'].includes(tx.state)?false:null;
    if(timestamp===null||net===null||fee===null||gasUsed===null)missing++;
    rows.push({hash,timestamp,incoming:units(incoming,1e18),outgoing:units(outgoing,1e18),net:units(net,1e18),fee:units(fee,1e9),size:gasUsed,vbytes:null,feeRate:units(gasPrice,1e9),confirmed,blockHeight:confirmed?tx.blockNumber:null,success:typeof tx.success==='boolean'?tx.success:null,
      exact:{incoming:incoming?.toString()??null,outgoing:outgoing?.toString()??null,net:net?.toString()??null,fee:fee?.toString()??null,gasPrice:gasPrice?.toString()??null}});
  }
  return {
    summary:{confirmed:units(wei(raw.balance),1e18),unconfirmed:null,utxo:null,txCount:count(raw.transactionCount),received:units(wei(raw.totalReceived),1e18),nonce:count(raw.nonce),balanceWei:raw.balance,totalReceivedWei:wei(raw.totalReceived)?.toString()??null},
    transactions:{rows,quality:{received:raw.transactions.length,valid:rows.length,invalid,duplicates,missing,excludedInternal},feeStats:summarize(rows.flatMap((r,i)=>r.fee===null?[]:[{x:i,y:r.fee}])),schema:Object.entries(raw.transactions[0]??{}).map(([field,v])=>({field,type:Array.isArray(v)?'array':v===null?'null':typeof v}))}
  };
}

export function ethereumCSV(rows){
  const header='tx_hash,timestamp_utc,incoming_wei,outgoing_wei,net_wei,fee_wei,gas_used,gas_price_wei,confirmed,success';
  return [header,...rows.map(t=>[t.hash,t.timestamp?new Date(t.timestamp*1000).toISOString():'',t.exact.incoming??'',t.exact.outgoing??'',t.exact.net??'',t.exact.fee??'',t.size??'',t.exact.gasPrice??'',t.confirmed??'',t.success??''].join(','))].join('\n');
}

export async function fetchEthereumAddress(address,offset,config,fetcher=fetch){
  if(!validEthAddress(address))throw new Error('Invalid Ethereum address format.');
  const base=gatewayBase(config.base),headers={'Content-Type':'application/json','Accept':'application/json'};
  if(config.key)headers['X-Explorer-Auth-Key']=config.key;
  const result={chain:'eth',address,offset,limit:50,fetchedAt:new Date().toISOString(),authenticated:Boolean(config.key),source:base,summary:null,transactions:null,errors:[]};
  try{
    const res=await fetcher(`${base}/eth/address`,{method:'POST',headers,redirect:'manual',body:JSON.stringify({network:'ETH',address,page:offset/50,size:50}),signal:AbortSignal.timeout(20000)});
    if(!res.ok)throw new Error(res.status===429?'Provider rate limit reached. Try again in a minute.':res.status===401||res.status===403?'Explorer API key rejected or insufficient Ethereum access.':`Provider request failed (HTTP ${res.status}).`);
    const text=await res.text();if(text.length>8000000)throw new Error('Provider response is too large.');
    let raw;try{raw=JSON.parse(text);}catch{throw new Error('Provider returned invalid JSON.');}
    return {...result,...normalizeEthereum(raw,address),fetchedAt:new Date().toISOString()};
  }catch(e){return {...result,errors:[{part:'address',message:e?.name==='TimeoutError'?'Provider request timed out.':e instanceof Error&&/^(Provider|Explorer|Unexpected)/.test(e.message)?e.message:'Unable to reach the provider.'}]};}
}
