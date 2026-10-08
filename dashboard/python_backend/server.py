"""Flask routes shared by local development and Vercel's Python function."""
import json
import math
import time
from collections import OrderedDict
from concurrent.futures import Future
from threading import Lock
from flask import Flask, Response, request
from .adapters import valid_address
from .exports import fee_report
from .gateway import config, fetch_address, fetch_snapshot, RANGES

app = Flask(__name__)
_cache, _pending, _lock = OrderedDict(), {}, Lock()


class BusyError(Exception): pass


def cached(key, loader):
    with _lock:
        saved = _cache.get(key)
        if saved and time.monotonic()-saved[0]<60:
            return saved[1]
        future = _pending.get(key)
        owner = future is None
        if owner:
            if len(_pending)>=12: raise BusyError()
            future = _pending[key] = Future()
    if not owner:
        return future.result(timeout=28)
    try:
        result = loader()
        with _lock:
            _cache[key]=(time.monotonic(),result)
            _cache.move_to_end(key)
            while len(_cache)>38: _cache.popitem(last=False)
        future.set_result(result)
        return result
    except BaseException as exc:
        future.set_exception(exc)
        raise
    finally:
        with _lock: _pending.pop(key,None)


def clean_json(value):
    if isinstance(value,float) and not math.isfinite(value): return None
    if isinstance(value,dict): return {k:clean_json(v) for k,v in value.items()}
    if isinstance(value,list): return [clean_json(v) for v in value]
    return value


def response(value,status=200):
    return Response(json.dumps(clean_json(value),allow_nan=False,separators=(',',':')),status=status,mimetype='application/json',headers={'Cache-Control':'no-store'})


def address_request():
    chain, address = request.args.get('chain','btc'), request.args.get('address','')
    try: offset = int(request.args.get('offset','0'))
    except ValueError: raise ValueError('Enter a page offset in multiples of 50.') from None
    if chain not in ('btc','eth') or not valid_address(address,chain) or offset<0 or offset>10_000_000 or offset%50:
        raise ValueError('Enter a valid mainnet address for the selected chain and a page offset in multiples of 50.')
    return chain,address,offset


@app.get('/api/address')
def address_route():
    try: chain,address,offset = address_request()
    except ValueError as exc: return response(dict(error=str(exc)),400)
    try:
        cfg=config()
        key=('address',chain,address.lower() if chain=='eth' else address,offset,cfg['base'],cfg['key'])
        return response(cached(key,lambda:fetch_address(address,offset,chain,cfg)))
    except BusyError: return response(dict(error='Too many requests. Try again shortly.'),429)
    except Exception: return response(dict(error='Unable to load the configured Python gateway.'),502)


@app.get('/api/analytics')
def analytics_route():
    try: days = int(request.args.get('days','30'))
    except ValueError: days = 0
    if days not in RANGES: return response(dict(error='Choose 7, 30, 90, or 365 days.'),400)
    try:
        cfg=config()
        return response(cached(('network',days,cfg['base']),lambda:fetch_snapshot(days,cfg)))
    except BusyError: return response(dict(error='Too many requests. Try again shortly.'),429)
    except Exception: return response(dict(error='Unable to load the configured Python gateway.'),502)


@app.get('/api/report')
def report_route():
    try: chain,address,offset = address_request()
    except ValueError as exc: return response(dict(error=str(exc)),400)
    try:
        cfg=config()
        snapshot=cached(('address',chain,address.lower() if chain=='eth' else address,offset,cfg['base'],cfg['key']),lambda:fetch_address(address,offset,chain,cfg))
        if snapshot['transactions'] is None or not snapshot['transactions']['analysis']['bins']:
            return response(dict(error='No fee observations available for this report.'),422)
        return Response(fee_report(snapshot),mimetype='image/png',headers={'Cache-Control':'no-store','Content-Disposition':f'attachment; filename="liveblocks-{chain}-fees.png"'})
    except BusyError: return response(dict(error='Too many requests. Try again shortly.'),429)
    except Exception: return response(dict(error='Unable to generate the report.'),502)
