"""Precio de referencia de mercado para comparar con la base.
- Vehículos: avisos de usados en Autocosmos para la misma marca, modelo y año (se renuevan cada 7 días).
- Resto: referencias cargadas a mano en data/precios_manual.json (máquinas, herramientas, etc.).
MercadoLibre no se usa porque bloquea la lectura automática de sus listados."""
import json
import logging
import re
import statistics
import time
from datetime import date

from .common import money, norm
from .red import get

URL = 'https://www.autocosmos.com.ar/auto/usado/{marca}/{modelo}?a={anio}'
AVISO = re.compile(r'([^"<>]{3,140}?) usado \((\d{4})\) color [^"<>]*? precio (u\$s|\$)\s?([\d.]+)', re.I)
DIAS_OK, DIAS_ERROR, MAX_CONSULTAS = 7, 1, 150
CATS = ('Autos y camionetas', 'Camiones y utilitarios')
MARCAS = {'toyota': 'toyota', 'ford': 'ford', 'chevrolet': 'chevrolet', 'volkswagen': 'volkswagen',
          'vw': 'volkswagen', 'peugeot': 'peugeot', 'renault': 'renault', 'fiat': 'fiat', 'citroen': 'citroen',
          'nissan': 'nissan', 'honda': 'honda', 'jeep': 'jeep', 'chery': 'chery', 'suzuki': 'suzuki',
          'mercedes benz': 'mercedes-benz', 'audi': 'audi'}
# texto del título -> modelo en la URL de Autocosmos; el orden importa (primero lo más específico)
MODELOS = {
    'toyota': ['hilux sw4:sw4', 'sw4', 'hilux', 'corolla cross:corolla-cross', 'corolla', 'etios', 'yaris', 'rav4'],
    'ford': ['ranger', 'ecosport', 'fiesta', 'focus', 'f 100:f-100', 'territory', 'maverick', 'transit', 'mondeo',
             'kuga', 'mustang', 'ka'],
    'chevrolet': ['s10:s-10', 's 10:s-10', 'onix', 'prisma', 'cruze', 'tracker', 'classic', 'corsa', 'agile', 'spin',
                  'montana', 'aveo', 'celta', 'meriva', 'captiva'],
    'volkswagen': ['gol trend:gol-trend', 'gold trend:gol-trend', 'saveiro', 'amarok', 'vento', 'polo', 'virtus',
                   'crossfox', 'suran', 'voyage', 'bora', 'golf', 'tiguan', 't cross:t-cross', 'taos', 'nivus',
                   'fox', 'gol', 'up'],
    'peugeot': ['208', '207 compact:207-compact', '207', '206', '306', '307', '308', '408', '3008', '5008', '2008',
                'partner patagonica:partner-patagonica', 'partner', 'expert', 'boxer'],
    'renault': ['duster oroch:duster-oroch', 'oroch:duster-oroch', 'duster', 'sandero stepway:sandero-stepway',
                'stepway:sandero-stepway', 'sandero', 'logan', 'kangoo', 'clio mio:clio-mio', 'clio', 'kwid',
                'megane', 'fluence', 'captur', 'master', 'symbol', 'koleos', 'alaskan'],
    'fiat': ['grand siena:grand-siena', 'siena', 'palio', 'cronos', 'mobi', 'strada', 'toro', 'argo', 'punto',
             'fiorino', 'ducato', 'idea', 'pulse', '500', 'uno'],
    'citroen': ['c4 lounge:c4-lounge', 'c3 aircross:c3-aircross', 'c3 picasso:c3-picasso', 'c elysee:c-elysee',
                'c3', 'c4', 'berlingo'],
    'nissan': ['frontier', 'march', 'versa', 'kicks', 'sentra', 'tiida', 'note', 'x trail:x-trail'],
    'honda': ['civic', 'fit', 'city', 'hr v:hr-v', 'cr v:cr-v', 'wr v:wr-v'],
    'jeep': ['renegade', 'compass'], 'chery': ['tiggo', 'qq'], 'suzuki': ['grand vitara:grand-vitara', 'fun', 'swift'],
    'mercedes-benz': ['sprinter', 'vito'], 'audi': ['a1', 'a3', 'a4', 'a5', 'q3', 'q5'],
}
VERSIONES = {'dx', 'srv', 'srx', 'sr', 'xli', 'xei', 'xls', 'xlt', 'xl', 'ltz', 'lt', 'ls', 'active', 'allure',
             'feline', 'griffe', 'authentique', 'expression', 'dynamique', 'intens', 'zen', 'life', 'trendline',
             'comfortline', 'highline', 'attractive', 'essence', 'sporting', 'drive', 'like', 'precision'}
log = logging.getLogger('precios')


def _texto(t):
    return ' ' + re.sub(r'[^a-z0-9]+', ' ', norm(t).replace('pick up', ' ')) + ' '


def _compacto(t):
    return re.sub(r'[^a-z0-9]', '', norm(t))


def clave(title):
    """Título del lote -> (marca, modelo, año, versiones) en términos de Autocosmos, o None."""
    n = _texto(title)
    marcas = list(dict.fromkeys(m for k, m in MARCAS.items() if f' {k} ' in n))
    for marca in marcas or list(MODELOS):
        for item in MODELOS[marca]:
            texto, _, slug = item.partition(':')
            if not marcas and (len(texto) < 4 or texto.isdigit()):
                continue  # sin marca en el título solo valen modelos inconfundibles
            if f' {texto} ' in n:
                resto = n.replace(f' {texto} ', ' ', 1)
                y = (re.search(r' (?:ano|modelo|mod|m) ?((?:19[6-9]|20[0-3])\d) ', resto)
                     or re.search(r' ((?:19[6-9]|20[0-3])\d) ', resto))
                if not y or int(y.group(1)) > date.today().year + 1:
                    return None
                return marca, slug or texto, int(y.group(1)), set(n.split()) & VERSIONES
    return None


def parse_avisos(h, modelo, anio):
    """Avisos (título, moneda, precio) de una página de resultados de Autocosmos."""
    out, vistos = [], set()
    for titulo, y, mon, precio in AVISO.findall(h):
        k = (titulo, y, mon, precio)
        if k in vistos or int(y) != anio or _compacto(modelo) not in _compacto(titulo):
            continue
        vistos.add(k)
        out.append((titulo.strip(), 'USD' if mon.lower() == 'u$s' else 'ARS', money(precio)))
    return out


def resumen(avisos):
    if not avisos:
        return None
    monedas = [m for _, m, _ in avisos]
    cur = max(set(monedas), key=monedas.count)
    vals = sorted(p for _, m, p in avisos if m == cur and p)
    if not vals:
        return None
    med = statistics.median(vals)
    vals = [v for v in vals if med / 3 <= v <= med * 3]  # descarta precios absurdos (anticipos, errores)
    return {'lo': vals[0], 'med': statistics.median(vals), 'hi': vals[-1], 'cur': cur, 'n': len(vals)}


class Autocosmos:
    def __init__(self, cache, red=True):
        self.cache, self.red, self.consultas = cache, red, 0

    def avisos(self, marca, modelo, anio):
        k = f'{marca}/{modelo}/{anio}'
        c = self.cache.get(k)
        vigente = c and time.time() - c['t'] < (DIAS_ERROR if c.get('error') else DIAS_OK) * 86400
        if not vigente and self.red and self.consultas < MAX_CONSULTAS:
            self.consultas += 1
            try:
                html = get(URL.format(marca=marca, modelo=modelo, anio=anio), tries=2, timeout=45).text
                c = self.cache[k] = {'t': time.time(), 'avisos': parse_avisos(html, modelo, anio)}
            except Exception as e:
                log.info('autocosmos %s: %s', k, e)
                c = self.cache[k] = {'t': time.time(), 'avisos': [], 'error': True}
        return [tuple(a) for a in (c or {}).get('avisos', [])]


def estimar(lots, cache_path, manual_path, red=True):
    try:
        cache = json.load(open(cache_path))
    except (OSError, ValueError):
        cache = {}
    ac, hoy, n = Autocosmos(cache, red), date.today().isoformat(), 0
    for l in lots:
        k = clave(l['title']) if l['cat'] in CATS else None
        if not k:
            continue
        marca, modelo, anio, versiones = k
        avisos, rango = ac.avisos(marca, modelo, anio), str(anio)
        if len(avisos) < 3:  # pocos avisos: se suma un año para cada lado
            avisos += ac.avisos(marca, modelo, anio - 1) + ac.avisos(marca, modelo, anio + 1)
            rango = f'{anio - 1} a {anio + 1}'
        afines = [a for a in avisos if versiones & set(_texto(a[0]).split())]
        if len(afines) >= 3:  # si alcanza, solo avisos de la misma versión
            avisos = afines
        r = resumen(avisos)
        if r and r['n'] >= 2:
            nombre = f"{marca.replace('-', ' ').title()} {modelo.replace('-', ' ').title()}"
            l['est'] = {**r, 'q': f"{nombre}{' ' + ' '.join(sorted(versiones)).upper() if len(afines) >= 3 else ''}, {rango}",
                        'kind': 'avisos usados', 'fuente': 'Autocosmos', 'fecha': hoy,
                        'url': URL.format(marca=marca, modelo=modelo, anio=anio)}
            n += 1
    try:
        manual = json.load(open(manual_path))
    except (OSError, ValueError):
        manual = []
    por_id = {i: m for m in manual for i in m['ids']}
    for l in lots:
        if 'est' not in l and l['id'] in por_id:
            l['est'] = {k: v for k, v in por_id[l['id']].items() if k != 'ids'}
            n += 1
    with open(cache_path, 'w') as f:
        json.dump(cache, f)
    log.info('precios de referencia: %d lotes (%d consultas a Autocosmos)', n, ac.consultas)
    return n
