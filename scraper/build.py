"""Arma el sitio en _site/ juntando todas las fuentes.

    python -m scraper.build            # corrida completa (la usa GitHub Actions)
    python -m scraper.build --sin-red  # solo con lo guardado en cache/ (para probar la página)

Si una fuente falla, se publica su última versión buena y la página lo avisa."""
import argparse
import glob
import json
import logging
import os
import shutil
import time
from datetime import datetime, timezone

from . import bancociudad, esubasta, fotos, judicial, precios

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE, SITE, OUT = (os.path.join(RAIZ, d) for d in ('cache', 'site', '_site'))
log = logging.getLogger('build')


def leer(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def escribir(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(obj, f, ensure_ascii=False, separators=(',', ':'))


def fuente(nombre, fn, estado):
    """Corre una fuente; si falla o viene vacía, devuelve la última versión buena."""
    path = os.path.join(CACHE, 'fuentes', nombre + '.json')
    try:
        lots = fn()
        if not lots:
            raise RuntimeError('no devolvió lotes')
        escribir(path, {'t': time.time(), 'lots': lots})
        estado[nombre] = {'ok': True, 'n': len(lots), 't': time.time()}
        return lots
    except Exception as e:
        log.exception('falló la fuente %s', nombre)
        prev = leer(path, {})
        estado[nombre] = {'ok': False, 'error': str(e)[:200], 'n': len(prev.get('lots', [])), 't': prev.get('t')}
        return prev.get('lots', [])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sin-red', action='store_true', help='usar solo lo guardado en cache/')
    sin_red = ap.parse_args().sin_red
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')

    estado, lots = {}, []
    if sin_red:
        for path in sorted(glob.glob(os.path.join(CACHE, 'fuentes', '*.json'))):
            prev = leer(path, {})
            nombre = os.path.basename(path)[:-5]
            lots += prev.get('lots', [])
            estado[nombre] = {'ok': True, 'n': len(prev.get('lots', [])), 't': prev.get('t')}
        judicial.detalles(None, lots, leer(os.path.join(CACHE, "detalles.json"), {}))
    else:
        from .red import Navegador
        with Navegador() as nav:
            for src in judicial.PORTALES:
                lots += fuente(src, lambda: judicial.listado(nav, src), estado)
            cache_fichas = leer(os.path.join(CACHE, 'detalles.json'), {})
            judicial.detalles(nav, lots, cache_fichas)
            escribir(os.path.join(CACHE, 'detalles.json'), cache_fichas)
            lots += fuente('bancociudad', lambda: bancociudad.lotes(nav), estado)
        lots += fuente('esubasta', esubasta.lotes, estado)

    shutil.rmtree(OUT, ignore_errors=True)
    shutil.copytree(SITE, OUT)
    n_fotos = fotos.miniaturas(lots, os.path.join(CACHE, 'fotos'), os.path.join(OUT, 'img'), red=not sin_red)
    n_precios = precios.estimar(lots, os.path.join(CACHE, 'precios.json'),
                                os.path.join(RAIZ, 'data', 'precios_manual.json'), red=not sin_red)
    lots = [{k: v for k, v in l.items() if v not in (None, '') and k != 'img'} for l in lots]
    ahora = datetime.now(timezone.utc)
    meta = {'generado': ahora.isoformat(timespec='seconds'), 'lotes': len(lots), 'fotos': n_fotos,
            'precios': n_precios, 'fuentes': estado}
    escribir(os.path.join(OUT, 'data', 'lots.json'), lots)
    escribir(os.path.join(OUT, 'data', 'meta.json'), meta)
    with open(os.path.join(RAIZ, 'ultima_actualizacion.txt'), 'w') as f:  # un commit por día mantiene vivo el cron
        f.write(ahora.date().isoformat() + '\n')
    log.info('listo: %d lotes, %d con foto, %d con precio de referencia, fuentes: %s', len(lots), n_fotos,
             n_precios, {k: (v['ok'], v['n']) for k, v in estado.items()})
    caidas = [k for k, v in estado.items() if not v['ok'] and not v['n']]
    if len(caidas) == len(estado):
        raise SystemExit('ninguna fuente respondió y no hay datos guardados')


if __name__ == '__main__':
    main()
