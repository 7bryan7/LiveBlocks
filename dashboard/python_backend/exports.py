"""CSV exports preserve exact base-unit strings, and report images use Matplotlib."""
import csv
import io
from datetime import datetime, timezone
from threading import Lock

_plot_lock = Lock()


def utc(timestamp):
    if timestamp is None:
        return ''
    try:
        return datetime.fromtimestamp(timestamp, timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')
    except (ValueError, OverflowError, OSError):
        return ''


def csv_text(header, rows):
    out = io.StringIO(newline='')
    writer = csv.writer(out, lineterminator='\n')
    writer.writerow(header)
    for row in rows:
        # Provider unit strings must not become spreadsheet formulas.
        writer.writerow([('true' if v else 'false') if isinstance(v,bool) else "'"+v if isinstance(v,str) and v.startswith(('=','+','-','@','\t','\r')) else v for v in row])
    return out.getvalue()


def address_csv(rows, chain):
    if chain=='eth':
        header = 'tx_hash,timestamp_utc,incoming_wei,outgoing_wei,net_wei,fee_wei,gas_used,gas_price_wei,confirmed,success'.split(',')
        # Integer conversion prevents formula escaping numeric minus signs and retains exact wei.
        def exact(r,k): return int(r['exact'][k]) if r['exact'][k] is not None else None
        values = [[r['hash'],utc(r['timestamp']),exact(r,'incoming'),exact(r,'outgoing'),exact(r,'net'),exact(r,'fee'),r['size'],exact(r,'gasPrice'),r['confirmed'],r['success']] for r in rows]
    else:
        header = 'tx_hash,timestamp_utc,incoming_satoshi,outgoing_satoshi,net_satoshi,fee_satoshi,size_bytes,fee_rate_sat_vbyte,confirmed'.split(',')
        values = [[r['hash'],utc(r['timestamp']),r['incoming'],r['outgoing'],r['net'],r['fee'],r['size'],r['feeRate'],r['confirmed']] for r in rows]
    return csv_text(header,values)


def network_csv(series):
    return csv_text(['timestamp_utc','metric','value','unit'],[[utc(p['x']),s['id'],p['y'],s['unit']] for s in series for p in s['values']])


def fee_report(snapshot):
    """Headless report of the same cached page; never generates synthetic observations."""
    import os
    os.environ.setdefault('MPLCONFIGDIR','/tmp/liveblocks-matplotlib')
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    tx = snapshot.get('transactions')
    if not tx or not tx['analysis']['bins']:
        raise ValueError('No fee observations available for this report.')
    with _plot_lock:
        fig = Figure(figsize=(10,5), facecolor='#111318')
        FigureCanvasAgg(fig)
        ax = fig.subplots()
        fig.subplots_adjust(left=.09, right=.98, top=.90, bottom=.20)
        ax.set_facecolor('#191c22')
        bins = tx['analysis']['bins']
        ax.bar([(b['lo']+b['hi'])/2 for b in bins],[b['count'] for b in bins],width=[b['hi']-b['lo'] or max(abs(b['lo'])*.05,1) for b in bins],color='#4acda5',edgecolor='#111318')
        unit = 'gwei' if snapshot['chain']=='eth' else 'satoshi'
        ax.set(xlabel=f'Whole-transaction fee ({unit})',ylabel='Transactions',title=f"{snapshot['chain'].upper()} fee distribution · {tx['feeStats']['count']} observations")
        ax.tick_params(colors='#edf1f7')
        for label in [ax.title,ax.xaxis.label,ax.yaxis.label]: label.set_color('#edf1f7')
        fig.text(.02,.035,f"API page {snapshot['offset']//50+1} · Equal-width histogram · Retrieved {snapshot['fetchedAt']} UTC",color='#939ead',fontsize=8)
        buffer = io.BytesIO()
        fig.savefig(buffer,format='png',dpi=150)
        fig.clear()
        return buffer.getvalue()
