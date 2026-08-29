"""Aranceles: se LEEN de `config/tariffs.json`, no se escriben aca.

POR QUE SON DATOS Y NO CODIGO. Un precio es una clausula del contrato con el proveedor:
cambia sin avisar, no lo decide nadie de este lado, y actualizarlo no deberia tocar un
`.py` ni pasar por una revision de codigo. Mientras estuvieron como constantes fueron
**referencia inventada** —0,05/0,40 para nano cuando el real es 0,20/1,25, un error de 4x
en la entrada— y nada en el sistema podia notarlo, porque un numero puesto a mano se lee
igual de seguro que uno verificado.

QUE SOBREVIVIO A ESE ERROR Y POR QUE. Las conclusiones de `X-5a` —el orden entre paradigmas
aguanta al pasar de tokens a plata— no dependian del valor: se enunciaron sobre lo
INVARIANTE al arancel y se barrio la proporcion salida/entrada de x1 a x32. La real es ~6x
en los cuatro modelos, bien adentro. Es la primera vez que la disciplina de «afirmar solo lo
invariante» se cobra sola.

EL HALLAZGO QUE NINGUN NUMERO INVENTADO HABRIA DADO: **`luna` cuesta lo mismo que `nano`**
(0,20/1,20 contra 0,20/1,25). No es el modelo caro del catalogo, es de clase nano. Si
resulta mas capaz al mismo precio, eso no es ruteo sino SUSTITUCION. Los caros de verdad son
`terra` (9,8x) y `sol` (24,5x).

TRES EJES QUE EL JSON DECLARA Y `Tariff` TODAVIA NO MODELA. Contexto largo (2x entrada, 1,5x
salida), entrada cacheada (10x menos) y escritura de cache (cobrada en los `5.6`, no en
nano). Se leen y se conservan en `TariffDetail`, y **no** entran en el calculo hasta que
algo los consuma — declarar campos que nadie usa es la falla que este repo se pasa el dia
encontrando.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .metrics import Tariff

TARIFFS_PATH = Path(__file__).resolve().parent.parent / "config" / "tariffs.json"


@dataclass(frozen=True)
class TariffDetail:
    """Todo lo que el proveedor cobra, no solo lo que el modelo de costo usa hoy.

    `Tariff` modela dos precios planos porque es lo que `Study` sabe barrer. Esto conserva
    el resto —cacheado, escritura, contexto largo— para que estén cuando algo los consuma,
    y para que actualizarlos sea editar un JSON y no descubrir que se perdieron.
    """

    name: str
    deployment: str
    tariff: Tariff
    cached_prompt: float | None
    cache_write: float | None
    long_context_prompt: float | None
    long_context_completion: float | None


def _load(path: Path = TARIFFS_PATH) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"No existe {path}. Los aranceles son DATOS y viven en un JSON: sin el, "
            f"cualquier numero que el codigo usara seria inventado, y un numero inventado "
            f"se lee igual de seguro que uno verificado. Se levanta."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _build(raw: dict[str, Any]) -> tuple[dict[str, TariffDetail], str]:
    fecha = raw.get("verified_on")
    if not fecha:
        raise ValueError(
            f"{TARIFFS_PATH.name} no declara `verified_on`. Un precio sin fecha no se "
            f"puede auditar: el reporte estampa la fecha para que un arancel viejo se VEA."
        )
    detalles: dict[str, TariffDetail] = {}
    for nombre, d in (raw.get("tariffs") or {}).items():
        for clave in ("prompt", "completion", "deployment"):
            if d.get(clave) is None:
                raise ValueError(
                    f"{nombre}: falta `{clave}`. Ausente no es cero — un arancel sin "
                    f"precio declarado haria parecer gratis a un modelo que no lo es."
                )
        detalles[nombre] = TariffDetail(
            name=nombre,
            deployment=d["deployment"],
            tariff=Tariff(
                name=f"{nombre}/{fecha}",
                prompt_per_mtok=float(d["prompt"]),
                completion_per_mtok=float(d["completion"]),
            ),
            cached_prompt=d.get("cached_prompt"),
            cache_write=d.get("cache_write"),
            long_context_prompt=d.get("long_context_prompt"),
            long_context_completion=d.get("long_context_completion"),
        )
    if not detalles:
        raise ValueError(f"{TARIFFS_PATH.name} no declara ningun arancel.")
    return detalles, fecha


_RAW = _load()
DETAILS, VERIFIED_ON = _build(_RAW)

# Los aranceles planos, que es lo que el analisis barre hoy.
DECLARADOS: dict[str, Tariff] = {n: d.tariff for n, d in DETAILS.items()}


def _role(papel: str) -> Tariff:
    """El arancel que juega ese papel del catalogo de modelos.

    Los papeles los declara el JSON —`fast: nano`, `deep: terra`— porque es una DECISION,
    no una derivación: `deep` es `terra` y no `sol` porque terra es el escalón más chico
    que existe, y la regla del repo es no comprar más garantía de la que la medición
    justifica. Que viva en el JSON hace que cambiarlo se vea en el diff.
    """
    roles = _RAW.get("roles") or {}
    nombre = roles.get(papel)
    if not nombre:
        raise ValueError(
            f"{TARIFFS_PATH.name} no declara que arancel juega el papel {papel!r}. "
            f"Elegir uno por omision seria decidir el precio del producto en silencio."
        )
    if nombre not in DECLARADOS:
        raise ValueError(
            f"El papel {papel!r} apunta a {nombre!r}, que no esta declarado "
            f"({sorted(DECLARADOS)})."
        )
    return DECLARADOS[nombre]


NANO = _role("fast")
DEEP = _role("deep")

# Embeddings: lo que HyDE paga aparte de su llamada al modelo.
EMBEDDINGS: dict[str, float] = dict(_RAW.get("embeddings") or {})


def breakeven(barato: Tariff, caro: Tariff, ratio_salida: float = 0.25) -> float:
    """Cuantas veces MENOS tokens tiene que usar el caro para costar lo mismo.

    `ratio_salida` es la fraccion de tokens que es completion. Un solo numero y no dos
    porque lo que decide es la MEZCLA, y la mezcla es una propiedad del paradigma que el
    registro ya tiene medida — no hace falta suponerla, se pasa la observada.

    Devuelve el multiplicador: si da 10, el caro necesita usar **1/10** de los tokens del
    barato para empatar. Cualquier numero grande es la respuesta honesta a «el caro
    resuelve con menos llamadas»: casi nunca alcanza, y por eso la decision correcta no es
    elegir modelo por defecto sino **rutear**.

    LA MEZCLA MUEVE POCO, y con los precios reales se ve cuanto: los cuatro aranceles
    tienen la salida entre 5,3x y 6,3x la entrada, asi que el equilibrio nano->terra va de
    9,6x a 10,0x segun la mezcla — un 4%. El orden de magnitud no depende de suponerla.

    Con los aranceles INVENTADOS eran exactamente proporcionales y el numero no se movia
    nada, y un test llego a afirmar esa igualdad como invariante. Era una propiedad de mis
    numeros, no del mundo.
    """
    if not 0.0 <= ratio_salida <= 1.0:
        raise ValueError("ratio_salida es una fraccion de los tokens, entre 0 y 1.")

    def por_token(t: Tariff) -> float:
        return (
            (1.0 - ratio_salida) * t.prompt_per_mtok
            + ratio_salida * t.completion_per_mtok
        )

    piso = por_token(barato)
    if piso <= 0:
        raise ValueError("Un arancel gratis no tiene punto de equilibrio.")
    return por_token(caro) / piso
