# -*- coding: utf-8 -*-
"""Ritmo de presupuestos y de trabajo cerrado con factura.
Emitido = entrada en «Pendiente confirmación presupuesto» (importe = campo del ticket hoy).
Cierre = primera entrada en Finalizada/Resuelto/Finalizado técnico externo (Cancelado NO cuenta).
Dias laborables = lunes a viernes (sin descontar festivos), como la serie historica."""
import json, collections
from datetime import date, timedelta
import os
d = json.load(open(os.environ.get('TL', os.path.expanduser('~/tl.json'))))['tickets']
EMI = "Pendiente confirmación presupuesto"
CER = {"Finalizada", "Resuelto", "Finalizado técnico externo"}
HOY = date.today()
en = collections.Counter(); ei = collections.Counter()
cn = collections.Counter(); fn = collections.Counter(); fi = collections.Counter()
for k, v in d.items():
    imp = v.get('importe') or 0
    for ts, de, a in v.get('transitions') or []:
        if a == EMI and de != EMI:
            en[ts[:10]] += 1; ei[ts[:10]] += imp
    fin = next((ts for ts, de, a in (v.get('transitions') or []) if a in CER), None)
    if fin:
        cn[fin[:10]] += 1
        if v.get('factura'): fn[fin[:10]] += 1; fi[fin[:10]] += v.get('factura_importe') or 0
dias = []; x = HOY
while len(dias) < 30:
    if x.weekday() < 5: dias.append(x)
    x -= timedelta(days=1)
dias.reverse()
D = [[x.strftime('%m-%d'), en[x.isoformat()], round(ei[x.isoformat()]),
      fn[x.isoformat()], round(fi[x.isoformat()])] for x in dias]
M = []
for m in ["2026-03","2026-04","2026-05","2026-06","2026-07","2026-08","2026-09"]:
    y, mm = int(m[:4]), int(m[5:]); n = 0; x = date(y, mm, 1)
    while x.month == mm and x <= HOY:
        if x.weekday() < 5: n += 1
        x += timedelta(days=1)
    M.append({"m": m, "en": sum(v for k, v in en.items() if k[:7] == m),
              "ei": round(sum(v for k, v in ei.items() if k[:7] == m)),
              "fn": sum(v for k, v in fn.items() if k[:7] == m),
              "fi": round(sum(v for k, v in fi.items() if k[:7] == m)),
              "cn": sum(v for k, v in cn.items() if k[:7] == m), "lab": n})
out = {"_f": HOY.isoformat(), "dias": D, "mes": M}
json.dump(out, open(os.path.expanduser('~/fact_new.json'), 'w'), ensure_ascii=False)
print(json.dumps(M[-1], ensure_ascii=False), D[-3:])
