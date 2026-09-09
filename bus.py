# -*- coding: utf-8 -*-
"""Reconstruye el indice del buscador (const BUS) desde la cache del dashboard."""
import json, os
tl = json.load(open(os.path.expanduser('~/tl.json')))
D, META = tl['tickets'], tl['_meta']
est=[]; cli=[]; tip=[]; ext=[]; fre=[]; loc=[]
def idx(L, v):
    v = v if v is not None else ''
    if v not in L: L.append(v)
    return L.index(v)
T={}
for k,v in D.items():
    tr=[]
    for ts,de,a in (v.get('transitions') or []):
        tr.append([ts[:16], idx(est,de), idx(est,a)])
    T[k]={"c":idx(cli,v.get('cliente')),"l":idx(loc,v.get('loc')),"ti":idx(tip,v.get('tipo')),
          "d":v.get('descripcion') or '', "cr":(v.get('created') or '')[:16],
          "e":idx(est,v.get('current_status')), "cs":v.get('consola') or '', "hp":v.get('hp') or '',
          "tt":v.get('tec_taller') or '', "te":idx(ext,v.get('tec_externo')), "as":v.get('asignado') or '',
          "ga":1 if (v.get('garantia') or '')=='Sí' else 0, "fr":idx(fre,v.get('forma_resolucion')),
          "im":v.get('importe') if v.get('importe') is not None else 0.0,
          "fa":v.get('factura') or '', "fi":v.get('factura_importe') if v.get('factura_importe') is not None else '',
          "fp":v.get('factura_pendiente') if v.get('factura_pendiente') is not None else '',
          "fe":v.get('factura_estado') or ''}
    T[k]["tr"]=tr
f=(META.get('last_fetched_at') or '')
# la fecha del indice, en hora local de Madrid
from datetime import datetime, timezone, timedelta
try:
    d=datetime.fromisoformat(f.replace('Z','+00:00')).astimezone(timezone(timedelta(hours=2)))
    fecha=d.strftime('%Y-%m-%d %H:%M')
except Exception:
    fecha=f[:16].replace('T',' ')
out={"_f":fecha,"est":est,"cli":cli,"tip":tip,"ext":ext,"fre":fre,"loc":loc,"t":T}
open(os.path.expanduser('~/sc/BUS.js'),'w',encoding='utf-8').write('const BUS = '+json.dumps(out,ensure_ascii=False,separators=(',',':'))+';')
print('fecha',fecha,'| tickets',len(T),'| est',len(est),'cli',len(cli),'tip',len(tip),'ext',len(ext),'fre',len(fre),'loc',len(loc))
