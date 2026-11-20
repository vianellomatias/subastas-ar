"""Pruebas de los parsers con páginas reales recortadas (tests/fixtures)."""
import json
import os

from scraper import bancociudad, common, esubasta, judicial, precios

FIX = os.path.join(os.path.dirname(__file__), 'fixtures')


def leer(nombre):
    with open(os.path.join(FIX, nombre), encoding='utf-8') as f:
        return f.read()


def test_listado_csjn():
    lots = judicial.parse_listado(leer('csjn_listado.html'), 'csjn')
    assert len(lots) == 7
    assert {l['status'] for l in lots} == {'proxima', 'en_curso', 'finalizada', 'cancelada'}
    for l in lots:
        assert l['id'].startswith('csjn-') and l['url'].endswith(l['id'][5:])
        assert l['title'] and l['cat'] in common.CATS
        assert l['img'] is None or l['img'].startswith(judicial.PORTALES['csjn'] + '/AuctionImages/')
    en_curso = [l for l in lots if l['status'] == 'en_curso']
    assert all(l['end'] and l['end'].endswith('-03:00') for l in en_curso)
    usd = next(l for l in lots if l['id'] == 'csjn-440')
    assert usd['cur'] == 'USD' and not usd['title'].upper().startswith('EN D') and usd['cat'] == 'Inmuebles'


def test_listado_scba():
    lots = judicial.parse_listado(leer('scba_listado.html'), 'scba')
    assert len(lots) == 5
    assert all(l['prov'] == 'Buenos Aires' and l['org'].startswith('Poder Judicial de Buenos Aires') for l in lots)
    assert any(l['cur'] == 'USD' for l in lots)
    assert any(l['bid'] for l in lots if l['status'] == 'en_curso') or all(
        l['bid_text'] for l in lots if l['status'] == 'en_curso')


def test_ficha_judicial():
    d = judicial.parse_detalle(leer('judicial_detalle.html'))
    assert d['start'] == '2026-11-20T11:00:00-03:00'
    assert d['end'] == '2026-12-04T14:30:00-03:00'  # 02:30 PM
    assert d['price'] == 130000 and d['price_label'] == 'Precio de reserva' and d['cur'] == 'USD'
    assert d['court'].startswith('JUZGADO NACIONAL') and d['court'].endswith('N° 7')
    assert d['auctioneer'] == 'MARIANO MANUEL ESPINA RAWSON'
    assert 'Rafaela Santa Fe' in d['place'] and 'Requiere' not in d['place']
    assert common.prov_from_text(d['place'], 'CABA') == 'Santa Fe'


def test_esubasta():
    data = json.loads(leer('esubasta_pagina.json'))
    auto, bici = (esubasta.lote(r) for r in data['results'])
    assert auto['id'] == 'es-fiat-cronos-estile-13-gse-bz-cgns-2023--l8x'
    assert auto['prov'] == 'La Pampa' and auto['org'] == 'Poder Judicial de La Pampa'
    assert auto['url'] == 'https://subastas.justicialapampa.gob.ar/lote/fiat-cronos-estile-13-gse-bz-cgns-2023--l8x/'
    assert auto['end'] == '2026-11-24T10:00:00-03:00' and auto['price'] == 11000000 and auto['cur'] == 'ARS'
    assert auto['cat'] == 'Autos y camionetas' and auto['img'].endswith('.webp')
    assert bici['cat'] == 'Bicicletas' and bici['prov'] == 'Privadas (esubasta)' and bici['img'] is None
    assert bici['url'].startswith('https://www.esubasta.ar/lote/')


def test_banco_ciudad():
    subs = bancociudad.parse_home(leer('bc_home.html'))
    assert len(subs) == 3 and [s['finalizada'] for s in subs] == [False, False, True]
    s = subs[0]
    assert s['nro'] == '4008' and s['nlots'] == 36 and s['cur'] == 'ARS'
    assert s['start'] == '2026-11-20T11:00:00-03:00' and s['end'] == '2026-11-20T17:00:00-03:00'
    lotes = bancociudad.parse_lotes(leer('bc_subasta.html'))
    assert lotes[0] == ('145037', 'CUATRO COMPUTADORAS DE ESCRITORIO MARCA LENOVO, MODELOS V520S-08IKL, V...',
                        291214.0, 58242.8)
    assert len(lotes) == 3


def test_clave_de_vehiculo():
    c = precios.clave
    assert c('Automotor- toyota hilux 4x2 cabina simple dx 2.5td cabina- pick-up- año 2009')[:3] == ('toyota', 'hilux', 2009)
    assert 'dx' in c('Automotor- toyota hilux 4x2 cabina simple dx 2.5td cabina- pick-up- año 2009')[3]
    assert c('Automotor- toyota hilux sw4 4x4 srv 3.0 tdia/t c/cuero- todo terreno- año 2007')[:3] == ('toyota', 'sw4', 2007)
    assert c('Automotor peugeot modelo 2008 allure 1.6 115, sedan 5 ptas. modelo 2019')[:3] == ('peugeot', '2008', 2019)
    assert c('PEUGEOT 208 AÑO 2024')[:3] == ('peugeot', '208', 2024)
    assert c('Automotor volkswagen tipo pick up cabina simple, modelo saveiro 1.6, año 2017')[:3] == ('volkswagen', 'saveiro', 2017)
    assert c('VW GOL Trendline 1.6 gas 101 CV MQ Sedan 5 P año: 2021')[:3] == ('volkswagen', 'gol', 2021)
    assert c('AUTOMOTOR- CHEVROLET S10 2.8TDI STD 4x2 ELECTRONIC- PICK UP- CABINA DOBLE- AÑO 2010')[:3] == ('chevrolet', 's-10', 2010)
    assert c('Automotor marca VOLKSWAGEN, modelo CROSSFOX M2014')[:3] == ('volkswagen', 'crossfox', 2014)
    assert c('Camión c/ cabina -mercedes benz-l 1218 r- año 1998') is None
    assert c('Volvo S60 D5 año 2007') is None


def test_avisos_autocosmos():
    av = precios.parse_avisos(leer('autocosmos.html'), 'corolla', 2018)
    assert len(av) == 5  # sin duplicados, sin el 2017, sin el Audi ni los precios sueltos
    r = precios.resumen(av)
    assert r == {'lo': 25000000, 'med': 26250000.0, 'hi': 28000000, 'cur': 'ARS', 'n': 4}


def test_utilidades():
    assert common.money('$ 1.234.567,89') == 1234567.89
    assert common.money('U$S 130.000,00') == 130000
    assert common.sentence('FORD KA FLY') == 'Ford ka fly'
    assert common.cat_from_text('Lote baldío - Sierra de los Padres') == 'Inmuebles'
