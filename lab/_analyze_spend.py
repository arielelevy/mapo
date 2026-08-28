"""X-2: en que se gasto, separado por clase de token, y que falta para convertirlo a plata.

EL DIAGNOSTICO ANTERIOR ESTABA MAL. El pendiente decia "falta el split prompt/completion y
la tarifa". El split EXISTE: `Usage` lleva `prompt_tokens` y `completion_tokens` desde
siempre, y cada respuesta cacheada trae el `usage` que devolvio el endpoint. Lo que pasaba
es que la FILA guardaba solo el total, asi que la informacion se tiraba al escribir.

Dos mitades, y son independientes:

  (1) EL SPLIT. Se arregla hacia adelante agregandolo a la fila; y para lo ya pagado se
      puede reconstruir desde el cache, que guarda el `usage` de cada respuesta.
  (2) LA TARIFA. NO se inventa. Un precio inventado produce un numero que parece una
      medicion y no lo es — que es exactamente la clase de cosa que este banco no hace.
      Se declara por variable de entorno o no se reporta plata.

POR QUE IMPORTA EL SPLIT Y NO SOLO EL TOTAL. Los precios de entrada y salida difieren por
un factor grande, y los paradigmas se diferencian JUSTO en esa proporcion: uno que relee el
contexto en cada vuelta gasta casi todo en entrada; uno que genera planes largos gasta en
salida. Sumar los dos y multiplicar por un precio promedio borra la diferencia que decide
cual es mas barato de verdad.
"""

import json
import os
import sys
from collections import defaultdict
from dataclasses import replace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings

# Precio por millon de tokens. Sin default: un precio inventado produce un numero que
# parece una medicion. Si no estan, se reportan tokens y no plata.
IN_VAR, OUT_VAR = "MAPO_PRICE_IN_PER_M", "MAPO_PRICE_OUT_PER_M"


def main() -> None:
    settings = Settings.from_env()
    by_fp: dict[str, dict[str, int]] = defaultdict(lambda: {
        "prompt": 0, "completion": 0, "entries": 0, "sin_usage": 0,
    })
    unreadable = 0

    for path in settings.cache_dir.rglob("*.json"):
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # Se cuenta y se reporta. Una entrada ilegible es un hecho del disco, y
            # saltearla en silencio haria que el total pareciera completo.
            unreadable += 1
            continue
        if not isinstance(rec, dict) or "fingerprint" not in rec:
            continue  # embeddings y grafo: otra forma de registro, otro precio
        fp = rec["fingerprint"]
        bucket = by_fp[fp]
        bucket["entries"] += 1
        usage = (rec.get("body") or {}).get("usage") or {}
        if not usage:
            bucket["sin_usage"] += 1
            continue
        bucket["prompt"] += usage.get("prompt_tokens", 0)
        bucket["completion"] += usage.get("completion_tokens", 0)

    if unreadable:
        print(f"entradas ilegibles, contadas y no ignoradas: {unreadable}\n")

    price_in = os.environ.get(IN_VAR)
    price_out = os.environ.get(OUT_VAR)

    print("gasto por decodificacion, reconstruido desde el cache")
    print(f"{'huella':<52} {'entradas':>9} {'entrada':>12} {'salida':>12} {'sal/ent':>8}")
    grand = {"prompt": 0, "completion": 0}
    for fp, b in sorted(by_fp.items(), key=lambda kv: -kv[1]["prompt"]):
        ratio = b["completion"] / b["prompt"] if b["prompt"] else 0.0
        print(f"{fp:<52} {b['entries']:>9,} {b['prompt']:>12,} "
              f"{b['completion']:>12,} {ratio:>7.1%}")
        if b["sin_usage"]:
            print(f"{'':<52} {b['sin_usage']:>9,} entradas SIN usage reportado")
        grand["prompt"] += b["prompt"]
        grand["completion"] += b["completion"]

    total = grand["prompt"] + grand["completion"]
    print(f"\n{'TOTAL':<52} {'':>9} {grand['prompt']:>12,} {grand['completion']:>12,}")
    print(f"tokens totales: {total:,}")
    share = grand["completion"] / total if total else 0
    print(f"la salida es el {share:.1%} de los tokens — y es la parte cara")

    print()
    if price_in and price_out:
        money = (grand["prompt"] / 1e6) * float(price_in) + \
                (grand["completion"] / 1e6) * float(price_out)
        print(f"tarifa declarada: entrada {price_in}/M · salida {price_out}/M")
        print(f"GASTO: {money:,.2f}")
    else:
        faltan = [v for v in (IN_VAR, OUT_VAR) if not os.environ.get(v)]
        print(f"SIN TARIFA: falta {', '.join(faltan)}. No se reporta plata.")
        print("Un precio inventado produce un numero que parece una medicion y no lo es.")
        print(f"Con la tarifa puesta, el calculo es exacto: "
              f"{grand['prompt']:,}/1e6 x precio_entrada + "
              f"{grand['completion']:,}/1e6 x precio_salida")

    out = replace(settings, results_dir=settings.results_dir).results_dir / "spend.json"
    out.write_text(json.dumps({
        "por_huella": {k: dict(v) for k, v in by_fp.items()},
        "total_prompt": grand["prompt"],
        "total_completion": grand["completion"],
        "entradas_ilegibles": unreadable,
        "tarifa_declarada": bool(price_in and price_out),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\ndetalle: {out}")


if __name__ == "__main__":
    main()
