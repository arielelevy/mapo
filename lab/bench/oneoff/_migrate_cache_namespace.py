"""Mueve el cache existente al namespace de la cuenta que lo pago.

POR QUE UNA MUDANZA Y NO UNA INVALIDACION. La clave de cache es un sha256 sobre
(fingerprint de decodificacion, payload del request), y el registro guardado NO conserva
el payload: no hay forma de re-derivar una clave nueva a partir de lo que hay en disco.
Meter el host adentro del hash, entonces, no habria sido "invalidar una vez" sino tirar
6292 completions y 810 embeddings ya pagados, y dejar sin replay sellada a la grilla
congelada. El namespace por directorio da la MISMA garantia -- dos cuentas no pueden
leerse las entradas -- sin tocar una sola clave.

Todo lo que hay hoy en cache/ lo produjo la cuenta que esta en el .env, asi que la
mudanza es: cache/<shard>/  ->  cache/<tag-de-cuenta>/<shard>/ ; y lo mismo con
embeddings/ (bajo el tag de SU endpoint, que puede ser otra cuenta) y con graph/.

Idempotente: si ya esta migrado, no toca nada. Cuenta archivos antes y despues.
"""

# Corre DESDE `lab/`: las rutas de datos son relativas al CWD. El prologo solo
# resuelve los imports, que es lo que se rompe al salir de la raiz.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import pathlib
import re
import shutil
import sys


from app.config import Settings

SHARD = re.compile(r"^[0-9a-f]{2}$")


def count_json(root: pathlib.Path) -> int:
    return sum(1 for _ in root.rglob("*.json")) if root.exists() else 0


def main() -> int:
    s = Settings.from_env()
    cache = s.cache_dir
    chat_tag, emb_tag = s.account_tag(), s.embedding_account_tag()
    before = count_json(cache)
    print(f"cache: {cache}")
    print(f"  archivos .json antes: {before}")
    print(f"  tag chat:       {chat_tag}")
    print(f"  tag embeddings: {emb_tag}")

    shards = [d for d in cache.iterdir() if d.is_dir() and SHARD.match(d.name)]
    legacy_emb = cache / "embeddings"
    legacy_graph = cache / "graph"
    if not shards and not legacy_emb.exists() and not legacy_graph.exists():
        print("  nada que migrar: el cache ya vive bajo un namespace de cuenta.")
        return 0

    moved = 0
    chat_root = cache / chat_tag
    chat_root.mkdir(parents=True, exist_ok=True)
    for shard in shards:
        target = chat_root / shard.name
        if target.exists():
            for entry in shard.iterdir():
                dest = target / entry.name
                if dest.exists():
                    entry.unlink()          # identica clave, identico contenido
                else:
                    shutil.move(str(entry), str(dest))
                moved += 1
            shard.rmdir()
        else:
            moved += sum(1 for _ in shard.glob("*.json"))
            shutil.move(str(shard), str(target))
    print(f"  completions movidas: {moved}")

    if legacy_emb.exists():
        emb_target = cache / emb_tag / "embeddings"
        emb_target.parent.mkdir(parents=True, exist_ok=True)
        n = count_json(legacy_emb)
        if emb_target.exists():
            sys.exit(f"FAIL: {emb_target} ya existe; resolver a mano.")
        shutil.move(str(legacy_emb), str(emb_target))
        print(f"  embeddings movidos: {n}")

    if legacy_graph.exists():
        # El indice de entidades ahora se keyea tambien por fingerprint del modelo, asi
        # que estos archivos quedan huerfanos igual. Se mudan en vez de borrarse: se
        # reconstruyen gratis desde el cache de completions si alguna corrida los pide.
        graph_target = chat_root / "graph"
        n = count_json(legacy_graph)
        if graph_target.exists():
            sys.exit(f"FAIL: {graph_target} ya existe; resolver a mano.")
        shutil.move(str(legacy_graph), str(graph_target))
        print(f"  indices de grafo movidos: {n} (quedan huerfanos por el nuevo digest)")

    after = count_json(cache)
    print(f"  archivos .json despues: {after}")
    if after != before:
        sys.exit(f"FAIL: se perdieron archivos ({before} -> {after})")
    print("OK: mismo conteo, nada perdido.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
