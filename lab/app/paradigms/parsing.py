"""Leer JSON que escribio un modelo: un extractor, un contrato de excepciones.

M14 — POR QUE UN MODULO. `raw[raw.index("{"): raw.rindex("}") + 1]` estaba copiado NUEVE
veces, y las tuplas de excepciones que lo rodeaban habian llegado a **cinco combinaciones
distintas**: `(ValueError, KeyError, TypeError)`, `(ValueError, TypeError)`,
`(json.JSONDecodeError, OSError)`, `(json.JSONDecodeError, KeyError, TypeError,
ValueError, IndexError)`... Cada copia decidia por su cuenta que era un error del modelo y
que un error del harness, y ninguna estaba de acuerdo con las otras. Un paradigma
degradaba donde otro moria.

M13 — POR QUE ADEMAS HAY UN VALIDADOR DE FORMA. Varias copias defendian el PARSEO y no la
FORMA: `json.loads` puede devolver perfectamente una lista de strings, o dicts sin la
clave que el codigo va a leer dos lineas mas abajo. El acceso quedaba **fuera del try** y
un plan malformado mataba la tarea entera en vez de degradar, que es lo que ese mismo
paradigma ya hacia cuando el JSON no parseaba.

EL CONTRATO, EN UN SOLO LUGAR: cualquier malformacion —texto sin llaves, JSON invalido,
clave ausente, tipo equivocado— devuelve el `default`. Nada de esto es un error del
harness: es el modelo devolviendo algo que no sirve, y eso es un dato del experimento.
"""

from __future__ import annotations

import json
from typing import Any

# Un objeto JSON del modelo puede venir envuelto en prosa o en un bloque de codigo. Se
# recorta entre la primera llave y la ultima, que es lo que las nueve copias hacian.
_OPEN, _CLOSE = "{", "}"


def extract_json(text: str | None, key: str | None = None, default: Any = None) -> Any:
    """El objeto JSON adentro de `text`, o `default` si no hay uno usable.

    Con `key`, devuelve ese campo del objeto. La clave ausente NO es distinta de un JSON
    roto: en los dos casos el modelo no entrego lo que se le pidio.
    """
    if not text:
        return default
    try:
        raw = text.strip()
        raw = raw[raw.index(_OPEN): raw.rindex(_CLOSE) + 1]
        payload = json.loads(raw)
    except (ValueError, TypeError):
        # ValueError cubre json.JSONDecodeError y el .index() que no encuentra llave.
        return default
    if key is None:
        return payload
    if not isinstance(payload, dict) or key not in payload:
        return default
    return payload[key]


def well_formed(items: Any, *required: str) -> list[dict[str, Any]]:
    """Sólo los elementos que son dicts y traen TODAS las claves requeridas.

    Filtrar en vez de levantar es deliberado: un plan con tres pasos de los cuales uno
    esta malformado sigue siendo un plan de dos pasos, y esa es la conducta que estos
    paradigmas ya tienen cuando el JSON entero no parsea. Levantar aca los haria morir
    por un elemento roto y degradar por un documento roto, que son incoherentes entre si.
    """
    if not isinstance(items, list):
        return []
    return [
        item for item in items
        if isinstance(item, dict) and all(k in item for k in required)
    ]
