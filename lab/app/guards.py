"""LA POLÍTICA DE GUARDAS: todos los límites de todos los patrones, en un solo lugar.

POR QUÉ ESTO EXISTE, y no es orden por el orden. Los diecisiete límites que gobiernan el
catálogo vivían cada uno en el archivo de su patrón: `SCOPES` en `handoff.py`,
`DAG_MAX_SUB_QUESTIONS` en `dag.py`, `MAX_DISPATCHES` en `supervisor.py`,
`MAX_PLAN_STEPS` en `modern.py`. Cada uno se leía solo y ninguno se podía comparar con los
demás.

**Y tres de ellos son la MISMA decisión tomada tres veces.** `handoff` parte el alcance en
2, `dag_strategy` en 4 sub-preguntas, `supervisor` despacha 4 veces sobre ventanas de 8
unidades. Son tres formas de contestar «¿en cuántos pedazos se corta este problema?», con
tres números elegidos por separado, en tres archivos, y **ninguno se midió nunca como
factor**. Puestos uno al lado del otro eso se ve; desparramados, no.

CÓMO ESTÁ ORGANIZADO: por **lo que la guarda gobierna**, no por patrón. Esa es la decisión
de diseño que hace que sirva — agrupar por patrón habría reproducido el problema con otro
nombre.

QUÉ **NO** HACE, y decirlo importa: no cambia ningún valor. Es una mudanza, y el registro
medido hasta hoy sigue siendo comparable porque cada constante conserva su número. Lo que
habilita es lo que antes no se podía ni formular: barrer un eje de guardas como factor, y
ver si el corte en 2, en 4 o en 8 explica algo de lo que hoy se le atribuye a la topología.

CÓMO SE USA: cada patrón importa de acá. Los alias con el nombre viejo se conservan en cada
módulo para que nada se rompa, y ese alias es lo único que queda en el archivo del patrón.
"""

from __future__ import annotations

# ───────────────────────────────────────────────────────────────────────────────
# 1. EN CUÁNTOS PEDAZOS SE CORTA EL PROBLEMA
#
# Los tres brazos de la familia de sub-agentes contestan esta pregunta, y contestan
# distinto. Es el eje más comparable del catálogo y el que nunca se cruzó.
# ───────────────────────────────────────────────────────────────────────────────

# `handoff`: alcances disjuntos por paso de índice. Dos porciones, fijas.
HANDOFF_SCOPES = 2

# `dag_strategy`: sub-preguntas por ola. El plan las fija antes de ejecutar.
DAG_SUB_QUESTIONS = 4

# `supervisor`: despachos sucesivos, decidiendo el próximo con lo que volvió del anterior.
SUPERVISOR_DISPATCHES = 4


# ───────────────────────────────────────────────────────────────────────────────
# 2. CUÁNTO PUEDE VER CADA PEDAZO
#
# Y acá está la asimetría que la separación escondía: `handoff` le da a su sub-agente
# TODO su alcance —la mitad del corpus— mientras `supervisor` le da una ventana de 8
# unidades recortada por una búsqueda. No son dos parámetros del mismo tipo con valores
# distintos: son dos definiciones distintas de qué es un sub-agente.
# ───────────────────────────────────────────────────────────────────────────────

# `supervisor`: el sub-agente ve una ventana recortada por el código, no el alcance.
SUPERVISOR_SCOPE_UNITS = 8

# `graph_traverse`: cuántos saltos camina el grafo antes de leer.
GRAPH_WALK_DEPTH = 2

# `streaming_scan`: tamaño del trozo de material por pasada.
SCAN_CHUNK_TOKENS = 6_000


# ───────────────────────────────────────────────────────────────────────────────
# 3. CUÁNTAS VUELTAS TIENE CADA UNO
#
# El costo de una vuelta NO es constante entre patrones: en un bucle que reenvía la
# conversación entera, la vuelta N cuesta como N. Medido: el turno 0 de `react` consume
# 607 tokens de prompt y el turno 8 consume 67.233. Así que estos números no son
# comparables entre sí sin mirar qué arrastra cada vuelta.
# ───────────────────────────────────────────────────────────────────────────────

HANDOFF_TURNS_PER_AGENT = 6
SUPERVISOR_TURNS_PER_SUB = 3
DAG_SUB_AGENT_ITERATIONS = 10
REWOO_PLAN_STEPS = 8

# LOS QUE FALTABAN, Y NO ERAN LOS CHICOS (2026-08-30). Este módulo dice en su primera línea
# que tiene «todos los límites de todos los patrones», y no era cierto: los cuatro brazos
# clásicos tenían sus topes escritos a mano adentro de `paradigms/__init__.py` —un `20`, un
# `10`, un `8`, un `4`— y ninguno aparecía acá ni en `TECHO_LLAMADAS`.
#
# **Y son los caros.** `reflection` es el brazo más caro del catálogo, 118.911 tokens por
# celda, y sus dos topes —10 vueltas para el borrador, 8 para la revisión— eran justamente
# los que nadie había nombrado. `react` es el FALLBACK, o sea el brazo contra el que se mide
# la brecha de oráculo de todo el banco, y su `20` era un literal en medio de una llamada.
#
# Que el límite del patrón más caro y el del patrón de referencia fueran los dos invisibles
# no es casualidad: son los que nadie tocó nunca, y por eso nadie los movió de lugar.
REACT_ITERATIONS = 20
REFLECTION_DRAFT_ITERATIONS = 10
REFLECTION_REVISE_ITERATIONS = 8
PLAN_SUB_QUESTIONS = 5
PLAN_SUB_AGENT_ITERATIONS = 4
# `pointer_chase`: el techo duro de saltos. El presupuesto puede bajarlo —el cap real es
# `min(CHASE_MAX_HOPS, max(2, presupuesto // unidad_media))`— pero nunca subirlo.
CHASE_MAX_HOPS = 6
CHASE_MIN_HOPS = 2


# ───────────────────────────────────────────────────────────────────────────────
# 4. CUÁNDO SE DEJA DE INSISTIR
#
# `dag_strategy` es el único que tiene una regla de corte por rendimiento, y eso es una
# ventaja estructural que no está medida como tal: los demás corren hasta su tope de
# vueltas. La señal de agotamiento del retriever (`stop_on_barren`) es la versión general
# de esto y está APAGADA por defecto — medido, entre el 46% y el 70% de las búsquedas de
# los brazos iterativos no traen nada nuevo.
# ───────────────────────────────────────────────────────────────────────────────

DAG_REPLAN_ITERATIONS = 3
DAG_READY_THRESHOLD = 0.8
DAG_DIMINISHING_RETURNS = 0.05


# ───────────────────────────────────────────────────────────────────────────────
# 5. CUÁNTO ESTADO SE ARRASTRA, Y CON CUÁNTA PÉRDIDA
#
# Todos estos son compresiones con pérdida, y la pérdida es la parte interesante: lo que
# el acarreo no conserva se perdió, y ningún patrón declara qué descartó.
# ───────────────────────────────────────────────────────────────────────────────

SCAN_CARRY_CHARS = 6_000        # `streaming_scan`: estado entre trozos, sin vuelta atrás
CHASE_LEDGER_FACT_CHARS = 400   # `pointer_chase`: por hecho en el ledger
# CUANTOS CANDIDATOS MIRA CADA SALTO de `pointer_chase`. Ocho, y esta MEDIDO sobre los nueve
# eslabones de las tres cadenas de C3: con 8 caen los nueve, y el peor —`S. Quiroga`— aparece
# en el puesto 7. Era 3, escrito a mano adentro del paradigma.
#
# Y ES ANCHO PORQUE HAY GUARDA. Antes el codigo tomaba el primer hit no visitado a ciegas, y
# con eso un limite ancho es PEOR: mas candidatos equivocados a los que saltar. Con la
# verificacion de contencion —la unidad tiene que nombrar a quien se persigue— ancho pasa a
# ser estrictamente mejor. Subir este numero sin esa guarda seria un retroceso.
CHASE_HITS = 8
REWOO_EVIDENCE_ITEM_CHARS = 32_000   # `rewoo`: por item de evidencia del plan
REWOO_SUBSTITUTION_CHARS = 800       # `rewoo`: al sustituir un resultado en el paso siguiente


# ───────────────────────────────────────────────────────────────────────────────
# LO QUE ESTA TABLA HACE VISIBLE, y es el motivo de haberla escrito
#
#   · tres cortes distintos del mismo problema: 2, 4 y 4-sobre-8
#   · tres topes de vueltas distintos: 6, 3 y 10 — sin que el costo de una vuelta sea
#     comparable entre ellos
#   · UN solo patrón con regla de corte por rendimiento decreciente, y ninguno con la
#     señal de agotamiento encendida
#   · cuatro compresiones con pérdida, ninguna de las cuales declara qué descartó
#
# Ninguno de esos cuatro ejes se midió jamás como factor. Están en `PENDIENTES.es.md`.
# ───────────────────────────────────────────────────────────────────────────────


# ───────────────────────────────────────────────────────────────────────────────
# EL DESAFÍO: CUÁLES DE ESTAS GUARDAS ATAN DE VERDAD (medido 2026-08-30)
#
# Centralizarlas las volvió comparables, y comparadas no aguantan parejo. La pregunta
# honesta no es si el número es lindo sino **cuántas veces se alcanza**: una guarda que
# nunca se toca no es una guarda, y una que se toca siempre es el límite real disfrazado
# de parámetro.
#
#   brazo          techo real               máx observado   ¿ata?
#   handoff        2 × 6 = 12                          11   sí, y justo (0 de 129 exceden)
#   supervisor     4 × (1+3) + 1 = 17                  17   SIEMPRE
#   dag_strategy   4 × 10 × (1+3) = 160                19   NUNCA — es 8× más floja
#   rewoo          2, por construcción                  2   por construcción
#
# TRES COSAS QUE ESO DESTAPA:
#
# 1. LA DE `dag` NO ES UNA GUARDA, ES DECORACIÓN. Su techo teórico es 160 llamadas y el
#    máximo que se observó en 138 celdas es 19. Un tope puesto ocho veces por encima de
#    todo lo que pasa no restringe nada: lo que corta a `dag` es otra cosa —el umbral de
#    rendimiento decreciente, o que se queda sin qué preguntar— y esa otra cosa es la que
#    habría que nombrar.
#
# 2. LA DE `supervisor` NO SE DEDUCE DE SUS CONSTANTES. Los números dicen «4 despachos, 3
#    turnos» y el total observado es 17, porque el patrón hace además **una llamada de plan
#    por despacho y una final**, y ninguna constante las nombra. El techo real es
#    `DISPATCHES × (1 + TURNS) + 1`, y estaba sólo en la forma del código.
#
#    Ningún nombre de este archivo acota el TOTAL. Cada guarda acota una parte, y la suma
#    es una propiedad emergente que nadie escribió.
#
# 3. Y LA MÁS BARATA DEL CATÁLOGO NO ES UN TOPE: ES UNA FORMA. `rewoo` hace exactamente
#    dos llamadas al modelo porque su diseño tiene dos —planificar y resolver—, no porque
#    un número se lo impida. Por eso cuesta 1.050 tokens contra 137.211 de `react`, y por
#    eso gana 23 de 46 tareas bajo «máxima utilidad al menor costo».
#
#       Una guarda estructural le gana a un techo numérico, porque no se puede aflojar
#       sin cambiar el patrón. Un techo se elige; una forma se respeta.
#
# Y UNA CUARTA, SOBRE LA VENTANA DEL SUPERVISOR. `SUPERVISOR_SCOPE_UNITS = 8` es absoluto
# y los alcances del corpus van de 1 a 60 unidades. Medido: en **28 de 78 tareas el
# sub-agente ve el alcance ENTERO**, o sea que el aislamiento —que el docstring del patrón
# llama «no una optimización sino su definición»— **no existe en el 36% del corpus**. Una
# ventana fija sobre un alcance variable no es una ventana: es una constante que a veces
# resulta ser todo.
#
# QUÉ HABRÍA QUE HACER, y ninguna es cara:
#   · nombrar el techo TOTAL de cada patrón, y que el test lo verifique contra lo observado
#   · que la ventana del supervisor sea una fracción del alcance y no un absoluto
#   · sacar el tope de `dag` o bajarlo a donde ate, y nombrar lo que realmente lo corta
#   · barrer el eje de corte —2 contra 4 contra 4-sobre-8— que es la misma decisión tomada
#     tres veces y nunca se midió
# ───────────────────────────────────────────────────────────────────────────────


# ───────────────────────────────────────────────────────────────────────────────
# EL BALANCE DE ESFUERZO — y el eje sobre el que hay que balancear (2026-08-30)
#
# La pregunta del autor: **el esfuerzo total por patrón tiene que estar balanceado.** Es
# correcta y no estaba planteada en ningún lado, y medirla dio algo peor de lo esperado.
#
#   brazo             techo de llamadas    tokens por celda    contra el más barato
#   rewoo                             2               1.050                     1×
#   gist_reader                       —              21.654                    21×
#   supervisor                       17              59.258                    56×
#   dag_strategy                    160              84.916                    81×
#   handoff                          12              86.646                    83×
#   react                             —              90.665                    86×
#   reflection                        —             118.911                   113×
#
# **113× entre el más barato y el más caro.** Si los patrones no compiten al mismo
# presupuesto, la comparación no mide la topología: mide el presupuesto. Y toda conclusión
# de la forma «el patrón X gana» arrastra ese confundido.
#
# Y EL DATO QUE DECIDE CUÁL ES EL EJE CORRECTO: `handoff` tiene techo de **12** llamadas y
# gasta 86.646 tokens; `dag_strategy` tiene techo de **160** y gasta 84.916. **Casi lo
# mismo, con un factor 13 de diferencia en el techo.**
#
#     El techo está puesto sobre LLAMADAS y el costo lo maneja lo que cada llamada
#     ARRASTRA. Una llamada de `handoff` carga medio corpus de alcance; una de `rewoo`
#     carga un plan. Contar llamadas para acotar esfuerzo es contar envases para acotar
#     peso.
#
# ASÍ QUE EL BALANCE VA EN TOKENS, no en llamadas — y en la misma unidad en que ya trabaja
# la factibilidad, que es la porción del presupuesto declarado de la tarea. Un patrón que
# se pasa deja de ser una topología distinta y pasa a ser la misma topología con más plata.
#
# ESTÁ APAGADO POR DEFECTO, y por la razón de siempre: encenderlo cambia comportamiento y
# volvería incomparable el registro ya pagado. Es un FACTOR (`effort_balanced`), que es
# como este banco introduce cualquier cambio que toca lo medido.
# ───────────────────────────────────────────────────────────────────────────────

# La porción del presupuesto de la tarea que un patrón puede gastar cuando el balance está
# encendido. `BUDGET_SHARE` de `feasibility.py` ya define la porción que la poda aritmética
# usa para decidir si entra; ésta es la que decide cuándo un patrón tiene que parar.
#
# 1,0 significa «lo que la tarea declara», que es el presupuesto contra el que la
# factibilidad ya lo admitió. No es generoso: es coherente — admitir un brazo porque entra
# en el presupuesto y después dejarlo gastar diez veces eso es admitirlo con una cuenta y
# medirlo con otra.
EFFORT_BUDGET_SHARE = 1.0

# EL TECHO TOTAL DE LLAMADAS, NOMBRADO. Faltaba, y su ausencia fue lo primero que medí mal:
# deduje el techo de `supervisor` multiplicando sus constantes y me dio 12, cuando el real
# es 17 porque el patrón hace además una llamada de plan por despacho y una final. Ninguna
# constante las nombraba. Ahora el total está escrito y el test lo verifica contra lo
# observado.
TECHO_LLAMADAS = {
    "rewoo": 2,                                    # estructural: planificar y resolver
    "handoff": HANDOFF_SCOPES * HANDOFF_TURNS_PER_AGENT,
    "supervisor": SUPERVISOR_DISPATCHES * (1 + SUPERVISOR_TURNS_PER_SUB) + 1,
    # `dag_strategy`: NO es un límite de diseño, es un ALAMBRE DE AVISO, y conviene decirlo
    # con esa palabra. Su techo estructural son 160 llamadas y nunca se acerca; lo que de
    # verdad lo corta es `DAG_DIMINISHING_RETURNS`. Un número acá sólo sirve para que una
    # corrida que se dispara se note.
    #
    # Y ASÍ ESTABA MAL PUESTO. Valía 24, calibrado sobre `gold_h1` donde el máximo son 19
    # llamadas — pero sobre el registro COMPLETO el máximo es **38**. O sea que la guarda
    # estaba violada por 858 filas y nadie lo veía, porque el test la contrastaba contra el
    # mismo archivo del que había salido el número.
    #
    #     Un umbral calibrado sobre una muestra y verificado contra esa misma muestra no
    #     puede fallar. Es la forma exacta que ya tuvo `_potencia_corpus.py`, cuyo umbral
    #     de 1,0 aprobaba justamente al corpus que lo había motivado.
    #
    # 48 = el máximo del registro entero más un cuarto. Se recalibra cuando el registro
    # crezca, y el test mira TODOS los archivos para que se note cuando haya que hacerlo.
    "dag_strategy": 48,
    # LOS CLASICOS, que no estaban. Cada uno es su forma, no un producto de constantes:
    #   `react`        un solo bucle
    #   `reflection`   borrador + la llamada de critica + revision
    #   `plan_execute` la llamada de plan + sub-preguntas x vueltas + la sintesis
    #   `pointer_chase` el ancla + un par de llamadas por salto (sentido, y a veces busqueda)
    "react": REACT_ITERATIONS,
    "reflection": REFLECTION_DRAFT_ITERATIONS + 1 + REFLECTION_REVISE_ITERATIONS,
    "plan_execute": 1 + PLAN_SUB_QUESTIONS * PLAN_SUB_AGENT_ITERATIONS + 1,
    "pointer_chase": 1 + CHASE_MAX_HOPS * 2,
}

# LA VENTANA DEL SUB-AGENTE, COMO FRACCIÓN Y NO COMO ABSOLUTO. `SUPERVISOR_SCOPE_UNITS = 8`
# es fijo y los alcances del corpus van de 1 a 60 unidades: medido, en **28 de 78 tareas el
# sub-agente ve el alcance entero**, así que el aislamiento —que su docstring llama «no una
# optimización sino su definición»— no existe en el 36% del corpus. Una ventana fija sobre
# un alcance variable no es una ventana.
#
# Con el balance encendido, la ventana es `max(MINIMO, fracción × alcance)`: escala con el
# problema y nunca deja de aislar.
SUPERVISOR_SCOPE_FRACTION = 0.4
SUPERVISOR_SCOPE_MINIMO = 3


# EL QUE NO TIENE TECHO, DICHO EN VEZ DE FALTANDO. `map_reduce` hace una llamada por
# unidad más la reducción, así que su techo no es una constante: **es el tamaño del
# alcance**. Sobre las 78 tareas eso va de 1 a 60 llamadas, y la factibilidad es lo único
# que lo acota — cuando el alcance no entra, el brazo no corre.
#
# Está acá y no ausente porque un patrón que falta en la tabla se lee como un olvido, y un
# olvido invita a inventarle un número. Éste no tiene número, y ésa es la información.
SIN_TECHO_FIJO = {
    "map_reduce": "una llamada por unidad del alcance, mas la reduccion",
    "direct": "una sola llamada, siempre",
    "cot": "una sola llamada, siempre",
    "gist_reader": "dos llamadas: triage sobre gists y solve",
    "graph_traverse": "una por unidad al indexar, mas la solve",
    "extract_compute": "una de esquema, una por unidad, una de computo",
    "streaming_scan": "una por trozo, mas la solve",
}


def ventana_sub_agente(unidades_en_alcance: int, balanceado: bool) -> int:
    """Cuántas unidades ve un sub-agente. Absoluto por defecto, fracción si se balancea.

    Con `balanceado=False` devuelve el número histórico (8) y el registro medido sigue
    siendo comparable. Con `True` escala con el alcance, que es lo que hace que el
    aislamiento exista también en las tareas chicas.
    """
    if not balanceado:
        return SUPERVISOR_SCOPE_UNITS
    return max(SUPERVISOR_SCOPE_MINIMO,
               int(unidades_en_alcance * SUPERVISOR_SCOPE_FRACTION))


def presupuesto_de_esfuerzo(budget_tokens: int, balanceado: bool) -> int | None:
    """Cuántos tokens puede gastar un patrón. `None` = sin tope, que es el régimen medido.

    Devolver `None` en vez de un número grande es deliberado: un tope enorme se lee como
    una decisión y es lo contrario — es la ausencia de una. Quien consume esto tiene que
    distinguir «no hay tope» de «el tope es alto», que es la misma distinción que este
    repo hace entre `None` y `0` en las proyecciones de factibilidad.
    """
    if not balanceado:
        return None
    return int(budget_tokens * EFFORT_BUDGET_SHARE)
