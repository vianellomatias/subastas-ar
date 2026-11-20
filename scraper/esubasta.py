"""Plataforma esubasta: portales judiciales de varias provincias y ventas privadas de esubasta.ar.
Una sola API pública (paginada de a 12) devuelve los lotes activos de todos los portales."""
import re

from .common import cat_from_text, norm, sentence
from .red import get

API = 'https://www.esubasta.ar/compat/good_search/?status=active&adult_content=false'
PORTALES = {  # source -> (provincia, dominio del portal)
    'córdoba': ('Córdoba', 'subastas.justiciacordoba.gob.ar'),
    'san_luis': ('San Luis', 'subastas.justiciasanluis.gov.ar'),
    'entre_ríos': ('Entre Ríos', 'subastas.jusentrerios.gob.ar'),
    'la_pampa': ('La Pampa', 'subastas.justicialapampa.gob.ar'),
    'salta': ('Salta', 'subastas.justiciasalta.gov.ar'),
    'chaco': ('Chaco', 'subastas.justiciachaco.gov.ar'),
    'san_juan': ('San Juan', 'subastas.jussanjuan.gov.ar'),
    'jujuy': ('Jujuy', 'subastas.jujuy.gob.ar'),
    'mpa_jujuy': ('Jujuy', 'subastas.mpajujuy.gob.ar'),
    'subastas_electrónicas': ('Privadas (esubasta)', 'www.esubasta.ar'),
}
PRIVADAS = 'subastas_electrónicas'
CAT = {'Inmuebles': 'Inmuebles', 'Motos y Otros': 'Motos', 'Herramientas': 'Herramientas',
       'Electrodomésticos': 'Electro y hogar', 'Electrónica, Audio y Video': 'Tecnología', 'Computación': 'Tecnología',
       'Hogar y Muebles': 'Muebles y oficina', 'Arte y Antiguedades': 'Arte, joyas y antigüedades',
       'Joyas y Relojes': 'Arte, joyas y antigüedades', 'Derechos y Acciones': 'Derechos y acciones',
       'Construcción': 'Maquinaria industrial', 'Indumentaria y Accesorios': 'Otros', 'Salud y Belleza': 'Otros'}


def rubro(cat, sub, name):
    sub = norm(sub)
    if cat == 'Agro, Rural y Campo':
        return 'Maquinaria agrícola y vial' if sub in ('maquinarias', 'equipamientos') else 'Campos y rurales'
    if cat == 'Vehículos':
        if sub == 'camiones': return 'Camiones y utilitarios'
        if sub == 'nautica': return 'Náutica'
        c = cat_from_text(name)
        return c if c in ('Autos y camionetas', 'Camiones y utilitarios', 'Maquinaria agrícola y vial', 'Motos',
                          'Náutica') else 'Autos y camionetas'
    if cat == 'Deportes y Fitness':
        return 'Bicicletas' if sub == 'ciclismo' else cat_from_text(name)
    if cat == 'Industrias y Oficinas':
        if sub == 'oficinas': return 'Muebles y oficina'
        c = cat_from_text(name)
        return c if c in ('Maquinaria industrial', 'Herramientas', 'Tecnología', 'Electro y hogar',
                          'Muebles y oficina') else 'Maquinaria industrial'
    if cat == 'Inmuebles' and sub == 'campos':
        return 'Campos y rurales'
    return CAT.get(cat) or cat_from_text(name)


def _fecha(s):
    return re.sub(r'\.\d+', '', s) if s else None  # quita microsegundos


def lote(r):
    src = r.get('source') or ''
    prov, dominio = PORTALES.get(src, (src.replace('_', ' ').title(), 'www.esubasta.ar'))
    name = r.get('name') or ''
    return {
        'id': 'es-' + r['slug'], 'src': 'esubasta', 'sub_src': src, 'prov': prov,
        'org': 'Venta privada en esubasta.ar' if src == PRIVADAS else f'Poder Judicial de {prov}',
        'title': sentence(name),
        'cat': rubro((r.get('category') or {}).get('name'), (r.get('subcategory') or {}).get('name'), name),
        'start': _fecha(r.get('start_date')), 'end': _fecha(r.get('end_date')),
        'price': r.get('price') or None, 'price_label': 'Precio',
        'cur': (r.get('currency') or {}).get('code') or 'ARS',
        'url': f"https://{dominio}{r.get('uri') or '/lote/' + r['slug'] + '/'}", 'img': r.get('mini_photo'),
    }


def lotes(max_paginas=150):
    url, vistos, out = API, set(), []
    for _ in range(max_paginas):
        d = get(url).json()
        for r in d.get('results', []):
            if r.get('slug') and r['slug'] not in vistos:
                vistos.add(r['slug'])
                out.append(lote(r))
        url = d.get('next')
        if not url:
            break
    return out
