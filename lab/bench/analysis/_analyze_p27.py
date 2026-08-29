"""P27: el modelo como brazo. Veredicto sobre las predicciones registradas.

LA COMPARACION ES PAREADA POR TAREA Y POR PARADIGMA. Promediar cada modelo por separado y
restar mezclaria composicion con efecto: si un modelo corrio una tarea mas facil que el
otro, la diferencia mide el reparto y no el modelo. Solo se comparan celdas donde los dos
tienen fila.

Y EL COSTO SE COMPARA EN PLATA, no en tokens. `terra` razona por su cuenta y esos tokens se
facturan como salida, asi que en tokens crudos parece mas barato de lo que es. Esa
discrepancia es exactamente `P27d`, y se reporta como direccion —si en algun lambda las dos
unidades dan veredictos opuestos— y no como una diferencia de magnitud.
"""

# Corre DESDE `lab/`: las rutas de datos son relativas al CWD. El prologo solo
# resuelve los imports, que es lo que se rompe al salir de la raiz.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.runner import load_rows
from app.tariffs import DECLARADOS
from bench._sanity import bounded

CORPUS = "gold_p18"
MODELOS = [("nano", "nano"), ("terra", "terra"), ("luna", "luna")]
SALIDA = 0.15


def celdas(carpeta: str) -> dict[tuple[str, str], dict]:
    f = Path(f"results/{carpeta}/{CORPUS}_rows.jsonl")
    if not f.exists():
        return {}
    por = defaultdict(list)
    for r in load_rows(f):
        if not r.get("error"):
            por[(r["task_id"], r["paradigm"])].append(r)
    out = {}
    for k, rs in por.items():
        n = len(rs)
        out[k] = {
            "u": sum(r["utility"] for r in rs) / n,
            "prompt": sum(r.get("prompt_tokens", 0) for r in rs) / n,
            "completion": sum(r.get("completion_tokens", 0) for r in rs) / n,
            # AUSENTE NO ES CERO, y este analizador ya lo reporto mal una vez: las filas
            # escritas antes de capturar el campo no lo TIENEN, y decir «0 tokens de
            # razonamiento» sobre un modelo que razona es afirmar lo contrario de lo
            # medido. `None` cuando ninguna fila de la celda lo declara.
            "razonamiento": (
                sum(r["reasoning_tokens"] for r in rs) / n
                if all("reasoning_tokens" in r for r in rs) else None
            ),
            "ttft": statistics.median(
                [r.get("first_ttft_ms", 0) for r in rs if r.get("first_ttft_ms")] or [0]
            ),
            "wall": sum(r.get("wall_seconds", 0) for r in rs) / n,
            "n": n,
        }
    return out


def plata(c: dict, arancel: str) -> float:
    t = DECLARADOS[arancel]
    return (c["prompt"] * t.prompt_per_mtok
            + c["completion"] * t.completion_per_mtok) / 1_000_000


def main() -> None:
    datos = {etq: celdas(carpeta) for etq, carpeta in MODELOS}
    presentes = [e for e, d in datos.items() if d]
    if "nano" not in presentes:
        print("Sin linea base de nano — SIN N. Se dice, no se supone.")
        return
    print(f"modelos con filas: {presentes}")
    faltan = [e for e, _ in MODELOS if e not in presentes]
    if faltan:
        print(f"sin desplegar o sin correr: {faltan} — quedan FUERA, no cuentan como "
              f"perdidos")

    base = datos["nano"]
    for etq in presentes:
        if etq == "nano":
            continue
        otro = datos[etq]
        comunes = sorted(set(base) & set(otro))
        if not comunes:
            print(f"\n{etq}: ninguna celda en comun con nano — SIN N")
            continue

        print(f"\n=== nano vs {etq} — {len(comunes)} celdas pareadas")
        du = [otro[k]["u"] - base[k]["u"] for k in comunes]
        dtok = [
            (otro[k]["prompt"] + otro[k]["completion"])
            - (base[k]["prompt"] + base[k]["completion"]) for k in comunes
        ]
        dplata = [plata(otro[k], etq) - plata(base[k], "nano") for k in comunes]
        raz = [otro[k]["razonamiento"] for k in comunes
               if otro[k]["razonamiento"] is not None]
        raz_nano = [base[k]["razonamiento"] for k in comunes
                    if base[k]["razonamiento"] is not None]

        print(f"  utilidad     nano {statistics.mean(base[k]['u'] for k in comunes):.4f}"
              f"   {etq} {statistics.mean(otro[k]['u'] for k in comunes):.4f}"
              f"   delta {statistics.mean(du):+.4f}")
        gana = sum(1 for d in du if d > 0)
        pierde = sum(1 for d in du if d < 0)
        print(f"  celdas       gana {gana}  pierde {pierde}  empata "
              f"{len(du) - gana - pierde}")
        print(f"  tokens       delta {statistics.mean(dtok):+,.0f} por celda")
        print(f"  plata        delta USD {statistics.mean(dplata):+.6f} por celda")
        if raz and raz_nano:
            print(f"  razonamiento {etq} {statistics.mean(raz):.0f} tok/celda   "
                  f"nano {statistics.mean(raz_nano):.0f}")
        else:
            sin = [e for e, v in ((etq, raz), ("nano", raz_nano)) if not v]
            print(f"  razonamiento NO REGISTRADO en {sin} — filas anteriores a la captura "
                  f"del campo. Cero seria afirmar que no razona, y esta medido que si")

        ttft_b = [base[k]["ttft"] for k in comunes if base[k]["ttft"]]
        ttft_o = [otro[k]["ttft"] for k in comunes if otro[k]["ttft"]]
        if ttft_b and ttft_o:
            print(f"  TTFT p50     nano {statistics.median(ttft_b):,.0f} ms   "
                  f"{etq} {statistics.median(ttft_o):,.0f} ms")
        else:
            # AUSENTE NO ES CERO: el registro viejo no tiene el campo hasta que se
            # rellene desde el cache, y reportar 0 diria que responde instantaneo.
            print("  TTFT p50     no registrado en una de las dos — sin rellenar (`L-4`)")

        # P27d: las dos unidades, ¿discrepan en DIRECCION?
        st, sp = statistics.mean(dtok), statistics.mean(dplata)
        if st == 0 or sp == 0:
            print("  P27d: alguna de las dos deltas es cero — no hay direccion que comparar")
        elif (st > 0) != (sp > 0):
            print("  P27d CONFIRMADA: tokens y plata dan veredictos OPUESTOS. Toda "
                  "comparacion entre modelos tiene que ser en plata")
        else:
            print("  P27d: tokens y plata coinciden en direccion aca — la discrepancia, si "
                  "existe, esta en la magnitud y no en el signo")

        cuota = bounded(gana / len(du), 0.0, 1.0, f"{etq} tasa de victoria")
        print(f"  tasa de victoria por celda: {cuota:.1%}")


if __name__ == "__main__":
    main()
