"""Subastas del Banco Ciudad (propias y de organismos como ARCA). La web es una app Angular: se lee renderizada.
Cada subasta tiene varios lotes; se publica uno por lote, con su foto y precio base."""
import html
import logging
import re
import time

from .common import cat_from_text, clean, money, prov_from_text, sentence

BASE = 'https://subastas.bancociudad.com.ar'
log = logging.getLogger('bancociudad')


def _tokens(seg):
    t = html.unescape(re.sub(r'<[^>]+>', '|', seg))
    return [clean(x) for x in t.split('|') if clean(x)]


def parse_home(h):
    """Lista de subastas de la portada (próximas, en curso y finalizadas)."""
    fin = h.find('Subastas finalizadas')
    pos = [m.start() for m in re.finditer(r'<app-subasta\b', h)]
    out = []
    for i, p in enumerate(pos):
        seg = h[p:pos[i + 1] if i + 1 < len(pos) else p + 8000]
        nro = re.search(r'href="/subasta/(\d+)"', seg)
        t = [x for x in _tokens(seg) if x not in ('Previous', 'Next', 'Suscripción CERRADA', 'Finalizó', '(GMT-3)')]
        j = ' '.join(t)
        fecha = next((k for k, x in enumerate(t) if re.fullmatch(r'\d\d/\d\d/\d{4}', x)), None)
        horas = re.search(r'De (\d\d):(\d\d) a (\d\d):(\d\d)', j)
        if not (nro and fecha and fecha >= 2 and horas):
            continue
        d, mo, y = t[fecha].split('/')
        reg = re.search(r'Suscribite antes del (\d\d)/(\d\d)/(\d{4}) (\d\d):(\d\d)', j)
        nl = re.search(r'(\d+) Lotes?', j)
        out.append({
            'nro': nro.group(1), 'org': t[fecha - 2], 'title': sentence(t[fecha - 1]),
            'nlots': int(nl.group(1)) if nl else None, 'cur': 'USD' if 'En dólar' in t else 'ARS',
            'start': f'{y}-{mo}-{d}T{horas.group(1)}:{horas.group(2)}:00-03:00',
            'end': f'{y}-{mo}-{d}T{horas.group(3)}:{horas.group(4)}:00-03:00',
            'reg_close': (f'{reg.group(3)}-{reg.group(2)}-{reg.group(1)}T{reg.group(4)}:{reg.group(5)}:00-03:00'
                          if reg else None),
            'finalizada': fin != -1 and p > fin,
        })
    return out


def parse_lotes(h):
    """Tarjetas de lotes de la página de una subasta: [(id, título, precio, depósito en garantía, finalizado)].
    En las subastas terminadas la tarjeta muestra el precio final en lugar de la base."""
    pos = [m.start() for m in re.finditer(r'<app-lote\b', h)]
    out = []
    for i, p in enumerate(pos):
        seg = h[p:pos[i + 1] if i + 1 < len(pos) else len(h)]
        lid = re.search(r'href="/lote/(\d+)"', seg)
        desc = re.search(r'texto-descripcion[^"]*">(.*?)</p>', seg, re.S)
        if not lid or not desc:
            continue
        precio = re.search(r'Precio (base|final)\s*</span>\s*<h5[^>]*>(.*?)</h5>', seg, re.S)
        garantia = re.search(r'Dep\. en garant[ií]a:\s*<span[^>]*>(.*?)</span>', seg, re.S)
        out.append((lid.group(1), clean(re.sub(r'<[^>]+>', ' ', desc.group(1))),
                    money(precio.group(2)) if precio else None, money(garantia.group(1)) if garantia else None,
                    bool(precio and precio.group(1) == 'final')))
    return out


def parse_lote(h):
    """Página de un lote: descripción completa (en la tarjeta viene cortada con '...') y lugar de exhibición."""
    d = re.search(r'Detalle de Lote\s*</h5>\s*<p[^>]*>(.*?)</p>', h, re.S)
    p = re.search(r'Exhibici[oó]n\s*</h5>.*?<span[^>]*font-weight-bold[^>]*>(.*?)</span>', h, re.S)
    texto = lambda m: clean(re.sub(r'<[^>]+>', ' ', m.group(1))) if m else None
    return {'desc': texto(d), 'place': texto(p)}


def _registro_subasta(s):
    return {'id': f"bc-{s['nro']}", 'src': 'bancociudad', 'prov': prov_from_text(s['title'], 'Nacional'),
            'org': f"Banco Ciudad por cuenta de {s['org']}", 'code': f"Subasta {s['nro']}", 'title': s['title'],
            'cat': cat_from_text(s['title']), 'status': 'finalizada' if s['finalizada'] else None,
            'start': s['start'], 'end': s['end'], 'reg_close': s['reg_close'], 'nlots': s['nlots'],
            'price_label': f"{s['nlots'] or 'Varios'} lotes", 'cur': s['cur'],
            'url': f"{BASE}/subasta/{s['nro']}", 'img': f"{BASE}/subastas_rest/subastas/imagen/{s['nro']}/1"}


def _ids(h):
    return re.findall(r'href="/lote/(\d+)"', h)


def _paginas(nav, nro):
    """HTML de cada página de lotes (8 por página) navegando la paginación."""
    h = nav.html(f'{BASE}/subasta/{nro}', selector='app-lote')
    paginas = [h]
    for n in range(2, 60):
        link = nav.page.locator('a', has_text=re.compile(rf'^\s*{n}\s*$'))
        if link.count() == 0:
            break
        antes = _ids(h)[:1]
        link.first.click()
        for _ in range(30):  # hasta 15 s a que cambien las tarjetas
            nav.page.wait_for_timeout(500)
            h = nav.page.content()
            if _ids(h)[:1] != antes:
                break
        paginas.append(h)
    return paginas


def lotes(nav):
    out = []
    for s in parse_home(nav.html(BASE + '/', selector='app-subasta')):
        base = _registro_subasta(s)
        items = {}
        try:
            for h in _paginas(nav, s['nro']):
                for lid, *datos in parse_lotes(h):
                    items[lid] = datos
        except Exception as e:  # si falla la subasta, queda publicada como un solo aviso
            log.warning('subasta %s: %s', s['nro'], e)
        if not items:
            out.append(base)
            continue
        for lid, (titulo, precio, garantia, final) in items.items():
            out.append({**base, 'id': f'bc-{s["nro"]}-{lid}', 'code': f"Subasta {s['nro']} · Lote {lid}",
                        'title': sentence(titulo), 'cat': cat_from_text(titulo), 'nlots': None,
                        'auction_title': s['title'], 'price': precio,
                        'price_label': 'Precio final' if final else 'Base',
                        'guarantee': garantia, 'url': f'{BASE}/lote/{lid}',
                        'img': f'{BASE}/subastas_rest/lotes/imagen/{lid}/1'})
    return out


def descripciones(nav, lots, cache, presupuesto=12 * 60):
    """Reemplaza el título cortado de cada lote por la descripción completa de su página (con caché por lote).
    Lo que no entre en el presupuesto de tiempo queda para la próxima corrida."""
    t0, nuevas = time.time(), 0
    for l in lots:
        if l['src'] != 'bancociudad' or '/lote/' not in l['url']:
            continue
        lid = l['url'].rsplit('/', 1)[1]
        if lid not in cache and nav and l['title'].endswith('...') and time.time() - t0 < presupuesto:
            try:
                cache[lid] = parse_lote(nav.html(l['url'], selector='text=Detalle de Lote', timeout=45_000))
                nuevas += 1
            except Exception as e:
                log.warning('lote %s: %s', lid, e)
        d = cache.get(lid) or {}
        if d.get('desc'):
            l['title'], l['cat'] = sentence(d['desc']), cat_from_text(d['desc'])
        if d.get('place'):
            l['place'] = d['place']
    log.info('descripciones de lotes: %d nuevas, %d en caché', nuevas, len(cache))
