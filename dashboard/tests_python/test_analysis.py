import csv
import io
import json
import math
import unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from python_backend.analytics import summarize, histogram, correlate, rolling_mean
from python_backend.adapters import (METRICS, MAX_SAFE, DEFAULT_ADDRESS as BTC, DEFAULT_ETH_ADDRESS as ETH,
    normalize_address, normalize_transactions, normalize_ethereum, normalize_chart, valid_address)
from python_backend.exports import address_csv, network_csv, fee_report
from python_backend.gateway import gateway_base, fetch_address, fetch_snapshot, post
from python_backend import server


def points(values): return [dict(x=(i+1)*86400,y=v) for i,v in enumerate(values)]
def btc_tx(**kw): return dict(dict(txId='a'*64,time=1700000000,mempool=False,fee=100,size=200,weight=401,inputs=[dict(address=BTC,value=1000)],outputs=[dict(address=BTC,value=250),dict(address='other',value=650)]),**kw)
def eth_tx(**kw): return dict(dict(hash='0x'+'a'*64,type='EXTERNAL',**{'from':'0x'+'1'*40},to=ETH.lower(),value='1000000000000000001',fee='21000000000000',gasUsed=21000,gasPrice='1000000000',timestamp=1700000000,blockNumber=18000000,success=True),**kw)
def eth_raw(txs=None,**kw): return dict(dict(address=ETH,balance='1234567890123456789012345',nonce='4',transactionCount='99',totalReceived='4560000000000000000',transactions=[eth_tx()] if txs is None else txs),**kw)
def summary(): return dict(address=BTC,confirmed=10,unconfirmed=-1,utxo=2,txCount=70,received=12)


class AnalysisTests(unittest.TestCase):
    def test_statistics_and_empty(self):
        s=summarize(points([1,2,3,4]))
        self.assertEqual((s['mean'],s['median'],s['q1'],s['q3']),(2.5,2.5,1.75,3.25))
        self.assertAlmostEqual(s['std'],math.sqrt(5/3))
        self.assertIsNone(summarize(points([0]))['std'])
        self.assertIsNone(summarize(points([0,2]))['change'])
        self.assertEqual(summarize([])['count'],0)
        self.assertEqual(summarize(points([False,None,float('nan'),4]))['count'],1)

    def test_outliers(self):
        s=summarize(points([1,2,2,3,100]))
        self.assertEqual((s['count'],s['outliers'],s['max']),(5,1,100))

    def test_histogram_edges(self):
        bins=histogram(points([1,2,3,4,5]),4)
        self.assertEqual([b['count'] for b in bins],[1,1,1,2])
        self.assertEqual(histogram(points([2,2,2])),[dict(lo=2,hi=2,count=3)])
        self.assertEqual(histogram([]),[])

    def test_correlation(self):
        a,b=points([1,2,3,4]),points([8,6,4,2])[1:]
        self.assertAlmostEqual(correlate(a,b)['r'],-1)
        self.assertEqual(correlate(a,b)['count'],3)
        self.assertIsNone(correlate(a,points([2,2,2,2]))['r'])
        self.assertIsNone(correlate(a,b[:2])['r'])

    def test_rolling_gaps(self):
        data=points(list(range(1,9)))
        self.assertIsNone(rolling_mean(data)[5]['average'])
        self.assertEqual(rolling_mean(data)[6]['average'],4)
        self.assertIsNone(rolling_mean(data[:3]+data[4:])[-1]['average'])

    def test_network_cleaning(self):
        result=normalize_chart(dict(status='ok',values=[dict(x=86400,y=1),dict(x=259200,y=3),dict(x=86400,y=5),dict(x=172800,y=None),dict(x=float('nan'),y=4),dict(x=345600,y='6')]),METRICS[0])
        self.assertEqual(result['values'],[dict(x=86400,y=5),dict(x=259200,y=3)])
        self.assertEqual(result['quality'],dict(received=6,valid=2,missing=1,invalid=2,duplicates=1,gaps=1))
        with self.assertRaises(ValueError): normalize_chart(dict(data=[]),METRICS[0])

    def test_summary_precision_and_boolean(self):
        self.assertEqual(normalize_address(summary(),BTC)['unconfirmed'],-1)
        for value in (MAX_SAFE+1,True,None):
            with self.assertRaises(ValueError): normalize_address(dict(summary(),confirmed=value),BTC)
        with self.assertRaises(ValueError): normalize_address(summary(),ETH)

    def test_bitcoin_flows_and_fee_rate(self):
        d=normalize_transactions(dict(transactions=[btc_tx()]),BTC)
        r=d['rows'][0]
        self.assertEqual((r['incoming'],r['outgoing'],r['net'],r['vbytes']),(250,1000,-750,101))
        self.assertEqual(r['feeRate'],100/101)
        self.assertEqual(d['analysis']['totals'],dict(incoming=250,outgoing=1000,known=1))
        self.assertEqual(d['quality']['completeness'],100)

    def test_unknown_outputs(self):
        for value,expected in [(0,4),(10,None)]:
            d=normalize_transactions(dict(transactions=[btc_tx(outputs=[dict(address=BTC,value=4),dict(address=None,value=value)])]),BTC)
            self.assertEqual(d['rows'][0]['incoming'],expected)

    def test_missing_duplicates_invalid(self):
        d=normalize_transactions(dict(transactions=[btc_tx(time=None,fee=None,weight=None,outputs=[dict(address=BTC,value=MAX_SAFE+1)]),btc_tx(),btc_tx(txId='b'*64,deleted=True),dict(txId='bad')]),BTC)
        self.assertEqual((d['quality']['duplicates'],d['quality']['invalid'],d['quality']['missing']),(1,2,1))
        self.assertIsNone(d['rows'][0]['net'])
        self.assertIsNone(d['rows'][0]['feeRate'])
        self.assertEqual(d['feeStats']['count'],0)

    def test_daily_utc_and_missing_days(self):
        d=normalize_transactions(dict(transactions=[btc_tx(time=86401),btc_tx(txId='b'*64,time=172799),btc_tx(txId='c'*64,time=345600),btc_tx(txId='d'*64,time=None)]),BTC)
        self.assertEqual([r['timestamp'] for r in d['analysis']['flow']],[86400,345600])
        self.assertEqual(d['analysis']['flow'][0]['count'],2)
        self.assertEqual(d['analysis']['totals']['known'],4)

    def test_eth_exact_wei(self):
        d=normalize_ethereum(eth_raw(),ETH)
        r=d['transactions']['rows'][0]
        self.assertEqual(d['summary']['balanceWei'],'1234567890123456789012345')
        self.assertEqual(r['exact']['incoming'],'1000000000000000001')
        self.assertEqual((r['incoming'],r['fee'],r['feeRate'],r['size']),(1,21000,1,21000))
        self.assertEqual(d['summary']['nonce'],4)
        self.assertIsNone(d['summary']['unconfirmed'])

    def test_eth_execution(self):
        for tx,net in [(eth_tx(**{'from':ETH,'to':ETH}),0),(eth_tx(**{'from':ETH,'to':None}),-1),(eth_tx(success=False),0),(eth_tx(success=None),None)]:
            r=normalize_ethereum(eth_raw([tx]),ETH)['transactions']['rows'][0]
            self.assertEqual(r['net'],net)
            self.assertEqual(r['fee'],21000)

    def test_eth_unknown_and_schema(self):
        d=normalize_ethereum(eth_raw([eth_tx(success=None,fee=None,gasUsed=None,timestamp=None),eth_tx(),eth_tx(hash='bad')]),ETH)
        q=d['transactions']['quality']
        self.assertEqual((q['received'],q['valid'],q['invalid'],q['duplicates'],q['missing']),(3,1,1,1,1))
        for raw in [eth_raw(balance=123),eth_raw(address=BTC)]:
            with self.assertRaises(ValueError): normalize_ethereum(raw,ETH)
        self.assertIsNone(normalize_ethereum(eth_raw(transactionCount=None,totalReceived=None),ETH)['summary']['txCount'])

    def test_internal_exclusion(self):
        d=normalize_ethereum(eth_raw([eth_tx(type='INTERNAL',fee=None),eth_tx()]),ETH)['transactions']
        self.assertEqual((d['quality']['excludedInternal'],d['quality']['duplicates'],len(d['rows'])),(1,0,1))
        self.assertEqual(d['rows'][0]['exact']['fee'],'21000000000000')

    def test_exports(self):
        rows=normalize_ethereum(eth_raw([eth_tx(**{'from':ETH,'to':None})]),ETH)['transactions']['rows']
        export=list(csv.DictReader(io.StringIO(address_csv(rows,'eth'))))[0]
        self.assertEqual(export['net_wei'],'-1000000000000000001')
        self.assertEqual(export['fee_wei'],'21000000000000')
        self.assertEqual(export['confirmed'],'true')
        self.assertIn('1970-01-02T00:00:00.000Z',network_csv([dict(id='price',unit='USD',values=points([12]))]))

    def test_matplotlib_report(self):
        snapshot=dict(chain='btc',offset=0,fetchedAt='2026-10-08T00:00:00Z',transactions=normalize_transactions(dict(transactions=[btc_tx()]),BTC))
        self.assertTrue(fee_report(snapshot).startswith(b'\x89PNG\r\n\x1a\n'))
        with self.assertRaises(ValueError): fee_report(dict(transactions=None))


class GatewayTests(unittest.TestCase):
    def test_address_validation(self):
        self.assertTrue(valid_address(BTC))
        self.assertTrue(valid_address(ETH,'eth'))
        self.assertFalse(valid_address(BTC,'eth'))
        self.assertFalse(valid_address('0x123','eth'))

    def test_gateway_allowlist(self):
        self.assertEqual(gateway_base(),'https://api.blockchain.info/explorer-gateway-kt')
        for value in ['http://api.blockchain.info/explorer-gateway-kt','https://evil.test/explorer-gateway-kt','https://api.blockchain.info:444/explorer-gateway-kt','https://api.blockchain.info/other','https://user@api.blockchain.info/explorer-gateway-kt']:
            with self.assertRaises(ValueError): gateway_base(value)

    def test_btc_partial_failure(self):
        calls=[]
        def requester(path,body,cfg):
            calls.append((path,body,cfg))
            if path.endswith('/transactions'): raise ValueError('Explorer API key rejected or insufficient access.')
            return summary()
        result=fetch_address(BTC,50,'btc',dict(key='test-key'),requester)
        self.assertEqual(result['summary']['txCount'],70)
        self.assertIsNone(result['transactions'])
        self.assertEqual(result['errors'][0]['part'],'transactions')
        self.assertEqual(calls[0][1],dict(network='BTC',address=BTC,page=0))
        self.assertEqual(calls[1][1],dict(address=BTC,limit=50,offset=50))
        self.assertNotIn('test-key',json.dumps(result))

    def test_eth_request_and_failure(self):
        calls=[]
        def requester(path,body,cfg):
            calls.append((path,body,cfg))
            return eth_raw()
        result=fetch_address(ETH,50,'eth',dict(key='test-key'),requester)
        self.assertEqual(calls[0][0],'/eth/address')
        self.assertEqual(calls[0][1],dict(network='ETH',address=ETH,page=1,size=50))
        self.assertEqual(result['errors'],[])
        def broken(*a): raise ValueError('Explorer API key rejected or insufficient access.')
        failed=fetch_address(ETH,0,'eth',{},broken)
        self.assertIsNone(failed['summary'])
        self.assertIsNone(failed['transactions'])
        self.assertEqual(len(failed['errors']),1)

    def test_public_network_partial_failure(self):
        calls=[]
        def requester(path,body,cfg,**kw):
            calls.append((path,body,cfg))
            if path.endswith('hash-rate'): raise ValueError('Provider rate limit reached.')
            return dict(status='ok',values=points([1,2,3]))
        d=fetch_snapshot(30,dict(key='test-key'),requester)
        self.assertEqual((len(d['series']),len(d['errors'])),(3,1))
        self.assertEqual(calls[0][2]['key'],'')
        self.assertEqual(calls[0][1],dict(timespan='30days',sampled=False,metadata=True,rollingAverage='24h',cors=False,format='json'))
        self.assertIsNone(d['correlations']['hash-rate']['market-price']['r'])
        self.assertAlmostEqual(d['correlations']['market-price']['n-transactions']['r'],1)

    @patch('python_backend.gateway.requests.post')
    def test_http_auth_redirect_and_size(self,mock):
        r=mock.return_value.__enter__.return_value
        r.status_code=200
        r.iter_content.return_value=[b'{"ok":true}']
        self.assertEqual(post('/btc/address',{},dict(key='test-key')),dict(ok=True))
        self.assertFalse(mock.call_args.kwargs['allow_redirects'])
        self.assertEqual(mock.call_args.kwargs['headers']['X-Explorer-Auth-Key'],'test-key')
        r.status_code=302
        with self.assertRaisesRegex(ValueError,'302'): post('/btc/address',{}, {})
        r.status_code=200
        r.iter_content.return_value=[b'123456']
        with self.assertRaisesRegex(ValueError,'size'): post('/btc/address',{}, {},limit=5)


class ServerTests(unittest.TestCase):
    def setUp(self):
        server._cache.clear()
        server._pending.clear()
        self.client=server.app.test_client()

    def test_invalid_requests(self):
        for path in ['/api/address?address=invalid','/api/address?chain=doge&address='+BTC,'/api/address?address='+BTC+'&offset=1','/api/analytics?days=2']:
            self.assertEqual(self.client.get(path).status_code,400)

    @patch('python_backend.server.fetch_address')
    def test_json_cache_and_routes(self,fetch):
        fetch.return_value=dict(chain='btc',summary=None,transactions=None,errors=[dict(message='Unavailable')])
        for _ in range(2):
            r=self.client.get('/api/address?address='+BTC)
            self.assertEqual(r.status_code,200)
            self.assertEqual(r.headers['Cache-Control'],'no-store')
            self.assertIsNone(r.json['transactions'])
        self.assertEqual(fetch.call_count,1)
        self.assertEqual(self.client.get('/api/report?address='+BTC).status_code,422)

    def test_concurrent_cache_deduplication(self):
        started,release=Event(),Event()
        calls=[]
        def loader():
            calls.append(1); started.set(); release.wait(2); return {'value':1}
        with ThreadPoolExecutor(max_workers=2) as pool:
            a=pool.submit(server.cached,('test',),loader)
            started.wait(2)
            b=pool.submit(server.cached,('test',),loader)
            release.set()
            self.assertEqual(a.result(),b.result())
        self.assertEqual(len(calls),1)

    def test_json_is_strict(self):
        with server.app.app_context():
            r=server.response(dict(value=float('nan'),other=float('inf')))
            self.assertEqual(json.loads(r.data),dict(value=None,other=None))

if __name__=='__main__': unittest.main()
