# Corpus gold

Los corpus existen para medir decisiones bajo ground truth exacto sin juez LLM. El gold
pertenece al evaluador y nunca es una feature de producción.

## Componentes

| Artefacto | Propósito |
|---|---|
| `documents.json` | Mundo documental visible para el agente. |
| `tasks.json` | Preguntas, scope y metadatos experimentales. |
| `entities.json` | Las personas del mundo, con sus **variantes de superficie** y las menciones contadas contra el TEXTO —no contra la intención del generador. |
| `manifest.json` | Parámetros de generación y conteos. |
| `generate.py` | Construcción determinista desde seed. |
| `verify.py` | Re-derivación independiente del gold. |

El verificador no reutiliza el estado interno del generador. Esto existe porque una
versión previa desplazó silenciosamente IDs después de crear amendments y produjo
oráculos incorrectos sin lanzar una excepción.

## El corpus de la campaña: `gold_h1`

Es el que usa la corrida homogénea. **78 tareas**, y se regenera con:

```powershell
py corpus\generate.py --seed 101 --people 60 --per-cell 3 --widths 4,16,48 `
   --unit-tokens 8000 --hard --honest-detectors --out corpus\gold_h1
py corpus\verify.py --corpus corpus\gold_h1
```

La cuenta: `3 por celda × (5 celdas sin width + 7 celdas × 3 widths) = 78`.

Los tres regímenes de ancho no son decorativos. `w4` son ~40k tokens de material por
tarea y `w48` son ~483k: **12×**. `w48` es el único donde el material **no entra en
ventana** (los 272k de nano), y ése es el régimen que el banco existe para medir. Por eso
`w4` sirve para probar el cableado y no sirve para concluir nada.

> **La receta se escribe.** Hasta el 2026-08-29 `gold_h1` existía sólo como directorio
> generado a mano, y sobrevivía por accidente en una carpeta temporal. Un corpus que no se
> puede regenerar desde una receta escrita no es reproducible, por más que sus archivos
> estén ahí.

## Familias de tarea

Son **once**, no seis. Las cinco de abajo del corte no dependen del ancho; las siete de
arriba se generan una vez por cada `width`.

| Celda | Propiedad principal | ¿Hay detector barato? |
|---|---|---|
| C2 | Cobertura independiente («listá todos los X»). | No: verificar la completitud **es** la tarea. |
| C4 | Agregación de cobertura completa. | No: verificar el conteo exige el conteo. |
| C5 | Horizonte desconocido. | No: saber cuándo parar **es** la pregunta. |
| C8 | Vigencia: ¿este valor sigue siendo el actual? | No: exige encontrar toda enmienda que pudiera reemplazarlo. |
| C9 | Roster declarado — el único dominio de completitud que viene **enunciado**. | No. |
| B2 | Ausencia: «nadie ocupa el rol R». | No: chequearlo es barrer el dominio entero. |
| D1 | Presuposición: la respuesta correcta es que la premisa no se sostiene. | No. |
| C1 | Hecho único verificable. | **Sí**: se mira y se sabe. |
| C3 | Cadena acoplada. | No: chequear el extremo es caminar la cadena. |
| C7 | Decisión irreversible y gate humano. | **Sí**: el disparador está o no está. |
| W1 | Contención de escrituras compartidas. | **Sí**: el registro de cambio pendiente está o no está. |

La columna de la derecha no es un adorno: es la partición de la **Afirmación 2**. Donde
hay detector barato no hace falta ruteador, hace falta cascada. Y se declara por celda
(`--honest-detectors`) en vez de asumir `True` en todas — el oráculo gold no se toca, lo
único que cambia es lo que a la DECISIÓN se le dice.

## Entidades: por qué el corpus tiene personas y no strings

Un corpus donde cada mención de una persona es su nombre canónico completo hace que
resolver entidades sea **gratis**, y un patrón que existe para resolverlas no se puede
falsear ahí. Por eso el generador produce variantes de superficie por persona y por firma,
anáfora con concordancia, y la referencia cruzada en forma **no canónica**.

Medido sobre el texto, no declarado:

- **36,5%** de las menciones son invisibles a un `keyword_search` del nombre completo.
- El **100%** de los saltos de cadena C3 exige resolver una variante.

Con **guarda de ambigüedad**: una forma que matchea a dos personas se descarta, porque
unir de más destruye la verdad derivable y produce una confusión que nada aguas abajo
detecta. Y el verificador sigue siendo independiente: resuelve **por matching contra los
canónicos**, no regenerando las variantes — si la regla estuviera mal, coincidirían en el
error.

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
