"""Genera los diagramas de control de flujo del catalogo, uno por patron activo.

POR QUE GENERADOS Y NO DIBUJADOS A MANO. Ocho SVG escritos a mano son ocho archivos que se
desincronizan de a uno: el dia que un patron cambia de forma, siete siguen bien y uno
miente, y no hay como saber cual. Aca la forma de cada patron es un DATO —la misma tabla
que el README documenta— y el dibujo es su render.

QUE DIBUJAN, Y ES LO UNICO QUE DISTINGUE UN PATRON DE OTRO. Las cuatro preguntas de
`PATRON_O_FACTOR.es.md`: cuantas llamadas y quien las decide, quien elige la proxima
accion, si hay estado compartido, y si un paso puede cambiar el plan. Nada de fraseo — un
diagrama que se pudiera dibujar igual para dos patrones distintos estaria dibujando otra
cosa.

PALETA. Fondo claro explicito y texto oscuro, en vez de heredar el tema. GitHub sirve los
SVG referenciados adentro de un `<img>`, asi que un dibujo transparente se lee sobre el
fondo del lector y desaparece en tema oscuro. Una tarjeta impresa se lee en los dos.

LA GUARDA. Un patron ACTIVO sin forma declarada levanta. Sin eso el README lo mostraria
como una imagen rota, que se lee como un archivo perdido y no como lo que es: un patron
que nadie dibujo.

Corre DESDE `lab/`:  py app/paradigms/_diagramas.py
"""

from pathlib import Path

SALIDA = Path("app/paradigms/diagramas")

TINTA = "#1f2933"
SUAVE = "#7b8794"
FONDO = "#f7f8fa"
MODELO = "#dbe7f3"
CODIGO = "#e8ece9"
BORDE_MODELO = "#5a7fa6"
BORDE_CODIGO = "#8a9a90"

# nombre -> (subtitulo, nodos, arcos)
#   nodo  = (etiqueta, tipo) con tipo en {"modelo", "codigo"}
#   arco  = (desde, hasta, etiqueta) por indice; `hasta < desde` es un lazo
FORMAS = {
    "direct": (
        "una llamada, todo el material adentro",
        [("todo el|material", "codigo"), ("1 llamada", "modelo"),
         ("respuesta", "codigo")],
        [],
    ),
    "react": (
        "bucle sin cota fija - el MODELO elige la proxima herramienta",
        [("pregunta", "codigo"), ("modelo", "modelo"), ("tool", "codigo"),
         ("respuesta", "codigo")],
        [(2, 1, "el modelo|decide seguir")],
    ),
    "reflection": (
        "una pasada mas de critica sobre la salida anterior",
        [("pregunta", "codigo"), ("borrador", "modelo"), ("critica", "modelo"),
         ("revision", "modelo")],
        [],
    ),
    "rewoo": (
        "plan completo primero; la ejecucion no vuelve a consultar",
        [("pregunta", "codigo"), ("plan", "modelo"),
         ("ejecuta sin|preguntar", "codigo"), ("solve", "modelo")],
        [],
    ),
    "gist_reader": (
        "triage barato, despues lectura selectiva",
        [("gists de|todo", "codigo"), ("elige que|leer", "modelo"),
         ("lee esas", "codigo"), ("respuesta", "modelo")],
        [],
    ),
    "dag_strategy": (
        "descomposicion con dependencias, verificacion y REPLAN acotado",
        [("plan|(DAG)", "modelo"), ("olas|topologicas", "codigo"),
         ("verifica|4 ejes", "codigo"), ("sintesis", "modelo")],
        [(2, 0, "replan <= 3")],
    ),
    "handoff": (
        "alcances FIJOS; la transferencia la autoriza el CODIGO",
        [("parte en|alcances", "codigo"), ("agente 1", "modelo"),
         ("autoriza?|literal", "codigo"), ("agente 2", "modelo")],
        [],
    ),
    "supervisor": (
        "despacha el proximo sub-agente DESPUES de ver el anterior",
        [("pregunta", "codigo"), ("supervisor", "modelo"),
         ("sub-agente|8 unidades", "modelo"), ("respuesta", "codigo")],
        [(2, 1, "mira lo|que volvio")],
    ),
}

ANCHO_NODO, ALTO_NODO, GAP = 108, 52, 34
MARGEN_X, TOPE = 18, 62


def _texto(x, y, contenido, tam, color, peso="normal", anchor="middle"):
    lineas = contenido.split("|")
    dy = tam * 1.15
    y0 = y - dy * (len(lineas) - 1) / 2
    fuente = "ui-sans-serif,-apple-system,Segoe UI,Roboto,sans-serif"
    return "".join(
        '<text x="%.1f" y="%.1f" font-size="%d" fill="%s" font-weight="%s" '
        'text-anchor="%s" font-family="%s">%s</text>'
        % (x, y0 + i * dy, tam, color, peso, anchor, fuente, linea)
        for i, linea in enumerate(lineas)
    )


def dibujar(nombre):
    subtitulo, nodos, arcos = FORMAS[nombre]
    n = len(nodos)
    ancho = MARGEN_X * 2 + n * ANCHO_NODO + (n - 1) * GAP
    alto = TOPE + ALTO_NODO + 30

    def cx(i):
        return MARGEN_X + i * (ANCHO_NODO + GAP) + ANCHO_NODO / 2

    p = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
         'viewBox="0 0 %d %d" role="img" aria-label="%s: %s">'
         % (ancho, alto, ancho, alto, nombre, subtitulo)]
    p.append('<rect width="%d" height="%d" rx="10" fill="%s"/>' % (ancho, alto, FONDO))
    p.append('<defs><marker id="f" markerWidth="7" markerHeight="7" refX="6" refY="3" '
             'orient="auto"><path d="M0,0 L7,3 L0,6 z" fill="%s"/></marker></defs>' % SUAVE)
    p.append(_texto(MARGEN_X, 24, nombre, 15, TINTA, "600", "start"))
    p.append(_texto(MARGEN_X, 41, subtitulo, 11, SUAVE, "normal", "start"))

    y = TOPE
    for i, (etiqueta, tipo) in enumerate(nodos):
        x = MARGEN_X + i * (ANCHO_NODO + GAP)
        relleno = MODELO if tipo == "modelo" else CODIGO
        borde = BORDE_MODELO if tipo == "modelo" else BORDE_CODIGO
        radio = 6 if tipo == "modelo" else 16
        p.append('<rect x="%d" y="%d" width="%d" height="%d" rx="%d" fill="%s" '
                 'stroke="%s" stroke-width="1.2"/>'
                 % (x, y, ANCHO_NODO, ALTO_NODO, radio, relleno, borde))
        p.append(_texto(x + ANCHO_NODO / 2, y + ALTO_NODO / 2, etiqueta, 11, TINTA))
        if i:
            p.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" '
                     'stroke-width="1.3" marker-end="url(#f)"/>'
                     % (x - GAP + 3, y + ALTO_NODO / 2, x - 5, y + ALTO_NODO / 2, SUAVE))

    for desde, hasta, etiqueta in arcos:
        xa, xb = cx(desde), cx(hasta)
        piso = y + ALTO_NODO
        fondo = piso + 20
        p.append('<path d="M%.1f,%.1f C%.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="none" '
                 'stroke="%s" stroke-width="1.3" stroke-dasharray="4 3" '
                 'marker-end="url(#f)"/>'
                 % (xa, piso, xa, fondo, xb, fondo, xb, piso + 3, SUAVE))
        p.append(_texto((xa + xb) / 2, fondo + 9, etiqueta, 10, SUAVE))

    p.append("</svg>")
    return "".join(p)


def main():
    from app.paradigms import CATALOG, Status

    activos = {n for n, e in CATALOG.items() if e.status is Status.ACTIVE}
    faltan = sorted(activos - set(FORMAS))
    if faltan:
        raise SystemExit(
            "Patrones ACTIVOS sin forma declarada: %s. Un catalogo con un diagrama que "
            "falta se ve como una imagen rota, que se lee como un archivo perdido y no "
            "como lo que es: un patron que nadie dibujo." % faltan
        )
    sobran = sorted(set(FORMAS) - activos)
    if sobran:
        print("[aviso] formas de patrones que ya no estan activos: %s" % sobran)
    SALIDA.mkdir(parents=True, exist_ok=True)
    for nombre in sorted(FORMAS):
        destino = SALIDA / ("%s.svg" % nombre)
        destino.write_text(dibujar(nombre), encoding="utf-8")
        print("  %s" % destino)
    print("\n%d diagramas." % len(FORMAS))


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    main()
