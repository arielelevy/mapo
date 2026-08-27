# Paradigmas ejecutables

Un paradigma es una estructura de control, no una variante de prompt. El banco conserva
controles históricos y candidatos falsificados para reproducibilidad; eso no los vuelve
candidatos activos del producto.

## Catálogo

| Nombre | Estructura | Región o propósito | Estado actual |
|---|---|---|---|
| `direct` | Una llamada con todo el material. | Caso degenerado cuando la evidencia cabe. | Control gateado por factibilidad. |
| `cot` | Igual estructura que Direct con instrucción de razonamiento. | Control nulo. | Retirado de nuevas corridas; dominado por Direct. |
| `react` | Bucle abierto de herramientas. | Fallback general. | Activo, costoso y sensible al modelo. |
| `map_reduce` | Map por unidad y reducción. | Cobertura independiente. | Activo; falla estructuralmente en acoplamiento. |
| `plan_execute` | Plan de subpreguntas, ejecución y síntesis. | Descomposición. | Sin región ganadora medida. |
| `reflection` | Borrador, crítica y revisión. | Corrección de respuesta. | Mejora anterior retirada como ruido. |
| `dag_strategy` | DAG, blackboard, verificación y replanning. | Dependencias complejas. | Activo en el banco; costo alto y flujo menos certificable. |
| `rewoo` | Plan de dataflow previo, ejecución y solve final. | Cobertura independiente barata. | Especialista activo; falla con continuidad no prevista. |
| `gist_reader` | Tabla de gists y lecturas dirigidas. | Evidencia fuera de ventana. | Falsificado en dos de tres regiones objetivo. |
| `graph_traverse` | Índice de entidades y BFS. | Cadenas reducibles a adyacencia. | P10a falsificado. |
| `extract_compute` | Extracción estructurada y cómputo. | Agregación exacta. | Infactible bajo presupuesto de producción medido. |
| `streaming_scan` | Escaneo secuencial con estado acotado. | Cobertura estable. | Infactible bajo presupuesto de producción medido. |
| `pointer_chase` | Bucle por código, una unidad por salto. | Cadenas con punteros visibles. | P14a falsificado; frenos P14b confirmados. |

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
