"""La ingesta como ETAPA, separada del request que responde (G-4, G-1).

LA REGLA QUE IMPONE. **Ningun paradigma construye estado derivado propio adentro de un
request.** No es higiene: son dos defectos concretos y separados, y los dos estaban
ocurriendo en `graph_traverse`.

  ECONOMICO      el indice se paga una vez y sirve a todas las consultas futuras, pero su
                 costo caia entero sobre la PRIMERA fila que lo necesitaba — una fila
                 arbitraria, la que el orden del cross product puso primero. Promediar el
                 brazo mezclaba entonces «amortizar» con «responder», y el paradigma salia
                 caro por una construccion que ninguna otra fila volvia a pagar.

  INSTRUMENTACION  construir LEE, y leer se registra. Un paradigma que indexa el corpus
                 entero para responder una pregunta figura leyendolo entero, asi que su
                 huella de lectura describe la ingesta y no la respuesta.

LO QUE ESTE MODULO NO HACE: no acelera nada ni cachea mejor que antes. Mueve el gasto y la
lectura a donde se pueden atribuir, que es lo unico que estaba mal.

PREFERIR LA ETAPA, Y SI FALTA CONSTRUIR AL VUELO SIN COBRARLO (decision del autor,
2026-08-29). La version anterior de este modulo se negaba a construir en el request, y esa
regla resolvia la mitad equivocada del problema: el defecto no era QUE se construyera, era
QUIEN lo pagaba. Un paradigma que no puede construir su indice deja de ser medible; uno que
lo construye y se lo carga a una fila arbitraria produce un costo que ninguna otra fila
repite.

Asi que el fallback existe y su gasto va a un contador APARTE (`ToolSurface.ingest_tokens`),
que el runner descuenta de `cost_tokens` y registra en su propia columna. La ingesta es otra
medicion, no un renglon de la de ejecucion.

Es tambien la condicion (b) del revival de `graph_traverse` (`K-5`): un indice con la
disciplina de la sonda, construido antes y aparte, no adentro de la pregunta.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .fsio import write_atomic
from .llm import LLMClient, Usage
from .paradigms.parsing import extract_json

INGEST_SUBDIR = "ingest"
INDEX_MAX_TOKENS = 500


class IngestMissing(RuntimeError):
    """La ingesta no corrio y el paradigma la necesita. NO se construye al vuelo."""


@dataclass(frozen=True)
class Ingested:
    """El estado derivado del corpus, ya construido. De solo lectura para el request."""

    digest: str
    entity_graph: dict[str, Any]
    # LO QUE COSTO, para que se pueda reportar aparte y no dentro de una fila. `units` es
    # cuanto LEYO la ingesta: es la lectura que dejaba de significar «lo que el paradigma
    # necesito» cuando pasaba por la fila.
    tokens: int = 0
    calls: int = 0
    units: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "digest": self.digest,
            "ingest_tokens": self.tokens,
            "ingest_calls": self.calls,
            "ingest_units_read": self.units,
            "entities": len(self.entity_graph.get("entity_units", {})),
            "edges": len(self.entity_graph.get("edges", {})),
        }


def corpus_digest(documents: dict[str, str], unit_ids: list[str], fingerprint: str) -> str:
    """Identidad del indice: el corpus que describe Y la decodificacion que lo produjo.

    El corpus solo no alcanzaba. El indice lo extrae el modelo, asi que uno construido por
    un modelo se estaba sirviendo a una corrida de otro — contaminacion cruzada silenciosa
    justo en el brazo que depende de que el indice sea fiel.
    """
    key = json.dumps(
        [fingerprint, sorted((u, len(documents[u])) for u in unit_ids if u in documents)]
    ).encode()
    return hashlib.sha256(key).hexdigest()[:16]


def _path(client: LLMClient, digest: str) -> Path:
    root = client.cache_root / INGEST_SUBDIR
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{digest}.json"


def load(client: LLMClient, documents: dict[str, str], unit_ids: list[str]) -> Ingested | None:
    """La ingesta ya construida, o `None`. NUNCA la construye."""
    digest = corpus_digest(documents, unit_ids, client.fingerprint)
    path = _path(client, digest)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # Un indice truncado (crash o carrera de escritura) se descarta, no se sirve para
        # siempre. Se borra aca y lo reconstruye la ETAPA, no el request.
        path.unlink(missing_ok=True)
        return None
    return Ingested(
        digest=digest,
        entity_graph=payload.get("graph", {}),
        tokens=payload.get("ingest_tokens", 0),
        calls=payload.get("ingest_calls", 0),
        units=payload.get("ingest_units_read", 0),
    )


def build(
    client: LLMClient, documents: dict[str, str], unit_ids: list[str], force: bool = False
) -> Ingested:
    """Construye el estado derivado del corpus. Se llama DESDE la etapa, no desde un request.

    Una extraccion corta por unidad. Su gasto se devuelve adentro del `Ingested` y NO se
    mezcla con el `Usage` de ninguna fila: esa mezcla es la mitad economica de `G-4`.
    """
    existing = None if force else load(client, documents, unit_ids)
    if existing is not None:
        return existing

    usage = Usage()
    calls = 0
    entity_units: dict[str, list[str]] = defaultdict(list)
    edges: dict[str, list[str]] = defaultdict(list)
    for unit_id in unit_ids:
        if unit_id not in documents:
            continue
        prompt = (
            "List the entities (people, document ids, projects, addresses, dates) "
            "mentioned in this text, and directed relations between them.\n"
            'JSON only: {"entities": ["..."], "relations": [["a","b"], ...]}\n\n'
            f"[{unit_id}]\n{documents[unit_id]}"
        )
        completion = client.complete(
            messages=[{"role": "user", "content": prompt}], max_tokens=INDEX_MAX_TOKENS
        )
        usage.merge(completion.usage)
        calls += 1
        payload = extract_json(completion.text)
        if not isinstance(payload, dict):
            continue
        ents = [
            str(e).strip().lower() for e in payload.get("entities", []) if str(e).strip()
        ]
        for e in ents:
            entity_units[e].append(unit_id)
        for pair in payload.get("relations", []):
            if isinstance(pair, list) and len(pair) >= 2:
                a, b = str(pair[0]).lower(), str(pair[1]).lower()
                edges[a].append(b)
                edges[b].append(a)
        # La co-mencion tambien es una arista: el backbone de co-ocurrencia.
        for i, a in enumerate(ents):
            for b in ents[i + 1:]:
                edges[a].append(b)
                edges[b].append(a)

    graph = cluster(
        {k: sorted(set(v)) for k, v in entity_units.items()},
        {k: sorted(set(v)) for k, v in edges.items()},
    )
    digest = corpus_digest(documents, unit_ids, client.fingerprint)
    result = Ingested(
        digest=digest,
        entity_graph=graph,
        tokens=usage.total_tokens,
        calls=calls,
        units=len([u for u in unit_ids if u in documents]),
    )
    write_atomic(
        _path(client, digest),
        json.dumps(
            {
                "graph": graph,
                "ingest_tokens": result.tokens,
                "ingest_calls": result.calls,
                "ingest_units_read": result.units,
            },
            ensure_ascii=False,
        ),
    )
    return result


def canonical_form(a: str, b: str) -> bool:
    """Si `a` y `b` pueden ser la misma entidad nombrada de dos formas.

    LA CLUSTERIZACION ES OBLIGATORIA, NO UNA MEJORA. Un extractor que devuelve
    «m. cavallero» de una unidad y «marta cavallero» de otra crea DOS nodos, y el grafo
    queda partido justo entre las unidades que habia que conectar. Con el corpus de
    entidades eso es peor que no tener grafo: `graph_traverse` recorreria un grafo cuya
    fragmentacion es artefacto del extractor y no del mundo.

    LA REGLA ES CONSERVADORA A PROPOSITO. Une solo cuando una forma es una ABREVIATURA
    reconocible de la otra —inicial mas apellido, nombre mas inicial, apellido solo— y
    nunca por parecido de string. Unir de mas es peor que unir de menos: dos personas
    fundidas en un nodo producen una respuesta con la confianza de una travesia y el
    contenido de una confusion, y nada aguas abajo lo puede detectar.
    """
    if a == b:
        return True
    corto, largo = sorted((a, b), key=len)
    pl = largo.split()
    if len(pl) < 2:
        return False
    nombre, apellido = pl[0], pl[-1]
    resto = " ".join(pl[1:])
    return corto in (
        f"{nombre[0]}. {resto}", f"{nombre[0]}.{resto}",
        f"{nombre} {apellido[0]}.", f"{nombre} {apellido[0]}",
        apellido,
    )


def cluster(entity_units: dict[str, list[str]], edges: dict[str, list[str]]) -> dict[str, Any]:
    """Agrupa superficies de la misma entidad y deduplica, eligiendo un representante.

    EL REPRESENTANTE ES LA FORMA MAS LARGA del grupo, no la mas frecuente. La mas larga es
    la mas especifica —«marta cavallero» sobre «cavallero»— y elegir por frecuencia dejaria
    que un mundo donde la abreviatura abunda canonice la forma ambigua.

    LO QUE ESTA FUNCION NO PUEDE HACER, y por eso el corpus guarda su gold aparte: si dos
    personas distintas comparten apellido, «cavallero» es genuinamente ambigua y unirla a
    cualquiera de las dos seria inventar. Se queda como su propio nodo, sin fusionar, y el
    grafo lo refleja en vez de esconderlo.
    """
    formas = sorted(set(entity_units) | set(edges), key=lambda x: (-len(x), x))
    padre: dict[str, str] = {}
    for f in formas:
        elegido = None
        for otra in formas:
            if otra in padre and canonical_form(f, padre[otra]):
                # AMBIGUEDAD: si la forma corta pega con DOS representantes distintos, no
                # se une a ninguno. Es el caso de un apellido compartido.
                if elegido is not None and padre[otra] != elegido:
                    elegido = None
                    break
                elegido = padre[otra]
        padre[f] = elegido or f

    unidades: dict[str, list[str]] = {}
    aristas: dict[str, list[str]] = {}
    for forma, rep in padre.items():
        unidades.setdefault(rep, []).extend(entity_units.get(forma, []))
        aristas.setdefault(rep, []).extend(edges.get(forma, []))
    # Las aristas tambien se mapean al representante: una arista a «cavallero» y otra a
    # «marta cavallero» son la misma arista, y contarlas dos veces infla el grado.
    aristas = {
        rep: sorted({padre.get(v, v) for v in vs} - {rep})
        for rep, vs in aristas.items()
    }
    return {
        "entity_units": {k: sorted(set(v)) for k, v in unidades.items()},
        "edges": aristas,
        # QUE SE FUSIONO CON QUE. Sin esto un grafo raro no se puede diagnosticar: no se
        # sabria si el extractor no vio la entidad o si la clusterizacion la absorbio.
        "aliases": {f: r for f, r in sorted(padre.items()) if f != r},
    }


def require(surface: Any, client: LLMClient, documents: dict[str, str],
            unit_ids: list[str], paradigm: str) -> Ingested:
    """El estado derivado: el de la etapa si existe, construido al vuelo si no.

    LO QUE CAMBIA NO ES SI SE CONSTRUYE, ES QUIEN LO PAGA. Construir al vuelo esta bien —un
    paradigma que no puede construir su indice deja de ser medible— y lo que estaba mal era
    que el costo cayera adentro de `cost_tokens` de una fila cualquiera. Aca se acumula en
    `surface.ingest_tokens`, el runner lo descuenta, y la ingesta queda como su propia
    medicion.

    `IngestMissing` sigue existiendo para el caso sin cliente: sin con que construir, decir
    que falta es la unica respuesta honesta.
    """
    ya = getattr(surface, "ingested", None)
    if ya is not None:
        return ya
    if client is None:
        raise IngestMissing(
            f"{paradigm} necesita el estado derivado del corpus, la etapa de ingesta no "
            f"corrio y no hay cliente con que construirlo."
        )
    antes = getattr(client, "spent", None)
    marca = antes.total_tokens if antes is not None else 0
    ingested = build(client, documents, unit_ids)
    despues = antes.total_tokens if antes is not None else 0
    # SE MIDE CONTRA EL MEDIDOR DE LA CELDA, no contra `ingested.tokens`. Un indice servido
    # del cache devuelve sus tokens historicos y no gasto NADA ahora: cobrar esos tokens
    # inventaria gasto, y descontarlos de `cost_tokens` lo inventaria en negativo.
    surface.ingest_tokens = getattr(surface, "ingest_tokens", 0) + max(0, despues - marca)
    return ingested
