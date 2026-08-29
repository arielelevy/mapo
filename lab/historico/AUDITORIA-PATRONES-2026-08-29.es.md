# Auditoría de consistencia de los patrones — 2026-08-29

> **Qué se preguntó** (autor, 2026-08-29): que los trece patrones manejen igual el estado,
> llamen a las mismas tools, tengan el mismo retrieval, tengan el blackboard a
> disposición; si la comparación de memoria/olvido está implicada; y si son consistentes
> con las buenas prácticas actuales de diseño de agentes.
>
> **Cómo se contesta.** Cada eje se mide sobre el registro —3.679 filas, 20 archivos de
> resultados— y recién después se cruza con el código. Donde el registro no alcanza se
> dice, no se supone.
>
> **Un defecto de construcción no es un hallazgo.** Lo que sigue separa las dos cosas
> explícitamente: los ejes 1, 2 y 6 son propiedades del diseño y se sostienen; los ejes 3,
> 4 y 5 son **deuda**, van a `PENDIENTES.es.md` como trabajo y no son premisa de ninguna
> conclusión del paper.

---

## Eje 1 — El menú de tools: CONSISTENTE, y por construcción

`Runner.surface_for` (`runner.py:510`) **no recibe el nombre del paradigma**. La superficie
se arma desde el corpus, la tarea y los flags del *runner* —`variant`, `offer_read_all`,
`offer_board`, `shared_state`, `terse_tools`, `demand_obligations`—, nunca desde quién la
va a usar. Los trece ven el mismo menú, y ningún paradigma puede pedir una tool que otro no
tenga.

Esto no es una convención que se pueda romper por descuido: no hay parámetro por donde
entre el paradigma. **Es la propiedad más fuerte del banco y se sostiene.**

## Eje 2 — El uso real: muy dispar, y eso es la ESTRUCTURA, no una preferencia

Mismas tools disponibles no es mismo comportamiento. Contado sobre todo el registro:

| paradigma | filas | `search` | `keyword_search` | `semantic_search` | `read` | `read_all` | `coverage` | `note`/`notes` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `react` | 783 | 822 | 431 | 171 | 820 | 3 | 0 | 0 |
| `rewoo` | 686 | 1.937 | 1.345 | 0 | 781 | 0 | 0 | 0 |
| `dag_strategy` | 634 | 598 | 2.696 | 207 | 1.699 | 1 | 1 | 3 |
| `gist_reader` | 626 | 0 | 0 | 0 | 575 | 0 | 0 | 0 |
| `plan_execute` | 92 | 374 | 466 | 45 | 428 | 2 | 2 | 0 |
| `reflection` | 88 | 81 | 208 | 12 | 102 | 3 | 2 | 0 |

Que `gist_reader` no busque **nunca** no es que prefiera no buscar: no tiene la llamada.
Enumera `surface.unit_ids()`, resume todas las unidades y decide sobre los resúmenes
(`modern.py:107-113`). Eso es su grafo de control, y es exactamente lo que
`PATRON_O_FACTOR.es.md` llama un patrón. **La dispersión de esta tabla es la variable
dependiente del banco, no un defecto de uniformidad.**

Dos cosas sí son señales, y las dos ya tienen pendiente escrito:

- **`note`/`notes` — 3 llamadas en 3.679 filas.** Las tools de memoria de trabajo están
  ofrecidas y nadie las usa. Es la observación que ya motivó `manage_history`: el modelo no
  se autogestiona, así que la disciplina la pone el entorno (`cognitive.py:316-323`).
- **`read_all` — 9 llamadas en total.** `P21` pregunta si ofrecerlo en `basic` cambia algo,
  y `P21a` prevé que lo ignoren. Los 9 usos son consistentes con esa previsión, pero
  **`read_all` estuvo apagado en casi todo el registro**, así que esto no es su medición.

## Eje 3 — DEUDA: la mitad de los patrones lee fuera de la instrumentación

`ToolSurface.read_one` (`tools.py:626`) valida el id y devuelve el texto. **No incrementa
`calls`, no suma `units_read`, no toca `relevant_units_read`, no descuenta presupuesto y no
pasa por `stop_on_barren`.** Toda la contabilidad vive en `dispatch` (`tools.py:796`).

Y ocho patrones leen el corpus por ahí: `direct` y `cot` (`__init__.py:251`), `gist_reader`
(`modern.py:113`), `extract_compute` (`:370`), `streaming_scan` (`:435`), `pointer_chase`,
`graph_traverse` (`:225`) y `handoff` para armar sus alcances (`handoff.py:96-99`).

Consecuencias medibles, no hipotéticas:

1. **`units_read` no significa lo mismo entre patrones.** Comparar la columna entre un
   patrón que lee por `dispatch` y uno que lee por `read_one` compara dos definiciones.
2. **El recall de unidades portadoras subestima** a los que leen fuera de banda. Es la
   columna que decide `P26a`.
3. **El presupuesto acota a unos y no a otros.** `gist_reader` aplica su propio tope a
   mano (`modern.py:144`); los demás no.

Que sea *deliberado* —el trace mide lo que el modelo decidió llamar, y una lectura escrita
en el código no es una decisión del modelo— **no lo hace inocuo**: la distinción no está
declarada en ningún lado, así que un número agregado la borra en silencio. La reparación
barata no es prohibir `read_one`, es que registre **aparte**: `units_read_structural`
contra `units_read_elected`. Sin eso, cualquier promedio de lectura entre patrones mezcla.

## Eje 4 — DEUDA: el retrieval NO es el mismo, y la dosis está medida

Las tres tools de búsqueda existen para todos, pero el **brazo** de recuperación sustituye
sólo a `hybrid` — la tool `search`. `runner.py:539-543` pasa `hybrid=retriever` mientras
`semantic` y `lexical` salen fijos de `self._arms`. Así que cambiar de brazo trata sólo a
una de las tres, y **la dosis de tratamiento que recibe cada patrón es la fracción de sus
búsquedas que va por `search`**:

| paradigma | `search` | `keyword` | `semantic` | **dosis** |
|---|---:|---:|---:|---:|
| `react` | 96 | 22 | 19 | **70,1 %** |
| `rewoo` | 275 | 187 | 0 | **59,5 %** |
| `dag_strategy` | 70 | 334 | 25 | **16,3 %** |
| `gist_reader` | 0 | 0 | 0 | **0 %** |

Esto **no invalida P26, lo explica**: `gist_reader` sale idéntico al token porque su dosis
es cero, y `dag_strategy` —el líder del corpus— recibe una sexta parte del tratamiento que
`react`. Un efecto de brazo promediado sobre los patrones es un efecto **ponderado por una
dosis que nadie declaró**. Lo que hay que registrar por fila es la dosis, para que la
comparación entre brazos sea condicional a ella en vez de a un promedio.

## Eje 5 — DEUDA: el blackboard no estuvo a disposición de nadie

**0 posts y 0 reads en las 3.679 filas del registro, en los trece patrones.**

`offer_board` es `False` por defecto (`tools.py:241`), así que la tool de board nunca entró
en ninguna corrida medida. Lo que `dag_strategy` usa es el board **estructural** —el objeto
que escribe su propio código, gobernado por `shared_state` (`dag.py:331,350`)—, y ese no
pasa por la tool, por eso no aparece en el conteo.

O sea: la mitad de `F-2` está construida y **ninguna medida**. `F-2b` —correr
`{offer_board, sin} × {patrones}`— sigue siendo la corrida que lo convierte en factor. Hoy
la respuesta honesta a «¿todos tienen el blackboard a disposición?» es **no: nadie lo
tuvo**.

## Eje 6 — Memoria, olvido y compactación: implementada, y sin correr

La máquina está entera. `basic` no compacta; `managed` degrada sin preguntar todo resultado
de tool anterior al batch actual (`cognitive.py:316`); `cognitive` ofrece las tools y deja
que el modelo se administre; `compact_history` reemplaza el texto crudo por un puntero a la
nota una vez que la unidad está anotada (`cognitive.py:233`).

Lo que falta es la medición, y el desbalance es de dos órdenes:

| variante | filas | |
|---|---:|---|
| `basic` | 3.053 | sin compactación |
| *(sin registrar)* | 561 | filas anteriores al campo |
| `accounting` | 28 | |
| `cognitive` | 27 | |
| `managed` | 16 | |

**43 filas de 3.679 — el 1,2 %.** Y hay un segundo límite, estructural y más interesante:
la compactación vive en `_run_tool_loop`, así que **sólo puede actuar sobre los cinco
patrones que llevan historia** —`react`, `map_reduce`, `reflection`, `dag_strategy`,
`handoff`—. Los otros ocho hacen una o dos llamadas sin reenviar historia: no tienen nada
que olvidar. Eso se ve en la retención, que sólo dos patrones registran hoy:

    dag_strategy / basic   0,749   n=119
    react        / basic   1,000   n=219

`react` da 1,000 **por construcción** —en `basic` no hay compactación— que es la variante de
todos los estudios. Es lo que `M-2` ya había concluido y esto lo confirma con el conteo:
la medida no faltaba por descuido, **no tenía nada que decir donde se midió**.

**Respuesta directa: la comparación memoria/olvido NO está implicada en ningún resultado
publicado.** Está construida, cruza sólo cinco de trece patrones, y para medirla hace falta
correr `{basic, managed} × {los cinco con historia}`. Sobre los otros ocho no se puede
enunciar, y decirlo es parte del resultado.

## Eje 7 — Buenas prácticas actuales de diseño de agentes

De lo que hoy se considera práctica corriente, el banco tiene ejecutado casi todo:

| práctica | estado |
|---|---|
| planificación explícita vs. reactiva | `rewoo` contra `react`, medido |
| subagentes con alcance aislado | `handoff` (alcances disjuntos), `dag_strategy` (olas) |
| verificación antes de responder / citado-o-callado | `certify.py`, contratos `C-COMPLETE`/`C-NUM` |
| gestión de contexto y compactación | construido, **1,2 % del registro** (eje 6) |
| estado compartido entre agentes | estructural en `dag`; como tool, **sin correr** (eje 5) |
| verificar-y-replanificar | `dag_strategy`, hasta 3 replans |
| regla de parada por señal de entorno | `stop_on_barren`, premio medido (33 % del gasto), `P20` |

Lo que falta no es una práctica ausente: es **medición** de dos que ya están construidas.

**MCP: coincido con el autor, y por la regla del propio repo.** MCP es transporte de
herramientas. No cambia cuántas llamadas hay, ni quién elige la próxima acción, ni si hay
estado compartido, ni si un paso puede cambiar el plan — las cuatro preguntas con las que
`PATRON_O_FACTOR.es.md` decide qué es un patrón. Con todo local no agrega ni una tool que
hoy no exista, así que **no es un patrón ni un factor: es plomería**. Entraría a la
discusión sólo si trajera capacidades que la superficie no tiene, y no es el caso.

---

## Lo que esta auditoría deja como trabajo

1. **`read_one` registra aparte** (eje 3) — `units_read_structural` contra
   `units_read_elected`. Sin esto ningún promedio de lectura entre patrones significa algo.
2. **La dosis de brazo por fila** (eje 4) — fracción de búsquedas por `search`. Convierte
   una comparación entre brazos ponderada en silencio en una condicional declarada.
3. **`F-2b`** (eje 5) — `{offer_board, sin} × {patrones}`. Es la corrida que le da sentido a
   una tool que hoy nadie vio.
4. **`{basic, managed} × {los cinco con historia}`** (eje 6) — y enunciar el resultado
   acotado a esos cinco, no a los trece.

Ninguno de los cuatro cambia un número publicado. Los dos primeros cambian **qué se puede
promediar**, que es distinto y peor de descubrir tarde.
