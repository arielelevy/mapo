"""RRF contra Relative Score Fusion, y el tokenizador viejo contra el nuevo. SIN GASTAR.

POR QUE SE PUEDE MEDIR GRATIS. La fusion opera sobre rankings ya computados, y los
embeddings estan cacheados por contenido. Asi que comparar dos fusiones no necesita correr
ni un paradigma: se le da a cada una las mismas consultas, se mira que unidades PORTADORAS
devuelve, y se cuenta. Correr paradigmas mediria la fusion mezclada con trece topologias.

QUE SE MIDE. `recall@k` contra las unidades relevantes que la tarea declara, para varios
`k`. Es la metrica correcta para un recuperador porque lo que el paradigma hace despues
depende de si el material ESTA en lo devuelto: una unidad que no vuelve no se puede leer,
y ninguna topologia la recupera.

LA CONSULTA ES LA PREGUNTA DE LA TAREA, sin reformular. Reformularla mediria la
reformulacion. Es la peor consulta posible y es la honesta: es la que un paradigma emite
en su primera busqueda, antes de saber nada.
"""

# Corre DESDE `lab/`.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import json
import statistics
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings
from app.embeddings import EmbeddingClient
from app.retrieval import CorpusView, HybridRetriever, LexicalRetriever, SemanticRetriever

KS = (1, 3, 5, 10)


def recall_at(devueltas: list[str], relevantes: set[str], k: int) -> float | None:
    if not relevantes:
        return None
    return len(set(devueltas[:k]) & relevantes) / len(relevantes)


def evaluar(nombre, ranker, vistas, k_max) -> dict[int, float]:
    por_k: dict[int, list[float]] = {k: [] for k in KS}
    for view, pregunta in vistas:
        devueltas = ranker.rank(view, pregunta, k_max)
        for k in KS:
            r = recall_at(devueltas, view.relevant, k)
            if r is not None:
                por_k[k].append(r)
    return {k: statistics.mean(v) for k, v in por_k.items() if v}


def main() -> None:
    corpus = sys.argv[1] if len(sys.argv) > 1 else "corpus/gold_p18"
    base = Path(corpus)
    documents = json.loads((base / "documents.json").read_text(encoding="utf-8"))
    tasks = json.loads((base / "tasks.json").read_text(encoding="utf-8"))
    if isinstance(tasks, dict):
        tasks = list(tasks.values())

    vistas = []
    for t in tasks:
        view = CorpusView(
            task_id=t["task_id"],
            documents=documents,
            unit_ids=t["unit_ids"],
            relevant_units=t.get("relevant_units", []),
        )
        if view.relevant:
            vistas.append((view, t["question"]))

    print(f"{corpus}: {len(vistas)} tareas con unidades portadoras declaradas")
    print(f"unidades relevantes por tarea: mediana "
          f"{statistics.median(len(v.relevant) for v, _ in vistas):.0f}\n")

    settings = Settings.from_env()
    embedder = EmbeddingClient(settings, settings.embedding_deployment)

    brazos = [
        ("lexical (bm25)", LexicalRetriever()),
        ("semantic (dense)", SemanticRetriever(embedder)),
        ("hybrid + RRF", HybridRetriever(embedder, fusion="rrf")),
        ("hybrid + relative_score", HybridRetriever(embedder, fusion="relative_score")),
    ]

    print(f"{'brazo':<26}" + "".join(f"{'R@'+str(k):>9}" for k in KS))
    resultados = {}
    for nombre, ranker in brazos:
        r = evaluar(nombre, ranker, vistas, max(KS))
        resultados[nombre] = r
        print(f"{nombre:<26}" + "".join(f"{r.get(k, 0):>9.3f}" for k in KS))

    # LA COMPARACION ES PAREADA POR TAREA. Restar dos promedios no dice si la diferencia
    # sobrevive a la variacion entre tareas, y con 29 tareas esa variacion es grande.
    print()
    rrf_r = HybridRetriever(embedder, fusion="rrf")
    rel_r = HybridRetriever(embedder, fusion="relative_score")
    for k in KS:
        difs = []
        for view, pregunta in vistas:
            a = recall_at(rrf_r.rank(view, pregunta, max(KS)), view.relevant, k)
            b = recall_at(rel_r.rank(view, pregunta, max(KS)), view.relevant, k)
            if a is not None and b is not None:
                difs.append(b - a)
        m = statistics.mean(difs)
        sd = statistics.pstdev(difs)
        ee = sd / len(difs) ** 0.5 if sd else 0.0
        sig = f"{abs(m)/ee:.2f}" if ee else ("0.00" if abs(m) < 1e-12 else "inf")
        mejor = sum(1 for d in difs if d > 1e-9)
        peor = sum(1 for d in difs if d < -1e-9)
        print(f"  relative_score - RRF  @{k:<3} {m:+.4f}  ee {ee:.4f}  {sig:>5} ee   "
              f"(mejor en {mejor} tareas, peor en {peor}, igual en {len(difs)-mejor-peor})")
    print()
    print("  Un delta menor que la diferencia entre dos tareas cualesquiera no elige nada.")
    print("  La decision es de PRODUCTO: si produccion fusiona distinto que el banco, el")
    print("  banco mide otra cosa — asi que lo que importa es que sean LA MISMA, y cual")
    print("  sea se decide por este numero.")


if __name__ == "__main__":
    main()
