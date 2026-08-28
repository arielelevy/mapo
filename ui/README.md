# mapo-ui — consola de prueba

Interfaz para ejercitar el motor: workspaces con corpus, ingesta asincrónica, contexto
curado por request, y la decisión a la vista **antes** que la respuesta.

**Estado: propuesta ejecutable.** Corre y se puede usar hoy, pero el modo `motor` habla
con endpoints que todavía no existen (`../lab/ARQUITECTURA.es.md` §6). El modo `demo`
genera localmente los mismos eventos tipados, así que la interfaz se trabaja sin gastar
un token. El selector está arriba a la derecha y dice en cuál estás.

---

## Arrancar

```bash
npm install
npm run dev          # http://localhost:5173
```

| Script | Qué hace |
|---|---|
| `npm run dev` | Servidor de desarrollo con HMR. |
| `npm run build` | `tsc -b && vite build` → `dist/`. |
| `npm run preview` | Sirve `dist/` para probar el build. |
| `npm run typecheck` | Sólo tipos, sin emitir. |

El proxy de `vite.config.ts` manda `/v1/*` a `http://localhost:8000`, que es donde se
espera la API de FastAPI. Sin motor levantado, dejá el selector en `demo`.

---

## Qué muestra, y por qué así

### La escalera de decisión es lo primero

Los trece paradigmas se tachan por etapa —factibilidad, garantía, θ— con **motivo tipado
en cada tachadura**, antes de que exista un token. Es el trace del router renderizado, no
una animación. La numeración `01/02/03/04` no decora: es la secuencia real del router, y
el orden carga información.

### La respuesta no es el protagonista

Va más chica y más abajo que la escalera. Es deliberado: el banco no usa juez LLM porque
puntuar prosa premia verbosidad y castiga lo barato. Si el banco se niega a puntuar
prosa, la interfaz se niega a hacerla el centro.

### Los tres terminales son estructuralmente distintos

No son tres colores del mismo cartel. Cambia qué se muestra, no sólo cómo.

| Terminal | Qué pasó | Qué se ve |
|---|---|---|
| `done` | Un paradigma corrió y contestó. | Respuesta, citas y consumo. Azul `--live`. |
| `gated` | **Nada se ejecutó.** | Sin respuesta, sin tokens, sin sonda. Aviso de revisión humana. Rojo `--halt`. |
| `deferred` | θ no tuvo margen; corrió el fallback. | Respuesta **más** el aviso de abstención con el margen que faltó. Ocre `--abstain`. |

Cada uno de esos tres colores significa **una sola cosa** en toda la aplicación. Nada más
los usa.

Confundir `gated` con `deferred` es la falla que esta capa existe para evitar: un sistema
que "resuelve" un pedido irreversible eligiendo calladamente un paradigma seguro ya tomó
la decisión que le correspondía a una persona.

### El contexto es un conjunto curado, no una lista de adjuntos

Arrastrás unidades del workspace a la bandeja de la derecha, y ahí elegís cuáles entran.

**Apagar una unidad no la saca de la bandeja.** Queda a la vista, tachada, para que
puedas ver qué cambia y volver a prenderla. Sacarla y excluirla son dos gestos distintos
porque responden preguntas distintas.

El panel de abajo recalcula en cada toggle **qué paradigmas te quedan admisibles** y por
qué murieron los otros. Esa poda es aritmética y no consume inferencia, así que se puede
mostrar antes de gastar nada — que es exactamente lo que el motor promete. Agregar una
unidad mata a `direct` por ventana; agregar la quinta mata a `map_reduce` por
cardinalidad.

### Lo irreversible se declara, no se infiere

Los toggles `irreversible`, `escrituras compartidas` y `regulado` los marca quien
pregunta. `../lab/app/serve.py` es explícito: el motor los asienta como `COMPUTED` con
credencia 1.0, y deducirlos de la redacción pondría una conjetura donde la capa de
creencias promete un hecho.

> Esto empezó como una regex sobre el texto y **no disparaba**: "Publicá" y "transferí"
> no matchean `publica` ni `transferi`, porque en voseo el acento cae justo en esa vocal.
> El arreglo no fue una regex mejor. Era la interfaz contradiciendo el contrato del
> producto.

### La ingesta muestra el veredicto del sensor

Antes de parsear se mide la cobertura de la capa de texto, y **eso** decide OCR. El
resultado queda escrito en cada documento (`capa de texto sana · 1347 chars/pág → sin
OCR`). Es una creencia `COMPUTED`, no una heurística escondida en una rama.

Los seis pasos son los de `../lab/ARQUITECTURA.es.md` §3: `en cola → sensor → parseo →
chunks → embeddings → indexado`. Cada documento avanza por su cuenta: subir cinco no
serializa nada.

---

## El contrato con el motor

La consola consume **SSE tipado**, no un chorro de tokens. El backend tiene que emitir
frames con `event:` y `data:` en JSON. Los tipos están en `src/types.ts` (`StreamEvent`).

`POST /v1/answer` → `text/event-stream`

Cuerpo (snake_case, el vocabulario de `Request` en `serve.py`):

```json
{
  "question": "…",
  "unit_ids": ["u-01", "u-04"],
  "assurance": "A2",
  "budget_tokens": 24000,
  "irreversible": false,
  "shared_writes": false,
  "regulated": false
}
```

Eventos, en orden de emisión:

| `event:` | `data:` | Cuándo |
|---|---|---|
| `decision` | `{ plan }` | **Primero, antes de ejecutar nada.** Es lo que la escalera dibuja. |
| `probe` | `{ unit, result, provenance }` | Si la sonda corrió. `provenance` es la jerarquía real. |
| `paradigm.step` | `{ label }` | Progreso del paradigma elegido. |
| `token` | `{ text }` | Fragmento de respuesta. |
| `citation` | `{ unit, page, chunk }` | Cita verificada contra el índice vivo. |
| `usage` | `{ tokens, probes, ms }` | Consumo real, sondas incluidas. |
| `done` \| `gated` \| `deferred` | `{ plan }` | Terminal. Exactamente uno. |

La forma de `plan` está en `src/types.ts`. Lo esencial: `feasibility` y `assuranceStage`
son listas de `{ paradigm, reason }` donde `reason: null` significa que sobrevivió —
**el motivo del rechazo es parte del contrato**, no un detalle de log.

Dos reglas que el backend tiene que respetar:

1. `gated` **no** puede venir acompañado de `token`, `usage` ni `probe`. Si algo se
   ejecutó, no era un gate.
2. En A3, no emitir `token` hasta que las citas verifiquen. Streamear antes contradice
   "citado-o-callado" (`../lab/ARQUITECTURA.es.md` §6.1).

---

## Estructura

```
src/
  types.ts              vocabulario compartido con lab/app/
  store.ts              zustand: workspaces, ingesta, contexto, intercambios
  lib/feasibility.ts    espejo local de la poda aritmética (VISTA PREVIA)
  lib/transport.ts      SSE contra el motor + generador de trazas demo
  lib/tokens.ts         estimador barato y formateo
  components/           TopBar · WorkspacePanel · ContextTray · Composer · ExchangeView
  styles/tokens.css     la paleta y las tres semánticas de color
```

`lib/feasibility.ts` es una **vista previa**, no la autoridad: el veredicto que vale es
el del evento `decision`. La interfaz lo dice al pie del panel para que nadie confunda
una estimación con una decisión.

Los multiplicadores de costo ahí adentro son **priors, no mediciones**. Los números
reales están en `../lab/results/`.

---

## Decisiones técnicas

- **Vite + React 19 + TypeScript.** Sin Next: no hay SSR que ganar, y agregaría un
  servidor entre la consola y el motor que no queremos.
- **Zustand.** El estado es real —workspaces × documentos × máquina de ingesta ×
  selección × streaming— y Context volvería a renderizar todo con cada token.
  *Cuidado*: un selector que construye un array nuevo en cada llamada le devuelve a
  `useSyncExternalStore` un snapshot distinto siempre, y eso es un render infinito. Por
  eso las derivaciones de `store.ts` son funciones puras que se usan dentro de un
  `useMemo` sobre las referencias crudas.
- **dnd-kit** en vez del drag-and-drop nativo, que no es operable con teclado.
- **CSS Modules**, sin Tailwind. El diseño es un sistema de tokens con tres colores
  semánticos; la sopa de utilidades los enterraría.
- **Sin librería de fetching.** `fetch` + `ReadableStream` alcanzan para SSE.

### Piso de calidad

Responsive hasta 1000px (los tres paneles se apilan), foco de teclado visible en todo lo
interactivo, `prefers-reduced-motion` respetado, y las barras de ingesta son
`role="progressbar"` con sus valores. Doble clic en una unidad la manda al contexto sin
arrastrar.

---

## Pendiente

- Las tipografías se cargan desde Google Fonts. Para on-prem hay que self-hostearlas: es
  la única dependencia de red que queda fuera del motor.
- No hay router. Con más de dos workspaces conviene que el activo viva en la URL.
- El botón **Ver EXPLAIN** de un gate no abre nada todavía. Necesita `/v1/replay`.
- La ingesta en modo `motor` no está cableada: hoy siempre simula. Falta
  `POST /v1/workspaces/{id}/documents` y un canal de progreso.
