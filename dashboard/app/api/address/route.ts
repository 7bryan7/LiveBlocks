import { env } from 'cloudflare:workers';
import { fetchAddress, validAddress } from '@/lib/address.mjs';
type Data=Awaited<ReturnType<typeof fetchAddress>>;
const cache=new Map<string,{at:number;data:Data}>();
const pending=new Map<string,Promise<Data>>();
export async function GET(request:Request){
  const params=new URL(request.url).searchParams,address=params.get('address')??'',offset=Number(params.get('offset')??0);
  if(!validAddress(address)||!Number.isSafeInteger(offset)||offset<0||offset>10000000||offset%50!==0)return Response.json({error:'Enter a valid Bitcoin address and a page offset in multiples of 50.'},{status:400});
  const vars=env as unknown as Record<string,string|undefined>;
  const config={base:vars.BLOCKCHAIN_API_BASE_URL,key:vars.BLOCKCHAIN_API_KEY?.trim()};
  const key=JSON.stringify([address,offset,config.base,config.key]),saved=cache.get(key);
  if(saved&&Date.now()-saved.at<60000)return Response.json(saved.data,{headers:{'Cache-Control':'no-store'}});
  if(pending.size>=12&&!pending.has(key))return Response.json({error:'Too many requests. Try again shortly.'},{status:429});
  try{
    let work=pending.get(key);
    if(!work){work=fetchAddress(address,offset,config).then(data=>{if(cache.size>=30)cache.delete(cache.keys().next().value!);cache.set(key,{at:Date.now(),data});return data;}).finally(()=>pending.delete(key));pending.set(key,work);}
    return Response.json(await work,{headers:{'Cache-Control':'no-store'}});
  }catch{return Response.json({error:'Unable to load the configured gateway.'},{status:502});}
}
