"""Declarar el detector de runtime en corpus YA generados. Cero tokens, cero riesgo.

POR QUE EN SU LUGAR Y NO REGENERANDO. `--honest-detectors` toca exactamente un campo por
tarea: `has_oracle`. No toca documentos, ni preguntas, ni el gold, ni los unit_ids. Asi
que regenerar el corpus entero para cambiar un booleano seria arriesgar deriva de mundo
—una version distinta del generador produce otros documentos, y las filas ya pagadas
dejarian de corresponder— a cambio de nada. Declararlo en su lugar deja las filas
exactamente igual de validas que antes.

QUE ARREGLA. Los corpus de entrenamiento se generaron antes de que el campo existiera,
asi que declaran detector en TODAS las tareas. Medido: 265 de 270 episodios del registro
viven en regiones `oracle` y sólo 5 en `no_oracle`. Bajo la regla honesta, 20 de las 26
tareas de `gold_p17` son `no_oracle`. Sin esto, theta no tendria estadisticas donde
gold_p17 aterriza y P17 mediria "no hay datos" en vez de "la seleccion no paga".

QUE NO ARREGLA, Y HAY QUE DECIRLO. La `region` grabada EN CADA FILA se computo cuando la
fila se escribio, con el vocabulario de entonces (tres segmentos) y la regla de entonces.
Este script no la reescribe: las filas son el registro de lo que paso y no se editan. El
analisis tiene que RECOMPUTAR la region desde la tarea, que es lo correcto igual — la
region es una funcion de los features, no un dato de la corrida.

EFECTO SOBRE VEREDICTOS YA REGISTRADOS. Ninguno: P15 y P16 estan congelados en sus JSON.
Un re-analisis posterior daria numeros distintos, y debe darlos — se computaria bajo otra
regla. El veredicto que vale es el del archivo, con la regla vigente cuando se registro.
"""

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent / "corpus"))
from generate import HONEST_DETECTORS  # noqa: E402

CORPORA = sys.argv[1:] or ["gold_deep", "gold_holdout", "gold_v2", "gold_transfer"]


def main() -> None:
    for corpus in CORPORA:
        path = Path("corpus") / corpus / "tasks.json"
        if not path.exists():
            print(f"{corpus}: no existe, se saltea")
            continue

        tasks = json.loads(path.read_text(encoding="utf-8"))
        changed, unknown = 0, set()
        for task in tasks:
            prefix = task["cell"].split("_")[0]
            if prefix not in HONEST_DETECTORS:
                unknown.add(prefix)
                continue
            declared = HONEST_DETECTORS[prefix]
            if task.get("has_oracle") != declared:
                task["has_oracle"] = declared
                changed += 1

        if unknown:
            raise ValueError(
                f"{corpus}: celdas sin detector declarado {sorted(unknown)}. Una celda "
                "cuyo detector nadie decidio es la conflacion que esto viene a sacar."
            )

        with_detector = sum(1 for t in tasks if t["has_oracle"])
        path.write_text(
            json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"{corpus:<16} {changed:>3} tareas cambiadas | "
              f"con detector {with_detector}/{len(tasks)}")

    print("\nLos documentos no se tocaron. Las filas ya pagadas siguen siendo validas.")
    print("Correr `corpus/verify.py` para confirmar que el gold sigue verificando.")


if __name__ == "__main__":
    main()
