"""Miniaturas: baja la primera foto de cada lote, la achica a 480 px y la sirve desde el propio sitio
(más rápido y sin depender de que los portales acepten enlaces directos)."""
import io
import logging
import os
import shutil
import time
from concurrent.futures import ThreadPoolExecutor

from PIL import Image

from .red import get

LADO, CALIDAD, DIAS_CACHE = 480, 72, 21
log = logging.getLogger('fotos')


def guardar(datos, destino):
    im = Image.open(io.BytesIO(datos))
    im.thumbnail((LADO, LADO))
    if im.mode != 'RGB':  # PNG con transparencia, paletas, webp: fondo blanco
        fondo = Image.new('RGB', im.size, 'white')
        fondo.paste(im.convert('RGBA'), mask=im.convert('RGBA').split()[-1])
        im = fondo
    im.save(destino, 'JPEG', quality=CALIDAD, optimize=True, progressive=True)


def miniaturas(lots, cache_dir, out_dir, red=True, workers=8):
    os.makedirs(cache_dir, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    ruta = lambda l: os.path.join(cache_dir, l['id'] + '.jpg')

    def bajar(l):
        try:
            guardar(get(l['img'], tries=2, timeout=40, headers={'Referer': l['url']}).content, ruta(l))
            return True
        except Exception as e:
            log.info('sin foto %s: %s', l['id'], e)
            return False

    pendientes = [l for l in lots if red and l.get('img') and not os.path.exists(ruta(l))]
    with ThreadPoolExecutor(workers) as ex:
        nuevas = sum(ex.map(bajar, pendientes))
    con_foto = 0
    for l in lots:
        if os.path.exists(ruta(l)):
            shutil.copy(ruta(l), os.path.join(out_dir, l['id'] + '.jpg'))
            l['thumb'] = f"img/{l['id']}.jpg"
            con_foto += 1
    # limpia fotos de lotes que ya no están publicados
    vigentes, limite = {l['id'] + '.jpg' for l in lots}, time.time() - DIAS_CACHE * 86400
    for f in os.listdir(cache_dir):
        p = os.path.join(cache_dir, f)
        if f not in vigentes and os.path.getmtime(p) < limite:
            os.remove(p)
    log.info('fotos: %d nuevas de %d pendientes, %d lotes con foto de %d', nuevas, len(pendientes), con_foto, len(lots))
    return con_foto
