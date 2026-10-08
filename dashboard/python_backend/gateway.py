"""Bounded HTTPS access to the verified Blockchain.com gateway only."""
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urlsplit
import requests
from .adapters import METRICS, normalize_address, normalize_transactions, normalize_ethereum, normalize_chart
from .analytics import correlate
from .exports import address_csv, network_csv

BASE_URL = 'https://api.blockchain.info/explorer-gateway-kt'
RANGES = (7,30,90,365)


def gateway_base(value=None):
    value = value or BASE_URL
    url = urlsplit(value)
    if url.scheme!='https' or url.netloc!='api.blockchain.info' or url.path.rstrip('/')!='/explorer-gateway-kt' or url.query or url.fragment:
        raise ValueError('Use the Blockchain.com Explorer Gateway HTTPS base URL.')
    return value.rstrip('/')


def config():
    return dict(base=gateway_base(os.environ.get('BLOCKCHAIN_API_BASE_URL')),key=os.environ.get('BLOCKCHAIN_API_KEY','').strip())


def post(path, body, cfg, timeout=20, limit=8_000_000):
    headers = {'Content-Type':'application/json','Accept':'application/json'}
    if cfg.get('key'): headers['X-Explorer-Auth-Key']=cfg['key']
    start = time.monotonic()
    try:
        with requests.post(gateway_base(cfg.get('base'))+path,json=body,headers=headers,timeout=(5,timeout),allow_redirects=False,stream=True) as response:
            if not 200<=response.status_code<300:
                if response.status_code==429: raise ValueError('Provider rate limit reached. Try again in a minute.')
                if response.status_code in (401,403): raise ValueError('Explorer API key rejected or insufficient access.')
                raise ValueError(f'Provider request failed (HTTP {response.status_code}).')
            chunks, size = [],0
            for chunk in response.iter_content(65536):
                size+=len(chunk)
                if size>limit: raise ValueError('Provider response exceeded the supported size.')
                if time.monotonic()-start>timeout: raise ValueError('Provider request timed out.')
                chunks.append(chunk)
            try: return json.loads(b''.join(chunks))
            except (ValueError,UnicodeError): raise ValueError('Provider returned invalid JSON.') from None
    except requests.Timeout:
        raise ValueError('Provider request timed out.') from None
    except requests.RequestException:
        raise ValueError('Unable to reach the provider.') from None


def error_message(error):
    if isinstance(error,ValueError) and str(error).startswith(('Provider','Explorer','Unexpected','The provider','Unable')):
        return str(error)
    return 'Unable to process the provider response.'


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')


def fetch_address(address,offset,chain,cfg,requester=post):
    result = dict(chain=chain,address=address,offset=offset,limit=50,fetchedAt=stamp(),authenticated=bool(cfg.get('key')),source=gateway_base(cfg.get('base')),summary=None,transactions=None,errors=[])
    if chain=='eth':
        try:
            result.update(normalize_ethereum(requester('/eth/address',dict(network='ETH',address=address,page=offset//50,size=50),cfg),address))
        except Exception as exc:
            result['errors'].append(dict(part='address',message=error_message(exc)))
    else:
        jobs = [('summary','/btc/address',dict(network='BTC',address=address,page=0),normalize_address),('transactions','/btc/address/transactions',dict(address=address,limit=50,offset=offset),normalize_transactions)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [(part,pool.submit(lambda path=path,body=body,adapter=adapter:adapter(requester(path,body,cfg),address))) for part,path,body,adapter in jobs]
            for part,future in futures:
                try: result[part]=future.result()
                except Exception as exc: result['errors'].append(dict(part=part,message=error_message(exc)))
    result['csv'] = address_csv(result['transactions']['rows'],chain) if result['transactions'] else None
    result['fetchedAt']=stamp()
    return result


def fetch_snapshot(days,cfg,requester=post):
    if days not in RANGES: raise ValueError('Unsupported time range.')
    # Network charts explicitly use public access; no authenticated fallback.
    chart_config = dict(base=gateway_base(cfg.get('base')),key='')
    body = dict(timespan=f'{days}days',sampled=False,metadata=True,rollingAverage='24h',cors=False,format='json')
    series, errors = [],[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [(metric,pool.submit(lambda m=metric:normalize_chart(requester('/charts/'+m['id'],body,chart_config,timeout=15,limit=2_000_000),m))) for metric in METRICS]
        for metric,future in futures:
            try: series.append(future.result())
            except Exception as exc: errors.append(dict(id=metric['id'],message=error_message(exc)))
    index = {s['id']:s['values'] for s in series}
    correlations = {a['id']:{b['id']:{k:v for k,v in correlate(index.get(a['id'],[]),index.get(b['id'],[])).items() if k!='pairs'} for b in METRICS} for a in METRICS}
    return dict(fetchedAt=stamp(),days=days,source=chart_config['base'],authenticated=False,series=series,errors=errors,correlations=correlations,csv=network_csv(series))
