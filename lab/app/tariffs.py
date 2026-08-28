"""Precios de REFERENCIA por millon de tokens. No son una medicion, y no son un dato.

QUE SON. Ordenes de magnitud declarados, puestos a mano, para poder preguntar en que
unidad se decide. **Ninguna conclusion puede depender de su valor exacto** — si un
resultado cambia porque el precio era 0,05 y no 0,06, ese resultado no existe. Lo que si
se puede afirmar es lo que sea INVARIANTE a la referencia, y para eso estan:

  vale                 «el orden entre paradigmas cambia al pasar de tokens a plata»
  no vale              «rewoo sale 0,0021 dolares»
  vale                 «los dos aranceles son proporcionales, asi que la mezcla no decide»
  no vale              «el caro cuesta 25x» como numero publicable

POR QUE ESTAN ACA Y NO EN EL REGISTRO. Todo lo demas en el banco es medido, y esto no.
Meterlo en la fila lo haria parecer una observacion y quedaria congelado en registros que
sobreviven al cambio de precio. Vive aparte, se pasa al analisis, y el reporte estampa
cual uso: `cost_unit()` devuelve `usd@nano/2026-08-28`, con la fecha adentro, para que un
lector vea la referencia vieja en vez de confiar en ella.

POR QUE IMPORTA LA SEPARACION ENTRADA/SALIDA. Los aranceles cobran la salida varias veces
la entrada, y **los paradigmas se diferencian justo en esa proporcion**: `rewoo` planifica
largo y contesta corto, `react` acumula entrada a cada vuelta, `dag_strategy` paga entrada
por rama. Barrer lambda sobre el total promedia dos precios y le cobra a cada brazo un mix
que no gasto. Esa asimetria es cualitativa y sobrevive a cualquier referencia razonable;
el numero puntual no.

DE DONDE SALE LA PREGUNTA. `X-5e` midio con lo ya pagado que el modelo caro usa 0,81x los
tokens del barato en `gold_deep` y 1,90x en `gold_v2`: gana **donde la tarea es dificil**.
Pero «0,81x los tokens» no es «mas barato» hasta que se sepa cuanto vale cada token, y esa
conversion es esto.
"""

from __future__ import annotations

from .metrics import Tariff

# REFERENCIA, no medicion. El modelo de medicion vigente: barato, y el unico con grilla
# completa. Los valores son ordenes de magnitud de lista publica al 2026-08-28.
NANO = Tariff(name="nano/2026-08-28", prompt_per_mtok=0.05, completion_per_mtok=0.40)

# REFERENCIA. El brazo caro de la comparacion multi-modelo. Lo que importa de este par
# no es el precio sino que la escala entera se mueve un orden de magnitud: por eso «menos
# tokens» no implica «menos plata», y esa implicacion falsa es lo que hay que romper.
DEEP = Tariff(name="deep/2026-08-28", prompt_per_mtok=1.25, completion_per_mtok=10.00)

# Todos los aranceles declarados, para que un analisis pueda barrer sobre la lista sin
# tener que enumerarlos y olvidarse de uno cuando entre el tercero.
DECLARADOS: dict[str, Tariff] = {"nano": NANO, "deep": DEEP}


def breakeven(barato: Tariff, caro: Tariff, ratio_salida: float = 0.25) -> float:
    """Cuantas veces MENOS tokens tiene que usar el caro para costar lo mismo.

    `ratio_salida` es la fraccion de tokens que es completion. Un solo numero y no dos
    porque lo que decide es la MEZCLA, y la mezcla es una propiedad del paradigma que el
    registro ya tiene medida — no hace falta suponerla, se pasa la observada.

    Devuelve el multiplicador: si da 25, el caro necesita usar **1/25** de los tokens del
    barato para empatar. Cualquier numero grande es la respuesta honesta a «el caro
    resuelve con menos llamadas»: casi nunca alcanza, y por eso la decision correcta no
    es elegir modelo por defecto sino **rutear**.

    Y ACA HAY UN HALLAZGO QUE CORRIGE LO QUE ESCRIBI ARRIBA. Para `NANO` contra `DEEP` la
    mezcla **no cambia nada**: da 25,0 al 10%, al 25% y al 50% de salida, porque los dos
    aranceles son proporcionales —25x en entrada y 25x en salida—. Asi que para comparar
    ESTOS DOS MODELOS el ratio de tokens ya es el ratio de plata, multiplicado por 25.

    La separacion entrada/salida sigue importando, pero en el otro eje: entre PARADIGMAS
    bajo un mismo arancel, donde la salida cuesta 8x la entrada y las mezclas si difieren.
    El parametro se queda porque un tercer arancel no proporcional lo volveria a activar,
    y entonces el numero cambiaria sin que nadie se entere de que antes no lo hacia.
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
