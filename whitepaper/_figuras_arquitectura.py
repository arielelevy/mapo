"""Borradores v2 de las dos figuras de arquitectura, con las ideas del esquema de ExploitGym:
contenedores con nombre debajo, filas apiladas con separador punteado e icono, un actor visible
para el LLM, salidas colgando de una llave, y rayado para lo que el modelo nunca toca.
Misma paleta y tipografia que los SVG vigentes."""
from pathlib import Path

AZUL, ROJO, VERDE, GRIS, TXT = "#3b6ea5", "#b5495b", "#2e8b6f", "#6b7178", "#22252a"
PANEL_AZUL, PANEL_ROJO, BORDE = "#f4f7fa", "#fdf5f6", "#d8dbdf"
FONT = "Segoe UI, Helvetica, Arial, sans-serif"
OUT = Path(__file__).parent / "figuras"


def defs():
    return f"""<defs>
<marker id="p" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="{GRIS}"/></marker>
<marker id="pv" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="{VERDE}"/></marker>
<marker id="pr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="{ROJO}"/></marker>
<pattern id="rayas" patternUnits="userSpaceOnUse" width="8" height="8" patternTransform="rotate(45)"><rect width="8" height="8" fill="#ffffff"/><line x1="0" y1="0" x2="0" y2="8" stroke="{AZUL}" stroke-opacity="0.22" stroke-width="1.5"/></pattern>
</defs>"""


def t(x, y, s, size=11, fill=GRIS, w=None, anchor="start", italic=False):
    fw = f' font-weight="{w}"' if w else ""
    fs = ' font-style="italic"' if italic else ""
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" text-anchor="{anchor}"{fw}{fs}>{s}</text>'


def caja(x, y, w, h, stroke=AZUL, fill="#ffffff", sw=1.6, dash=None, rx=7):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>'


def flecha(x1, y1, x2, y2, color=GRIS, marker="p", dash=None, sw=1.6):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{sw}" marker-end="url(#{marker})"{d}/>'


def robot(cx, cy, color=ROJO, escala=1.0):
    """Un sensor con cara: cabeza, dos ojos, antena. Sin pretensiones."""
    s = escala
    return f"""<g transform="translate({cx},{cy}) scale({s})">
<line x1="0" y1="-30" x2="0" y2="-20" stroke="{color}" stroke-width="2"/><circle cx="0" cy="-32" r="3" fill="{color}"/>
<rect x="-24" y="-20" width="48" height="36" rx="8" fill="#ffffff" stroke="{color}" stroke-width="2"/>
<circle cx="-9" cy="-3" r="4.5" fill="{color}"/><circle cx="9" cy="-3" r="4.5" fill="{color}"/>
<line x1="-10" y1="8" x2="10" y2="8" stroke="{color}" stroke-width="2"/>
<rect x="-30" y="-10" width="6" height="14" rx="2" fill="{color}"/><rect x="24" y="-10" width="6" height="14" rx="2" fill="{color}"/>
</g>"""


def icono(kind, x, y, color=AZUL):
    """Iconos de 14px: documento, moneda, bandera, regla, retículo, embudo, etiqueta, dial, tabla."""
    g = f'<g transform="translate({x},{y})" fill="none" stroke="{color}" stroke-width="1.5">'
    if kind == "doc":
        g += '<path d="M2 1h7l3 3v9H2z"/><path d="M4 7h6M4 10h6"/>'
    elif kind == "moneda":
        g += '<circle cx="7" cy="7" r="6"/><path d="M7 4v6M5 6h4M5 8h4"/>'
    elif kind == "bandera":
        g += '<path d="M3 13V1M3 2h8l-2 3 2 3H3"/>'
    elif kind == "regla":
        g += '<path d="M1 10L10 1l3 3-9 9z"/><path d="M4 7l1 1M6 5l1 1M8 3l1 1"/>'
    elif kind == "capas":
        g += '<path d="M7 1l6 3-6 3-6-3z"/><path d="M1 7l6 3 6-3M1 10l6 3 6-3"/>'
    elif kind == "embudo":
        g += '<path d="M1 1h12L8 7v5l-2 1V7z"/>'
    elif kind == "etiqueta":
        g += '<path d="M1 1h6l6 6-6 6-6-6z"/><circle cx="4" cy="4" r="1"/>'
    elif kind == "dial":
        g += '<path d="M1 11a6 6 0 0 1 12 0"/><path d="M7 11L10 5"/>'
    elif kind == "tabla":
        g += '<rect x="1" y="2" width="12" height="10"/><path d="M1 6h12M5 2v10M9 2v10"/>'
    elif kind == "check":
        g += '<path d="M2 7l3 3 7-7"/>'
    elif kind == "bifurca":
        g += '<path d="M2 7h4m0 0l4-4h3M6 7l4 4h3"/>'
    return g + "</g>"


def fila(x, y, w, kind, titulo, sub, color=AZUL, num=None):
    """Una fila apilada dentro de un contenedor: icono, titulo en negrita, subtitulo gris."""
    n = f"{num} · " if num is not None else ""
    return (icono(kind, x + 10, y + 6, color)
            + t(x + 32, y + 15, f"{n}{titulo}", 11.5, TXT, w=600)
            + t(x + 32, y + 29, sub, 9.3))


def separador(x, y, w):
    return f'<line x1="{x + 8}" y1="{y}" x2="{x + w - 8}" y2="{y}" stroke="{BORDE}" stroke-dasharray="2 3"/>'


def contenedor(x, y, w, filas, nombre, color=AZUL, alto_fila=40, pad=8, fill="#ffffff"):
    h = pad * 2 + alto_fila * len(filas)
    s = caja(x, y, w, h, stroke=color, fill=fill)
    for i, (kind, titulo, sub, num) in enumerate(filas):
        fy = y + pad + i * alto_fila
        s += fila(x, fy, w, kind, titulo, sub, color, num)
        if i < len(filas) - 1:
            s += separador(x, fy + alto_fila - 1, w)
    s += t(x + w / 2, y + h + 16, nombre, 11.5, color, w=700, anchor="middle")
    return s, h


# ------------------------------------------------------------------ Figura 1: contrato de garantía
def contrato():
    W, H = 980, 470
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="{FONT}">',
         defs(), f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
         t(16, 28, "El contrato de garantía, y qué pasa cuando la evidencia no alcanza", 17, TXT, w=600),
         t(16, 45, "la abstención es una salida, no un fallo · y el rechazo sube el piso para el próximo request, sin tocar un peso", 12)]

    # carril del código
    s.append(f'<rect x="16" y="58" width="948" height="262" rx="10" fill="{PANEL_AZUL}" stroke="{BORDE}"/>')
    s.append(t(30, 338, "LO QUE DECIDE EL CÓDIGO · determinista, contable, auditable", 12, AZUL, w=700))

    # request apilado
    req, hreq = contenedor(30, 88, 168, [
        ("doc", "material", "unidades del corpus", None),
        ("moneda", "presupuesto", "tokens disponibles", None),
        ("bandera", "banderas de riesgo", "irreversible · shared · regulated", None),
    ], "request · lo declara el caller", color=GRIS)
    s.append(req)

    # tres pasos, una fila
    y0, hh = 118, 68
    pasos = [(226, "1 · factibilidad", "una desigualdad,", "no una estimación", "regla"),
             (410, "2 · piso exigido", "A0–A3, derivado de", "creencias del request", "dial"),
             (594, "3 · admisibles", "los que alcanzan", "el piso", "embudo")]
    pw = 156
    for x, tt, a, b, ic in pasos:
        s.append(caja(x, y0, pw, hh))
        s.append(icono(ic, x + 10, y0 + 8))
        s.append(t(x + pw / 2 + 8, y0 + 24, tt, 13, TXT, w=600, anchor="middle"))
        s.append(t(x + pw / 2, y0 + 42, a, 9.8, anchor="middle"))
        s.append(t(x + pw / 2, y0 + 55, b, 9.8, anchor="middle"))
    ym = y0 + hh / 2
    s.append(flecha(198, ym, 224, ym))
    s.append(flecha(382, ym, 408, ym))
    s.append(flecha(566, ym, 592, ym))
    s.append(flecha(750, ym, 776, ym))

    # llave y dos salidas
    bx = 786
    s.append(f'<path d="M{bx} {ym} q10 0 10 -10 v-22 q0 -10 10 -10 M{bx} {ym} q10 0 10 10 v40 q0 10 10 10" fill="none" stroke="{GRIS}" stroke-width="1.6"/>')
    s.append(caja(810, 84, 148, 56, stroke=VERDE))
    s.append(icono("check", 818, 92, VERDE))
    s.append(t(892, 106, "ejecuta y responde", 12, TXT, w=600, anchor="middle"))
    s.append(t(884, 125, "alguna procedencia alcanzó el piso", 8.8, VERDE, anchor="middle", italic=True))
    s.append(caja(810, 188, 148, 56, stroke=ROJO))
    s.append(icono("bifurca", 818, 196, ROJO))
    s.append(t(894, 210, "se abstiene o difiere", 12, TXT, w=600, anchor="middle"))
    s.append(t(884, 229, "ninguna procedencia alcanzó el piso", 8.8, ROJO, anchor="middle", italic=True))
    s.append(t(884, 262, "toda decisión termina en una de las dos", 10, GRIS, anchor="middle", italic=True))

    # lazo de plasticidad: de la salida roja, por abajo, hasta el paso 2
    s.append(f'<path d="M950 244 v44 H488 V{y0 + hh + 2}" fill="none" stroke="{VERDE}" stroke-width="1.6" stroke-dasharray="5 4" marker-end="url(#pv)"/>')
    s.append(t(690, 302, "el registro de rechazos sube el piso del próximo request · offline, con guarda anti-regresión, sin tocar un peso", 10.5, VERDE, anchor="middle", italic=True))

    # carril del modelo
    s.append(f'<rect x="16" y="350" width="948" height="88" rx="10" fill="{PANEL_ROJO}" stroke="{BORDE}"/>')
    s.append(t(30, 456, "LO QUE EMITE EL MODELO · un sensor estocástico con los pesos congelados", 12, ROJO, w=700))
    s.append(robot(120, 396))
    s.append(t(170, 388, "LLM", 13, TXT, w=600))
    s.append(t(170, 404, "lee la unidad que el código le da y contesta", 9.8))
    s.append(t(170, 418, "«¿qué dice esta unidad?» · «¿hacia dónde sigue el rastro?»", 9.8))
    # la única flecha que cruza la frontera
    s.append(flecha(488, 366, 488, y0 + hh + 4, ROJO, "pr", dash="3 3"))
    s.append(t(500, 200, "proposiciones tipadas, hacia arriba", 10.5, ROJO, italic=True))
    s.append(t(500, 213, "nunca control de flujo, hacia abajo", 10.5, ROJO, italic=True))
    # el bucle, rayado: lo que el modelo no toca
    s.append(caja(226, 226, 340, 44, stroke=AZUL, fill="url(#rayas)", sw=1.2))
    s.append(t(396, 245, "el bucle es del código", 12, AZUL, w=700, anchor="middle"))
    s.append(t(396, 260, "cuántas vueltas · qué índice · cuándo parar · qué unidad es el ancla", 9.3, AZUL, anchor="middle"))

    s.append("</svg>")
    return "\n".join(s)


# ------------------------------------------------------------------ Figura 2: cómo se decide un request
def metodo():
    W, H = 980, 500
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="{FONT}">',
         defs(), f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
         t(16, 30, "Cómo se decide un request", 17, TXT, w=600),
         t(16, 46, "la frontera entre percepción estocástica y control determinista organiza toda la decisión", 12)]

    s.append(f'<rect x="16" y="58" width="948" height="260" rx="10" fill="{PANEL_AZUL}" stroke="{BORDE}"/>')
    s.append(t(30, 336, "LO QUE DECIDE EL CÓDIGO · determinista, contable, auditable", 12, AZUL, w=700))

    y = 84
    c1, h1 = contenedor(30, y, 200, [
        ("regla", "sensores", "forma cerrada, sin modelo", 1),
        ("capas", "creencias tipadas", "con procedencia, de ASSUMED a COMPUTED", 2),
    ], "sensar", alto_fila=42)
    c2, h2 = contenedor(262, y, 262, [
        ("embudo", "portón de factibilidad", "aritmética pura: ¿entra en el presupuesto?", 3),
        ("etiqueta", "capacidades exigidas", "ontología de la pregunta → capacidades", 4),
        ("check", "brazos candidatos", "los que tienen TODAS las exigidas", 5),
        ("dial", "dial de garantía", "max(caller, request, piso aprendido)", 6),
    ], "acotar", alto_fila=42)
    c3, h3 = contenedor(556, y, 200, [
        ("bifurca", "elegir o abstenerse", "entre los que empatan, el más barato", 7),
        ("tabla", "EXPLAIN", "qué se creyó, con qué procedencia", 8),
    ], "decidir", alto_fila=42)
    s += [c1, c2, c3]
    ymid = y + 45
    s.append(flecha(230, ymid, 260, ymid))
    s.append(flecha(524, ymid, 554, ymid))
    s.append(flecha(756, ymid, 786, ymid))

    # ejecuta, con el bucle rayado adentro
    ex, ew = 788, 166
    s.append(caja(ex, y, ew, 128, stroke=VERDE))
    s.append(t(ex + ew / 2, y + 22, "el brazo elegido ejecuta", 12, TXT, w=600, anchor="middle"))
    s.append(caja(ex + 10, y + 34, ew - 20, 82, stroke=AZUL, fill="url(#rayas)", sw=1.2, rx=5))
    s.append(t(ex + ew / 2, y + 52, "el bucle es del código", 10.5, AZUL, w=700, anchor="middle"))
    for i, l in enumerate(["cuántas vueltas", "qué índice", "cuándo parar"]):
        s.append(t(ex + ew / 2, y + 68 + i * 14, l, 10.5, AZUL, anchor="middle"))
    s.append(t(ex + ew / 2, y + 128 + 16, "ejecutar", 11.5, VERDE, w=700, anchor="middle"))

    # carril del modelo
    yb = 348
    s.append(f'<rect x="16" y="{yb}" width="948" height="112" rx="10" fill="{PANEL_ROJO}" stroke="{BORDE}"/>')
    s.append(t(30, yb + 132, "LO QUE EMITE EL MODELO · sensor: proposiciones, nunca flujo de control", 12, ROJO, w=700))
    s.append(robot(96, yb + 50))
    s.append(t(96, yb + 100, "LLM", 11.5, TXT, w=600, anchor="middle"))

    # dos preguntas y el tipado
    s.append(caja(176, yb + 22, 210, 60, stroke=ROJO))
    s.append(t(281, yb + 44, "extraer un hecho", 12, TXT, w=600, anchor="middle"))
    s.append(t(281, yb + 62, "«¿qué dice esta unidad?»", 9.8, anchor="middle"))
    s.append(caja(414, yb + 22, 210, 60, stroke=ROJO))
    s.append(t(519, yb + 44, "proponer el próximo paso", 12, TXT, w=600, anchor="middle"))
    s.append(t(519, yb + 62, "«¿hacia dónde sigue el rastro?»", 9.8, anchor="middle"))
    s.append(flecha(624, yb + 52, 650, yb + 52, ROJO, "pr"))
    s.append(caja(652, yb + 22, 290, 60, stroke=ROJO))
    s.append(t(797, yb + 44, "la salida se TIPA antes de usarse", 12, TXT, w=600, anchor="middle"))
    s.append(t(797, yb + 62, "«M. Arrieta settlement account» → entidad: M. Arrieta", 9.8, anchor="middle"))

    # flechas que cruzan la frontera
    s.append(flecha(ex + 40, y + 128, ex + 40, yb + 20, ROJO, "pr"))
    s.append(t(ex + 36, 300, "pregunta", 10.5, ROJO, italic=True, anchor="end"))
    s.append(flecha(ex + ew - 30, yb + 20, ex + ew - 30, y + 130, ROJO, "pr"))
    s.append(t(ex + ew - 36, 300, "proposición", 10.5, ROJO, italic=True, anchor="end"))
    s.append(flecha(148, yb + 50, 174, yb + 50, ROJO, "pr"))

    s.append(t(16, H - 8, "Una decisión delegada puede abrir un canal desde el modelo hacia el control: en muestra, el ancla elegida por el modelo dio u=1,000 / 0,000 / 0,000 con la misma huella.", 10.5))
    s.append("</svg>")
    return "\n".join(s)


if __name__ == "__main__":
    (OUT / "contrato-de-garantia.svg").write_text(contrato(), encoding="utf-8")
    (OUT / "metodo-determinista.svg").write_text(metodo(), encoding="utf-8")
    print("ok")
