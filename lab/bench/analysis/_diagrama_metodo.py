"""El diagrama del método determinista, en SVG escrito a mano. Cero llamadas al modelo.

POR QUÉ NO ES UNA FIGURA DE MATPLOTLIB. Las otras nueve figuras del paper son DATOS: hay un
registro detrás y si el registro cambia, la figura cambia. Ésta es una **arquitectura**, y
dibujarla con una librería de gráficos estadísticos obliga a pelear con ejes que no existen.
Un SVG escrito a mano es menos código, se lee, y no tiene una capa de abstracción en el medio
que decida por su cuenta dónde va cada caja.

POR QUÉ ES UN GENERADOR Y NO UN `.svg` SUELTO. Porque las coordenadas se derivan de una
declaración de filas y cajas, así que agregar una etapa no obliga a recalcular a mano treinta
números. El archivo generado es el artefacto; esta declaración es la fuente.

QUÉ TIENE QUE MOSTRAR, y es lo único que importa del diagrama: **dónde está la frontera entre
lo que decide el código y lo que emite el modelo**. Todo el paper gira alrededor de esa línea,
y en prosa se pierde. Acá es una línea, literalmente.

Corre DESDE `lab/`:  py bench/analysis/_diagrama_metodo.py
"""

from __future__ import annotations

import html
from pathlib import Path

SALIDA = Path("../whitepaper/figuras/metodo-determinista.svg")

W, H = 980, 560
TINTA, GRIS, SUAVE = "#22252a", "#6b7178", "#d8dbdf"
AZUL, VERDE, GRANATE = "#3b6ea5", "#2e8b6f", "#b5495b"
FONDO_CODIGO, FONDO_SENSOR = "#f4f7fa", "#fdf5f6"


def caja(x, y, w, h, titulo, sub, color, relleno="#ffffff", punteada=False) -> str:
    lineas = []
    dash = ' stroke-dasharray="5 4"' if punteada else ""
    lineas.append(
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="7" fill="{relleno}" '
        f'stroke="{color}" stroke-width="1.8"{dash}/>')
    lineas.append(
        f'<text x="{x + w / 2}" y="{y + 21}" text-anchor="middle" font-size="13.5" '
        f'font-weight="600" fill="{TINTA}">{html.escape(titulo)}</text>')
    for i, s in enumerate(sub):
        lineas.append(
            f'<text x="{x + w / 2}" y="{y + 39 + i * 14}" text-anchor="middle" '
            f'font-size="9.8" fill="{GRIS}">{html.escape(s)}</text>')
    return "\n".join(lineas)


def flecha(x1, y1, x2, y2, color=GRIS, etiqueta="", lado="der") -> str:
    s = (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" '
         f'stroke-width="1.7" marker-end="url(#punta)"/>')
    if etiqueta:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        dx = 8 if lado == "der" else -8
        anc = "start" if lado == "der" else "end"
        s += (f'<text x="{mx + dx}" y="{my + 4}" text-anchor="{anc}" font-size="10" '
              f'font-style="italic" fill="{color}">{html.escape(etiqueta)}</text>')
    return s


def main() -> None:
    p = []
    p.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
             f'width="{W}" height="{H}" font-family="Segoe UI, Helvetica, Arial, sans-serif">')
    p.append('<defs><marker id="punta" viewBox="0 0 10 10" refX="9" refY="5" '
             'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
             f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{GRIS}"/></marker></defs>')
    p.append(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')

    # ── LOS DOS CARRILES, y la línea entre ellos es la tesis ────────────────────
    p.append(f'<rect x="16" y="52" width="{W - 32}" height="330" rx="10" '
             f'fill="{FONDO_CODIGO}" stroke="{SUAVE}"/>')
    p.append(f'<rect x="16" y="392" width="{W - 32}" height="120" rx="10" '
             f'fill="{FONDO_SENSOR}" stroke="{SUAVE}"/>')
    p.append(f'<text x="30" y="74" font-size="11.5" font-weight="700" fill="{AZUL}">'
             'LO QUE DECIDE EL CÓDIGO — determinista, contable, auditable</text>')
    p.append(f'<text x="30" y="414" font-size="11.5" font-weight="700" fill="{GRANATE}">'
             'LO QUE EMITE EL MODELO — sensor: proposiciones, nunca flujo de control</text>')

    p.append(f'<text x="16" y="30" font-size="17" font-weight="600" fill="{TINTA}">'
             'Cómo se decide un request</text>')
    p.append(f'<text x="16" y="46" font-size="11" fill="{GRIS}">'
             'la frontera entre los dos carriles es la única decisión de diseño que el '
             'registro muestra que importa</text>')

    # ── fila 1: sensores → creencias ────────────────────────────────────────────
    y1 = 88
    p.append(caja(34, y1, 196, 74, "1 · sensores", [
        "forma cerrada sobre la pregunta", "y el material · sin modelo"], AZUL))
    # La escalera va en DOS renglones: en uno solo se desborda la caja, y una etiqueta que
    # sale de su recuadro se lee como si perteneciera a la de al lado.
    p.append(caja(266, y1, 196, 74, "2 · creencias tipadas", [
        "con procedencia, de menor a mayor:",
        "ASSUMED · ELICITED · OBSERVED · COMPUTED"], AZUL))
    p.append(caja(498, y1, 196, 74, "3 · portón de factibilidad", [
        "aritmética pura:", "¿entra en el presupuesto?"], AZUL))
    p.append(caja(730, y1, 216, 74, "4 · capacidades exigidas", [
        "ontología de la pregunta →", "capacidades, no paradigmas"], AZUL))
    for x in (230, 462, 694):
        p.append(flecha(x, y1 + 37, x + 36, y1 + 37))

    # ── fila 2: candidatos → dial → ruteo ───────────────────────────────────────
    y2 = 208
    p.append(caja(730, y2, 216, 74, "5 · brazos candidatos", [
        "los que tienen TODAS", "las capacidades exigidas"], AZUL))
    p.append(caja(498, y2, 196, 74, "6 · dial de garantía", [
        "A0–A3 · lo declara el caller,", "jamás se infiere del texto"], AZUL))
    p.append(caja(266, y2, 196, 74, "7 · elegir o abstenerse", [
        "entre los que empatan,", "el más barato"], AZUL))
    p.append(caja(34, y2, 196, 74, "8 · EXPLAIN", [
        "qué se creyó, con qué", "procedencia, y qué se podó"], AZUL))
    p.append(flecha(838, y1 + 74, 838, y2, GRIS))
    for x in (730, 498, 266):
        p.append(flecha(x, y2 + 37, x - 36, y2 + 37))

    # ── fila 3: el bucle de ejecución, con la frontera ──────────────────────────
    y3 = 314
    p.append(caja(266, y3, 428, 52, "el brazo elegido ejecuta", [
        "el CÓDIGO lleva el bucle: cuántas vueltas, qué índice, cuándo parar"],
        VERDE, punteada=False))
    p.append(flecha(132, y2 + 74, 132, y3 + 26, GRIS))
    p.append(f'<line x1="132" y1="{y3 + 26}" x2="266" y2="{y3 + 26}" stroke="{GRIS}" '
             f'stroke-width="1.7" marker-end="url(#punta)"/>')

    y4 = 432
    p.append(caja(266, y4, 196, 62, "extraer un hecho", [
        "«¿qué dice esta unidad?»"], GRANATE))
    p.append(caja(498, y4, 196, 62, "proponer el próximo paso", [
        "«¿a dónde sigue el rastro?»"], GRANATE))
    p.append(flecha(364, y3 + 52, 364, y4, GRANATE, "pregunta", "izq"))
    p.append(flecha(596, y4, 596, y3 + 52, GRANATE, "proposición", "der"))

    # LA GUARDA QUE CIERRA EL CICLO, y es el resultado del 2026-08-30.
    p.append(caja(730, y4 - 6, 216, 74, "la salida se TIPA", [
        "«M. Arrieta settlement account»", "→ entidad: M. Arrieta"], GRANATE,
        relleno="#ffffff"))
    p.append(flecha(694, y4 + 25, 730, y4 + 25, GRANATE))
    p.append(f'<path d="M 838 {y4 - 6} L 838 {y3 + 78} L 694 {y3 + 78} L 694 {y3 + 52}" '
             f'fill="none" stroke="{GRANATE}" stroke-width="1.7" marker-end="url(#punta)"/>')

    p.append(f'<text x="16" y="{H - 14}" font-size="10.5" fill="{GRIS}">'
             'Una decisión que cruza al carril de abajo se lleva el determinismo con ella: '
             'medido, el ancla de una caminata elegida por el modelo dio '
             'u=1,000 / 0,000 / 0,000 con la misma huella.</text>')
    p.append("</svg>")

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text("\n".join(p), encoding="utf-8")
    print(f"ok  {SALIDA.name}  ({SALIDA.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
