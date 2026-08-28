# mapo-ui — consola de prueba

Interfaz para ejercitar el motor: workspaces con corpus, ingesta asincrónica, contexto
curado por request y la decisión a la vista antes que la respuesta.

**Estado: propuesta ejecutable.** Corre y se puede usar, pero el modo `motor` habla con
endpoints que todavía no existen (`lab/ARQUITECTURA.es.md` §6). El modo `demo` genera
localmente los mismos eventos tipados, así que la interfaz se trabaja sin gastar tokens.

```bash
npm install
npm run dev        # http://localhost:5173
npm run build      # tsc -b && vite build
npm run typecheck
```

El proxy de `vite.config.ts` manda `/v1/*` a `http://localhost:8000`, que es donde se
espera la API de FastAPI. Sin motor levantado, dejá el selector de arriba a la derecha en
`demo`.

## Qué muestra, y por qué así

**La escalera de decisión es lo primero.** Los trece paradigmas se tachan por etapa
—factibilidad, garantía, θ— con motivo tipado en cada tachadura, antes de que exista un
token. Es el trace del router renderizado, no una animación.

**La respuesta no es el protagonista.** Va más chica y más abajo que la escalera. El
banco no usa juez LLM porque puntuar prosa premia verbosidad; la interfaz aplica el mismo
criterio y se niega a hacerla el centro.

**Los tres terminales son estructuralmente distintos**, no tres colores del mismo cartel:

| Terminal | Qué pasó | Color |
|---|---|---|
| `done` | Un paradigma corrió y contestó. | azul `--live` |
| `gated` | **Nada se ejecutó.** Una persona tiene que decidir. | rojo `--halt` |
| `deferred` | θ no tuvo margen. Corrió el fallback, y queda anotado como abstención. | ocre `--abstain` |

Cada color significa una sola cosa en toda la aplicación.

**El contexto es un conjunto curado, no una lista de adjuntos.** Arrastrás unidades a la
bandeja de la derecha y ahí elegís cuáles entran. Apagar una unidad no la saca de la
bandeja: la deja a la vista, apagada, para que puedas ver qué cambia y volver a
prenderla. El panel de abajo recalcula en cada toggle **qué paradigmas te quedan
admisibles** y por qué murieron los otros. Esa poda es aritmética y no consume
inferencia, así que se puede mostrar antes de gastar un token — que es exactamente lo
que el motor promete.

**Lo irreversible se declara, no se infiere.** Los toggles `irreversible`, `escrituras
compartidas` y `regulado` los marca quien pregunta. `lab/app/serve.py` es explícito:
el motor los asienta como `COMPUTED` con credencia 1.0, y deducirlos de la redacción
pondría una conjetura donde la capa de creencias promete un hecho.

**La ingesta muestra el veredicto del sensor.** Antes de parsear se mide la cobertura de
la capa de texto y eso decide OCR; el resultado queda escrito en cada documento. Es una
creencia `COMPUTED`, no una heurística escondida en una rama.

## Estructura

```
src/
  types.ts              vocabulario compartido con lab/app/
  store.ts              zustand: workspaces, ingesta, contexto, intercambios
  lib/feasibility.ts    espejo local de la poda aritmética (vista previa)
  lib/transport.ts      SSE contra el motor + generador de trazas demo
  components/           TopBar · WorkspacePanel · ContextTray · Composer · ExchangeView
  styles/tokens.css     la paleta y las tres semánticas de color
```

`lib/feasibility.ts` es una **vista previa**, no la autoridad: el veredicto que vale es
el del evento `decision`. La interfaz lo dice al pie del panel para que nadie confunda
una estimación con una decisión.

## Decisiones técnicas

- **Vite + React 19 + TypeScript.** Sin Next: no hay SSR que ganar y agregaría un
  servidor que no queremos entre la consola y el motor.
- **Zustand.** El estado es real —workspaces × documentos × máquina de ingesta ×
  selección × streaming— y Context volvería a renderizar todo con cada token.
- **dnd-kit** en vez del drag-and-drop nativo: el nativo no es operable con teclado.
- **CSS Modules**, sin Tailwind. El diseño es un sistema de tokens con tres colores
  semánticos; la sopa de utilidades los enterraría.
- **Sin librería de fetching.** `fetch` + `ReadableStream` alcanzan para SSE.

Las tipografías se cargan hoy desde Google Fonts. Para el despliegue on-prem hay que
self-hostearlas: es la única dependencia de red que queda fuera del motor.
