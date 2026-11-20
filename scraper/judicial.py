"""Portal de subastas electrónicas judiciales que usan la CSJN, la SCBA y Mendoza (mismo software)."""
import logging
import re
import time
from datetime import datetime

from .common import cat_from_text, clean, iso, money, norm, prov_from_text, sentence, text_of

PORTALES = {'csjn': 'https://subastaselectronicasjudiciales.csjn.gov.ar',
            'scba': 'https://subastas.scba.gov.ar',
            'mendoza': 'https://esubastas.jus.mendoza.gov.ar'}
ESTADO = {'Published': 'proxima', 'InProgress': 'en_curso', 'Finalized': 'finalizada', 'Finished': 'finalizada',
          'Canceled': 'cancelada', 'Cancelled': 'cancelada', 'Suspended': 'cancelada'}
SCBA_DEPTO = {'AZ': 'Azul', 'BB': 'Bahía Blanca', 'DO': 'Dolores', 'JU': 'Junín', 'LM': 'La Matanza',
              'LP': 'La Plata', 'LZ': 'Lomas de Zamora', 'MP': 'Mar del Plata', 'ME': 'Mercedes', 'MO': 'Morón',
              'MR': 'Moreno-Gral. Rodríguez', 'NE': 'Necochea', 'PE': 'Pergamino', 'QU': 'Quilmes',
              'SI': 'San Isidro', 'SM': 'San Martín', 'SN': 'San Nicolás', 'TL': 'Trenque Lauquen',
              'ZC': 'Zárate-Campana', 'AL': 'Avellaneda-Lanús', 'AV': 'Avellaneda-Lanús'}
CARD = re.compile(r'<li\b([^>]*\bauction_card\b[^>]*)>(.*?)</li>', re.S)
log = logging.getLogger('judicial')


def _attr(attrs, name):
    m = re.search(name + r'''=["']([^"']*)["']''', attrs)
    return m.group(1) if m else None


def _fecha_listado(s):
    """El listado usa MM/DD/YYYY HH:MM:SS."""
    try:
        d = datetime.strptime(s.strip(), '%m/%d/%Y %H:%M:%S')
    except (AttributeError, ValueError):
        return None
    return iso(d.year, d.month, d.day, d.hour, d.minute)


def parse_listado(h, src):
    base = PORTALES[src]
    out = []
    for attrs, body in CARD.findall(h):
        aid = _attr(attrs, 'data-auction-id')
        if not aid:
            continue

        def g(p):
            m = re.search(p, body, re.S)
            return m.group(1) if m else None

        desc = clean(g(r'thumbnail-description">(.*?)</div>'))
        code = clean(g(r'hCod">COD\.\s*([^<]+)<'))
        kind = clean(g(r'data__title">\s*Subasta\s+(\w+)'))
        img = g(r'''data-src=["']([^"']+)["']''')
        if img and not img.startswith('http'):
            img = base + '/' + img.replace('\\', '/').lstrip('/')
        fin = g(r'''finishdate=["']([^"']+)["']''')
        textos = [text_of(t) for t in re.findall(r'<small class="hTime"[^>]*>(.*?)</small>', body, re.S)]
        cuando = norm(textos[0]) if textos else ''
        bid = bid_text = None
        for t in textos:
            if t.startswith('Tramo'):
                bid_text, bid = t, money(t.split(':')[-1])
            elif 'No se realizaron ofertas' in t:
                bid_text = t
        usd = bool(re.search(r'\bD[ÓO]LARES\b', desc, re.I))
        title = re.sub(r'^EN D[ÓO]LARES-?\s*', '', desc, flags=re.I)
        if src == 'scba':
            depto = SCBA_DEPTO.get(re.sub(r'\d', '', code)[:2])
            prov, org = 'Buenos Aires', 'Poder Judicial de Buenos Aires' + (f' – Depto. Judicial {depto}' if depto else '')
        elif src == 'mendoza':
            prov, org = 'Mendoza', 'Poder Judicial de Mendoza'
        else:
            prov = prov_from_text(title, 'CABA')
            org = 'Justicia Nacional y Federal' + (' – Comercial' if code.startswith('COM') else
                                                   ' – Civil' if code.startswith('CIV') else '')
        out.append({
            'id': f'{src}-{aid}', 'src': src, 'prov': prov, 'org': org, 'code': code,
            'title': sentence(title), 'cat': cat_from_text(title, kind),
            'status': ESTADO.get(_attr(attrs, 'data-auction-status') or '', None),
            'end': _fecha_listado(fin) if 'termina' in cuando else None,
            'reg_close': _fecha_listado(fin) if 'inscrip' in cuando else None,
            'price_label': clean(g(r'withoutprice[^"]*">([^<]+)<')) or None,
            'cur': 'USD' if usd else 'ARS', 'bid': bid, 'bid_text': bid_text,
            'url': f'{base}/Auctions/Details/{aid}', 'img': img,
        })
    return out


ETIQUETAS = (r'Inicio de inscripci[oó]n|Fecha de inicio|Fecha de fin|Precio de reserva|Valor base|Precio base|'
             r'[OÓ]rgano jurisdiccional|Martillero|Lugar y fecha de exhibici[oó]n|Requiere|No requiere|'
             r'No permite|Permite|Estado de la subasta')


def _fecha_detalle(t, etiqueta):
    """El detalle usa 'DD/MM/YYYY - HH:MM AM'."""
    m = re.search(etiqueta + r'\s*:?\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*-?\s*(\d{1,2}):(\d{2})\s*([AaPp])?', t)
    if not m:
        return None
    d, mo, y, hh, mi, ampm = m.groups()
    hh = int(hh)
    if ampm:
        hh = hh % 12 + (12 if ampm in 'Pp' else 0)
    return iso(y, mo, d, hh, mi)


def _campo(t, etiqueta):
    m = re.search(etiqueta + r'\s*:?\s*(.+?)(?=\s+(?:' + ETIQUETAS + r')\b|$)', t)
    return clean(m.group(1))[:220] if m else None


def parse_detalle(h):
    t = text_of(h)
    d = {'start': _fecha_detalle(t, 'Fecha de inicio'), 'end': _fecha_detalle(t, 'Fecha de fin'),
         'court': _campo(t, r'[OÓ]rgano jurisdiccional que decret[oó] la subasta'),
         'auctioneer': _campo(t, 'Martillero'), 'place': _campo(t, r'Lugar y fecha de exhibici[oó]n')}
    m = re.search(r'(Valor base|Precio de reserva|Precio base)\s*:?\s*(U\$S|US\$|u\$s)?\s*\$?\s*([\d.,]+)', t)
    if m and money(m.group(3)):
        d['price'] = money(m.group(3))
        d['price_label'] = 'Precio de reserva' if 'reserva' in m.group(1) else 'Base'
        if m.group(2):
            d['cur'] = 'USD'
    return {k: v for k, v in d.items() if v}


def listado(nav, src):
    # espera las tarjetas o el aviso de portal vacío ("Sin subastas publicadas")
    return parse_listado(nav.html(PORTALES[src] + '/', selector='li.auction_card, :text("Sin subastas")'), src)


def detalles(nav, lots, cache, horas=72, presupuesto=15 * 60):
    """Completa fechas de inicio, base, juzgado y lugar desde la ficha de cada lote (con caché).
    Baja primero las fichas que nunca se leyeron; lo que no entre en el presupuesto queda para la próxima corrida."""
    ahora, nuevos, fallas = time.time(), 0, 0
    vencida = lambda l: l['src'] in PORTALES and l['status'] in ('proxima', 'en_curso') and not (
        l['id'] in cache and ahora - cache[l['id']]['t'] < horas * 3600)
    pendientes = sorted((l for l in lots if vencida(l)), key=lambda l: cache.get(l['id'], {}).get('t', 0))
    for i, l in enumerate(pendientes if nav else []):
        if time.time() - ahora > presupuesto:
            log.info('fichas: presupuesto agotado, quedan %d para la próxima corrida', len(pendientes) - i)
            break
        try:
            cache[l['id']] = {'t': time.time(), **parse_detalle(nav.html(l['url'], timeout=45_000))}
            nuevos += 1
        except Exception as e:  # una ficha caída no frena el resto
            fallas += 1
            log.warning('ficha %s: %s', l['id'], e)
        if (i + 1) % 25 == 0:
            log.info('fichas: %d de %d', i + 1, len(pendientes))
    for l in lots:
        c = cache.get(l['id']) if l['src'] in PORTALES else None
        if c:
            l.update({k: v for k, v in c.items() if k != 't'})
            if c.get('place'):
                l['prov'] = prov_from_text(c['place'], l['prov'])
    log.info('fichas: %d nuevas, %d con error', nuevos, fallas)
