"""`paper-es.md` -> HTML autocontenido -> PDF. Sin dependencias que haya que instalar.

POR QUE ASI Y NO CON PANDOC. En esta maquina no hay pandoc, ni wkhtmltopdf, ni weasyprint
(que en Windows arrastra GTK). Lo que SI hay siempre en Windows 11 es Edge, y Chromium sabe
imprimir a PDF desde la linea de comandos. Asi que el camino es markdown -> HTML -> Edge
headless, y las tres etapas son inspeccionables: si el PDF sale mal, se abre el HTML.

LOS SVG VAN EMBEBIDOS, NO ENLAZADOS. Un `<img src="figuras/x.svg">` obliga al navegador a
resolver una ruta relativa desde un archivo temporal, y ahi es donde se rompe silenciosamente
—la figura no aparece y el PDF sale igual—. Se inserta el XML del SVG en linea: el HTML queda
autocontenido, y una figura que falta FALLA en vez de desaparecer.

EL MARKDOWN SE CONVIERTE A MANO y no con una libreria, porque las que hay que instalar no
estan y el subconjunto que este paper usa es chico y conocido: titulos, tablas, listas,
citas, bloques de codigo, enfasis, enlaces e imagenes. Cada regla esta escrita abajo y se
puede leer; una libreria seria menos codigo y una dependencia mas, y el archivo tiene que
correr sin red.

Corre DESDE `whitepaper/`:  py _a_pdf.py [paper-es.md] [salida.pdf]
"""

from __future__ import annotations

import html
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

EDGE = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

CSS = """
@page { size: A4; margin: 18mm 16mm 18mm 16mm; }
body { font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
       font-size: 10.5pt; line-height: 1.52; color: #1f2328; max-width: 100%; }
h1 { font-size: 20pt; margin: 34pt 0 10pt; padding-bottom: 5pt;
     border-bottom: 2px solid #d8dbdf; }
/* Sin salto de pagina forzado antes de cada h1: dejaba paginas a medio llenar. */
h2 { font-size: 14.5pt; margin: 20pt 0 7pt; color: #22252a; }
h3 { font-size: 11.8pt; margin: 15pt 0 5pt; color: #3b4046; }
h4 { font-size: 10.8pt; margin: 12pt 0 4pt; color: #3b4046; }
h1, h2, h3, h4 { page-break-after: avoid; }
p { margin: 0 0 8pt; }
code { font-family: Consolas, "SF Mono", Menlo, monospace; font-size: 9.2pt;
       background: #f2f3f5; padding: 1px 4px; border-radius: 3px; }
pre { background: #f7f8fa; border: 1px solid #e4e6ea; border-radius: 5px;
      padding: 8pt 10pt; overflow-x: auto; page-break-inside: avoid; }
pre code { background: none; padding: 0; font-size: 8.6pt; line-height: 1.42; }
table { border-collapse: collapse; margin: 9pt 0 12pt; font-size: 9.3pt; width: 100%;
        page-break-inside: avoid; }
th { background: #f2f3f5; text-align: left; font-weight: 600; }
th, td { border: 1px solid #dfe1e5; padding: 3.5pt 6pt; }
tr:nth-child(even) td { background: #fafbfc; }
blockquote { margin: 10pt 0; padding: 6pt 12pt; border-left: 3px solid #3b6ea5;
             background: #f6f8fb; color: #2c3138; page-break-inside: avoid; }
blockquote p:last-child { margin-bottom: 0; }
ul, ol { margin: 0 0 9pt; padding-left: 20pt; }
li { margin-bottom: 3pt; }
figure { margin: 12pt 0 14pt; text-align: center; page-break-inside: avoid; }
figure svg { max-width: 100%; height: auto; }
/* matplotlib pide DejaVu Sans, que Windows no tiene; sin esto el visor cae a serif */
figure svg text, figure svg tspan { font-family: Arial, "Helvetica Neue", sans-serif !important; }
figcaption { font-size: 8.8pt; color: #6b7178; margin-top: 4pt; font-style: italic; }
a { color: #2c5c8f; text-decoration: none; }
.cita { font-family: Consolas, "SF Mono", Menlo, monospace; font-size: 8.6pt; color: #5b6b7f;
        white-space: nowrap; }
.refs li { margin-bottom: 4pt; font-size: 9.6pt; }
hr { border: none; border-top: 1px solid #e4e6ea; margin: 16pt 0; }
/*__DENSO__*/
"""

_EN_LINEA = [
    (re.compile(r"`([^`]+)`"), lambda m: f"<code>{html.escape(m.group(1))}</code>"),
    (re.compile(r"\*\*([^*]+)\*\*"), lambda m: f"<strong>{m.group(1)}</strong>"),
    (re.compile(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])"), lambda m: f"<em>{m.group(1)}</em>"),
    (re.compile(r"\[arXiv:(\d{4}\.\d{4,5})(v\d+)?\](?!\()"),
     lambda m: f'<a class="cita" href="https://arxiv.org/abs/{m.group(1)}">[arXiv:{m.group(1)}]</a>'),
    (re.compile(r"\[((?:Zenodo|DOI|OpenAI|Thinking Machines|Anthropic|Google|Microsoft|Meta)[^\]]{0,60})\](?!\()"),
     lambda m: f'<span class="cita">[{m.group(1)}]</span>'),
    (re.compile(r"\[([^\]]+)\]\(([^)]+)\)"),
     lambda m: f'<a href="{html.escape(m.group(2), quote=True)}">{m.group(1)}</a>'),
]


def en_linea(texto: str) -> str:
    """Escapa y despues aplica las reglas de linea. El ORDEN importa.

    Se escapa PRIMERO, asi que `<` de un ejemplo no abre una etiqueta; y el codigo entre
    backticks se re-escapa adentro de su propia regla porque ya viene escapado del paso
    anterior — hacerlo al reves convertiria `&lt;` en `&amp;lt;`.
    """
    t = html.escape(texto)
    # Los backticks vienen con el contenido ya escapado: se desescapa para no doblar.
    t = re.sub(r"`([^`]+)`",
               lambda m: f"<code>{m.group(1)}</code>", t)
    for rx, f in _EN_LINEA[1:]:
        t = rx.sub(f, t)
    return t


def convertir(md: str, base: Path) -> str:
    salida: list[str] = []
    lineas = md.split("\n")
    i = 0
    en_lista = None
    faltantes: list[str] = []

    def cerrar_lista() -> None:
        nonlocal en_lista
        if en_lista:
            salida.append(f"</{en_lista}>")
            en_lista = None

    while i < len(lineas):
        L = lineas[i]

        # bloque de codigo
        if L.startswith("```"):
            cerrar_lista()
            i += 1
            cuerpo = []
            while i < len(lineas) and not lineas[i].startswith("```"):
                cuerpo.append(html.escape(lineas[i]))
                i += 1
            salida.append("<pre><code>" + "\n".join(cuerpo) + "</code></pre>")
            i += 1
            continue

        # imagen: el SVG se EMBEBE, y si falta se levanta
        m = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", L.strip())
        if m:
            cerrar_lista()
            ruta = base / m.group(2)
            if not ruta.exists():
                faltantes.append(m.group(2))
                salida.append(f'<figure><p style="color:#b5495b">[FALTA {html.escape(m.group(2))}]</p></figure>')
            else:
                svg = ruta.read_text(encoding="utf-8")
                # El prologo XML y el DOCTYPE no van adentro de un HTML.
                svg = re.sub(r"<\?xml[^>]*\?>", "", svg)
                svg = re.sub(r"<!DOCTYPE[^>]*>", "", svg, flags=re.I)
                # Si la linea siguiente es el pie «**Figura N.**», el alt no se repite debajo.
                j = i + 1
                while j < len(lineas) and not lineas[j].strip():
                    j += 1
                con_pie = j < len(lineas) and (lineas[j].startswith("**Figura") or lineas[j].startswith("Figura "))
                pie = "" if con_pie else f"<figcaption>{en_linea(m.group(1))}</figcaption>"
                salida.append(f"<figure>{svg}{pie}</figure>")
            i += 1
            continue

        # tabla
        if L.strip().startswith("|") and i + 1 < len(lineas) and \
                re.match(r"^\s*\|[\s:|-]+\|\s*$", lineas[i + 1]):
            cerrar_lista()
            def celdas(x: str) -> list[str]:
                return [c.strip() for c in x.strip().strip("|").split("|")]
            enc = celdas(L)
            i += 2
            filas = []
            while i < len(lineas) and lineas[i].strip().startswith("|"):
                filas.append(celdas(lineas[i]))
                i += 1
            salida.append("<table><thead><tr>"
                          + "".join(f"<th>{en_linea(c)}</th>" for c in enc)
                          + "</tr></thead><tbody>")
            for f in filas:
                salida.append("<tr>" + "".join(f"<td>{en_linea(c)}</td>" for c in f)
                              + "</tr>")
            salida.append("</tbody></table>")
            continue

        # cita (puede abarcar varias lineas)
        if L.startswith(">"):
            cerrar_lista()
            cuerpo = []
            while i < len(lineas) and lineas[i].startswith(">"):
                cuerpo.append(lineas[i].lstrip(">").strip())
                i += 1
            texto = " ".join(x for x in cuerpo if x)
            salida.append(f"<blockquote><p>{en_linea(texto)}</p></blockquote>")
            continue

        # titulos
        m = re.match(r"^(#{1,4})\s+(.*)$", L)
        if m:
            cerrar_lista()
            n = len(m.group(1))
            salida.append(f"<h{n}>{en_linea(m.group(2))}</h{n}>")
            i += 1
            continue

        if re.match(r"^-{3,}$|^\*{3,}$", L.strip()):
            cerrar_lista()
            salida.append("<hr>")
            i += 1
            continue

        # listas
        m = re.match(r"^\s*([-*·]|\d+\.)\s+(.*)$", L)
        if m:
            tipo = "ol" if re.match(r"\d", m.group(1)) else "ul"
            if en_lista != tipo:
                cerrar_lista()
                salida.append(f"<{tipo}>")
                en_lista = tipo
            # Un item sigue en las lineas de continuacion (no vacias, sin abrir otro
            # bloque) hasta el corte: un item que se corta a los 100 caracteres no son
            # dos items.
            item = [m.group(2)]
            i += 1
            while i < len(lineas) and lineas[i].strip() and not re.match(
                    r"^(#{1,4}\s|>|```|\||!\[|\s*([-*·]|\d+\.)\s|-{3,}$)", lineas[i]):
                item.append(lineas[i].strip())
                i += 1
            valor = f' value="{m.group(1)[:-1]}"' if tipo == "ol" else ""
            salida.append(f"<li{valor}>{en_linea(' '.join(item))}</li>")
            continue

        if not L.strip():
            # Una linea vacia entre dos items del mismo tipo no cierra la lista: es una
            # lista espaciada, y numerarla de nuevo desde 1 seria inventar tres listas.
            j = i
            while j < len(lineas) and not lineas[j].strip():
                j += 1
            sig = re.match(r"^\s*([-*·]|\d+\.)\s+", lineas[j]) if j < len(lineas) else None
            if not (en_lista and sig and ("ol" if re.match(r"\d", sig.group(1)) else "ul") == en_lista):
                cerrar_lista()
            i += 1
            continue

        # parrafo: junta lineas hasta el proximo corte
        cerrar_lista()
        parr = [L]
        i += 1
        while i < len(lineas) and lineas[i].strip() and not re.match(
                r"^(#{1,4}\s|>|```|\||!\[|\s*([-*·]|\d+\.)\s|-{3,}$)", lineas[i]):
            parr.append(lineas[i])
            i += 1
        salida.append(f"<p>{en_linea(' '.join(x.strip() for x in parr))}</p>")

    cerrar_lista()
    if faltantes:
        print(f"  [!] {len(faltantes)} figura(s) FALTAN y salen marcadas en rojo: {faltantes}")
    return "\n".join(salida)


def main() -> None:
    base = Path(__file__).resolve().parent
    args = [a for a in sys.argv[1:] if a != "--denso"]
    denso = "--denso" in sys.argv
    extra = (base / "_denso.css").read_text(encoding="utf-8") if denso else ""
    css = CSS.replace("/*__DENSO__*/", extra)
    fuente = base / (args[0] if args else "paper-es.md")
    destino = base / (args[1] if len(args) > 1 else fuente.stem + ".pdf")
    md = fuente.read_text(encoding="utf-8")
    # `md.count("![")` y no un regex: dentro de una f-string el `\[` se escapa dos veces y
    # la clase de caracteres queda abierta. Contar una subcadena no tiene esa trampa.
    print(f"  {fuente.name}: {len(md.splitlines())} lineas, {md.count('![')} figuras")

    cuerpo = convertir(md, base)
    doc = (f'<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">'
           f"<title>{html.escape(fuente.stem)}</title><style>{css}</style></head>"
           f"<body>{cuerpo}</body></html>")

    tmp = Path(tempfile.gettempdir()) / f"{fuente.stem}.html"
    tmp.write_text(doc, encoding="utf-8")
    print(f"  HTML: {tmp}  ({len(doc) / 1024:.0f} KB)")

    edge = next((e for e in EDGE if os.path.exists(e)), None)
    if edge is None:
        raise SystemExit("No se encontro Edge. El HTML quedo escrito y se puede imprimir a mano.")

    if destino.exists():
        destino.unlink()
    subprocess.run(
        [edge, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
         f"--print-to-pdf={destino}", tmp.as_uri()],
        check=False, capture_output=True, timeout=300,
    )
    if not destino.exists():
        raise SystemExit(f"Edge no produjo {destino}. El HTML esta en {tmp}.")
    print(f"  PDF:  {destino}  ({destino.stat().st_size / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    main()
