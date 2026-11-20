"""Utilidades compartidas: texto, montos, fechas, rubros y provincias."""
import html
import re
import unicodedata

TZ = '-03:00'  # todas las fechas de los portales son hora argentina


def norm(s):
    """Minúsculas y sin acentos, para comparar texto."""
    s = unicodedata.normalize('NFD', (s or '').lower())
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn')


def clean(s):
    return re.sub(r'\s+', ' ', html.unescape(s or '')).strip(' -|')


def text_of(h):
    """HTML -> texto plano en una línea."""
    h = re.sub(r'(?is)<(script|style)\b.*?</\1>', ' ', h or '')
    return clean(re.sub(r'<[^>]+>', ' ', h))


def money(s):
    """'$ 1.234.567,89' -> 1234567.89 (formato argentino)."""
    s = re.sub(r'[^\d,.]', '', s or '')
    if not s:
        return None
    try:
        return float(s.replace('.', '').replace(',', '.'))
    except ValueError:
        return None


def currency(s):
    return 'USD' if re.search(r'U\$S|US\$|u\$s|d[óo]lar', s or '', re.I) else 'ARS'


def iso(y, mo, d, hh=0, mi=0):
    return f'{int(y):04d}-{int(mo):02d}-{int(d):02d}T{int(hh):02d}:{int(mi):02d}:00{TZ}'


def sentence(t):
    """Pasa a oración los títulos escritos todo en mayúsculas."""
    t = clean(t)
    return t[:1].upper() + t[1:].lower() if t.isupper() else t


# ---------- rubros ----------
CATS = ['Autos y camionetas', 'Motos', 'Camiones y utilitarios', 'Bicicletas', 'Herramientas',
        'Maquinaria industrial', 'Maquinaria agrícola y vial', 'Náutica', 'Inmuebles', 'Campos y rurales',
        'Electro y hogar', 'Tecnología', 'Muebles y oficina', 'Arte, joyas y antigüedades',
        'Derechos y acciones', 'Marcas y acciones', 'Otros']


def cat_from_text(t, kind=None):
    n = norm(t)

    def has(*ws):
        return any(re.search(r'\b' + w + r'\b', n) for w in ws)

    if has('lote baldio', 'terreno', 'inmueble', 'departamento'): return 'Inmuebles'  # antes que 'sierra' (Sierra de los Padres)
    if has('auriculares'): return 'Tecnología'
    if has('bicicleta', 'bicicletas', 'mountainbike', 'mountain bike', 'bici'): return 'Bicicletas'
    if has('motocicleta', 'moto', 'motos', 'ciclomotor', 'cuatriciclo', 'motomel', 'yamaha ybr', 'honda cg'): return 'Motos'
    if has('lancha', 'velero', 'barco', 'nautica', 'gomon', 'embarcacion'): return 'Náutica'
    if has('tractor', 'cosechadora', 'pulverizadora', 'sembradora', 'tolva', 'retroexcavadora', 'motoniveladora',
           'topadora', 'autoelevador', 'excavadora'): return 'Maquinaria agrícola y vial'
    if has('camion', 'semirremolque', 'acoplado', 'batea', 'carreton', 'minibus', 'furgon', 'utilitario', 'trafic',
           'sprinter', 'daily', 'kangoo', 'fiorino', 'partner', 'berlingo', 'boxer', 'master', 'carroceria'):
        return 'Camiones y utilitarios'
    if has('automotor', 'automovil', 'auto', 'pick up', 'pick-up', 'pickup', 'camioneta', 'sedan', 'hilux', 'ranger',
           'amarok', 's10', 's-10', 'saveiro', 'strada', 'toyota', 'peugeot', 'renault', 'chevrolet', 'fiat', 'ford',
           'volkswagen', 'citroen', 'nissan', 'honda', 'audi', 'bmw', 'mercedes', 'chery', 'jeep', 'suzuki', 'kia',
           'hyundai', 'alfa romeo', 'volvo', 'mustang', 'etios', 'corolla', 'gol', 'palio', 'cronos', 'mobi', 'onix',
           'cruze', 'sandero', 'logan', 'clio', 'megane', 'focus', 'fiesta', 'ka', 'tracker', 'meriva', 'corsa',
           'agile', 'prisma', 'frontier', 'tiggo', 'motorhome'): return 'Autos y camionetas'
    if has('torno', 'fresadora', 'balancin', 'plegadora', 'guillotina', 'prensa', 'punzonadora', 'extrusora',
           'confeccionadora', 'enfardadora', 'impresora rotocalco', 'cnc', 'puente grua', 'lijadora de banda',
           'pegadora', 'enfichadora', 'escuadradora', 'transfer', 'estampadora', 'cabina de pintura',
           'cabinas de pintura', 'compresor', 'grupo electrogeno', 'telares', 'maquinarias', 'maquina', 'elevador',
           'balanceadora', 'desarmadora', 'tronzadora', 'proyector de perfiles', 'tinglado', 'camara de frio',
           'racks', 'lavadora de canto', 'bancada'): return 'Maquinaria industrial'
    if has('herramienta', 'herramientas', 'taladro', 'amoladora', 'soldadora', 'sodadoras', 'sierra', 'caladora',
           'llave de impacto', 'roto percutor', 'rotopercutor', 'martillo', 'esmeril', 'morsa', 'pistola',
           'termofusora', 'nivel laser', 'tarrajas', 'torquimetro', 'calibres', 'motocierra', 'escalera', 'andamio',
           'gato hidraulico', 'llaves', 'mandriles', 'aspiradores'): return 'Herramientas'
    if kind == 'Inmueble' or has('casa', 'depto', 'dpto', 'lote', 'local', 'galpon', 'oficina', 'cochera', 'ph',
                                 'cabanas', 'vivienda', 'edificio', 'planta industrial', 'baldio', 'quinta', 'piso'):
        if has('campo', 'has', 'hectareas', 'hectarea', 'chacra', 'establec', 'rural', 'agropecuario'):
            return 'Campos y rurales'
        return 'Inmuebles'
    if has('campo', 'hectareas', 'chacra', 'rural'): return 'Campos y rurales'
    if has('notebook', 'cpu', 'computadora', 'computadoras', 'pc', 'monitor', 'monitores', 'consolas', 'playstation',
           'ps5', 'celular', 'celulares', 'informatic', 'tv', 'televisor', 'smart', 'parlante', 'camaras de seguridad'):
        return 'Tecnología'
    if has('heladera', 'freezer', 'lavarropa', 'lavarropas', 'secarropas', 'cocina', 'microondas', 'horno',
           'aire acondicionado', 'aires acondicionados', 'estufa', 'caloventor', 'cafetera', 'electrodomesticos',
           'dispenser', 'frigobar', 'cava'): return 'Electro y hogar'
    if has('mobiliario', 'muebles', 'mueble', 'escritorio', 'silla', 'sillas', 'sillon', 'mesa', 'biblioteca',
           'estanterias', 'lockers', 'tarimas', 'pallets', 'mostrador'): return 'Muebles y oficina'
    if has('anillo', 'reloj', 'relojes', 'joya', 'joyas', 'oro', 'cuadro', 'pintura', 'obra de arte', 'antiguedad',
           'escultura', 'moneda', 'monedas'): return 'Arte, joyas y antigüedades'
    if has('derechos y acciones', 'derechos'): return 'Derechos y acciones'
    if has('marca', 'acciones nominativas'): return 'Marcas y acciones'
    return 'Otros'


def prov_from_text(t, default):
    n = norm(t)
    for k, v in [('pcia. de buenos aires', 'Buenos Aires'), ('pcia. buenos aires', 'Buenos Aires'),
                 ('pcia.bs.as', 'Buenos Aires'), ('pcia. bs.as', 'Buenos Aires'), ('pcia bsas', 'Buenos Aires'),
                 ('pcia. bs. as', 'Buenos Aires'), ('prov. bs. as', 'Buenos Aires'),
                 ('provincia de buenos aires', 'Buenos Aires'), ('entre rios', 'Entre Ríos'),
                 ('pcia. cordoba', 'Córdoba'), ('santa fe', 'Santa Fe'), ('c.a.b.a', 'CABA'), ('caba', 'CABA'),
                 ('ca.b.a', 'CABA'), ('mendoza', 'Mendoza'), ('neuquen', 'Neuquén'), ('rio negro', 'Río Negro'),
                 ('chubut', 'Chubut'), ('tucuman', 'Tucumán'), ('misiones', 'Misiones'), ('corrientes', 'Corrientes')]:
        if k in n:
            return v
    return default
