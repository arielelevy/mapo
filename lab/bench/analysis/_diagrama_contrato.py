"""La figura de apertura: el contrato de garantía, con su rama de rechazo y su lazo.

POR QUÉ EXISTE, cuando ya hay un diagrama del método. `_diagrama_metodo.py` muestra **dónde
está la frontera** entre lo que decide el código y lo que emite el modelo, y para eso necesita
los ocho pasos. Ésta responde otra pregunta, más temprana: **qué pasa cuando la evidencia no
alcanza**. Y muestra dos cosas que ninguna de las trece figuras del paper muestra hoy:

  · **la rama de rechazo.** Que la abstención sea una salida de primera clase y no un fallo
    es la mitad del argumento de §5.4, y en prosa se lee como una concesión.
  · **el lazo de realimentación.** Que el piso de garantía SUBA donde el registro muestra que
    las aserciones del modelo se rechazan es la plasticidad de §6.3, y hoy vive sólo en texto.
    Un lazo dibujado dice en un renglón lo que un párrafo no logra: el sistema cambia de
    comportamiento sin que nadie toque un peso.

POR QUÉ SVG A MANO Y NO MATPLOTLIB. Igual que su hermana: es una arquitectura, no datos. No
hay ejes que pelear, el código es menos, y las coordenadas salen de una declaración de filas
en vez de treinta números sueltos.

Corre DESDE `lab/`:  py bench/analysis/_diagrama_contrato.py
"""

from __future__ import annotations

import html
from pathlib import Path

SALIDA = Path("../whitepaper/figuras/contrato-de-garantia.svg")

W, H = 980, 410
TINTA, GRIS, SUAVE = "#22252a", "#6b7178", "#d8dbdf"
AZUL, VERDE, GRANATE = "#3b6ea5", "#2e8b6f", "#b5495b"
FONDO_CODIGO, FONDO_SENSOR = "#f4f7fa", "#fdf5f6"


def caja(x, y, w, h, titulo, sub, color, relleno="#ffffff", punteada=False) -> str:
    dash = ' stroke-dasharray="5 4"' if punteada else ""
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="7" fill="{relleno}" '
           f'stroke="{color}" stroke-width="1.8"{dash}/>',
           f'<text x="{x + w / 2}" y="{y + 21}" text-anchor="middle" font-size="13" '
           f'font-weight="600" fill="{TINTA}">{html.escape(titulo)}</text>']
    for i, s in enumerate(sub):
        out.append(f'<text x="{x + w / 2}" y="{y + 38 + i * 13}" text-anchor="middle" '
                   f'font-size="9.5" fill="{GRIS}">{html.escape(s)}</text>')
    return "\n".join(out)


def flecha(x1, y1, x2, y2, color=GRIS, punteada=False, punta="punta") -> str:
    dash = ' stroke-dasharray="5 4"' if punteada else ""
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" '
            f'stroke-width="1.7"{dash} marker-end="url(#{punta})"/>')


def camino(d, color=GRIS, punteada=False, punta="punta") -> str:
    dash = ' stroke-dasharray="5 4"' if punteada else ""
    return (f'<path d="{d}" fill="none" stroke="{color}" stroke-width="1.7"{dash} '
            f'marker-end="url(#{punta})"/>')


def rotulo(x, y, txt, color=GRIS, anc="middle", cursiva=True, peso="400") -> str:
    it = ' font-style="italic"' if cursiva else ""
    return (f'<text x="{x}" y="{y}" text-anchor="{anc}" font-size="10"{it} '
            f'font-weight="{peso}" fill="{color}">{html.escape(txt)}</text>')


def main() -> None:
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
         f'width="{W}" height="{H}" font-family="Segoe UI, Helvetica, Arial, sans-serif">']
    for nombre, col in (("punta", GRIS), ("punta_v", VERDE), ("punta_g", GRANATE)):
        p.append(f'<defs><marker id="{nombre}" viewBox="0 0 10 10" refX="9" refY="5" '
                 'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
                 f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{col}"/></marker></defs>')
    p.append(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')

    p.append(f'<text x="16" y="28" font-size="17" font-weight="600" fill="{TINTA}">'
             'El contrato de garantía, y qué pasa cuando la evidencia no alcanza</text>')
    p.append(f'<text x="16" y="45" font-size="11" fill="{GRIS}">'
             'la abstención es una salida, no un fallo · y el rechazo sube el piso para el '
             'próximo request, sin tocar un peso</text>')

    # ── el carril del código, y el del sensor ───────────────────────────────────
    p.append(f'<rect x="16" y="58" width="{W - 32}" height="242" rx="10" '
             f'fill="{FONDO_CODIGO}" stroke="{SUAVE}"/>')
    p.append(f'<rect x="16" y="316" width="{W - 32}" height="74" rx="10" '
             f'fill="{FONDO_SENSOR}" stroke="{SUAVE}"/>')
    p.append(f'<text x="30" y="76" font-size="11.5" font-weight="700" fill="{AZUL}">'
             'LO QUE DECIDE EL CÓDIGO</text>')
    p.append(f'<text x="30" y="334" font-size="11.5" font-weight="700" fill="{GRANATE}">'
             'LO QUE EMITE EL MODELO</text>')

    # ── el riel principal ───────────────────────────────────────────────────────
    y = 100
    p.append(caja(30, y, 148, 66, "request", [
        "material · presupuesto", "banderas del caller"], GRIS))
    p.append(caja(214, y, 168, 66, "1 · factibilidad", [
        "una desigualdad,", "no una estimación"], AZUL))
    p.append(caja(418, y, 168, 66, "2 · piso exigido", [
        "A0–A3, derivado de", "creencias del request"], AZUL))
    p.append(caja(622, y, 168, 66, "3 · admisibles", [
        "los que alcanzan", "el piso"], AZUL))
    p.append(caja(826, y, 110, 66, "ejecuta", ["y responde"], VERDE))
    for x1, x2 in ((178, 214), (382, 418), (586, 622), (790, 826)):
        p.append(flecha(x1, y + 33, x2, y + 33))

    # ── la rama de rechazo: sale del piso, y es una SALIDA ───────────────────────
    yr = 226
    p.append(caja(640, yr, 250, 58, "se abstiene o difiere", [
        "ninguna procedencia alcanza el piso"], GRANATE))
    p.append(camino(f"M 560 {y + 66} L 560 196 L 765 196 L 765 {yr}", GRANATE,
                    punta="punta_g"))
    p.append(rotulo(570, 190, "procedencia insuficiente", GRANATE, anc="start"))

    # ── el lazo: rodea por la derecha y entra al piso POR ARRIBA, para no cruzar
    #    la flecha del sensor, que sube por x=502
    p.append(camino("M 890 255 L 950 255 L 950 88 L 460 88 L 460 100", VERDE,
                    punteada=True, punta="punta_v"))
    p.append(rotulo(700, 82, "el registro de rechazos sube el piso del próximo request "
                             "— offline, con guarda anti-regresión", VERDE))

    # ── el sensor alimenta las CREENCIAS, que es de donde se deriva el piso ──────
    ys = 348
    p.append(caja(418, ys, 232, 42, "LLM · sensor estocástico", [
        "proposiciones tipadas · pesos congelados"], GRANATE, punteada=True))
    p.append(camino(f"M 502 {ys} L 502 {y + 66}", GRIS, punteada=True))
    p.append(rotulo(492, 252, "proposiciones, nunca control de flujo", GRIS, anc="end"))

    p.append(f'<text x="16" y="{H - 8}" font-size="10.5" fill="{GRIS}">'
             'La garantía no es «mismo prompt ⟹ misma respuesta», que ningún LLM puede dar. '
             'Es «misma base de creencias ⟹ misma decisión», que se verifica repitiéndola.'
             '</text>')

    p.append("</svg>")
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text("\n".join(p), encoding="utf-8")
    print(f"  {SALIDA}  ({SALIDA.stat().st_size // 1024} KB, {W}x{H})")


if __name__ == "__main__":
    main()
