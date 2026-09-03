Sí. Lo revisé con foco de **revisor de arXiv / cs.AI-cs.LG**, no sólo de estilo. Mi impresión es que el paper tiene una idea central valiosa y bastante más sólida que una simple “arquitectura de agentes”: intenta convertir una intuición de ingeniería —no dejar que el LLM gobierne el flujo— en una propiedad formal, una arquitectura ejecutable y una medición empírica. El propio paper además hace algo poco común y positivo: declara explícitamente qué está probado, qué está medido y qué queda fuera de alcance. 

Pero antes de enviarlo, yo haría cambios importantes. El principal riesgo no es que el paper sea débil; es que **está intentando defender demasiadas contribuciones a la vez**, y algunas son mucho más fuertes que otras.

### Mi evaluación rápida

| Aspecto                           |     Evaluación |
| --------------------------------- | -------------: |
| Idea central                      |       **9/10** |
| Originalidad de la combinación    |       **8/10** |
| Rigor conceptual                  |     **8.5/10** |
| Evidencia empírica actual         |   **6.5–7/10** |
| Claridad de la tesis              |       **7/10** |
| Riesgo de rechazo por reviewers   | **medio-alto** |
| Potencial con una revisión fuerte |       **alto** |

La contribución que considero más potente es esta:

> **Las decisiones que deben ser reproducibles no deben depender directamente de una salida estocástica del LLM.**

El paper la vuelve concreta mediante la definición de ramificación delegada y confinamiento de varianza: si ninguna identidad del próximo nodo depende del LLM, la trayectoria queda determinada por `q,M`, y las diferencias entre ejecuciones pueden localizarse en nodos concretos. 

Eso me parece mucho más fuerte que varias de las otras historias que aparecen alrededor.

## 1. Haría que el paper tenga una sola tesis principal

Ahora el resumen presenta **cuatro contribuciones casi equivalentes**: confinamiento de varianza, capacidades, plasticidad y dónde está el premio de selección. El problema es que no tienen el mismo nivel epistemológico.

La primera tiene una definición formal y una propiedad estructural. La segunda tiene evidencia sugestiva pero todavía limitada. La tercera es una arquitectura de aprendizaje de política. La cuarta es un resultado empírico particular del banco.

Yo reorganizaría el paper así:

**Contribución principal**

**Deterministic control-plane principle:** la aleatoriedad del LLM puede confinarse al plano de percepción/contenido si las decisiones que alteran la trayectoria pertenecen a un plano de control determinista.

Luego:

**C1 — Formal:** definición + proposición de confinamiento/localización.

**C2 — Architectural:** procedencia tipada + policy-as-code + abstención.

**C3 — Empirical:** mover una decisión concreta fuera del modelo cambia reproducibilidad/utilidad.

**C4 — Secondary:** capacidades y política aprendida como demostración de que ese control-plane puede adaptarse sin actualizar pesos.

Eso haría al paper bastante más difícil de atacar.

Ahora mismo el abstract da casi el mismo peso a resultados como el leave-one-arm-out, aunque el propio documento reconoce que ese experimento tiene sólo ocho puntos y que no cruza su nulo (`p≈0.066`). 

Yo no pondría ese resultado al mismo nivel que la tesis estructural.

---

# 2. Cambiaría el claim “la única forma”

Hay una frase peligrosa:

> “La única forma de sacar esa aleatoriedad de una decisión es que la decisión la tome el código.”



El espíritu es correcto, pero **“la única forma” es innecesariamente absoluta**.

Un reviewer puede responder: ejecución determinista especializada, constrained decoding, caching, canonicalization, replicated voting con regla determinista, model compilation, formal methods alrededor del modelo, etc.

Tu argumento real es más preciso:

> **A decision cannot inherit stochastic model variation if its value is a deterministic function of model-independent state.**

O en lenguaje del paper:

> Una condición suficiente para que una decisión no herede la varianza del LLM es que su regla de decisión no dependa de ninguna emisión estocástica no canonizada del modelo.

Más preciso y matemáticamente defendible.

---

# 3. Hay una distinción fundamental que conviene hacer explícita

El paper usa “determinismo” en varios niveles:

1. determinismo de la trayectoria;
2. determinismo de la política;
3. determinismo de una decisión dada una base de creencias;
4. reproducibilidad de la respuesta final.

Pero **no son lo mismo**.

De hecho tu propio paper dice correctamente que la garantía es:

> “misma base de creencias, misma decisión”

y no:

> “mismo prompt, misma respuesta”.

Eso está muy bien expresado en la explicación de la Figura 1. 

Yo lo transformaría en una caja formal al principio:

### Three determinisms

$$
D_T: (q,M) \mapsto T
$$

trayectoria determinista.

$$
D_P: B \mapsto a
$$

política determinista dada una belief base.

$$
D_O: (q,M) \mapsto y
$$

salida final determinista.

Y decir explícitamente:

**este paper garantiza \(D_T\) y \(D_P\), no \(D_O\).**

Eso elimina mucha ambigüedad y evita que un reviewer crea que estás prometiendo outputs deterministas de un LLM.

---

# 4. La Proposición 4 es correcta, pero hoy parece casi tautológica

Actualmente:

* defines confinamiento como `d(T)=0`,
* es decir, la trayectoria es determinista,
* y después pruebas que las trayectorias son iguales.



No está mal. Pero un reviewer te puede decir:

> “The main theorem follows directly from the definition.”

Y tendría bastante razón.

Yo no eliminaría la proposición. Haría una de estas dos cosas.

### Opción A — llamarla Lemma

**Lemma 1 — Trajectory invariance under non-delegated branching.**

Y reservar “Theorem” para algo más interesante.

### Opción B — fortalecerla

Definir:

$$
T = f(q,M,Z_1,\ldots,Z_k)
$$

donde \(Z_i\) son outputs estocásticos.

Entonces demostrar algo del estilo:

$$
\frac{\partial T}{\partial Z_i}=0
$$

en sentido funcional cuando todas las decisiones de transición dependen sólo del estado computado.

O, más formal:

$$
I(T;Z \mid q,M)=0
$$

bajo las condiciones del motor.

Ahí aparece una caracterización mucho más fuerte:

**el control plane corta el canal causal entre la aleatoriedad del modelo y la trayectoria.**

Esa formulación, en mi opinión, puede ser uno de los puntos más interesantes del paper.

---

# 5. El concepto de “varianza” debería formalizarse mejor

Este es probablemente el punto técnico que más fácilmente atacaría un reviewer teórico.

“Varianza” normalmente significa una cantidad estadística:

$$
Var[X].
$$

Pero vos usás “confinamiento de varianza” como una propiedad estructural de dependencia.

No es incorrecto conceptualmente, pero genera una expectativa matemática distinta.

Yo introduciría:

### Control-flow stochasticity

Sea \(Z\) la aleatoriedad del modelo y \(T\) la trayectoria.

Definir:

$$
V_T(q,M) = \Pr[T_1 \neq T_2 \mid q,M]
$$

para dos ejecuciones independientes.

Entonces:

$$
d(T)=0 \Rightarrow V_T(q,M)=0
$$

**bajo stack determinista**.

Después podés medir \(V_T\).

Esto conecta maravillosamente teoría con el experimento donde decís que 12–28% de las celdas cambian entre réplicas. 

Incluso podés tener dos métricas:

$$
V_T = P(T_1\neq T_2)
$$

y

$$
V_Y = P(Y_1\neq Y_2)
$$

Y mostrar que reducir \(V_T\) no necesariamente lleva \(V_Y\) a cero.

Eso haría la tesis mucho más limpia.

---

# 6. Tu propia limitación identifica el experimento que más necesita el paper

El documento reconoce algo importante:

> la variación observada mezcla ramificación delegada y nondeterminism del stack de serving.



Ésta es probablemente **la mayor amenaza causal** del resultado “12–28%”.

Porque el título del paper apunta precisamente a una explicación causal:

> delegar decisiones al LLM introduce varianza.

Pero el experimento actual demuestra más directamente:

> hay varianza de réplica en esos sistemas.

Yo haría un experimento nuevo que para mí vale muchísimo.

### Experimento factorial 2×2

|                            | branching en código | branching en LLM |
| -------------------------- | ------------------: | ---------------: |
| serving reproducible/local |                   A |                B |
| serving API normal         |                   C |                D |

Idealmente con un modelo open-weight local.

La comparación clave sería:

$$
B-A
$$

con exactamente mismo stack.

Ahí sí aislarías el efecto de **delegated branching**.

Aunque sean sólo 20–30 tareas, sería probablemente más convincente que otra campaña gigante.

---

# 7. Necesitás una ablación “misma capacidad, cambia sólo quién decide”

Actualmente los paradigmas difieren en muchas cosas.

Por ejemplo, el documento reconoce que una parte muy grande del costo viene de cuánto material se lleva al prompt, no necesariamente de la topología misma. 

Por eso el experimento más fuerte sería crear pares:

**Agent A**

```text
LLM chooses next node
```

**Agent A′**

```text
same retrieval
same prompts
same model
same evidence
same maximum hops
code chooses next node
```

La única diferencia:

$$
\text{controller} \in \{\text{LLM},\text{code}\}
$$

Y medir:

* accuracy,
* trajectory disagreement,
* answer disagreement,
* tokens,
* abstention.

Ese experimento sería extremadamente fácil de explicar en una review.

---

# 8. Separaría “provenance” de “truth” todavía más agresivamente

Esta es una de las mejores ideas del documento:

> procedencia y credencia son campos distintos.



Yo la explotaría más.

Una tabla muy simple:

| Evidence            | provenance | credibility |
| ------------------- | ---------- | ----------: |
| calculado por regla | COMPUTED   |         1.0 |
| leído de documento  | OBSERVED   |   calibrada |
| dicho por LLM       | ELICITED   |   calibrada |
| supuesto            | ASSUMED    |       prior |

Y luego una frase central:

> **Provenance answers “where did this proposition come from?”; credibility answers “how much should the system trust it?”**

Porque esa separación tiene vida propia incluso más allá del routing de agentes.

---

# 9. “COMPUTED” es demasiado fuerte si el sensor computado puede estar mal

Tu clasificación dice que COMPUTED tiene credencia `1.0`. 

Esto podría generar una objeción.

Que algo sea calculado determinísticamente no significa necesariamente que sea verdadero.

Por ejemplo:

```python
entity_count(text)
```

puede ser determinista y incorrecto.

Yo separaría:

**provenance strength**

de

**semantic reliability**.

Quizá:

* `COMPUTED`: producido por una función determinista auditada.
* no implica verdad semántica;
* implica reproducibilidad del cálculo.

Podés mantener credencia 1 sólo para proposiciones definicionalmente ligadas a la función.

Ejemplo:

> “token_count = 1421”

sí.

Pero:

> “request_has_cross_document_dependency = False”

aunque lo compute una heurística, no debería ganar credencia 1 automáticamente.

Esta distinción es importante.

---

# 10. “El dial lo declara el caller” necesita defensa

La Figura 2 dice:

> “A0–A3 · lo declara el caller, no el texto”.



Arquitectónicamente tiene sentido: evita que el LLM determine el nivel de riesgo.

Pero introduce otra pregunta:

> ¿por qué confiar en el caller?

Para una plataforma empresarial eso se resuelve fácilmente:

```text
caller assertion
        ↓
policy normalization
        ↓
effective risk level
```

Por ejemplo:

$$
A_\text{effective} =
\max(A_\text{caller}, A_\text{resource}, A_\text{policy})
$$

Así un caller no puede decir A0 al borrar una base de datos.

Creo que eso mejora mucho el argumento de “governance”.

---

# 11. Las afirmaciones regulatorias deberían suavizarse

El paper dice que determinadas normas “piden una propiedad del sistema” y conecta eso con tu solución. 

Yo evitaría cualquier lectura de:

> nuestra arquitectura satisface GDPR / EU AI Act.

Usaría:

> “motivates system-level traceability requirements”

o

> “is aligned with requirements such as traceability and human oversight”.

No necesitás meterte en una discusión legal para sostener la tesis técnica.

---

# 12. La historia de “plasticidad” me gusta, pero hoy distrae un poco

La idea es interesante:

* pesos congelados,
* creencias acumuladas,
* policy tables consolidadas,
* promotion guard,
* política versionada.



Pero “plasticidad” puede llevar a reviewers hacia continual learning, meta-learning, lifelong learning, policy learning, etc.

Tu propia sección de limitaciones aclara que lo que aprende son tablas y creencias, **no nuevos sensores**. 

Yo lo llamaría primero:

**Policy adaptation without weight updates**

y después introduciría “plasticity” como término interno.

Es mucho menos controvertido.

---

# 13. La selección por capacidades todavía no está lista para ser claim central

Tu resultado es interesante porque intenta generalizar hacia brazos no vistos:

> la política opera sobre capacidades, no identidades.

Eso sí es conceptualmente bueno.

Pero el paper reconoce:

* ocho puntos en leave-one-arm-out,
* p exacto alrededor de 0.066,
* ontología parcialmente basada en etiquetas de diseño,
* todavía falta recuperar esos ejes desde requests externos.



Entonces yo cambiaría el framing de:

> “una interfaz aprendible que no depende de nombres”

a algo como:

> **Evidence that capability-based representations can support arm-independent selection.**

La palabra **evidence** te protege.

Y movería la gran promesa a future work.

---

# 14. El resultado “58% menos tokens” puede ser una estrella, pero necesita baseline simple

El resultado:

> 58% de ahorro en tokens a utilidad equivalente al mejor fijo

es muy atractivo. 

Yo agregaría baselines que un reviewer va a pedir:

* cheapest feasible;
* cheapest capability-compatible;
* best fixed;
* random feasible;
* learned router;
* oracle.

Entonces la tabla sería algo como:

| Policy           | utility | tokens | coverage |
| ---------------- | ------: | -----: | -------: |
| best fixed       |     .XX |  1.00× |     100% |
| cheapest         |     .XX |   .25× |     100% |
| cheapest capable |     .XX |   .42× |     100% |
| learned θ        |     .XX |   .42× |      XX% |
| oracle           |     .XX |      — |        — |

Esto permitiría saber cuánto del 58% viene realmente de **learning** y cuánto de una regla estática de capacidades.

---

# 15. Necesitás reportar confidence intervals más visualmente

El paper parece bastante cuidadoso con pisos de ruido, pseudo-brazos, maxT, etc. Eso es excelente.

Pero un reviewer no debería tener que reconstruir todo desde texto.

Yo pondría tres gráficos centrales.

### Figura A — Stability vs delegated branching

X:

$$
d(T)
$$

Y:

$$
P(T_1=T_2)
$$

### Figura B — Risk–coverage

```text
error
  |
  |\
  | \
  |  \
  +------ coverage
```

para policy con abstention.

### Figura C — Cost / utility frontier

```text
utility
  |      oracle
  |   * θ
  | *
  |________________ tokens
```

Si el paper tiene esos tres gráficos claros, el argumento se entiende casi solo.

---

# 16. El corpus sintético debería venderse como “controlled benchmark”, no simplemente corpus

El paper ya es transparente:

> corpus sintético, ground truth re-derivado independientemente, sin benchmarks públicos.



Eso no es necesariamente una debilidad.

Para estudiar causalidad puede ser una fortaleza.

Yo lo explicaría explícitamente:

> We use a controlled synthetic benchmark because the experiment requires known absence, false presupposition, cross-document chains, and exact provenance, properties that are difficult to establish reliably in public corpora.

Entonces convertís una potencial crítica en una decisión metodológica.

Pero agregaría **aunque sea un pequeño benchmark externo**.

No para demostrar todas las cifras.

Sólo para demostrar:

$$
\text{mechanism survives outside generator}
$$

20–30 casos manuales o benchmark público adaptado ya ayudan muchísimo.

---

# 17. Tenés que separar “domain-general theorem” de “domain-general architecture”

El paper ya lo dice bastante bien:

> la teoría se afirma para agentes en general; las mediciones valen para extracción exacta sobre documentos.



Yo lo pondría mucho antes.

Algo así, en la primera página:

| Claim                               | Scope                |
| ----------------------------------- | -------------------- |
| deterministic branching proposition | general              |
| provenance contract                 | general architecture |
| effectiveness numbers               | forensic document QA |
| capability ontology                 | this benchmark       |
| cost savings                        | this benchmark/model |

Muy buena defensa preventiva contra overclaiming.

---

# 18. Reduciría bastante el related work

Ahora es muy rico, pero también genera un riesgo.

Tenés AGM, ATMS, provenance semirings, BDI, Soar, Hebb, Chow, Dung, routing, RAG, cascades, symbolic governance, etc. 

Intelectualmente es interesante, pero puede dar sensación de:

> “el paper quiere fundar un campo entero.”

Yo dejaría en cuerpo sólo cuatro grupos:

1. workflow / agent routing;
2. deterministic/symbolic governance;
3. provenance / typed belief systems;
4. selective prediction / abstention.

El linaje clásico completo puede ir al apéndice.

Probablemente te ahorre 4–6 páginas y haga más afilada la contribución.

---

# 19. El paper es demasiado largo para la cantidad de ideas que el lector necesita retener

91 páginas está bien como technical report, pero para el primer contacto es pesado.

Yo haría dos artefactos:

### Main paper

~20–25 páginas.

### Technical appendix

todo lo demás:

* proofs;
* preregistrations;
* experiment maps;
* exhaustive related work;
* artifact inventory;
* anti-pattern catalog.

Incluso para arXiv, el main PDF podría mantener appendices, pero las primeras ~20 páginas deberían contar una historia cerrada.

---

# 20. Cambiaría el título

**Hardness Over Hope** es memorable, pero “Hardness” puede sonar a computational hardness.

No es exactamente lo que estás diciendo.

Algunas variantes:

**Hard Guarantees over Hope: Deterministic Control for LLM Agents**

o

**Deterministic Control Planes for Stochastic LLM Agents**

o, mi favorita:

### **Confining Stochasticity in LLM Agents with Deterministic Control Planes**

Subtítulo:

**Policy-as-Code, Provenance, and Selective Execution**

Ese título comunica inmediatamente la contribución científica.

---

# 21. El abstract puede quedar mucho más fuerte si eliminás números secundarios

Ahora el resumen está muy cargado de resultados.

Yo lo reduciría a esta lógica:

**Problema**

LLMs son estocásticos y agent harnesses frecuentemente delegan al mismo LLM decisiones de control.

**Principio**

Separar stochastic perception de deterministic control.

**Formal**

Definimos delegated branching y variance confinement.

**Sistema**

beliefs con provenance + deterministic policy-as-code + feasibility + abstention.

**Experimento**

78 tareas × 12 paradigmas × 3 réplicas.

**Resultado principal**

delegated branching produce trajectory/output instability; moving a control decision to code materially increases reproducibility.

**Secondary result**

capability-aware deterministic routing reduces cost without degrading utility.

Nada más.

---

# 22. La frase más potente del paper debería convertirse en principio

Hay una línea conceptual excelente:

> “El LLM sólo dice qué hay en el material; reglas en código deciden sobre esa base.”



Yo la formalizaría como:

### Sensor–Controller Principle

> **A stochastic model may propose facts; it must not directly govern decisions whose invariance the system promises.**

Eso puede ser el principio por el cual la gente recuerde el paper.

---

# 23. Una arquitectura todavía más limpia sería “propose → type → verify → decide”

Tu arquitectura actualmente aparece repartida entre creencias, provenance, probes, dial, capabilities, θ, etc.

Yo la condensaría en cuatro operaciones:

```text
LLM
 ↓
PROPOSE
 ↓
TYPE + PROVENANCE
 ↓
VERIFY / ADMIT
 ↓
DETERMINISTIC DECIDE
```

y alrededor:

```text
             ┌───────────────┐
request ───▶ │ deterministic │ ───▶ action
             │ control plane │
             └───────▲───────┘
                     │
             typed propositions
                     │
                   LLM
```

Después todos tus componentes caen naturalmente ahí.

---

# 24. Hay un resultado potencialmente más grande escondido: control-plane/data-plane

Yo explotaría explícitamente la analogía de sistemas.

El paper ya distingue dos carriles en las figuras.

Eso se parece muchísimo a:

* networking: control plane / data plane;
* databases: optimizer / executor;
* operating systems: policy / mechanism;
* safety systems: controller / sensor.

Y tu arquitectura podría formularse:

$$
\text{LLM} = stochastic data/perception plane
$$

$$
\text{policy engine} = deterministic control plane
$$

Esto hace la idea inmediatamente comprensible para sistemas y ML.

Además explica por qué **Policy-as-Code** no es sólo un nombre comercial o DevOps: es precisamente la materialización del control plane.

---

# 25. Una cosa que NO cambiaría: la sección de limitaciones

La sección 8 es extraordinariamente útil.

Reconoce:

* un solo régimen principal;
* ruido de tokens;
* múltiples modelos sin mezclar estadísticas;
* confounder de serving;
* corpus sintético;
* falta de acciones externas reales;
* ontology detection todavía pendiente;
* deuda de versionado.

 

Eso genera confianza.

No la achicaría demasiado.

De hecho, movería dos de esas limitaciones al cuerpo.

---

# Las cinco mejoras que haría antes de subirlo

Si querés maximizar la probabilidad de que el paper tenga impacto, yo priorizaría sólo estas cinco:

1. **Reformular todo alrededor de una tesis:** stochastic sensor + deterministic control plane.
2. **Agregar una métrica formal de trajectory stochasticity**, no sólo `d(T)`.
3. **Hacer una ablación controlada donde sólo cambia quién toma una ramificación.**
4. **Bajar capability generalization y plasticity de “major contribution” a evidencia secundaria hasta completar P31/P35.**
5. **Crear una versión principal mucho más corta**, con el material exhaustivo en apéndice.

Mi impresión final: **hay un paper fuerte acá**. El riesgo actual es que el lector tenga que descubrirlo dentro de un paper aún más ambicioso. La tesis “confinar estocasticidad separando sensor y control” es suficientemente fuerte como para sostener el trabajo casi sola; el routing, las capabilities, la provenance y la plasticidad deberían reforzar esa tesis, no competir con ella.
