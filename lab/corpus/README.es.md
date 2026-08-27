# Corpus gold

Los corpus existen para medir decisiones bajo ground truth exacto sin juez LLM. El gold
pertenece al evaluador y nunca es una feature de producción.

## Componentes

| Artefacto | Propósito |
|---|---|
| `documents.json` | Mundo documental visible para el agente. |
| `tasks.json` | Preguntas, scope y metadatos experimentales. |
| `manifest.json` | Parámetros de generación y conteos. |
| `generate.py` | Construcción determinista desde seed. |
| `verify.py` | Re-derivación independiente del gold. |

El verificador no reutiliza el estado interno del generador. Esto existe porque una
versión previa desplazó silenciosamente IDs después de crear amendments y produjo
oráculos incorrectos sin lanzar una excepción.

## Familias de tarea

| Celda | Propiedad principal |
|---|---|
| C1 | Hecho único verificable. |
| C2 | Cobertura independiente. |
| C3 | Cadena acoplada. |
| C4 | Agregación de cobertura completa. |
| C5 | Contradicción mediante join entre unidades. |
| C7 | Decisión irreversible y gate humano. |

## Corrección semántica pendiente en C5

El C5 actual está rotulado como horizonte desconocido, pero el generador y el
verificador construyen exactamente dos saltos. Ese truth no debe usarse para afirmar que
el horizonte es intrínsecamente desconocido.

Para REC se requiere separar:

- **continuación observada:** una clave literal recurre entre unidades distintas;
- **longitud variable:** el número de continuaciones depende de evidencia encontrada;
- **horizonte desconocido:** no existe una cota previa suficiente para planificar.

Son propiedades distintas y necesitan verificadores distintos.

## Prevención de leakage

El objeto que recibe producto debe excluir:

- `oracle` de evaluación;
- `cell`;
- `truth_*`;
- `relevant_units`;
- cualquier ID cuyo formato revele la clase.

Si existe un detector de runtime, se representa como una capacidad independiente. No se
deduce de que el evaluador tenga gold.

## Mundo final para REC

`gold_transfer` ya fue observado y solo puede usarse para diagnóstico. La evaluación
final necesita:

- seeds o mundos nuevos generados después de congelar el diseño;
- nombres, orden, formatos de clave y distractores distintos;
- pares equiparados de cobertura y continuidad;
- cadenas de longitud realmente variable con terminación verificable;
- suficientes escenarios independientes por estrato;
- al menos un corpus ajeno a este generador para una afirmación doctoral.
