# lab — el entregable, en español

> 🇬🇧 English (documento canónico, incluye protocolo de medición y cómo correr):
> [README.md](README.md)

Esta página resume la solución. La arquitectura, las decisiones, las deudas comprobadas
y los diagramas viven en [`DISENO.es.md`](DISENO.es.md). El patrón futuro de
automejora vive en [`PATRON_REC.es.md`](PATRON_REC.es.md) y está marcado como propuesta
no implementada.

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
  │      policy.py         al fallback general. θ conserva estadísticas por región,
  │                        versión y digest de integridad. Mismo estado completo ⟹ plan.
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

El aprendizaje está diseñado como **offline y copy-on-write**, nunca adentro de un
request. Hoy existe construcción de candidatos, estadísticas, pisos aprendidos y una
guarda de promoción. No obstante, el bucle todavía no justifica llamarse automejora
segura completa: la consolidación deja que el bloque final influya en theta antes de
evaluarlo, los trials inflan episodios y el peso Hebbiano almacenado no participa en la
decisión. Estas deudas y su orden de reparación están documentados en `DISENO.es.md`.

## Qué garantiza, y qué no

| Garantizado | No garantizado |
|---|---|
| Misma base, reglas, bundle, candidatos y configuración ⟹ misma decisión | Mismo prompt ⟹ misma respuesta (imposible con un LLM, y nunca se reclama) |
| Un plan infactible nunca se intenta, y su exclusión queda registrada con la razón | Que el paradigma seleccionado tenga éxito — la selección acota el regret, no los resultados |
| Las acciones irreversibles se gatean sólo con evidencia computada/observada | Nada sobre tareas fuera de extracción de respuesta exacta sobre documentos |
| El incumbente se conserva cuando la guarda rechaza una candidata | Que la guarda actual esté libre de leakage estadístico |
| Los fallos de infraestructura (429) quedan excluidos de toda estadística | — |

## Próxima dirección: REC

La **Reparación Epistémica Contrafactual** propone convertir una explicación fallida en
una pregunta operativa: qué creencia mínima habría cambiado el plan y qué evidencia
acotada puede resolverla. El aprendizaje sería offline; runtime ejecutaría solamente
cláusulas deterministas promovidas con certificado. El diseño completo, sus vecinos de
literatura y los criterios de falsación están en [`PATRON_REC.es.md`](PATRON_REC.es.md).
