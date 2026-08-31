"""Extraer el SVG de un HTML de archify, con su CSS adentro.

POR QUÉ HACE FALTA. El CLI de archify escribe HTML y el export a SVG es un botón del visor,
en el browser. El HTML sí lleva SVG inline, pero **el estilo no está adentro**: las clases
(`a-*`, `c-*`, …) se definen en el `<style>` de la página. Extraer el `<svg>` pelado da un
diagrama sin colores ni tipografía.

Esto levanta las reglas de las clases que el SVG realmente usa y las embebe como `<style>`
dentro del propio SVG, así el archivo queda autocontenido y `_a_pdf.py` lo puede inlinear sin
arrastrar el CSS de la página.

    py _svg_de_archify.py <entrada.html> <salida.svg>
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# el CSS de la página trae reglas del visor (botones, paneles) que al SVG no le sirven
NO_SIRVEN = re.compile(r"^\s*(?:html|body|button|input|\.av-|\.viewer|@media|@supports|:root\s*\[)")


def clases_usadas(svg: str) -> set[str]:
    """Toda clase que aparece en un `class="..."` dentro del SVG."""
    return {c for attr in re.findall(r'class="([^"]+)"', svg) for c in attr.split()}


def reglas_de(css: str) -> list[tuple[str, str]]:
    """(selector, cuerpo) de cada regla de primer nivel, salteando las anidadas."""
    fuera: list[tuple[str, str]] = []
    i = 0
    while i < len(css):
        j = css.find("{", i)
        if j < 0:
            break
        prof, k = 1, j + 1
        while k < len(css) and prof:
            prof += (css[k] == "{") - (css[k] == "}")
            k += 1
        fuera.append((css[i:j].strip(), css[j + 1:k - 1].strip()))
        i = k
    return fuera


def extraer(html: Path, salida: Path, tema: str = "light") -> None:
    t = html.read_text(encoding="utf-8")

    m = re.search(r"<svg\b.*?</svg>", t, re.S)
    if not m:
        raise SystemExit(f"[!] {html.name} no tiene un <svg> inline")
    svg = m.group(0)

    usadas = clases_usadas(svg)
    css_pagina = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", t, re.S))

    guardadas, descartadas = [], 0
    for sel, cuerpo in reglas_de(css_pagina):
        if not sel or NO_SIRVEN.match(sel):
            descartadas += 1
            continue
        # se guarda la regla si alguno de sus selectores nombra una clase que el SVG usa,
        # o si es de elemento SVG puro (text, path, marker…) sin clase
        clases_sel = set(re.findall(r"\.([A-Za-z0-9_-]+)", sel))
        if clases_sel and not (clases_sel & usadas):
            descartadas += 1
            continue
        guardadas.append(f"{sel}{{{cuerpo}}}")

    # CDATA obligatorio: el SVG se parsea como XML, y el CSS trae `>` de selectores
    # descendientes y `&` de nada — sin envolver, aborta el documento entero
    cuerpo_css = "\n".join(guardadas).replace("]]>", "]] >")
    estilo = '<style type="text/css"><![CDATA[\n' + cuerpo_css + "\n]]></style>"
    # dos cosas que un <svg> inline no necesita en HTML y un `.svg` suelto sí:
    #   · `xmlns`, o el browser lo muestra como árbol XML sin estilo
    #   · el tema: el `:root` de archify trae los valores OSCUROS y el paper va en claro,
    #     así que se estampa `data-theme` en la raíz para que gane el bloque que corresponde
    abre = svg[:svg.index(">") + 1]
    if "xmlns=" not in abre:
        abre = abre[:-1] + (' xmlns="http://www.w3.org/2000/svg"'
                            ' xmlns:xlink="http://www.w3.org/1999/xlink">')
    if "data-theme=" not in abre:
        abre = abre[:-1] + f' data-theme="{tema}">'
    svg = abre + "\n" + estilo + svg[svg.index(">") + 1:]

    salida.write_text(svg, encoding="utf-8")
    vb = re.search(r'viewBox="([^"]+)"', svg)
    print(f"  {salida.name}: {len(svg) // 1024} KB · viewBox {vb.group(1) if vb else '?'}")
    print(f"  clases usadas por el SVG : {len(usadas)}")
    print(f"  reglas embebidas         : {len(guardadas)}  (descartadas {descartadas})")
    faltan = usadas - {c for r in guardadas for c in re.findall(r"\.([A-Za-z0-9_-]+)", r)}
    print(f"  clases sin regla         : {sorted(faltan) if faltan else 'ninguna'}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    extraer(Path(sys.argv[1]), Path(sys.argv[2]))
