# Paradigmas ejecutables

Un paradigma es una estructura de control, no una variante de prompt. El banco conserva
controles históricos y candidatos falsificados para reproducibilidad; eso no los vuelve
candidatos activos del producto.

## Catálogo

Son **15 registrados**, **13 que se corren**. Actualizado 2026-08-29.

| Nombre | Estructura | Región o propósito | Estado actual |
|---|---|---|---|
| `direct` | Una llamada con todo el material. | Caso degenerado cuando la evidencia cabe. | Control, gateado por factibilidad. |
| `react` | Bucle abierto de herramientas. | Fallback general. | Activo, costoso y sensible al modelo. |
| `reflection` | Borrador, crítica y revisión. | Corrección de respuesta. | Activo; la mejora anterior se retiró como ruido. |
| `dag_strategy` | DAG, blackboard, verificación y replanning. | Dependencias complejas. | Activo; costo alto y flujo menos certificable. |
| `rewoo` | Plan de dataflow previo, ejecución y solve final. | Cobertura independiente barata. | Especialista activo; falla con continuidad no prevista. |
| `handoff` | Agentes con alcance propio y transferencia **autorizada por código**. | Partición fija del alcance. | Candidato nuevo (K-8). P23 registrada antes de correr. |
| `supervisor` | Orquestador que elige el próximo sub-agente **después** de ver el anterior. | El medio entre plan fijo y partición fija: lo que hoy se llama «subagentes». | Candidato nuevo (K-9). P28a–d registradas antes de correr. El sub-agente recibe **un pedazo** de contexto, y el recorte lo hace el código (`SUB_SCOPE_UNITS = 8`), no el modelo. |
| `gist_reader` | Tabla de gists y lecturas dirigidas. | Evidencia fuera de ventana. | Falsificado en dos de tres regiones objetivo. |
| `extract_compute` | Extracción estructurada y cómputo. | Agregación exacta. | Infactible bajo el presupuesto de producción medido. |
| `streaming_scan` | Escaneo secuencial con estado acotado. | Cobertura estable. | Infactible bajo el presupuesto de producción medido. |
| `pointer_chase` | Bucle por código, una unidad por salto. | Cadenas con punteros visibles. | P14a falsificado; frenos P14b confirmados. |

### Fuera del ruteo, por decisión escrita

| Nombre | Por qué |
|---|---|
| `cot` | **La ingeniería de prompts no es un patrón** (2026-08-26). Dominado por `direct` en toda celda medida: misma utilidad, nunca más barato, y redundante con modelos razonadores. Se conserva **sólo** como control nulo — es la evidencia de que el andamiaje por prompt no compra nada. |
| `plan_execute` | Retirado por dominado (2026-08-29). Sin región ganadora medida. |

### En `standby`: no retirados, y con condición de revival escrita

| Nombre | Estructura | Por qué está en standby |
|---|---|---|
| `map_reduce` | Map por unidad y reducción. | Decisión del autor (2026-08-28): no se le gasta más cuota de medición. Gana **1 celda de 33** en las que compite, la aritmética lo poda en **180 de 270** filas, y en P20 su reducción fue **0,0%** — su fan-out lo fija el código, así que no tiene nada que ahorrar donde el resto ahorra. |
| `graph_traverse` | Índice de entidades y BFS. | **P10a falsificado** (u=0,000 en las dos celdas acopladas, con las aristas presentes y el índice 100% anclado al texto). Revive con (a) un corpus con resolución de entidades real y (b) un índice con la disciplina de la sonda — las dos condiciones están escritas en el ejecutable. |

Su dato histórico **se replaya igual**: un brazo que no se corre igual se replaya, y un
replay sobre código roto falla igual.

## Reglas del catálogo

- Una diferencia de fraseo no crea un paradigma.
- Todo paradigma nuevo declara estructura, nicho, anti-nicho, factibilidad y frenos.
- Un candidato falsificado no se borra del registro experimental.
- El fallback debe estar medido en todas las tareas usadas para juzgar el motor.
- Un nivel de garantía puede excluir un paradigma por flujo no acotado aunque su calidad
  sea alta.
- El costo de una herramienta forma parte de la topología, no es ruido externo.

## Relación con REC

REC no es un paradigma de esta lista. Es una política de adquisición de evidencia antes
de elegir entre paradigmas. Puede terminar en especialización, fallback, deferral o gate.
