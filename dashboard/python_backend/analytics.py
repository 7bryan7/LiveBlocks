"""Pure EDA: finite observations only, UTC grouping, sample standard deviation."""
import math
import numpy as np
import pandas as pd


def finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def summarize(points):
    values = np.asarray([p['y'] for p in points if finite(p.get('y'))], dtype=float)
    result = dict.fromkeys(('mean', 'median', 'min', 'max', 'std', 'q1', 'q3', 'lower', 'upper', 'change'))
    result.update(count=len(values), outliers=0)
    if not len(values):
        return result
    q1, median, q3 = np.quantile(values, [.25, .5, .75], method='linear')
    lower, upper = q1 - 1.5 * (q3-q1), q3 + 1.5 * (q3-q1)
    first, last = points[0].get('y'), points[-1].get('y')
    result.update(mean=float(np.mean(values)), median=float(median), min=float(values.min()), max=float(values.max()),
                  std=float(np.std(values, ddof=1)) if len(values)>1 else None,
                  q1=float(q1), q3=float(q3), lower=float(lower), upper=float(upper),
                  outliers=int(np.count_nonzero((values<lower)|(values>upper))),
                  change=(last-first)/abs(first)*100 if finite(first) and finite(last) and first!=0 else None)
    return result


def histogram(points, count=8):
    values = np.asarray([p['y'] for p in points if finite(p.get('y'))], dtype=float)
    if not len(values):
        return []
    if values.min() == values.max():
        return [dict(lo=float(values[0]), hi=float(values[0]), count=len(values))]
    counts, edges = np.histogram(values, bins=count)
    return [dict(lo=float(edges[i]), hi=float(edges[i+1]), count=int(n)) for i,n in enumerate(counts)]


def correlate(a, b):
    right = {p['x']:p['y'] for p in b if finite(p.get('y'))}
    pairs = [dict(x=p['y'], y=right[p['x']], timestamp=p['x']) for p in a if finite(p.get('y')) and p['x'] in right]
    r = None
    if len(pairs)>=3:
        frame = pd.DataFrame(pairs)
        if frame.x.nunique()>1 and frame.y.nunique()>1:
            r = float(np.clip(np.corrcoef(frame.x.to_numpy(dtype=float), frame.y.to_numpy(dtype=float))[0,1], -1, 1))
    return dict(r=r, count=len(pairs), pairs=pairs)


def rolling_mean(points, window=7):
    if not points:
        return []
    frame = pd.DataFrame(points)
    means = frame.y.rolling(window, min_periods=window).mean()
    # A full rolling window must contain consecutive daily observations.
    consecutive = frame.x.diff().eq(86400).rolling(window-1, min_periods=window-1).sum().eq(window-1)
    return [dict(p, average=float(means.iloc[i]) if consecutive.iloc[i] and pd.notna(means.iloc[i]) else None) for i,p in enumerate(points)]


def transaction_analysis(rows, quality, chain):
    fees = [dict(x=i, y=r['fee']) for i,r in enumerate(rows) if r['fee'] is not None]
    stats = summarize(fees)
    for row in rows:
        row['outlier'] = bool(row['fee'] is not None and stats['lower'] is not None and (row['fee']<stats['lower'] or row['fee']>stats['upper']))
    sizes = [dict(x=i, y=r['size']) for i,r in enumerate(rows) if r['size'] is not None]
    divisor = 1 if chain=='eth' else 100_000_000
    complete = [r for r in rows if r['net'] is not None]
    totals = dict(incoming=sum(r['incoming'] for r in complete), outgoing=sum(r['outgoing'] for r in complete), known=len(complete))
    timed = [dict(timestamp=r['timestamp']//86400*86400, incoming=r['incoming']/divisor, outgoing=r['outgoing']/divisor) for r in complete if r['timestamp'] is not None]
    flow = []
    if timed:
        frame = pd.DataFrame(timed)
        grouped = frame.groupby('timestamp', sort=True).agg(incoming=('incoming','sum'), outgoing=('outgoing','sum'), count=('incoming','size'))
        flow = [dict(timestamp=int(t), incoming=float(r.incoming), outgoing=float(r.outgoing), count=int(r['count'])) for t,r in grouped.iterrows()]
    eligible = quality['received']-quality.get('excludedInternal',0)
    quality['completeness'] = (quality['valid']-quality['missing'])/eligible*100 if eligible else None
    quality['invalidOrDuplicate'] = quality['invalid']+quality['duplicates']
    return dict(feeStats=stats, analysis=dict(bins=histogram(fees), relation=correlate(sizes,fees), flow=flow, totals=totals))
