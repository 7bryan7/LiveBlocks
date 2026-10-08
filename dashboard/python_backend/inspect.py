"""Credential-safe live diagnostic, invoked by the env-loading Node wrapper."""
import json
from .gateway import config, fetch_address, fetch_snapshot
from .adapters import DEFAULT_ADDRESS, DEFAULT_ETH_ADDRESS
cfg=config()
failed=False
for chain,address in [('btc',DEFAULT_ADDRESS),('eth',DEFAULT_ETH_ADDRESS)]:
    result=fetch_address(address,0,chain,cfg)
    print(json.dumps(dict(chain=chain,authenticated=result['authenticated'],quality=result['transactions']['quality'] if result['transactions'] else None,errors=result['errors'])))
    failed=failed or bool(result['errors'])
result=fetch_snapshot(7,cfg)
print(json.dumps(dict(kind='network',series=[dict(id=s['id'],quality=s['quality']) for s in result['series']],errors=result['errors'])))
raise SystemExit(1 if failed or result['errors'] else 0)
