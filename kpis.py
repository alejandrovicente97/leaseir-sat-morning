# -*- coding: utf-8 -*-
"""Mide el ciclo real del SAT a partir del historial de transiciones de Jira.
Fuente: cache/jira_status_timeline.json del repo iortizfigueroa/leaseir-sat-dashboard.
Salida: kpis.json, que es lo que se incrusta en el panel."""
import json
from datetime import datetime, timezone
from collections import defaultdict

import os
# Descargar antes:  curl -sL -o $HOME/tl.json https://raw.githubusercontent.com/iortizfigueroa/leaseir-sat-dashboard/main/cache/jira_status_timeline.json
SRC = os.environ.get('TL', os.path.expanduser('~/tl.json'))
raw = json.load(open(SRC))
D, META = raw['tickets'], raw['_meta']
AHORA = datetime.now(timezone.utc)
import re as _re
# Python < 3.11 no traga '+0200' sin dos puntos
def p(s): return datetime.fromisoformat(_re.sub(r'([+-]\d{2})(\d{2})$', r'\1:\2', s))

# Entrar y salir de un estado en menos de 2 minutos es un dedazo corrigiéndose,
# no tiempo real. Verificado en LEAS-7343 (Gonzalo, 04/09, dos rebotes en 2 segundos).
REBOTE = 120

# El ciclo, por tramos. Lo importante es separar lo que depende de nosotros
# de lo que depende del cliente: si no, cualquier retraso se justifica solo.
TRAMOS = [
  ("triaje",    "Alta y triaje",          "nosotros", {"Abierto","Pendiente agendar llamada","Pendiente definir servicio externo","Pendiente asignar técnico"}),
  ("transporte","Transporte a taller",    "tercero",  {"Pendiente recogida","Gestionado transporte"}),
  ("cola",      "Cola de taller",         "nosotros", {"En cola taller","Esperando inicio reparación"}),
  ("presup",    "Preparar presupuesto",   "nosotros", {"En preparación presupuesto","Presupuesto preparado pendiente de enviar"}),
  ("cliente",   "Esperando al cliente",   "cliente",  {"Esperando respuesta cliente a presupuesto","Pendiente confirmación presupuesto"}),
  ("repara",    "Reparación",             "nosotros", {"En reparación"}),
  ("externo",   "Técnico externo",        "tercero",  {"Enviado a técnico externo"}),
  ("inspec",    "Inspección de salida",   "nosotros", {"Inspección de salida"}),
  ("vuelta",    "Transporte de vuelta",   "tercero",  {"Devuelto a cliente"}),
]
CERRADOS = {"Finalizada","Resuelto","Cancelado","Finalizado técnico externo"}

CAD = ["Elha","Sin Vello","SinVello","Sinvello","Epil Point","Centri Unico","Centro Unico",
       "Smart Duck","Dermasana","Laser Factory","Dermoscan","Brull","Belenus","Corpoderm","Zurimed"]
def cadena(c):
    b = (c or "").lower()
    for x in CAD:
        if x.lower() in b:
            if "vello" in x.lower(): return "Sin Vello"
            if "unico" in x.lower(): return "Centri Unico"
            return x
    return "Otros y directos"

def periodos(tr, estados):
    """[(entrada, salida|None)] en esos estados, descartando rebotes."""
    out, ini = [], None
    for ts, de, a in tr:
        t = p(ts)
        if a in estados and de not in estados: ini = t
        elif de in estados and a not in estados and ini is not None:
            if (t - ini).total_seconds() >= REBOTE: out.append((ini, t))
            ini = None
    if ini is not None: out.append((ini, None))
    return out

def pct(v, q):
    if not v: return None
    v = sorted(v); i = max(0, min(len(v)-1, int(round(q*(len(v)-1)))))
    return v[i]

def resumen(xs, umbral):
    if not xs: return None
    xs = sorted(xs)
    return {"n": len(xs), "med": round(pct(xs,.5),1), "p90": round(pct(xs,.9),1),
            "media": round(sum(xs)/len(xs),1), "max": round(max(xs),0),
            "malos": sum(1 for x in xs if x > umbral), "umbral": umbral}

# ── Recorrido ──────────────────────────────────────────────────────────────
tramo_dias   = defaultdict(list)                       # tramo -> [dias]
tramo_cad    = defaultdict(lambda: defaultdict(list))  # tramo -> cadena -> [dias]
tramo_tec    = defaultdict(lambda: defaultdict(list))  # tramo -> tecnico -> [dias]
tramo_abierto= defaultdict(list)                       # tramo -> [(dias, key, cliente)]
ciclo        = []                                      # lead time de punta a punta
ciclo_cad    = defaultdict(list)
por_ticket   = {}

for k, v in D.items():
    tr = v.get('transitions') or []
    if not tr: continue
    cad, tec = cadena(v.get('cliente')), (v.get('tec_taller') or '').strip()
    det = {}
    for cl, _t, _d, estados in TRAMOS:
        suma, sigue = 0.0, False
        for a, b in periodos(tr, estados):
            if b is None:
                sigue = True
                tramo_abierto[cl].append((round(((AHORA-a).total_seconds()/86400),1), k, v.get('cliente') or '?'))
            else:
                suma += (b - a).total_seconds()/86400
        if suma > 0 and not sigue:          # solo tramos ya terminados
            tramo_dias[cl].append(suma)
            tramo_cad[cl][cad].append(suma)
            if tec and cl in ("repara","cola","inspec"): tramo_tec[cl][tec].append(suma)
            det[cl] = round(suma, 1)
    # lead time: de creado a primer estado de cierre
    fin = next((p(ts) for ts, de, a in tr if a in CERRADOS), None)
    if fin and v.get('created'):
        dias = (fin - p(v['created'])).total_seconds()/86400
        if 0 <= dias < 900:
            ciclo.append(dias); ciclo_cad[cad].append(dias)
            det['_total'] = round(dias,1)
    if det: por_ticket[k] = {"cli": v.get('cliente'), "cad": cad, "tipo": v.get('tipo'),
                             "tec": tec, "est": v.get('current_status'), "t": det}

# Umbral por tramo: el compromiso con el que se juzga. El de reparación son las
# 80 h del SLA 11122 (3,3 d); el resto, lo que ya usa la herramienta.
UMBRAL = {"triaje":2, "transporte":8, "cola":3, "presup":3, "cliente":7,
          "repara":3.3, "externo":7, "inspec":1, "vuelta":5}

out = {
  "_fuente": "iortizfigueroa/leaseir-sat-dashboard · cache/jira_status_timeline.json",
  "_fecha_datos": META.get('last_fetched_at'),
  "_calculado": AHORA.isoformat(timespec='minutes'),
  "_tickets": len(D), "_rebote_seg": REBOTE,
  "tramos": [], "ciclo": resumen(ciclo, 30), "ciclo_cad": {}, "abiertos": {},
}
for cl, tit, quien, estados in TRAMOS:
    r = resumen(tramo_dias[cl], UMBRAL[cl])
    if not r: continue
    r.update({"id": cl, "tit": tit, "quien": quien,
              "estados": sorted(estados),
              "cad": {c: resumen(x, UMBRAL[cl]) for c, x in tramo_cad[cl].items() if len(x) >= 10},
              "tec": {t: resumen(x, UMBRAL[cl]) for t, x in tramo_tec[cl].items() if len(x) >= 10}})
    out["tramos"].append(r)
    out["abiertos"][cl] = sorted(tramo_abierto[cl], reverse=True)[:12]
out["ciclo_cad"] = {c: resumen(x, 30) for c, x in ciclo_cad.items() if len(x) >= 10}

json.dump(out, open(os.path.expanduser('~/kpis_new.json'),'w'), ensure_ascii=False, indent=1)

print("datos de:", out["_fecha_datos"], "| tickets:", out["_tickets"])
print("\nCICLO COMPLETO  n=%(n)d  mediana %(med)s d  p90 %(p90)s d  max %(max)s d" % out["ciclo"])
print("\n%-22s %-9s %5s %8s %8s %9s" % ("TRAMO","DEPENDE",  "n","mediana","p90","% > umbr"))
for t in out["tramos"]:
    print("%-22s %-9s %5d %7.1f d %7.1f d %6.0f%%  (umbral %s d)"
          % (t["tit"], t["quien"], t["n"], t["med"], t["p90"], 100*t["malos"]/t["n"], t["umbral"]))
