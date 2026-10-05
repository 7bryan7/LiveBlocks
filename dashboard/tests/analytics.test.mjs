import test from 'node:test';
import assert from 'node:assert/strict';
import {summarize,quantile,normalizeChart,histogram,correlate,rollingMean,csvFor,METRICS} from '../lib/analytics.mjs';
import {fetchSnapshot,gatewayBase} from '../lib/gateway.mjs';
import {normalizeAddress,normalizeTransactions,fetchAddress,DEFAULT_ADDRESS} from '../lib/address.mjs';
const points=values=>values.map((y,i)=>({x:(i+1)*86400,y}));
const tx=(overrides={})=>({txId:'a'.repeat(64),time:1700000000,mempool:false,fee:100,size:200,weight:401,inputs:[{address:DEFAULT_ADDRESS,value:1000}],outputs:[{address:DEFAULT_ADDRESS,value:250},{address:'other',value:650}],...overrides});

test('summary uses sample variance, interpolated quartiles, and undefined single-point deviation',()=>{
 const s=summarize(points([1,2,3,4]));assert.equal(s.mean,2.5);assert.equal(s.median,2.5);assert.equal(s.q1,1.75);assert.equal(s.q3,3.25);assert.ok(Math.abs(s.std-Math.sqrt(5/3))<1e-10);assert.equal(summarize(points([0])).std,null);assert.equal(summarize(points([0,2])).change,null);assert.equal(summarize([]).count,0);assert.equal(quantile([],0.5),null);
});
test('IQR detects a large value without deleting it',()=>{const s=summarize(points([1,2,2,3,100]));assert.equal(s.outliers,1);assert.equal(s.count,5);assert.equal(s.max,100);});
test('normalization excludes missing/nonfinite values, deduplicates, and sorts',()=>{
 const s=normalizeChart({status:'ok',unit:'USD',values:[{x:86400,y:1},{x:259200,y:3},{x:86400,y:5},{x:172800,y:null},{x:NaN,y:4},{x:345600,y:'6'}]},METRICS[0]);
 assert.deepEqual(s.values,[{x:86400,y:5},{x:259200,y:3}]);assert.deepEqual(s.quality,{received:6,valid:2,missing:1,invalid:2,duplicates:1,gaps:1});assert.throws(()=>normalizeChart({data:[]},METRICS[0]),/Unexpected/);
});
test('histogram includes every value exactly once, including upper edge and constant data',()=>{
 assert.equal(histogram(points([1,2,3,4,5]),4).reduce((s,b)=>s+b.count,0),5);assert.equal(histogram(points([2,2,2])).length,1);assert.equal(histogram(points([2,2,2]))[0].count,3);assert.deepEqual(histogram([]),[]);
});
test('Pearson pairs by timestamp and rejects constant or insufficient data',()=>{
 const a=points([1,2,3,4]),b=points([8,6,4,2]).slice(1);assert.equal(correlate(a,b).r,-1);assert.equal(correlate(a,b).count,3);assert.equal(correlate(a,points([2,2,2,2])).r,null);assert.equal(correlate(a,b.slice(0,2)).r,null);
});
test('rolling mean never bridges a missing day or partial window',()=>{
 const a=points([1,2,3,4,5,6,7,8]);assert.equal(rollingMean(a)[5].average,null);assert.equal(rollingMean(a)[6].average,4);assert.equal(rollingMean(a.filter((_,i)=>i!==3)).at(-1).average,null);
});
test('CSV exports UTC, units, and cleaned series',()=>{const csv=csvFor([{id:'price',unit:'USD',values:[{x:86400,y:12}]}]);assert.match(csv,/1970-01-02T00:00:00.000Z/);assert.match(csv,/"price","12","USD"/);});
test('gateway allows only the intended HTTPS host and path',()=>{assert.equal(gatewayBase(), 'https://api.blockchain.info/explorer-gateway-kt');for(const s of ['http://api.blockchain.info/explorer-gateway-kt','https://evil.test/explorer-gateway-kt','https://api.blockchain.info:444/explorer-gateway-kt','https://api.blockchain.info/other'])assert.throws(()=>gatewayBase(s));});
test('network request uses correct auth and required options; partial errors retain successful series',async()=>{
 const seen=[];const d=await fetchSnapshot(30,{key:'test-only-key'},async(url,options)=>{seen.push({url,options});if(url.endsWith('hash-rate'))return new Response('',{status:429});return Response.json({status:'ok',values:points([1,2,3]),unit:'USD'});});
 assert.equal(d.series.length,3);assert.equal(d.errors.length,1);assert.equal(d.authenticated,true);assert.equal(seen[0].options.headers['X-Explorer-Auth-Key'],'test-only-key');assert.equal(seen[0].options.redirect,'manual');assert.deepEqual(JSON.parse(seen[0].options.body),{timespan:'30days',sampled:false,metadata:true,rollingAverage:'24h',cors:false,format:'json'});assert.ok(!JSON.stringify(d).includes('test-only-key'));await assert.rejects(()=>fetchSnapshot(12,{}));
});
test('address summary rejects schema drift and precision loss',()=>{const s={address:DEFAULT_ADDRESS,confirmed:10,unconfirmed:-1,utxo:2,txCount:3,received:12};assert.equal(normalizeAddress(s,DEFAULT_ADDRESS).unconfirmed,-1);assert.throws(()=>normalizeAddress({...s,confirmed:Number.MAX_SAFE_INTEGER+1},DEFAULT_ADDRESS));assert.throws(()=>normalizeAddress({...s,address:'wrong'},DEFAULT_ADDRESS));});
test('flows preserve satoshi; fee rate uses rounded virtual bytes, not raw bytes',()=>{
 const d=normalizeTransactions({transactions:[tx()]},DEFAULT_ADDRESS),t=d.rows[0];assert.equal(t.incoming,250);assert.equal(t.outgoing,1000);assert.equal(t.net,-750);assert.equal(t.vbytes,101);assert.equal(t.feeRate,100/101);assert.equal(d.quality.missing,0);
});
test('zero-value unaddressed outputs are harmless; positive unknown outputs remain missing',()=>{
 const a=normalizeTransactions({transactions:[tx({outputs:[{address:DEFAULT_ADDRESS,value:4},{address:null,value:0,pkscript:'6a'}]})]},DEFAULT_ADDRESS);assert.equal(a.rows[0].incoming,4);
 const b=normalizeTransactions({transactions:[tx({outputs:[{address:null,value:10}]})]},DEFAULT_ADDRESS);assert.equal(b.rows[0].net,null);assert.equal(b.quality.missing,1);
});
test('unsafe amounts, missing weights, duplicates, deleted transactions, and absent times are explicit',()=>{
 const d=normalizeTransactions({transactions:[tx({time:null,fee:null,weight:null,outputs:[{address:DEFAULT_ADDRESS,value:Number.MAX_SAFE_INTEGER+1}]}),tx(),tx({txId:'b'.repeat(64),deleted:true}),{txId:'malformed'}]},DEFAULT_ADDRESS);
 assert.equal(d.quality.duplicates,1);assert.equal(d.quality.invalid,2);assert.equal(d.rows[0].timestamp,null);assert.equal(d.rows[0].net,null);assert.equal(d.rows[0].feeRate,null);assert.equal(d.feeStats.count,0);assert.throws(()=>normalizeTransactions({},DEFAULT_ADDRESS));
});
test('address requests follow supplied contract and tolerate unavailable transaction page',async()=>{
 const requests=[];const d=await fetchAddress(DEFAULT_ADDRESS,50,{key:'test-only-secret'},async(url,options)=>{requests.push({url,options});return url.endsWith('/transactions')?new Response('',{status:403}):Response.json({address:DEFAULT_ADDRESS,confirmed:0,unconfirmed:0,utxo:0,txCount:70,received:0});});
 assert.equal(d.summary.txCount,70);assert.equal(d.transactions,null);assert.equal(d.errors[0].part,'transactions');assert.deepEqual(JSON.parse(requests[0].options.body),{network:'BTC',address:DEFAULT_ADDRESS,page:0});assert.deepEqual(JSON.parse(requests[1].options.body),{address:DEFAULT_ADDRESS,limit:50,offset:50});assert.ok(!JSON.stringify(d).includes('test-only-secret'));
});
