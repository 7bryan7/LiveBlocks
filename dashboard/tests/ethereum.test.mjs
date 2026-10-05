import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeEthereum,fetchEthereumAddress,ethereumCSV } from '../lib/ethereum.mjs';
import { DEFAULT_ETH_ADDRESS,validEthAddress } from '../lib/chains.mjs';
const target=DEFAULT_ETH_ADDRESS,other='0x'+'1'.repeat(40);
const tx=(overrides={})=>({hash:'0x'+'a'.repeat(64),type:'EXTERNAL',from:other,to:target.toLowerCase(),value:'1000000000000000001',fee:'21000000000000',gasUsed:21000,gasPrice:'1000000000',timestamp:1700000000,blockNumber:18000000,success:true,...overrides});
const response=(transactions=[tx()],overrides={})=>({address:target,balance:'1234567890123456789012345',nonce:'4',transactionCount:'99',totalReceived:'4560000000000000000',transactions,page:0,...overrides});

test('Ethereum accepts hexadecimal mainnet address syntax and rejects Bitcoin/test-format input',()=>{
 assert.equal(validEthAddress(target),true);assert.equal(validEthAddress(target.toLowerCase()),true);assert.equal(validEthAddress('bc1qq8dxdalmj3f89v5xm5f3y70sec9s0fa7qpesl7'),false);assert.equal(validEthAddress('0x123'),false);
});
test('Ethereum retains exact wei while using ETH/gwei/gas for analysis',()=>{
 const d=normalizeEthereum(response(),target),r=d.transactions.rows[0];
 assert.equal(d.summary.balanceWei,'1234567890123456789012345');assert.equal(d.summary.nonce,4);assert.equal(d.summary.unconfirmed,null);assert.equal(r.exact.incoming,'1000000000000000001');assert.equal(r.exact.net,'1000000000000000001');assert.equal(r.incoming,1);assert.equal(r.fee,21000);assert.equal(r.feeRate,1);assert.equal(r.size,21000);assert.equal(r.confirmed,true);assert.equal(d.transactions.quality.missing,0);
 assert.match(ethereumCSV(d.transactions.rows),/incoming_wei/);assert.match(ethereumCSV(d.transactions.rows),/1000000000000000001/);assert.match(ethereumCSV(d.transactions.rows),/21000000000000,21000,1000000000/);
});
test('Ethereum self-transfers net to zero and failed calls transfer zero but retain fees',()=>{
 const self=normalizeEthereum(response([tx({from:target,to:target.toLowerCase()})]),target).transactions.rows[0];assert.equal(self.net,0);
 const failed=normalizeEthereum(response([tx({from:target,to:other,success:false})]),target).transactions.rows[0];assert.equal(failed.net,0);assert.equal(failed.fee,21000);assert.equal(failed.success,false);
 const creation=normalizeEthereum(response([tx({from:target,to:null})]),target).transactions.rows[0];assert.equal(creation.net,-1);assert.equal(creation.exact.net,'-1000000000000000001');
});
test('Missing fields remain unknown; malformed hashes and duplicate records are reported',()=>{
 const d=normalizeEthereum(response([tx({success:null,fee:null,gasUsed:null,timestamp:null}),tx(),tx({hash:'bad'})]),target);
 assert.deepEqual(d.transactions.quality,{received:3,valid:1,invalid:1,duplicates:1,missing:1,excludedInternal:0});assert.equal(d.transactions.rows[0].net,null);assert.equal(d.transactions.rows[0].fee,null);assert.equal(d.transactions.feeStats.count,0);
 assert.throws(()=>normalizeEthereum(response([],{balance:123}),target),/schema changed/);assert.throws(()=>normalizeEthereum(response([],{address:other}),target),/schema changed/);
 assert.equal(normalizeEthereum(response([],{transactionCount:null,totalReceived:null}),target).summary.txCount,null);
});
test('Ethereum request uses the authenticated address route and translates offsets into pages',async()=>{
 let request;const result=await fetchEthereumAddress(target,50,{key:'test-only-key'},async(url,options)=>{request={url,options};return Response.json(response());});
 assert.ok(request.url.endsWith('/eth/address'));assert.equal(request.options.headers['X-Explorer-Auth-Key'],'test-only-key');assert.equal(request.options.redirect,'manual');assert.deepEqual(JSON.parse(request.options.body),{network:'ETH',address:target,page:1,size:50});assert.equal(result.chain,'eth');assert.equal(result.offset,50);assert.equal(result.errors.length,0);assert.ok(!JSON.stringify(result).includes('test-only-key'));
});
test('Ethereum errors never fall back to Bitcoin or fabricate data',async()=>{
 let calls=0;const r=await fetchEthereumAddress(target,0,{},async()=>{calls++;return new Response('',{status:403});});assert.equal(calls,1);assert.equal(r.summary,null);assert.equal(r.transactions,null);assert.match(r.errors[0].message,/Ethereum access/);
});
test('Internal calls do not replace external parents or duplicate their value and fees',()=>{
 const d=normalizeEthereum(response([tx({type:'INTERNAL',fee:null}),tx()]),target);
 assert.equal(d.transactions.quality.excludedInternal,1);assert.equal(d.transactions.quality.duplicates,0);assert.equal(d.transactions.rows.length,1);assert.equal(d.transactions.rows[0].exact.fee,'21000000000000');
});
