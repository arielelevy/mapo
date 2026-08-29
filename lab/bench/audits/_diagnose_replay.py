"""Cual es la PRIMERA llamada que falla el replay sellado, y en que se diferencia.

El test de R-1 dio miss por el camino del runner, asi que el defecto no estaba en el
script de replay anterior. Falta la causa, y la causa es una sola pregunta: el payload
que se construye hoy, ¿es el mismo que se construyo cuando se pago la fila?

Esto no lo puede contestar el cache solo — el registro guarda la clave y la respuesta,
no el payload. Asi que se instrumenta el cliente: se intercepta `complete`, se anota
cada payload con su clave, y se reporta el primero que no esta. Con el payload en la
mano se puede ver QUE llamada es (extractor de features, sonda, o el paradigma) y que
parte de ella pudo moverse.
"""

# Corre DESDE `lab/`: las rutas de datos son relativas al CWD. El prologo solo
# resuelve los imports, que es lo que se rompe al salir de la raiz.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import json
import sys
from dataclasses import replace
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings
from app.llm import LLMClient, SealedCacheMiss
from app.runner import Runner

CORPUS = "gold_p17"
TASK_ID = "c1-000"
PARADIGM = "react"

seen: list[dict] = []


def main() -> None:
    base = Settings.from_env()
    live = replace(base, results_dir=base.results_dir / "nano")
    scratch = live.results_dir / "_replay_probe"
    scratch.mkdir(parents=True, exist_ok=True)
    sealed_settings = replace(live, results_dir=scratch)

    original = LLMClient.complete

    def traced(self, messages, tools=None, max_tokens=None, seed_override=None):
        payload = {
            "messages": messages,
            "seed": self._settings.seed if seed_override is None else seed_override,
            "max_completion_tokens": max_tokens or self._settings.max_tokens,
        }
        # Sigue a `LLMClient.complete`: `temperature` se fue del payload el 2026-08-29
        # —los modelos de razonamiento no la aceptan— y la reemplaza `reasoning_effort`.
        # Este archivo REIMPLEMENTA la clave de cache, asi que divergir aca hace que el
        # diagnostico de replay reporte misses que no existen.
        if self._settings.reasoning_effort is not None:
            payload["reasoning_effort"] = self._settings.reasoning_effort
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        key = self._key(payload)
        hit = self._cache_path(key).exists()
        seen.append({"key": key, "hit": hit, "payload": payload,
                     "n_tools": len(tools or []), "n_msgs": len(messages)})
        return original(self, messages, tools=tools, max_tokens=max_tokens,
                        seed_override=seed_override)

    LLMClient.complete = traced
    try:
        runner = Runner(sealed_settings, CORPUS, sealed=True,
                        retriever_arm="hybrid", surface_variant="basic")
        runner.run_cross_product(paradigms=[PARADIGM], task_ids=[TASK_ID],
                                 repeat=1, resume=False)
        print("replayo sin miss (inesperado para este diagnostico)")
    except SealedCacheMiss:
        pass
    except Exception as exc:  # noqa: BLE001
        print(f"corto por {type(exc).__name__}: {exc}")
    finally:
        LLMClient.complete = original

    print(f"\nllamadas interceptadas: {len(seen)}")
    for i, call in enumerate(seen):
        mark = "HIT " if call["hit"] else "MISS"
        first = call["payload"]["messages"][0]
        role = first.get("role", "?")
        head = (first.get("content") or "")[:90].replace("\n", " ")
        print(f"  {i:>2} {mark} seed={call['payload']['seed']} "
              f"msgs={call['n_msgs']} tools={call['n_tools']} | {role}: {head}")

    misses = [c for c in seen if not c["hit"]]
    if not misses:
        print("\nno hubo miss en las llamadas interceptadas.")
        return

    first_miss = misses[0]
    out = Path("results/nano/_replay_probe/first_miss.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(first_miss, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"\nPRIMER MISS: indice {seen.index(first_miss)} · clave {first_miss['key'][:16]}")
    print(f"payload completo en {out}")
    print("\n--- mensajes de ese payload ---")
    for m in first_miss["payload"]["messages"]:
        content = (m.get("content") or "")
        print(f"\n[{m.get('role')}] ({len(content)} chars)")
        print(content[:1200])


if __name__ == "__main__":
    main()
