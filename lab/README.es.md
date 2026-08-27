# lab — el entregable, en español

> 🇬🇧 English (documento canónico, incluye protocolo de medición y cómo correr):
> [README.md](README.md)

Esta página documenta la **solución como producto final** — qué hace el sistema en
runtime y qué garantiza. No dice nada de cómo se verificaron las afirmaciones ni de lo
que costaron los experimentos; eso vive en el README en inglés y en el paper.

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
  │                        quien llama puede pedir más, nunca menos
  │
  ├─ 5. RUTEO SELECTIVO  Π(φ, θ) con abstención: emite un paradigma especializado sólo
  │      router.py         dentro de la región de alta confianza (κ > τ); si no, difiere
  │      policy.py         al fallback general. θ es una lista de decisión versionada,
  │                        firmada y legible — no pesos. Mismo φ y θ ⟹ mismo plan.
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
SÍ    "la misma base de creencias da la misma decisión" (verdadero, y auditable)
```

El default está en el extremo flexible; la estrictez es un escalamiento que se paga. Un
nivel acota el espacio de patrones admisibles; la plasticidad permuta libremente adentro.

| Nivel | Piso de procedencia | θ aprende online | Sellado | Patrones |
|---|---|---|---|---|
| `A0_EXPLORATORY` | `ASSUMED` | **sí** | no | álgebra completa |
| `A1_STANDARD` | `ELICITED` | no | no | catálogo |
| `A2_ACCOUNTABLE` | `ELICITED`* | no | no | catálogo, profundidad <= 3 |
| `A3_CERTIFIED` | `OBSERVED` | no | **sí** | subconjunto certificado |

\* sube a `OBSERVED` automáticamente mientras la calibración no esté ganada.

Un caller que pide `A0` sobre una tarea irreversible obtiene `A3` igual, y el espacio de
planes cae de 7 patrones a 4 — `dag_strategy`, `plan_execute` y `reflection` quedan
excluidos, no por ser peores (suelen ser mejores) sino porque su flujo de control no es
acotado y sus modos de falla no son enumerables. Por eso `A3` es un escalamiento y no un
default.

## Cómo aprende sin volverse inauditable

El aprendizaje es **offline y copy-on-write**, nunca adentro de un request. Los episodios
se consolidan en una política *candidata* θ' — que sigue siendo una lista de decisión
legible sobre φ, actualizada con estadísticas Hebbianas interpretables (`policy.py`). La
promoción está custodiada: θ' reemplaza a θ sólo si no regresiona sobre episodios
reservados, y el registro se parte en tres por tarea (una parte propone, una puntúa, una
la toca sólo la guarda de promoción), así que una regla descubierta nunca puede ser
puntuada por los datos que la propusieron. Una θ promovida recibe versión; dos versiones
se diffean como código. El rollback es trivial porque las políticas viejas son artefactos
inmutables.

## Qué garantiza, y qué no

| Garantizado | No garantizado |
|---|---|
| Misma base de creencias ⟹ misma decisión, reproducible desde el registro EXPLAIN | Mismo prompt ⟹ misma respuesta (imposible con un LLM, y nunca se reclama) |
| Un plan infactible nunca se intenta, y su exclusión queda registrada con la razón | Que el paradigma seleccionado tenga éxito — la selección acota el regret, no los resultados |
| Las acciones irreversibles se gatean sólo con evidencia computada/observada | Nada sobre tareas fuera de extracción de respuesta exacta sobre documentos |
| El aprendizaje no puede regresionar la política en silencio (guarda de promoción) | Que θ sea óptima — sólo que es inspeccionable, versionada y no-regresiva |
| Los fallos de infraestructura (429) quedan excluidos de toda estadística | — |
