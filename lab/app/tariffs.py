"""Precios por millon de tokens. MEDIDOS de la API de precios de Azure, no declarados.

DE DONDE SALEN Y QUE VALEN. `prices.azure.com/api/retail/prices`, Global Standard, region
`eastus2`, consultados el 2026-08-28. Son el precio de lista del proveedor: un hecho del
contrato, no una medicion nuestra. Cambian sin avisar y no hay nada en el codigo que se
entere, por eso cada arancel lleva la fecha adentro del nombre y el reporte la estampa —
`cost_unit()` devuelve `usd@nano/2026-08-28`.

LA VERSION ANTERIOR ERA REFERENCIA INVENTADA Y ERRABA FEO. Estaban puestos a mano en
0,05/0,40 para nano y 1,25/10,00 para el caro. El nano real es **0,20/1,25**: 4x en entrada
y 3,1x en salida. Que las conclusiones de `X-5a` sobrevivan no fue suerte — fue que se
enunciaron sobre lo INVARIANTE al arancel y se barrio el rango. La proporcion salida/entrada
real es ~6x para los tres modelos, adentro del barrido de x1 a x32 donde el orden aguanto.

EL HALLAZGO QUE NINGUN NUMERO INVENTADO HABRIA DADO: **`luna` sale lo mismo que `nano`**
(0,20/1,20 contra 0,20/1,25). No es el modelo caro del catalogo — es de clase nano. Si
resulta mas capaz al mismo precio, eso no es una pregunta de RUTEO sino de SUSTITUCION: se
cambia el barato y se termina. Los caros de verdad son `terra` (10x) y `sol` (25x).

TRES EJES DE PRECIO QUE EL BANCO NO MODELA, y conviene tenerlos escritos:

  contexto   `LongCo` cuesta el DOBLE que `ShortCo` (terra: 4,00 contra 2,00 la entrada).
             O sea que el precio depende del largo del contexto, y la cota de ventana de
             `feasibility.check_pair` tiene un gemelo economico que hoy no existe
  cache      la entrada servida del cache del proveedor sale **10x menos** (0,02 contra
             0,20 en nano). `X-4b` concluyo que esa via no existe porque el prefijo
             estable mide 567 tokens contra un umbral de 1.024 — eso sigue en pie, pero el
             premio es 90% de descuento y no un margen
  escritura  escribir al cache se COBRA en los `5.6` y **no en nano**. Es la asimetria
             menos obvia de todas: en `sol` la escritura sale 6,25 por millon —mas que la
             ENTRADA de `terra`— asi que un prefijo que cambia seguido paga escritura sin
             llegar a cobrar lectura nunca. En nano ese riesgo no existe

LOS NUMEROS DE ESOS TRES EJES, verificados contra la pagina el 2026-08-28:

    modelo   entrada  salida  cacheada  escritura  largo:entrada  largo:salida
    nano        0,20    1,25      0,02     (sin)          (sin)         (sin)
    luna        0,20    1,20      0,02      0,25           0,40          1,80
    terra       2,00   12,00      0,20      2,50           4,00         18,00
    sol         5,00   30,00      0,50      6,25          10,00         45,00

El contexto largo cuesta **2x la entrada y 1,5x la salida** en los tres `5.6`. Embeddings
(`text-embedding-3-large`): 0,143 por millon, que es lo que HyDE paga aparte de su llamada.

Nada de eso entra hoy en `Tariff`, que modela dos precios planos. **Se documenta y no se
declara como constante**: un campo que nadie consume es la falla que este repo se pasa el
dia encontrando (`_audit_declarado.py`). Entra cuando algo lo use, y esta registrado.
"""

from __future__ import annotations

from .metrics import Tariff

# Consultados 2026-08-28, Global Standard, eastus2. `ShortCo Std` para los `5.6`.
#
#   modelo          entrada   salida   entrada cacheada
#   gpt-5.4-nano       0,20     1,25       0,02
#   gpt-5.6-luna       0,20     1,20       0,02
#   gpt-5.6-terra      2,00    12,00       0,20
#   gpt-5.6-sol        5,00    30,00       0,50

# El modelo de medicion vigente, y el unico con grilla completa.
NANO = Tariff(name="nano/2026-08-28", prompt_per_mtok=0.20, completion_per_mtok=1.25)

# CLASE NANO, no caro: cuesta lo mismo que `nano` y sale 4% mas barato en salida. Esta en
# el catalogo de aranceles porque es un modelo distinto, no porque sea un escalon de precio.
LUNA = Tariff(name="luna/2026-08-28", prompt_per_mtok=0.20, completion_per_mtok=1.20)

# El escalon intermedio: 10x nano en entrada, 9,6x en salida.
TERRA = Tariff(name="terra/2026-08-28", prompt_per_mtok=2.00, completion_per_mtok=12.00)

# El caro: 25x nano en entrada, 24x en salida.
SOL = Tariff(name="sol/2026-08-28", prompt_per_mtok=5.00, completion_per_mtok=30.00)

# El brazo caro por defecto del catalogo de modelos. `TERRA` y no `SOL` a proposito: es el
# escalon mas chico que existe, y la regla de este repo es no comprar mas garantia de la
# que la medicion justifica. Cambiarlo a `SOL` es una decision, no un ajuste.
DEEP = TERRA

DECLARADOS: dict[str, Tariff] = {
    "nano": NANO, "luna": LUNA, "terra": TERRA, "sol": SOL,
}


def breakeven(barato: Tariff, caro: Tariff, ratio_salida: float = 0.25) -> float:
    """Cuantas veces MENOS tokens tiene que usar el caro para costar lo mismo.

    `ratio_salida` es la fraccion de tokens que es completion. Un solo numero y no dos
    porque lo que decide es la MEZCLA, y la mezcla es una propiedad del paradigma que el
    registro ya tiene medida — no hace falta suponerla, se pasa la observada.

    Devuelve el multiplicador: si da 10, el caro necesita usar **1/10** de los tokens del
    barato para empatar. Cualquier numero grande es la respuesta honesta a «el caro
    resuelve con menos llamadas»: casi nunca alcanza, y por eso la decision correcta no es
    elegir modelo por defecto sino **rutear**.

    LA MEZCLA CASI NO MUEVE EL RESULTADO, y con los precios reales se ve por que: los
    cuatro aranceles tienen la salida entre 5,3x y 6,3x la entrada, asi que son casi
    proporcionales entre si. El parametro se queda porque un arancel con otra forma lo
    volveria a activar, y entonces el numero cambiaria sin que nadie se entere de que
    antes no lo hacia.

    La separacion entrada/salida sigue importando en el otro eje: entre PARADIGMAS bajo un
    mismo arancel, donde la salida cuesta ~6x y las mezclas si difieren (0,3% a 9,9%).
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
