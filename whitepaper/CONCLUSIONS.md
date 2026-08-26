# Conclusiones por patrón, basadas en lo medido

**Fecha**: 2026-08-26 · **Estado**: gold_v2 completo (126 filas, repeat=3); gold_deep
**parcial** (101 filas, corrida en curso) — los números de gold_deep pueden moverse.

**El encuadre**: esto es un experimento estilo ML donde la variable no es el modelo sino
**el patrón de orquestación**. Mismas tareas, mismo modelo (`gpt-5-chat`), mismas
herramientas, mismo contrato de respuesta; lo único que permuta es la estructura de
control. Con réplicas (repeat=3), corpus held-out y piso de ruido por celda — igual que
se evalúa un algoritmo.

Celdas: **C2** = extracción independiente en masa · **C3** = cadena acoplada (A→B) ·
**C4** = agregación con cobertura total · **C5** = horizonte desconocido.
Regímenes: **gold_v2** = todo entra en ventana (~18k tokens) · **gold_deep** = fuera de
ventana (~483k tokens; leer todo no es caro, es imposible).

---

## La tabla (utilidad media / tokens medios por fila)

### En ventana (gold_v2, completo, repeat=3)

| patrón | C2 | C3 | C4 | C5 | flips | costo mediana (rango) |
|---|---|---|---|---|---|---|
| `direct` | 0,75 / 13k | **1,00** / 11k | 1,00 / 13k | **1,00** / 11k | **0/6** | **10,5k (1×)** |
| `cot` | 0,75 / 13k | **1,00** / 11k | 1,00 / 12k | **1,00** / 11k | **0/6** | 10,6k (1×) |
| `react` | 0,75 / 25k | 0,67 / 63k | 1,00 / **3k** | 1,00 / 61k | 3/6 | 23,8k (**70×**) |
| `map_reduce` | 0,75 / 16k | **0,00** / 14k | 1,00 / 16k | **0,00** / 16k | 0/6 | 15,1k (1×) |
| `plan_execute` | **0,00** / 27k | **0,00** / 11k | **0,00** / 32k | 0,33 / 29k | 1/6 | 19,0k (12×) |
| `reflection` | 0,83 / 31k | 0,44 / 40k | 1,00 / 8k | 0,67 / 113k | 3/6 | 21,2k (27×) |
| `dag_strategy` | 0,75 / 27k | 0,33 / 77k | 1,00 / 6k | 0,67 / 66k | 3/6 | 33,1k (**82×**) |

### Fuera de ventana (gold_deep, PARCIAL, corrida en curso)

| patrón | C2 | C3 | C4 | C5 | flips | costo mediana (rango) |
|---|---|---|---|---|---|---|
| `direct` | INFACTIBLE | INFACTIBLE | INFACTIBLE | 1,00 / 23k* | 0/5 | 22,9k (1×) |
| `cot` | INFACTIBLE | INFACTIBLE | INFACTIBLE | 1,00 / 23k* | 0/5 | 23,0k (1×) |
| `react` | 0,97 / 61k | 1,00 / 15k | 1,00 / 21k | 1,00 / 26k | **0/4** | 25,6k (40×) |
| `map_reduce` | 0,95 / 107k | **0,00** / 276k | 1,00 / 29k | **0,00** / 23k | 1/5 | 28,7k (15×) |
| `plan_execute` | 0,62 / 88k | 0,67 / 6k | 0,67 / 37k | 0,67 / 39k | **4/5** | 33,2k (52×) |
| `reflection` | 1,00 / 106k | 1,00 / 34k | 1,00 / 17k | 1,00 / 37k | 0/4 | 33,5k (19×) |
| `dag_strategy` | 1,00 / 50k | 1,00 / 17k | 1,00 / 19k | 1,00 / **16k** | 0/4 | **19,7k** (7×) |

\* sólo en las tareas w4 chicas que sí entran en ventana; la poda es por tarea, no por corpus.

Factibilidad (barrido aritmético, costo cero, sobre TODOS los tasks): a 135k tokens se
podan `direct`/`cot` en 12/32 tareas; a 483k en 24/26; a 1.272k en 24/32 — y a esa escala
la poda alcanza a `map_reduce` en 18-20 tareas (su proyección excede el budget).

---

## Conclusión por patrón

### `direct` / `cot` — imbatibles adentro de la ventana; inexistentes afuera
**Cuándo ganan**: siempre que la evidencia entra en el prompt. En ventana: utilidad
perfecta en C3/C4/C5, el costo más bajo (10,5k mediana), dispersión 1× y **cero flips en
6 celdas** — el único patrón perfectamente reproducible. **Límite**: es un límite
aritmético, no de calidad — fuera de ventana quedan infactibles en 24/26 tareas de
gold_deep, computado gratis antes de gastar un token. **CoT no agregó nada sobre direct
en ninguna celda medida** (mismas utilidades, mismo costo ±2%): en extracción sobre
documentos, el razonamiento explícito no compra nada.

### `react` — el fallback general: gana casi todo, pero su costo es una lotería
**Cuándo gana**: es el único patrón con u≥0,97 en TODAS las celdas factibles de gold_deep
(parcial) — el fallback general funciona a escala. Y cuando el retrieval superficializa
el dato es baratísimo (C4 en ventana: u=1,00 a 3k, más barato que direct). **Límites**:
(1) su costo es la mayor lotería medida — rango 70× en ventana (2,9k a 203k), y el caso
medido de manual: misma tarea C3, u=1 con 146k en una réplica y u=0 con 203k en otra —
el bucle de retrieval desbocado; (2) 3/6 celdas se dieron vuelta entre réplicas en
ventana — inestable justo donde el retrieval no alcanza. **El costo de react no lo
gobierna la tarea: lo gobierna la calidad del retrieval.**

### `map_reduce` — el especialista más confiable y el fallo más honesto
**Cuándo gana**: cobertura independiente (C2/C4) — a la par de los mejores con costo
estable (1× en ventana) y cero flips. **Límite estructural, no de escala**: u=0,00 en C3
(acoplado) y C5 en AMBOS regímenes — no puede comparar A con B porque procesa A y B en
aislamiento. Es ontológico: ninguna herramienta ni modelo lo arregla, y falla
**determinísticamente** (0 flips — hasta su fallo es reproducible). A 1,27M tokens además
empieza a podarse por presupuesto (18-20/32 tareas). **Regla dura: prohibido en cuanto
hay acoplamiento; primera opción en cobertura independiente.**

### `plan_execute` — el peor patrón medido, en ambos regímenes
En ventana: u=0,00 en C2, C3 y C4 **con la evidencia disponible** — la descomposición
destruye la dependencia contextual: cada sub-tarea pierde el estado global y el agregado
reconstruido es erróneo sin que nada falle. Fuera de ventana mejora algo (0,62-0,67) pero
es **el más inestable de todos: 4/5 celdas se dieron vuelta entre réplicas**. Ningún
régimen medido lo favorece. **Regla: no usarlo para QA/extracción; si se descompone, la
descomposición debe heredar estado (stateful chaining), no aislar.**

### `reflection` — paga fuera de ventana, carísimo adentro
En ventana: mediocre (0,44 en C3) e inestable (3/6 flips), con el peor caso de costo en
C5 (113k medio, hasta 199k) — reflexionar sobre lo que ya está en el prompt es gasto puro.
Fuera de ventana (parcial): u=1,00 en todo y 0 flips — cuando el primer intento puede
fallar por evidencia incompleta, el ciclo de crítica sí compra calidad. **El bucle de
reflexión sólo paga cuando hay algo nuevo que mirar entre iteraciones.**

### `dag_strategy` — de peor a mejor según el régimen (el resultado más interesante)
En ventana: el patrón más caro (mediana 33k, rango **82×**, hasta 251k), mediocre en C3
(0,33) e inestable (3/6 flips) — toda la maquinaria de verificar-replanificar es puro
overhead cuando direct resuelve con 11k. Fuera de ventana (parcial): **u=1,00 en todas
las celdas con la mediana de costo MÁS BAJA del régimen (19,7k) y 0 flips** — con las
señales contables (estancamiento, cobertura, contabilidad de IDs) el DAG explora sólo lo
que necesita. ⚠️ Preliminar: es el resultado que más puede moverse cuando termine la
corrida y con el piso de ruido por celda. Si se sostiene, **la topología elaborada no se
justifica por inteligencia sino por régimen**: es la mejor opción exactamente donde leer
todo es imposible, y la peor donde es posible.

---

## Las reglas que emergen (el θ en prosa)

1. **Primero aritmética, no juicio**: si la evidencia entra en la ventana → `direct`.
   Cero flips, costo 1×, utilidad máxima. Todo lo demás es para cuando NO entra.
2. **Acoplamiento manda**: hay cadena/comparación → `map_reduce` prohibido (u=0
   determinístico en ambos regímenes).
3. **Cobertura independiente** → `map_reduce` (el especialista estable) mientras su
   proyección entre en presupuesto; a 1,27M ya no siempre entra.
4. **Fuera de ventana, el defecto es `react`** (u≥0,97 en todo lo factible) — pero su
   costo lo gobierna el retrieval, no la tarea: sin señales de estancamiento es una
   lotería de 40-70×.
5. **`dag_strategy` es candidato a primera opción fuera de ventana** (mejor costo mediano
   y u=1,00, parcial) — y a última opción adentro (82× de rango).
6. **`plan_execute` no tiene región ganadora medida.**
7. **La inestabilidad vive donde el retrieval decide**: los patrones sin herramientas
   tienen 0-1 flips; los que buscan tienen 3/6 en ventana. La varianza que se le
   atribuye a la topología la gobierna la superficie de herramientas.

## Límites de estas conclusiones

- gold_deep está **en curso**: sus números pueden moverse; el veredicto final exige el
  piso de ruido POR CELDA y la brecha neta (protocolo §10).
- n chico: 3 tareas/celda en ventana, 2 fuera; un corpus sintético; un modelo.
- C2 en ventana da 0,75 parejo para casi todos — esa celda no discrimina patrones,
  discrimina el oráculo (empate estructural conocido).
- La latencia del DAG no es comparable (corre secuencial en el harness).
- Nada de esto es distribución del mundo real: dice qué propiedad estructural gobierna
  qué patrón, no con qué frecuencia aparece cada propiedad.
