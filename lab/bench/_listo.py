"""¿Está todo en condiciones de lanzar la campaña? Una sola cosa que correr.

POR QUE EXISTE. El protocolo de este repo son ocho cosas —tests, verificación de corpus,
auditorías, corrida light, estimación— repartidas en cinco comandos y en tres documentos.
Antes de gastar decenas de millones de tokens, «me acordé de correr todo» no es una
garantía: es una intención. Esto lo hace una condición.

QUE NO HACE. No corre la campaña ni gasta cuota nueva: todo sale del código, del corpus, del
registro de la light y del catálogo. Si algo acá falla, la campaña no se lanza.

QUE COMPRUEBA, Y POR QUE CADA UNO:

  tests            la capa de medición contra respuestas conocidas. Sin esto, un número de
                   la campaña puede ser un bug del banco y no un hallazgo.
  corpus           la verdad se re-deriva desde los documentos, independiente del generador.
                   Ya pasó que un corpus tuviera oráculos silenciosamente equivocados.
  light            que la matriz corra ENTERA y que cada factor LLEGUE al modelo. Un factor
                   desconectado no da error: da exactamente la base.
  documentos       que ningún documento vivo contradiga al catálogo.
  afirmaciones     que lo afirmado en prosa se re-derive del registro y del código.
  presupuesto      que la estimación exista y esté hecha contra el CORPUS, no contra un
                   `.jsonl` que no declara si está completo (error de 34x, medido).

Corre DESDE `lab/`:  py bench/_listo.py
"""

from __future__ import annotations

import subprocess
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PY = sys.executable
CORPUS = "gold_h1"

# (etiqueta, comando, gasta_cuota). El orden NO es cosmético: lo que no gasta va primero,
# así una falla barata no obliga a haber pagado la cara. Es la misma regla que la poda
# aritmética aplicada al protocolo.
PASOS = [
    ("tests de la capa de medición", [PY, "tests/test_science.py"], False),
    ("tests de consolidación", [PY, "tests/test_consolidation.py"], False),
    ("el corpus verifica, independiente del generador",
     [PY, "corpus/verify.py", "--corpus", f"corpus/{CORPUS}"], False),
    ("ningún documento vivo contradice al catálogo",
     [PY, "bench/audits/_audit_documentos.py"], False),
    ("lo afirmado se re-deriva del registro",
     [PY, "bench/audits/_audit_afirmaciones.py"], False),
    ("ninguna guarda quedó inerte", [PY, "bench/audits/_audit_inerte.py"], False),
    ("el presupuesto está estimado contra el corpus", [PY, "bench/_estimate.py"], False),
    # LA UNICA QUE GASTA, y va última a propósito: si algo de arriba falla, esto no se paga.
    # En la práctica pega en el caché y sale gratis, pero eso es una propiedad del caché y
    # no una garantía del protocolo.
    ("la matriz corre entera y cada factor llega al modelo",
     [PY, "bench/runs/_run_homogenea_light.py"], True),
]


def main() -> None:
    if not Path(f"corpus/{CORPUS}").is_dir():
        raise SystemExit(
            f"No existe `corpus/{CORPUS}`. La receta está en el docstring de "
            f"`bench/runs/_run_homogenea_light.py`: una corrida que no se puede regenerar "
            f"desde una receta escrita no es reproducible."
        )

    # HAY ALGO QUE LANZAR, y este chequeo faltaba — que es el peor de los que faltaban.
    #
    # La primera version de este archivo verificaba las ocho condiciones y decia «la
    # campaña se puede lanzar» cuando **el runner de la campaña no existia**: habia
    # `_run_homogenea_light.py` y `_run_campana.py`, que es otra campaña, mas vieja y de
    # tres brazos. O sea: se estaban chequeando las precondiciones de una corrida que
    # nadie podia correr.
    #
    # Es la misma familia que todo lo demas de esta tanda —algo declarado que nadie
    # ejecuta— cometida por mi y sobre el propio protocolo.
    runner = Path("bench/runs/_run_homogenea.py")
    if not runner.exists():
        raise SystemExit(
            f"No existe `{runner}`. Las ocho condiciones no significan nada sin algo que "
            f"lanzar: verificar las precondiciones de una corrida que no tiene runner es "
            f"exactamente el error que este archivo existe para no cometer."
        )

    fallaron: list[str] = []
    for etiqueta, comando, gasta in PASOS:
        marca = "$" if gasta else " "
        print(f"[{marca}] {etiqueta} ... ", end="", flush=True)
        proceso = subprocess.run(comando, capture_output=True, text=True,
                                 encoding="utf-8", errors="replace")
        if proceso.returncode == 0:
            print("OK")
            continue
        print("FALLA")
        fallaron.append(etiqueta)
        cola = (proceso.stdout or "").strip().splitlines()[-12:]
        for linea in cola:
            print(f"        {linea}")
        err = (proceso.stderr or "").strip().splitlines()[-4:]
        for linea in err:
            print(f"        {linea}")

    print()
    if fallaron:
        print(f"NO SE LANZA. {len(fallaron)} de {len(PASOS)} condiciones no se cumplen:")
        for f in fallaron:
            print(f"  - {f}")
        raise SystemExit(1)

    print(f"Las {len(PASOS)} condiciones se cumplen. La campaña se puede lanzar.")
    print()
    print("  Lo que sigue NO lo decide esto:")
    print("    - la plata y las horas de reloj (ver `bench/_estimate.py`)")
    print("    - que una corrida en background muere con la sesión")
    print("    - y que se corre DE A UNA: dos procesos appendean al mismo `.jsonl` y el")
    print("      resumen sale con más filas que celdas")


if __name__ == "__main__":
    main()
