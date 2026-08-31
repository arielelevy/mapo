"""El flujo de control del Algoritmo 1, en SVG. Estilo de paper de sistemas, no de estadística.

POR QUÉ ESTA FIGURA Y NO OTRA. El Algoritmo 1 tiene una propiedad que el pseudocódigo enuncia
y no muestra: **de sus quince líneas, dos llaman al modelo y trece no**. En una lista numerada
eso hay que contarlo; en un diagrama de flujo con la frontera dibujada se ve. Y esa frontera es
la tesis del paper, así que merece una figura y no un párrafo.

POR QUÉ ESCRITA A MANO Y NO CON UNA LIBRERÍA DE GRÁFICOS. Las figuras de datos de este paper
salen de `matplotlib` porque hay un registro detrás y si el registro cambia, la figura cambia.
Ésta es **control de flujo**: no tiene ejes, no tiene escala, y pelear con una librería
estadística para dibujar cajas y rombos cuesta más código y da un resultado peor. Es un
generador y no un `.svg` suelto para que las coordenadas se deriven de la declaración de nodos
en vez de escribirse treinta veces a mano.

LA CONVENCIÓN, y es la de un paper de sistemas: rectángulo = paso determinista, rombo =
decisión del código, rectángulo de borde grueso sobre fondo distinto = llamada al sensor,
terminador redondeado = salida. Cada nodo lleva el número de línea del algoritmo.

Corre DESDE `lab/`:  py bench/analysis/_diagrama_algoritmo.py
"""

from __future__ import annotations

import html
from pathlib import Path

SALIDA = Path("../whitepaper/figuras/algoritmo-1-flujo.svg")

W, H = 940, 620
TINTA, GRIS, SUAVE = "#22252a", "#6b7178", "#c9ccd1"
AZUL, GRANATE, VERDE = "#2c5c8f", "#b5495b", "#2e8b6f"
F_CODIGO, F_SENSOR = "#f5f7fa", "#fdf4f5"
MONO = "Consolas, 'SF Mono', Menlo, monospace"


def caja(x, y, w, h, ln, texto, sub="", color=AZUL, relleno="#ffffff", grueso=False):
    o = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" fill="{relleno}" '
         f'stroke="{color}" stroke-width="{2.4 if grueso else 1.5}"/>']
    if ln:
        o.append(f'<text x="{x + 7}" y="{y + 15}" font-family="{MONO}" font-size="10" '
                 f'fill="{GRIS}">{ln}</text>')
    o.append(f'<text x="{x + w / 2}" y="{y + (20 if sub else h / 2 + 4)}" '
             f'text-anchor="middle" font-size="12.5" fill="{TINTA}">{html.escape(texto)}</text>')
    if sub:
        o.append(f'<text x="{x + w / 2}" y="{y + 36}" text-anchor="middle" font-size="10" '
                 f'font-family="{MONO}" fill="{GRIS}">{html.escape(sub)}</text>')
    return "\n".join(o)


def rombo(cx, cy, w, h, ln, texto, color=AZUL):
    p = f"{cx},{cy - h / 2} {cx + w / 2},{cy} {cx},{cy + h / 2} {cx - w / 2},{cy}"
    return (f'<polygon points="{p}" fill="#ffffff" stroke="{color}" stroke-width="1.5"/>'
            f'<text x="{cx}" y="{cy + 4}" text-anchor="middle" font-size="11.5" '
            f'fill="{TINTA}">{html.escape(texto)}</text>'
            f'<text x="{cx - w / 2 + 6}" y="{cy - h / 2 + 14}" font-family="{MONO}" '
            f'font-size="10" fill="{GRIS}">{ln}</text>')


def term(cx, cy, w, h, texto, color):
    return (f'<rect x="{cx - w / 2}" y="{cy - h / 2}" width="{w}" height="{h}" rx="{h / 2}" '
            f'fill="#ffffff" stroke="{color}" stroke-width="1.8"/>'
            f'<text x="{cx}" y="{cy + 4}" text-anchor="middle" font-size="12" '
            f'font-weight="600" fill="{color}">{html.escape(texto)}</text>')


def flecha(x1, y1, x2, y2, etq="", color=GRIS, lado="der"):
    o = [f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" '
         f'stroke-width="1.5" marker-end="url(#p)"/>']
    if etq:
        dx = 7 if lado == "der" else -7
        o.append(f'<text x="{(x1 + x2) / 2 + dx}" y="{(y1 + y2) / 2 + 4}" '
                 f'text-anchor="{"start" if lado == "der" else "end"}" font-size="10" '
                 f'font-style="italic" fill="{color}">{html.escape(etq)}</text>')
    return "\n".join(o)


def main() -> None:
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" '
         f'height="{H}" font-family="Segoe UI, Helvetica, Arial, sans-serif">',
         f'<defs><marker id="p" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" '
         f'markerHeight="6" orient="auto-start-reverse">'
         f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{GRIS}"/></marker></defs>',
         f'<rect width="{W}" height="{H}" fill="#ffffff"/>']

    p.append(f'<text x="16" y="26" font-size="15.5" font-weight="600" fill="{TINTA}">'
             'Algoritmo 1 — dos de quince líneas llaman al modelo</text>')
    p.append(f'<text x="16" y="44" font-size="11" fill="{GRIS}">'
             'el carril inferior es el sensor: emite proposiciones y nunca decide '
             'el flujo</text>')

    # carriles
    p.append(f'<rect x="14" y="58" width="{W - 28}" height="392" rx="8" fill="{F_CODIGO}" '
             f'stroke="{SUAVE}"/>')
    p.append(f'<rect x="14" y="462" width="{W - 28}" height="118" rx="8" fill="{F_SENSOR}" '
             f'stroke="{SUAVE}"/>')
    p.append(f'<text x="26" y="76" font-size="10.5" font-weight="700" fill="{AZUL}">'
             'CÓDIGO — determinista</text>')
    p.append(f'<text x="26" y="480" font-size="10.5" font-weight="700" fill="{GRANATE}">'
             'SENSOR — el modelo</text>')

    # fila 1: preparacion
    y1 = 92
    p.append(caja(36, y1, 176, 48, "1-2", "leer q", "n ← saltos, e ← sujeto"))
    p.append(caja(252, y1, 176, 48, "3", "elegir índice", "entidad ⇒ léxico"))
    p.append(caja(468, y1, 176, 48, "4", "resolver ancla", "sin llamar al modelo"))
    p.append(rombo(772, y1 + 24, 150, 60, "5", "¿ancla?"))
    for a, b in ((212, 252), (428, 468), (644, 697)):
        p.append(flecha(a, y1 + 24, b, y1 + 24))

    # fila 2: el bucle
    y2 = 200
    p.append(rombo(772, y2 + 26, 150, 62, "7", "¿i ≤ n?"))
    p.append(caja(468, y2, 176, 52, "8", "leer unidad", "τ ← leer(u)"))
    p.append(caja(252, y2, 176, 52, "10-11", "tipar y rutear", "ρ ← entidad(ρ); ι ← índice(ρ)"))
    p.append(caja(36, y2, 176, 52, "12", "buscar y filtrar", "hit que NOMBRA a ρ"))
    p.append(flecha(772, y1 + 54, 772, y2 - 5, "sí", "der"))
    p.append(flecha(697, y2 + 26, 644, y2 + 26))
    p.append(flecha(468, y2 + 26, 428, y2 + 26))
    p.append(flecha(252, y2 + 26, 212, y2 + 26))

    y3 = 306
    p.append(rombo(124, y3 + 26, 160, 60, "13", "¿hit?"))
    p.append(flecha(124, y2 + 52, 124, y3 - 4))
    # vuelta del bucle
    p.append(f'<path d="M 204 {y3 + 26} L 700 {y3 + 26} L 700 {y2 + 90} L 772 {y2 + 90} '
             f'L 772 {y2 + 88}" fill="none" stroke="{GRIS}" stroke-width="1.5" '
             f'marker-end="url(#p)"/>')
    p.append(f'<text x="440" y="{y3 + 20}" text-anchor="middle" font-size="10" '
             f'font-style="italic" fill="{GRIS}">sí · i ← i+1</text>')

    # ── salidas, y el cableado es la mitad de lo que la figura afirma ─────────
    # ABSTENER tiene DOS entradas (ancla sin resolver, salto sin resolver) y el valor pedido
    # UNA sola, que pasa por el sensor. Cablearlo al reves haria que la figura dijera que se
    # responde sin llegar, que es exactamente lo contrario del algoritmo.
    p.append(term(124, 410, 168, 34, "ABSTENER", GRANATE))
    p.append(flecha(124, y3 + 56, 124, 393, "no", "izq"))
    # ancla irresoluble: baja por el borde derecho y entra a ABSTENER por la derecha
    p.append(f'<path d="M 847 {y1 + 24} L 906 {y1 + 24} L 906 452 L 124 452 L 124 427" '
             f'fill="none" stroke="{GRANATE}" stroke-width="1.5" marker-end="url(#p)"/>')
    p.append(f'<text x="898" y="{y1 + 18}" text-anchor="end" font-size="10" '
             f'font-style="italic" fill="{GRANATE}">no</text>')

    # EL SENSOR FINAL VA DEBAJO DE SU SALIDA, no en el medio. La primera disposicion los
    # cruzaba: la linea del sensor 15 pasaba por encima de la de tau y la de rho, y un
    # diagrama de flujo con lineas que se cruzan sin necesidad se lee mal aunque este bien.
    p.append(caja(700, 496, 190, 56, "15", "¿cuál es el valor?", "sobre camino[n]",
                  GRANATE, "#ffffff", grueso=True))
    p.append(term(795, 410, 190, 34, "valor pedido", VERDE))
    # el bucle termina -> el CODIGO elige la unidad -> el sensor la lee
    p.append(f'<path d="M 772 {y2 + 57} L 772 344 L 700 344 L 700 470 L 740 470 L 740 496" '
             f'fill="none" stroke="{GRIS}" stroke-width="1.5" marker-end="url(#p)"/>')
    p.append(f'<text x="766" y="336" text-anchor="end" font-size="10" font-style="italic" '
             f'fill="{GRIS}">no · i &gt; n · camino[n]</text>')
    p.append(f'<path d="M 850 496 L 850 427" fill="none" stroke="{GRANATE}" '
             f'stroke-width="1.5" marker-end="url(#p)"/>')

    # el sensor del salto: baja de «leer unidad» y vuelve a «tipar y rutear»
    p.append(caja(468, 496, 176, 56, "9", "¿hacia dónde sigue?", "una proposición",
                  GRANATE, "#ffffff", grueso=True))
    p.append(f'<path d="M 578 {y2 + 52} L 578 496" fill="none" stroke="{GRANATE}" '
             f'stroke-width="1.5" marker-end="url(#p)"/>')
    p.append(f'<path d="M 468 512 L 340 512 L 340 {y2 + 52}" fill="none" stroke="{GRANATE}" '
             f'stroke-width="1.5" marker-end="url(#p)"/>')
    p.append(f'<text x="584" y="478" font-size="10" font-style="italic" '
             f'fill="{GRANATE}">τ  el texto</text>')
    p.append(f'<text x="346" y="478" font-size="10" font-style="italic" '
             f'fill="{GRANATE}">ρ  la proposición</text>')

    p.append(f'<text x="16" y="{H - 16}" font-size="10.5" fill="{GRIS}">'
             'Las líneas 3 y 11 aplican la regla de creencias; la 10 tipa la salida del '
             'sensor; la 7 pone el largo bajo control del código; la 4 resuelve el ancla '
             'sin preguntar.</text>')
    p.append("</svg>")

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text("\n".join(p), encoding="utf-8")
    print(f"ok  {SALIDA.name}  ({SALIDA.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
