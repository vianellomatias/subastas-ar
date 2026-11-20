# Subastas Argentina

Buscador unificado de remates judiciales y oficiales de Argentina. Junta en una sola página los lotes de varios portales, con foto, fechas, estado (próxima, en curso, finalizada), base, cómo participar y un precio de referencia de mercado para vehículos, máquinas y herramientas.

La página se actualiza sola cada 2 horas con GitHub Actions y se publica en GitHub Pages.

## Fuentes

| Fuente | Cómo se lee |
|---|---|
| Poder Judicial de la Nación (CSJN) | Listado y ficha de cada lote, con Chromium (Playwright) |
| Poder Judicial de Buenos Aires (SCBA) | Igual que la CSJN (mismo software) |
| Portales judiciales de Córdoba, Salta, Entre Ríos, La Pampa, San Juan, Chaco, San Luis y Jujuy, y ventas privadas de esubasta.ar | API pública de la plataforma esubasta |
| Banco Ciudad (incluye remates de ARCA y otros organismos) | Portada y páginas de cada subasta, con Chromium; un aviso por lote |

Precio de referencia:
- Vehículos: avisos de usados en Autocosmos para la misma marca, modelo y año (se renuevan cada 7 días).
- Resto: referencias cargadas a mano en `data/precios_manual.json`.
- MercadoLibre no se usa porque bloquea la lectura automática de sus listados.

Pendientes: Mendoza (portal propio, hoy sin lotes), Tucumán, AABE y boletines oficiales. Río Negro no tiene portal: publica los remates por edicto.

## Puesta en marcha (una sola vez)

1. Settings → Pages → Build and deployment → Source: **GitHub Actions**.
2. Actions → "Actualizar subastas" → **Run workflow** para la primera corrida (tarda unos 20 minutos porque baja todas las fotos; después, 3 a 5).
3. La página queda en `https://<usuario>.github.io/subastas-ar/`.

## Cómo funciona

```
scraper/
  red.py          requests (JSON, fotos) y Chromium headless (portales con JavaScript)
  judicial.py     CSJN y SCBA: listado + ficha (fechas, base, juzgado, martillero, exhibición)
  esubasta.py     portales provinciales y ventas privadas
  bancociudad.py  subastas y sus lotes
  fotos.py        primera foto de cada lote, achicada a 480 px y servida desde el sitio
  precios.py      precio de referencia (Autocosmos + data/precios_manual.json)
  build.py        junta todo en _site/ (index.html, data/lots.json, data/meta.json, img/)
site/index.html   la página (HTML, CSS y JS sin dependencias)
tests/            pruebas de los parsers con páginas reales recortadas
```

- Si una fuente falla, se publica su última versión buena y la tabla "Fuentes y cobertura" lo muestra.
- Entre corridas se guardan en la caché de Actions las fotos, las fichas de lotes y los precios, así cada actualización solo baja lo nuevo.
- Los estados y las cuentas regresivas se recalculan en el navegador con la hora actual.

## Probar en la computadora

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m playwright install chromium
python -m pytest -q                 # parsers
python -m scraper.build             # corrida completa → _site/
python -m http.server -d _site 8000 # abrir http://localhost:8000
```

`python -m scraper.build --sin-red` arma el sitio solo con lo que haya en `cache/`, sin conectarse.

## Agregar una referencia de precio a mano

En `data/precios_manual.json`, un objeto por grupo de lotes:

```json
{"ids": ["csjn-614"], "q": "Cosechadora New Holland CR6.80, 2020 a 2022", "lo": 260000, "med": 265000,
 "hi": 270000, "cur": "USD", "n": 2, "url": "https://…", "kind": "avisos usados", "fuente": "Agroads",
 "fecha": "2026-11-19"}
```

Se usa solo si el lote no tiene una referencia automática.

Agregador independiente, sin relación con los organismos que publican los remates. Antes de ofertar, leé el edicto en el portal oficial.
