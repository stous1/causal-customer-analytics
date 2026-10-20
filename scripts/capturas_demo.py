"""Capturas y GIF de ``docs/demo.html`` con Playwright (usa el Chrome instalado).

Uso:
    uv run python scripts/capturas_demo.py   # -> docs/resultados/demo/*.png y placebo.gif

Sirve ``docs/`` en un puerto local, abre la página en escritorio y en celular (390 px),
**falla si hay errores de consola o desborde horizontal**, toma capturas de las dos pestañas
y graba la animación del placebo de adelanto como GIF.
"""

import functools
import http.server
import io
import sys
import threading

from PIL import Image
from playwright.sync_api import sync_playwright

from causal.rutas import DOCS, DOCS_RESULTADOS

SALIDA = DOCS_RESULTADOS / "demo"


def _servidor() -> tuple[http.server.ThreadingHTTPServer, int]:
    class Silencioso(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args: object) -> None:
            pass

    manejador = functools.partial(Silencioso, directory=str(DOCS))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), manejador)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def main() -> int:
    srv, puerto = _servidor()
    url = f"http://127.0.0.1:{puerto}/demo.html"
    errores: list[str] = []
    SALIDA.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        nav = p.chromium.launch(channel="chrome")
        for nombre, vista, escala in (
            ("escritorio", {"width": 1200, "height": 900}, 1),
            ("celular", {"width": 390, "height": 844}, 2),
        ):
            pag = nav.new_page(viewport=vista, device_scale_factor=escala, color_scheme="light")
            pag.on("console", lambda m: errores.append(m.text) if m.type == "error" else None)
            pag.on("pageerror", lambda e: errores.append(str(e)))
            pag.goto(url)
            pag.wait_for_selector("#anim")
            pag.wait_for_timeout(6500)
            desborde = pag.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
            if desborde:
                errores.append(f"{nombre}: desborde horizontal")
            pag.screenshot(path=str(SALIDA / f"{nombre}_predice_causa.png"), full_page=True)
            pag.click("#tab-sim")
            pag.wait_for_timeout(500)
            desborde = pag.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
            if desborde:
                errores.append(f"{nombre} (simulador): desborde horizontal")
            pag.screenshot(path=str(SALIDA / f"{nombre}_simulador.png"), full_page=True)
            pag.close()

        # GIF de la animación: fotogramas de la tarjeta del placebo
        pag = nav.new_page(
            viewport={"width": 760, "height": 900}, device_scale_factor=1, color_scheme="light"
        )
        pag.goto(url)
        tarjeta = pag.wait_for_selector(".anim-tarjeta")
        tarjeta.scroll_into_view_if_needed()
        pag.click("#anim-repetir")
        cuadros, duraciones = [], []
        for i in range(60):
            cuadros.append(Image.open(io.BytesIO(tarjeta.screenshot())).convert("RGB"))
            duraciones.append(120)
            pag.wait_for_timeout(100)
            if i == 59:
                duraciones[-1] = 2500
        cuadros[0].save(
            SALIDA / "placebo.gif",
            save_all=True,
            append_images=cuadros[1:],
            duration=duraciones,
            loop=0,
            optimize=True,
        )
        cuadros[-1].save(SALIDA / "placebo.png")
        nav.close()
    srv.shutdown()
    for e in errores:
        print("ERROR:", e)
    print(f"capturas en {SALIDA}; {len(errores)} errores")
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
