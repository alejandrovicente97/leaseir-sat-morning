// Escribe una nota interna en un ticket de Jira desde el panel del SAT.
// El token vive solo en las variables de entorno de Vercel: JIRA_EMAIL, JIRA_TOKEN, PANEL_CLAVE.
const BASE  = 'https://leaseir.atlassian.net';
const GENTE = ['Isaac','Chus','Gonzalo','Borja','Cristina','Alejandro'];

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', 'https://alejandrovicente97.github.io');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.status(204).end();
  if (req.method !== 'POST')    return res.status(405).json({ error: 'metodo' });

  const { leas, quien, texto, clave } = req.body || {};
  if (clave !== process.env.PANEL_CLAVE)      return res.status(401).json({ error: 'clave' });
  if (!/^LEAS-\d{3,5}$/.test(leas || ''))     return res.status(400).json({ error: 'leas' });
  if (!GENTE.includes(quien))                 return res.status(400).json({ error: 'quien' });
  if (!texto || !texto.trim())                return res.status(400).json({ error: 'texto' });
  if (texto.length > 1500)                    return res.status(400).json({ error: 'largo' });

  const auth = Buffer.from(`${process.env.JIRA_EMAIL}:${process.env.JIRA_TOKEN}`).toString('base64');
  const H = { Authorization: `Basic ${auth}`, Accept: 'application/json' };
  const hora = new Date().toLocaleTimeString('es-ES', { timeZone: 'Europe/Madrid', hour: '2-digit', minute: '2-digit' });
  const cuerpo = `${quien} (vía panel, ${hora}): ${texto.trim()}`;

  try {
    // ¿Es petición del portal? Si lo es, hay que usar servicedeskapi con public:false,
    // que es lo único que crea una NOTA INTERNA de verdad. commentVisibility no vale:
    // deja el comentario con jsdPublic true y el cliente lo ve.
    const esPortal = (await fetch(`${BASE}/rest/servicedeskapi/request/${leas}`, { headers: H })).ok;

    let r, via;
    if (esPortal) {
      via = 'nota interna (servicedeskapi)';
      r = await fetch(`${BASE}/rest/servicedeskapi/request/${leas}/comment`, {
        method: 'POST',
        headers: { ...H, 'Content-Type': 'application/json', 'X-Atlassian-Token': 'no-check' },
        body: JSON.stringify({ body: cuerpo, public: false })
      });
    } else {
      via = 'comentario (api/3) · el ticket no es del portal, no tiene vista de cliente';
      r = await fetch(`${BASE}/rest/api/3/issue/${leas}/comment`, {
        method: 'POST',
        headers: { ...H, 'Content-Type': 'application/json' },
        body: JSON.stringify({ body: { type:'doc', version:1, content:[{ type:'paragraph', content:[{ type:'text', text: cuerpo }] }] } })
      });
    }

    const j = await r.json().catch(() => ({}));
    if (!r.ok) return res.status(502).json({ error: 'jira', status: r.status, detalle: j.errorMessages || j.errors || j });

    // Verificar que ha quedado como nota interna, no fiarse de lo que devuelve el POST.
    let ok_interna = null;
    if (esPortal) {
      const v = await fetch(`${BASE}/rest/servicedeskapi/request/${leas}/comment?limit=50`, { headers: H });
      if (v.ok) {
        const vj = await v.json();
        const mio = (vj.values || []).find(c => String(c.id) === String(j.id));
        ok_interna = mio ? mio.public === false : null;
      }
    }
    return res.status(200).json({ ok: true, via, id: j.id, ok_interna });
  } catch (e) {
    return res.status(500).json({ error: 'fallo', detalle: String(e && e.message || e) });
  }
}
