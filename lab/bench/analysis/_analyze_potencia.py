"""Cuantas regiones pueden DECIDIR con este corpus. Cero llamadas al modelo.

LA ARITMETICA QUE GOBIERNA, y no depende de ninguna corrida: un par (region, paradigma)
junta UN episodio POR TAREA de esa region, asi que para cruzar el piso de evidencia hacen
falta esa cantidad de TAREAS en la misma region. `repeat` NO suma episodios — un episodio es
una celda, la media de sus replicas.

CONSECUENCIA: la potencia de theta la fija el CORPUS, no la cuota. Gastar mas agrega tareas,
y solo cuentan si caen en la region justa. Eso separa dos decisiones que se venian tomando
juntas — cuanta precision comprar, y cuantas regiones pueden opinar.

La region se computa desde phi para TODAS las tareas, corridas o no: es una funcion
determinista de los features, asi que no hace falta pagar una fila para saberla. La primera
version de este calculo extrapolaba desde las 10 tareas ya corridas y daba «ninguna region
cruza», que era falso.

Corre DESDE . Resultado en PENDIENTES.es.md, P-15b y P-15c.
"""
import json, sys, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from app.features import FeatureExtractor, payload_for, measure_continuation
from app.policy import MIN_EPISODES_FOR_CONFIDENCE as PISO
from dataclasses import replace

LAB = Path(".").resolve()
docs = json.loads((LAB/"corpus/gold_h1/documents.json").read_text(encoding="utf-8"))
tasks = json.loads((LAB/"corpus/gold_h1/tasks.json").read_text(encoding="utf-8"))
ex = FeatureExtractor()
reg = {}
for t in tasks:
    f, _ = ex.extract(payload_for(t), allow_derived=False)
    f = replace(f, continuation=measure_continuation(docs, t["unit_ids"]))
    reg[t["task_id"]] = f.region()

PODADAS = ("B2_absence","D1_presupposition")
vivas = [t for t in tasks if t["cell"] not in PODADAS]
print(f"piso de evidencia: {PISO} tareas por region\n")
print("TAREAS POR REGION — las 60 que corren (calculado de phi, no de filas):")
c = collections.Counter(reg[t["task_id"]] for t in vivas)
for r,n in c.most_common():
    print(f"  {r:<44}{n:>4}   {'CRUZA' if n>=PISO else ''}")
cruzan = sum(1 for n in c.values() if n>=PISO)
print(f"\n  {cruzan} de {len(c)} regiones cruzan el piso")
print(f"  tareas en regiones que cruzan: {sum(n for n in c.values() if n>=PISO)} de {len(vivas)}")
print()
c78 = collections.Counter(reg[t["task_id"]] for t in tasks)
cr78 = sum(1 for n in c78.values() if n>=PISO)
print(f"LAS 78 SIN PODAR: {cr78} de {len(c78)} regiones cruzan  "
      f"({sum(n for n in c78.values() if n>=PISO)} tareas)")
print()
print("Y LO QUE DECIDE: un par (region,paradigma) junta 1 episodio POR TAREA de esa region.")
print("`repeat` NO suma episodios — un episodio es una CELDA, la media de sus replicas.")
