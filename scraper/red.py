"""Acceso a la red: requests para JSON e imágenes, Chromium (Playwright) para portales con JavaScript."""
import logging
import time

import requests

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36')
log = logging.getLogger('red')

session = requests.Session()
session.headers.update({'User-Agent': UA, 'Accept-Language': 'es-AR,es;q=0.9'})


def get(url, tries=3, timeout=60, **kw):
    for i in range(tries):
        try:
            r = session.get(url, timeout=timeout, **kw)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            if i == tries - 1:
                raise
            log.warning('reintento %s (%s)', url, e)
            time.sleep(5 * (i + 1))


class Navegador:
    """Chromium headless. Bloquea imágenes y fuentes para cargar rápido."""

    def __enter__(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch()
        self.page = self._browser.new_page(user_agent=UA, locale='es-AR')
        self.page.route('**/*', lambda r: r.abort() if r.request.resource_type in ('image', 'media', 'font')
                        else r.continue_())
        return self

    def html(self, url, selector=None, timeout=90_000):
        """Devuelve el HTML ya renderizado; si se indica selector, espera a que aparezca."""
        self.page.goto(url, wait_until='domcontentloaded', timeout=timeout)
        if selector:
            self.page.wait_for_selector(selector, timeout=timeout)
        return self.page.content()

    def __exit__(self, *exc):
        self._browser.close()
        self._pw.stop()
