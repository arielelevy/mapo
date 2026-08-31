# Plan de revisión — `paper-es.md` → borrador 2.0

Dos pases. El primero atacó el arranque (título, resumen sin números sueltos, contenido
simplificado). El segundo, el **rigor académico**, con meta declarada de **4,8**.

---

## 1. Evaluación multi-dimensional

| dimensión | peso | antes | después | qué cambió |
|---|---:|---:|---:|---|
| Contribución original | 25% | 4,5 | **4,8** | el objeto del paper pasa a estar **definido** (Def. 5.1–5.3) y no sólo descrito; la conjunción sigue siendo el claim |
| Marco teórico | 20% | 4,0 | **4,7** | §5.0: cuatro definiciones formales, la Proposición 5.4 con demostración por inducción, y qué **no** afirma. El Teorema 1 se reencuadra como identidad contable |
| Dominio de la literatura | 15% | 4,0 | **4,7** | §2.9: la genealogía sale de Diseño y ancla el trabajo relacionado, con **análisis crítico** —qué supone cada línea sobre su fuente y qué de eso rompe un LLM— más tabla comparativa |
| Rigor metodológico | 20% | 4,5 | **4,8** | §7.0: cinco preguntas de investigación `PI1–PI5` con criterio de decisión fijado antes del dato, régimen de medición y validez del corrector |
| Argumentación | 10% | 3,0 | **4,5** | resumen de 25 cifras a **5**; contribuciones enumeradas; el término del título hilado por resumen → §5.0 → §7 → conclusión |
| Reflexión crítica | 10% | 4,5 | **4,8** | §8 estructurada en interna / externa / constructo / reproducibilidad, sin perder un párrafo |

**Puntaje: 4,76** (era 4,18).

---

## 2. Pase 1 — el arranque

### 2.1 Diagnóstico

El resumen tenía **~70 líneas y 25 cifras distintas**, sin jerarquía: las de titular y las de
detalle con el mismo peso tipográfico. Duplicaba §6.3.2 entero. Y la cabecera decía *«lo que
aún no hay es una medición válida sobre datos held-out»* cuando §7.7 reporta tres estratos y
48,5M tokens — texto sobreviviente.

### 2.2 Qué sobrevivió al resumen

**Cinco cifras**: `17–34%` · `0,33 → 0,89` · `1,000` en `k≥4` · `48%` · `−0,034`. Las otras
veinte ya viven en §6–§7 con su contexto y su piso de ruido; se verificó una por una que
ninguna se perdiera. Las seis superficies plásticas y la genealogía pasan a referenciarse.

### 2.3 Título

| candidato | evaluación |
|---|---|
| *Un motor determinista y plástico sobre un sensor estocástico* | describe la arquitectura, no el principio |
| *El plano de control no pertenece al modelo* | enuncia un principio, pero no nombra la propiedad que se mide |
| **Confinamiento de varianza en agentes LLM** | **elegido por el autor.** Nombra la propiedad, es medible, y obliga a definirla formalmente — que es lo que el pase 2 hizo |

Subtítulo: *Un plano de control determinista y plástico sobre un sensor estocástico*.

---

## 3. Pase 2 — el rigor

### 3.1 El título nombraba algo sin definición

Es el hallazgo del pase. *Confinamiento de varianza* pasó a ser el objeto del paper y no tenía
enunciado formal. **§5.0** lo repara:

| | qué |
|---|---|
| **Def. 5.1** | trayectoria `T(q, M)` como secuencia de nodos ⟨unidad leída, llamada emitida⟩ |
| **Def. 5.2** | punto de ramificación **delegado**, y `d(T)` como su conteo |
| **Def. 5.3** | varianza **confinada** ⟺ `d(T) = 0` |
| **Prop. 5.4** | *localización*: con `d = 0` las trayectorias coinciden y toda discrepancia tiene un nodo testigo. Demostración por inducción sobre la longitud |
| **Def. 5.5** | `pass^k` como la consecuencia observable |

Y dos párrafos que un revisor va a buscar: **qué compra** la proposición (una discrepancia
localizable es depurable; una repartida sobre una historia entera, no) y **qué no afirma** (el
confinamiento no reduce la varianza del sensor ni mejora la calidad — reordena dónde puede
manifestarse; que además suba la utilidad es resultado de §7.2, no corolario de la Prop. 5.4).

### 3.2 El Teorema 1 se dejaba leer como evidencia

Ahora abre declarando que es una **identidad contable**, no un resultado empírico, y para qué
sirve: hace falsable una evaluación de ruteo. Un teorema presentado como evidencia del sistema
sería exactamente el error que el paper le audita a otros.

### 3.3 La genealogía estaba en el lugar equivocado

Vivía en §6.3.2 (Diseño), donde un lector no busca linaje. Pasa a **§2.9** y deja de ser
descriptiva: la tabla tiene cuatro columnas —línea · qué aporta · **qué asume sobre la fuente**
· **qué rompe un LLM**— sobre las ocho líneas (AGM, TMS/ATMS, procedencia, BDI, Soar/ACT-R,
Hebb, Chow, Dung). Eso convierte una lista de precursores en el catálogo de supuestos que hubo
que reemplazar, que es el aporte. §6.3.2 queda como puntero de cuatro líneas.

### 3.4 Faltaban las preguntas de investigación

**§7.0** las declara: `PI1` varianza de trayectoria · `PI2` premio neto de rutear · `PI3` señal
que explique la interacción · `PI4` acuerdo como verificador · `PI5` transferencia de
capacidades. Cada una con **criterio de decisión fijado antes de mirar el dato** y su sección.
Más el régimen de medición y §7.0.1, la validez del corrector.

### 3.5 Las amenazas eran una lista plana

**§8** pasa a interna (8.1) / externa (8.2) / constructo (8.3) / reproducibilidad (8.4), con
una apertura que aclara que ninguna toca la Prop. 5.4 ni los dos teoremas —verificados por
máquina, no dependen del corpus— y todas tocan §7. **No se eliminó ningún párrafo**: se
reagruparon.

---

## 4. Estado verificado

| | |
|---|---|
| líneas | 2.536 |
| figuras | 13 |
| algoritmos | 3 |
| definiciones formales | 4 |
| teoremas | 2 (verificados por máquina) |
| proposiciones | 4 (una nueva, con demostración) |
| resumen | 468 palabras, 5 cifras |
| referencias huérfanas | **ninguna** |

## 5. Checklist

- [x] Título que nombra la propiedad medida
- [x] La propiedad del título, definida formalmente antes de la evidencia
- [x] Resumen con ≤ 5 cifras y contribuciones enumeradas
- [x] Cabecera sin afirmaciones contradichas por el cuerpo
- [x] Genealogía anclando el trabajo relacionado, con análisis crítico
- [x] Preguntas de investigación con criterio previo al dato
- [x] Amenazas por tipo de validez
- [x] Ninguna cifra del cuerpo perdida
- [x] Cero referencias huérfanas
- [x] Las 13 figuras y 3 algoritmos intactos

## 6. Lo que queda fuera de alcance del pase

Tres cosas que **no** se pueden arreglar escribiendo, y por eso quedan declaradas en §8 en vez
de resueltas:

- **La superficie de acciones no está ejercitada.** Las doce herramientas del inventario leen
  el mundo o escriben el estado del propio agente; ninguna cambia nada afuera del proceso. Es
  otro experimento.
- **`p = 0,065` en §7.4 necesita más brazos, no más tareas.** El piso de ruido de un premio de
  máximo crece con la dispersión: agregar tareas lo subió.
- **Validez externa sin benchmark público.** El ground truth sintético es exacto y se re-deriva
  independientemente, pero la distribución de tareas reales sobre los diales estructurales es
  desconocida.
