"""P27: el modelo como brazo, sobre las tareas que DISCRIMINAN.

QUE PREGUNTA. Dos, y son distintas:

  sustitucion   `luna` cuesta lo mismo que `nano` por token. Si es mejor, no hay decision
                de ruteo que tomar: se cambia el barato y se termina
  ruteo         `terra` cuesta 9,8x. Si gana, gana donde la tarea es dificil, y ESO es lo
                que el ruteo por region tiene que aprender a detectar

SOBRE QUE TAREAS. Solo las que DISCRIMINAN, que en `gold_p18` son 8 de 32. Una tarea que
nano ya resuelve con u=1 no distingue nada —los tres sacan 1,0— y una que nadie resuelve
tampoco. Correr las 32 gastaria 4x para agregar cero informacion sobre el orden.

  margen  0 < u < 1 con el mejor brazo de nano: hay que recuperar, y se sabe resoluble
  piso    u = 0 con TODOS: o es imposible, o necesita capacidad — y cual de las dos es
          exactamente lo que un modelo mas grande puede contestar

SOBRE QUE PATRONES. `rewoo` y `react`, y no los cinco. `rewoo` porque es el mas barato
(2.642 tokens/celda) y ADEMAS el de mayor utilidad sobre estas tareas (0,242), o sea que
deja margen visible sin pagar por verlo. `react` porque es el fallback y el mas
representativo del regimen de busqueda. `dag_strategy` queda afuera: 102.766 tokens/celda
para responder una pregunta sobre el MODELO, con el paradigma constante entre modelos.

EL RAZONAMIENTO ES PARTE DE LO QUE SE MIDE, no una molestia. `terra` razona por su cuenta
al default —66 tokens con herramientas, medido— y `nano` no razona nada. Esos tokens se
facturan como salida, asi que la comparacion de costo tiene que ser en PLATA y sobre el
medidor de la celda, no en tokens crudos.
"""

# Corre DESDE `lab/`: las rutas de datos son relativas al CWD. El prologo solo
# resuelve los imports, que es lo que se rompe al salir de la raiz.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import json
import os
import statistics
import sys
import time
from collections import defaultdict
from dataclasses import replace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings
from app.runner import Runner, load_rows

CORPUS = "gold_p18"
REPEAT = 3
PARADIGMS = ["rewoo", "react"]

# Que deployments comparar. `luna` entra en cuanto exista: el catalogo, los aranceles y el
# pool ya lo declaran, y lo unico que falta es el deployment.
CANDIDATOS = [
    ("nano", "gpt-5.4-nano"),
    ("terra", "gpt-5.6-terra"),
    ("luna", "gpt-5.6-luna"),
]


def discriminantes() -> list[str]:
    """Las tareas donde hay algo que recuperar. Se derivan del registro, no se eligen.

    Elegirlas a mano seria elegir donde el modelo caro tiene mas chance de lucirse, que es
    el sesgo mas facil de cometer y el mas dificil de ver despues.
    """
    f = _Path(f"results/nano/{CORPUS}_rows.jsonl")
    if not f.exists():
        raise FileNotFoundError(
            f"No hay registro de {CORPUS}: sin el no se sabe que tareas discriminan, y "
            f"elegirlas a mano seria elegir donde el caro se luce."
        )
    por = defaultdict(lambda: defaultdict(list))
    for r in load_rows(f):
        if not r.get("error"):
            por[r["task_id"]][r["paradigm"]].append(r["utility"])
    out = []
    for t, brazos in sorted(por.items()):
        mejor = max(statistics.mean(v) for v in brazos.values())
        if mejor < 1.0:
            out.append(t)
    return out


def main() -> None:
    tareas = discriminantes()
    base = Settings.from_env()

    disponibles = []
    for etiqueta, dep in CANDIDATOS:
        s = replace(
            base,
            endpoint=os.environ["MAPO_NANO_ENDPOINT"].rstrip("/"),
            api_key=os.environ["MAPO_NANO_KEY"],
            chat_deployment=dep,
            temperature=0.0 if etiqueta == "nano" else None,
            results_dir=base.results_dir / etiqueta,
        )
        disponibles.append((etiqueta, dep, s))

    celdas = len(tareas) * len(PARADIGMS) * REPEAT * len(disponibles)
    print(f"corpus: {CORPUS} | {len(tareas)} tareas que discriminan de 32")
    print(f"brazos: {PARADIGMS} | repeat={REPEAT} | modelos: "
          f"{[e for e, _, _ in disponibles]}")
    print(f"celdas: {celdas}")
    print("cota superior estimada: ~1,9M tokens (~USD 0,7 de referencia); el caro sube")
    print("por los tokens de razonamiento, que se facturan como salida\n", flush=True)

    for etiqueta, dep, s in disponibles:
        # LA TEMPERATURA. `nano` corrio siempre a 0 y asi se replica; los `5.6` son
        # modelos de razonamiento y forzarles 0 puede rechazarse, asi que se omite y la
        # OMISION queda en la huella — dos corridas con distinta decodificacion nunca se
        # promedian, que es justo lo que `load_rows` impide.
        try:
            runner = Runner(s, CORPUS, retriever_arm="hybrid", surface_variant="basic")
        except Exception as exc:
            print(f"=== {etiqueta} ({dep}): NO disponible — {exc}", flush=True)
            continue
        print(f"=== {etiqueta} ({dep}) -> {runner._results_path}", flush=True)  # noqa: SLF001
        t0 = time.perf_counter()
        try:
            filas = runner.run_cross_product(
                paradigms=PARADIGMS, repeat=REPEAT, task_ids=tareas
            )
        except Exception as exc:
            # SE DECLARA Y SE SIGUE con los otros modelos. Un deployment que no existe no
            # es un resultado sobre el modelo: es infraestructura, y mezclarlo con la
            # medicion seria contarlo como si hubiera perdido.
            print(f"  NO se pudo correr: {type(exc).__name__}: {str(exc)[:160]}\n",
                  flush=True)
            continue
        gasto = sum(r.cost_tokens for r in filas)
        infra = sum(1 for r in filas if r.infra_error)
        u = statistics.mean(r.utility for r in filas if not r.error) if filas else 0.0
        print(f"  filas={len(filas)} ({infra} infra_error, fuera de toda estadistica)")
        print(f"  tokens={gasto:,}  u media={u:.4f}  "
              f"wall={(time.perf_counter() - t0) / 60:.1f} min\n", flush=True)


if __name__ == "__main__":
    main()
