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


# Reglas de rubro (frases separadas por coma). Gana la primera que coincide, así que el orden importa:
# "celulares Motorola moto g22" es Tecnología antes que Motos y "todo terreno" es un auto, no un terreno.
REGLAS = [
    ('Tecnología', 'celular, celulares, smartphone, motorola, iphone, galaxy, tablet, tablets, notebook, notebooks, '
                   'computadora, computadoras, cpu, monitor, monitores, consola, consolas, playstation, play station, '
                   'xbox, nintendo, auriculares, antena, antenas'),
    ('Camiones y utilitarios', 'camion, camiones, semirremolque, acoplado, batea, carreton, minibus, furgon, furgoneta, '
                               'utilitario, trafic, sprinter, daily, kangoo, fiorino, partner, berlingo, boxer, master, '
                               'jumper, ducato, transit, hiace, carroceria'),
    ('Autos y camionetas', 'automotor, automotores, automovil, automoviles, camioneta, camionetas, pick up, pickup, '
                           'sedan, motorhome, todo terreno, 4x4, coupe, hatchback'),
    ('Náutica', 'lancha, lanchas, velero, barco, nautica, gomon, embarcacion, kayak, moto de agua, jet ski'),
    ('Bicicletas', 'bicicleta, bicicletas, mountainbike, mountain bike, bici, bmx'),
    ('Muebles y oficina', 'mobiliario, muebles'),
    ('Campos y rurales', 'campo, campos, chacra, hectareas, establecimiento agropecuario, establec agropecuario, '
                         'inmueble rural, fraccion de campo'),
    ('Marcas y acciones', 'marca registrada, marcas registradas, tipo mixta, tipo denominativa, tipo figurativa, '
                          'acciones nominativas, acciones clase, paquete accionario'),
    ('Inmuebles', 'inmueble, inmuebles, lote de terreno, lote baldio, terreno, terrenos, departamento, depto, dpto, '
                  'unidad funcional, uf, u f, ph, casa, vivienda, galpon, cochera, edificio, local comercial, quinta, '
                  'parcela, fraccion, ubicado en, ubicada en, superficie, m2, nomenclatura catastral, cabanas, '
                  'planta industrial, solar, propiedad, ambientes, amb, baulera, piso, locales, playa de estacionamiento, '
                  'chalet, monoambiente, oficina, oficinas, salon comercial, lote bladio, parte indivisa, edilicio, '
                  'estacion de servicio, est de serv, en la localidad'),
    ('Maquinaria agrícola y vial', 'tractor, tractores, cosechadora, pulverizadora, sembradora, tolva, retroexcavadora, '
                                   'motoniveladora, topadora, autoelevador, autoelevadores, excavadora, cargadora, '
                                   'minicargadora, rastra, arado, rotoenfardadora'),
    ('Maquinaria industrial', 'torno, tornos, fresadora, balancin, plegadora, guillotina, prensa, prensadora, '
                              'enfardadora, punzonadora, extrusora, confeccionadora, impresora rotocalco, cnc, '
                              'puente grua, lijadora de banda, pegadora, enfichadora, escuadradora, estampadora, '
                              'cabina de pintura, cabinas de pintura, compresor, compresores, motocompresor, '
                              'grupo electrogeno, grupos electrogenos, grupos electrogeno, generador, generadores, '
                              'telar, telares, lampara de secado, maquina de coser, maquinas de coser, elevador, balanceadora, desarmadora, tronzadora, '
                              'proyector de perfiles, camara de frio, racks, lavadora de canto, bancada, turbina, '
                              'turbinas, silo, caldera, montacargas, transpaleta'),
    ('Herramientas', 'herramienta, herramientas, taladro, taladros, agujereadora, agujereadoras, amoladora, amoladoras, '
                     'soldadora, soldadoras, soldar, sierra, sierras, caladora, llave de impacto, rotopercutor, '
                     'roto percutor, martillo, esmeril, morsa, pistola, termofusora, nivel laser, tarraja, tarrajas, '
                     'torquimetro, calibre, calibres, motosierra, motosierras, motocierra, motoguadana, motoguadanas, '
                     'desmalezadora, bordeadora, sopladora, sopladoras, hidrolavadora, hidro lavadora, escalera, '
                     'andamio, gato hidraulico, llaves, mandril, mandriles, odometro, odometros, pulidora, lijadora, '
                     'atornillador, remachadora, aspiradores, podadora, carretilla, carretillas, hidrolavadoras, '
                     'plancha vibratoria, planchas vibratorias, cortadora, hoyadora, hoyadoras, vibroapisonador, '
                     'perforadora, matafuegos, soldadura, rectificador'),
    ('Maquinaria industrial', 'maquinaria, maquinarias, maquina, maquinas'),
    ('Motos', 'motocicleta, motocicletas, ciclomotor, cuatriciclo, motomel, scooter, motito, moto, motos, cg150, cg 150, '
              'ybr, gilera, zanella, corven, keller, kawasaki, harley, ducati, ktm, bajaj, royal enfield'),
    ('Electro y hogar', 'heladera, heladeras, freezer, lavarropa, lavarropas, secarropas, cocina, microondas, horno, '
                        'aire acondicionado, aires acondicionados, estufa, caloventor, cafetera, electrodomesticos, '
                        'dispenser, frigobar, cava, ventilador, aspiradora, plancha, olla, ollas, vajilla'),
    ('Muebles y oficina', 'mobiliario, muebles, mueble, escritorio, escritorios, silla, sillas, sillon, sillones, mesa, mesas, '
                          'biblioteca, estanteria, estanterias, lockers, tarimas, pallets, mostrador, banqueta, '
                          'placard, cama, colchon'),
    ('Tecnología', 'pc, impresora, impresoras, televisor, '
                   'televisores, tv, smart, parlante, parlantes, camaras de seguridad, router, informatica, servidor'),
    ('Arte, joyas y antigüedades', 'anillo, anillos, reloj, relojes, joya, joyas, oro, cuadro, cuadros, pintura, '
                                   'obra de arte, antiguedad, antiguedades, escultura, monedas, billetes'),
    ('Derechos y acciones', 'derechos y acciones, derechos hereditarios, cuota parte, indiviso'),
    ('Autos y camionetas', 'toyota, ford, chevrolet, volkswagen, vw, fiat, renault, peugeot, citroen, nissan, honda, '
                           'audi, bmw, mercedes, chery, jeep, suzuki, kia, hyundai, alfa romeo, volvo, mustang, etios, '
                           'corolla, hilux, ranger, amarok, s10, saveiro, strada, gol, palio, cronos, mobi, onix, cruze, '
                           'sandero, logan, clio, megane, focus, fiesta, ka, tracker, meriva, corsa, agile, prisma, '
                           'frontier, tiggo'),
]
_REGLAS = [(rubro, re.compile(r'\b(?:' + '|'.join(re.escape(f.strip()) for f in frases.split(',')) + r')\b'))
           for rubro, frases in REGLAS]
CAMPO = re.compile(r'\b(?:campo|campos|has|hectareas|hectarea|chacra|establecimiento|rural|agropecuario)\b')


def cat_from_text(t, kind=None):
    n = ' '.join(re.sub(r'[^a-z0-9]+', ' ', norm(t)).split())
    if kind == 'Inmueble':
        return 'Campos y rurales' if CAMPO.search(n) else 'Inmuebles'
    if re.match(r'marcas? ', n):  # 'Marca "valle de golf"': se remata la marca registrada
        return 'Marcas y acciones'
    for rubro, rx in _REGLAS:
        if rx.search(n):
            return 'Campos y rurales' if rubro == 'Inmuebles' and CAMPO.search(n) else rubro
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
