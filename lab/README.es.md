# lab — el entregable, en español

> 🇬🇧 English (documento canónico, incluye protocolo de medición y cómo correr):
> [README.md](README.md)

Esta página resume la solución. La arquitectura, las decisiones, las deudas comprobadas
y los diagramas viven en [`DISENO.es.md`](DISENO.es.md); **la lista completa de lo que
falta, en un solo lugar, está en [`PENDIENTES.es.md`](PENDIENTES.es.md)**. El patrón de autorreparación
vive en [`PATRON_REC.es.md`](PATRON_REC.es.md).

> **Regla del repo**: nada se describe acá sin implementación que lo corra. Si una
> afirmación de esta página no tiene módulo detrás, es deuda y se saca.

## Qué es

Una capa de decisión determinística que se para **delante de** la orquestación de un
agente LLM. Para cada request entrante decide cuatro cosas, con registro:

1. **Qué paradigmas de orquestación pueden correr siquiera** (factibilidad),
2. **qué garantía exige el request** (el dial por solicitud),
3. **si seleccionar un paradigma especializado o diferir al fallback general**
   (ruteo selectivo con abstención),
4. **y deja un artefacto que le permite a un auditor reproducir la decisión** (EXPLAIN).

El LLM nunca maneja el flujo de control. Participa como **sensor**: emite proposiciones
tipadas sobre la tarea, con una credencia y una procedencia, y una capa simbólica
determinística decide sobre esa base de creencias.

## El flujo de un request

```
request
  │
  ├─ 1. FEATURES         φ(request): estructurales, baratas de extraer
  │      features.py       cardinalidad n, acoplamiento, disponibilidad de oráculo,
  │                        horizonte, reversibilidad, contención de escritura, budget
  │
  ├─ 2. FACTIBILIDAD     aritmética pura sobre lo que la tarea ya declara — sin LLM
  │      feasibility.py    "necesita 386k tokens en un prompt contra un margen de 24k"
  │                        → el paradigma queda registrado como infactible, a costo cero
  │
  ├─ 3. CREENCIAS        el LLM como sensor: proposiciones tipadas con credencia
  │      beliefs.py        + procedencia:  COMPUTED > OBSERVED > ELICITED > ASSUMED
  │      rules.py          reglas determinísticas deciden sobre la base; una regla puede
  │                        exigir procedencia mínima (una acción irreversible no acepta
  │                        la opinión del modelo como evidencia)
  │
  ├─ 4. GARANTÍA         el dial por solicitud A0–A3 (tabla abajo)
  │      assurance.py      el piso se deriva de creencias sobre el propio request;
  │                        quien llama puede pedir más, nunca menos. El piso además
  │                        APRENDE: una región donde el gate viene rechazando por
  │                        procedencia arranca más arriba, porque la estadística de
  │                        rechazos ya dijo que ahí la evidencia barata no alcanza
  │

  ├─ 5. RUTEO SELECTIVO  Π(φ, θ) con abstención: emite un paradigma especializado sólo
  │      router.py         dentro de la región de alta confianza (κ > τ); si no, difiere
  │      policy.py         al fallback general. θ conserva estadísticas por región,
  │                        versión y digest de integridad. Mismo estado completo ⟹ plan.
  │
  ├─ 5b. SONDA Y RE-PLAN si el plan pide evidencia que nadie produjo, se corre una
  │      probe.py          sonda de reconocimiento sobre UNA unidad y se vuelve a
  │      decide.py         planificar CONTINUANDO la misma historia de creencias, así
  │                        la observación supersede a la estimación en un solo linaje
  │                        de digest. `probe_then_decide` nombra dos pasos y el ciclo
  │                        vive una sola vez, compartido por el producto y el banco:
  │                        dos implementaciones de una decisión se separan solas.
  │                        Un plan que sigue sin resolver es un APLAZAMIENTO, nunca
  │                        una elección — ejecutarlo sería actuar sobre evidencia que
  │                        el gate acaba de declarar insuficiente. Lo que cuesta
  │                        decidir se devuelve en la cuenta, no se absorbe
  │
  ├─ 6. EJECUCIÓN        el paradigma elegido corre contra la superficie de herramientas,
  │      paradigms/        que carga señales contables determinísticas (estancamiento,
  │                        cobertura, contabilidad de IDs) como circuit breakers —
  │                        el bucle no puede replanificar para siempre por intuición
  │
  └─ 7. EXPLAIN          el artefacto registrado: φ, creencias con procedencia, nivel de
         router.py         garantía, veredictos, plan elegido, resultado. El auditor
                           inspecciona qué se afirmó y reproduce las reglas — nunca el
                           modelo.
```

## La garantía es una propiedad del request, no del sistema

El determinismo total no está disponible para un LLM, así que reclamarlo sería falso.
Perseguirlo dejando al modelo fuera de la decisión es peor: tira información que el
modelo genuinamente tiene y sigue prometiendo una garantía que no puede existir. La
garantía que SÍ se puede dar cambia de forma:

```
NO    "el mismo prompt da la misma respuesta"           (falso, siempre)
SÍ    "el mismo estado completo de decisión da el mismo plan" (auditable)
```

El default está en el extremo flexible; la estrictez es un escalamiento que se paga. Un
nivel acota el espacio de patrones admisibles; la plasticidad permuta libremente adentro.

| Nivel | Piso de procedencia | θ aprende online | Sellado | Patrones |
|---|---|---|---|---|
| `A0_EXPLORATORY` | `ASSUMED` | declarado, no implementado | no | álgebra completa |
| `A1_STANDARD` | `ELICITED` | no | no | catálogo |
| `A2_ACCOUNTABLE` | `ELICITED`* | no | no | catálogo, profundidad <= 3 |
| `A3_CERTIFIED` | `OBSERVED` | no | declarado, no impuesto completamente | subconjunto certificado |

\* sube a `OBSERVED` automáticamente mientras la calibración no esté ganada.

Un caller que pide `A0` sobre una tarea irreversible obtiene `A3` igual. El perfil A3
restringe el espacio a un subconjunto de control más acotado. El catálogo ejecutable
actual contiene trece paradigmas, incluidos controles históricos y candidatos
falsificados; el estado de cada uno está en `app/paradigms/README.es.md`.

## Cómo aprende sin volverse inauditable

El aprendizaje es **offline y copy-on-write**, nunca adentro de un request. Hay
construcción de candidatos, estadísticas por región, pisos de garantía aprendidos y una
guarda de promoción, con partición por tarea en tres bloques: `search` propone,
`validate` puntúa, y `final` lo toca únicamente la guarda de promoción.

Dos deudas que esta página declaraba ya están cerradas, y conviene decir por qué eran
deudas: **la candidata se ajusta SIN el bloque final** (antes se ajustaba con todo y
después se le entregaba ese mismo bloque a la guarda, que es marcarse el propio examen),
y **un episodio es una celda `(tarea, paradigma)` con utilidad media**, no un trial
(antes tres réplicas de una tarea contaban como tres evidencias, y una réplica con
suerte cobraba el refuerzo que la media de su paradigma nunca ganó).

Sigue abierta una: **el peso Hebbiano se almacena pero no participa en la decisión** —
`policy.py` lo actualiza, `router.py` no lo lee ni una vez. Es la herencia de v1 y hoy
es un número que se guarda, no una señal que decide. Está en `DISENO.es.md` con su
orden de reparación.

## Qué garantiza, y qué no

| Garantizado | No garantizado |
|---|---|
| Misma base, reglas, bundle, candidatos y configuración ⟹ misma decisión | Mismo prompt ⟹ misma respuesta (imposible con un LLM, y nunca se reclama) |
| Un plan infactible nunca se intenta, y su exclusión queda registrada con la razón | Que el paradigma seleccionado tenga éxito — la selección acota el regret, no los resultados |
| Las acciones irreversibles se gatean sólo con evidencia computada/observada | Nada sobre tareas fuera de extracción de respuesta exacta sobre documentos |
| El incumbente se conserva cuando la guarda rechaza una candidata | Que la guarda actual esté libre de leakage estadístico |

## REC: convertir una abstención en una pregunta

La **Reparación Epistémica Contrafactual** convierte una explicación fallida en una
pregunta operativa: qué creencia mínima habría cambiado el plan, y qué evidencia acotada
puede resolverla. Está implementada en dos piezas.

`rec.py` — **el diagnóstico**. Busca el déficit contrafactual mínimo bajo un orden
explícito: menos proposiciones primero, después la más barata, después la procedencia
suficiente MÁS DÉBIL, y desempate lexicográfico para que dos corridas den la misma
respuesta. El esquema de intervenciones es cerrado y firmado: sólo se pueden proponer
las hipótesis declaradas, porque un solucionador que puede inventar la evidencia que le
conviene siempre encuentra una reparación. El complemento se recalcula contra el piso de
la política, igual que en la decisión original — evaluarlo contra una clausura estática
dejaba que una hipótesis `ELICITED` apagara una regla que exige `OBSERVED`.

`certify.py` — **la certificación**, con la separación que le da sentido: el mundo de
proponer no decide nada, el de validar decide si se consulta el final, y el final es de
**un solo uso** y se gasta ANTES de responder. Una cláusula nace en borrador y no entra
al bundle firmado sin certificado; el certificado no entra en su propio digest, y la
instalación es fail-closed.

Los vecinos de literatura y los criterios de falsación están en
[`PATRON_REC.es.md`](PATRON_REC.es.md).
