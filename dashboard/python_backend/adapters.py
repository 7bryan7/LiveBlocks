"""Provider response adapters. Raw base-unit amounts never pass through a DataFrame."""
import math
import re
from .analytics import finite, summarize, rolling_mean, transaction_analysis

MAX_SAFE = 2**53-1
DEFAULT_ADDRESS = 'bc1qq8dxdalmj3f89v5xm5f3y70sec9s0fa7qpesl7'
DEFAULT_ETH_ADDRESS = '0xde0B295669a9FD93d5F28D9Ec85E40f4cb697BAe'
METRICS = [
    dict(id='market-price',name='Bitcoin price',short='Price',unit='USD',color='#4acda5'),
    dict(id='n-transactions',name='Daily transactions',short='Transactions',unit='transactions',color='#7798ff'),
    dict(id='hash-rate',name='Network hash rate',short='Hash rate',unit='TH/s',color='#b199f4'),
    dict(id='transaction-fees-usd',name='Network fees',short='Fees',unit='USD',color='#e2b26a'),
]


def safe_int(v):
    return finite(v) and int(v)==v and abs(v)<=MAX_SAFE


def amount(v):
    return safe_int(v) and v>=0


def valid_time(v):
    return safe_int(v) and 0<v<8640000000000


def valid_address(address, chain='btc'):
    pattern = r'0x[0-9a-fA-F]{40}' if chain=='eth' else r'(bc1[a-z0-9]{20,87}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})'
    return isinstance(address,str) and re.fullmatch(pattern,address) is not None


def schema(raw):
    def kind(v):
        if v is None: return 'null'
        if isinstance(v,bool): return 'boolean'
        if isinstance(v,list): return 'array'
        if isinstance(v,dict): return 'object'
        if isinstance(v,str): return 'string'
        return 'number'
    return [dict(field=k,type=kind(v)) for k,v in raw.items()] if isinstance(raw,dict) else []


def normalize_address(raw, address):
    keys = ['confirmed','unconfirmed','utxo','txCount','received']
    if not isinstance(raw,dict) or raw.get('address')!=address or not all(safe_int(raw.get(k)) for k in keys):
        raise ValueError('Unexpected response: address summary schema changed.')
    if any(raw[k]<0 for k in keys if k!='unconfirmed'):
        raise ValueError('Unexpected response: invalid address summary values.')
    return dict(address=address, **{k:raw[k] for k in keys})


def normalize_transactions(raw, address):
    if not isinstance(raw,dict) or not isinstance(raw.get('transactions'),list):
        raise ValueError('Unexpected response: transactions array missing.')
    rows, seen = [], set()
    quality = dict(received=len(raw['transactions']),valid=0,invalid=0,duplicates=0,missing=0)
    for tx in raw['transactions']:
        if not isinstance(tx,dict) or not isinstance(tx.get('txId'),str) or not re.fullmatch(r'[a-fA-F0-9]{64}',tx['txId']) or tx.get('deleted') is True:
            quality['invalid']+=1
            continue
        if tx['txId'] in seen:
            quality['duplicates']+=1
            continue
        seen.add(tx['txId'])
        def total(items):
            if not isinstance(items,list): return None
            if any(not isinstance(i,dict) or (not i.get('coinbase') and not isinstance(i.get('address'),str) and i.get('value')!=0) for i in items): return None
            matching = [i for i in items if i.get('address')==address]
            if any(not amount(i.get('value')) for i in matching): return None
            value = sum(i['value'] for i in matching)
            return value if safe_int(value) else None
        incoming, outgoing = total(tx.get('outputs')), total(tx.get('inputs'))
        net = incoming-outgoing if incoming is not None and outgoing is not None else None
        timestamp = tx.get('time') if valid_time(tx.get('time')) else tx.get('mempoolTime') if valid_time(tx.get('mempoolTime')) else None
        fee = tx.get('fee') if amount(tx.get('fee')) else None
        size = tx.get('size') if amount(tx.get('size')) and tx['size']>0 else None
        vbytes = math.ceil(tx['weight']/4) if amount(tx.get('weight')) and tx['weight']>0 else None
        if any(v is None for v in (timestamp,net,fee,size)): quality['missing']+=1
        rows.append(dict(hash=tx['txId'],timestamp=timestamp,incoming=incoming,outgoing=outgoing,net=net,fee=fee,size=size,vbytes=vbytes,
                         feeRate=fee/vbytes if fee is not None and vbytes else None,
                         confirmed=not tx['mempool'] if isinstance(tx.get('mempool'),bool) else None,
                         blockHeight=tx.get('blockHeight') if safe_int(tx.get('blockHeight')) else None))
    quality['valid']=len(rows)
    return dict(rows=rows,quality=quality,schema=schema(raw['transactions'][0]) if raw['transactions'] else [], **transaction_analysis(rows,quality,'btc'))


def wei(v):
    return int(v) if isinstance(v,str) and re.fullmatch(r'[0-9]{1,78}',v) else None


def count(v):
    return int(v) if isinstance(v,str) and re.fullmatch(r'[0-9]{1,16}',v) and int(v)<=MAX_SAFE else None


def units(v, divisor):
    return v/divisor if v is not None else None


def normalize_ethereum(raw,address):
    if not isinstance(raw,dict) or not isinstance(raw.get('address'),str) or raw['address'].lower()!=address.lower() or wei(raw.get('balance')) is None or not isinstance(raw.get('transactions'),list):
        raise ValueError('Unexpected response: Ethereum address schema changed.')
    target, rows, seen = address.lower(), [], set()
    quality = dict(received=len(raw['transactions']),valid=0,invalid=0,duplicates=0,missing=0,excludedInternal=0)
    for tx in raw['transactions']:
        if isinstance(tx,dict) and tx.get('type')=='INTERNAL':
            quality['excludedInternal']+=1
            continue
        if not isinstance(tx,dict) or tx.get('type')!='EXTERNAL' or not isinstance(tx.get('hash'),str) or not re.fullmatch(r'0x[0-9a-fA-F]{64}',tx['hash']):
            quality['invalid']+=1
            continue
        hash_ = tx['hash'].lower()
        if hash_ in seen:
            quality['duplicates']+=1
            continue
        seen.add(hash_)
        value, fee, gas_price = wei(tx.get('value')), wei(tx.get('fee')), wei(tx.get('gasPrice'))
        sender = tx['from'].lower() if valid_address(tx.get('from'),'eth') else None
        recipient = tx['to'].lower() if valid_address(tx.get('to'),'eth') else None
        incoming = outgoing = None
        if tx.get('success') is False:
            incoming = outgoing = 0
        elif tx.get('success') is True and value is not None and sender and (recipient or ('to' in tx and tx['to'] is None)):
            incoming = value if recipient==target else 0
            outgoing = value if sender==target else 0
        net = incoming-outgoing if incoming is not None and outgoing is not None else None
        timestamp = tx.get('timestamp') if valid_time(tx.get('timestamp')) else None
        gas_used = tx.get('gasUsed') if amount(tx.get('gasUsed')) and tx['gasUsed']>0 else None
        confirmed = True if safe_int(tx.get('blockNumber')) and tx['blockNumber']>0 else False if tx.get('state') in ['PENDING','MEMPOOL','UNCONFIRMED'] else None
        if any(v is None for v in (timestamp,net,fee,gas_used)): quality['missing']+=1
        rows.append(dict(hash=hash_,timestamp=timestamp,incoming=units(incoming,10**18),outgoing=units(outgoing,10**18),net=units(net,10**18),
                         fee=units(fee,10**9),size=gas_used,vbytes=None,feeRate=units(gas_price,10**9),confirmed=confirmed,
                         blockHeight=tx['blockNumber'] if confirmed else None, success=tx.get('success') if isinstance(tx.get('success'),bool) else None,
                         exact={k:str(v) if v is not None else None for k,v in dict(incoming=incoming,outgoing=outgoing,net=net,fee=fee,gasPrice=gas_price).items()}))
    quality['valid']=len(rows)
    return dict(summary=dict(confirmed=units(wei(raw['balance']),10**18),unconfirmed=None,utxo=None,txCount=count(raw.get('transactionCount')),
                             received=units(wei(raw.get('totalReceived')),10**18),nonce=count(raw.get('nonce')),balanceWei=raw['balance'],totalReceivedWei=str(wei(raw.get('totalReceived'))) if wei(raw.get('totalReceived')) is not None else None),
                transactions=dict(rows=rows,quality=quality,schema=schema(raw['transactions'][0]) if raw['transactions'] else [], **transaction_analysis(rows,quality,'eth')))


def normalize_chart(raw,metric):
    if not isinstance(raw,dict) or not isinstance(raw.get('values'),list):
        raise ValueError('Unexpected response: expected a values array.')
    if raw.get('status') and raw['status']!='ok':
        raise ValueError('The provider returned an unsuccessful chart status.')
    quality = dict(received=len(raw['values']),valid=0,missing=0,invalid=0,duplicates=0,gaps=0)
    by_time = {}
    for p in raw['values']:
        if not isinstance(p,dict) or p.get('x') is None or p.get('y') is None:
            quality['missing']+=1
            continue
        if not finite(p['x']) or not finite(p['y']) or not 0<p['x']<=8640000000000:
            quality['invalid']+=1
            continue
        if p['x'] in by_time: quality['duplicates']+=1
        by_time[p['x']] = dict(x=p['x'],y=p['y'])
    values = sorted(by_time.values(), key=lambda p:p['x'])
    quality['valid']=len(values)
    quality['gaps']=sum(max(0,math.floor((b['x']-a['x'])/86400+.5)-1) for a,b in zip(values,values[1:]))
    return dict(metric, unit=raw['unit'] if isinstance(raw.get('unit'),str) else metric['unit'],period=raw.get('period') if isinstance(raw.get('period'),str) else 'unknown',
                description=raw.get('description') if isinstance(raw.get('description'),str) else '',values=values,stats=summarize(values),quality=quality,schema=schema(raw),chart=rolling_mean(values))
