# mapo-ui — consola de prueba

Interfaz para ejercitar el motor: workspaces con corpus, ingesta asincrónica, contexto
curado por request, y la decisión a la vista **antes** que la respuesta.

**Estado: sólo el modo demo funciona.** El modo `motor` apunta a una API **propuesta**
(`../lab/ARQUITECTURA.es.md` §6) que el motor no tiene: hoy no hay streaming en ninguna
parte y `POST /answer` recibe los textos de los documentos, no ids de unidades. Ver
[Los tres desajustes](#los-tres-desajustes-en-orden-de-tamaño). El modo `demo` genera
localmente los mismos eventos tipados, así que la interfaz se trabaja sin gastar un
token y sin depender de que esa API exista.

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

### El replay es ejercitable, no un cartel

Cada veredicto imprime su digest de θ y el de su plan. Hacé clic ahí y se abre el
**EXPLAIN**: las entradas fijadas, la sonda si corrió, y un botón que **rederiva el plan
y compara digests**. Sin red, sin modelo.

La garantía que se verifica es la que el producto promete y ninguna otra: *misma base de
creencias ⟹ misma decisión*. Nunca *mismo prompt ⟹ misma respuesta* — el texto puede
variar y no integra la garantía.

Al pie, el EXPLAIN lista **lo que todavía le falta** para un replay integral
(`DISENO.es.md` §4.7): el vector y la región completos, factibilidad estructurada,
digest de reglas y perfiles, identidad de contenido, historia pre/post sonda, certificado
de promoción. Esa lista no es un TODO decorativo: es la diferencia entre explicar una
decisión y poder reconstruirla, y esconderla convertiría una propuesta en una capacidad.

### Aprobar un gate no borra el gate

*Aprobar y ejecutar* corre el paradigma que el plan ya había elegido — **no reabre la
decisión**, porque el plan estaba tomado y firmado antes de que apareciera el humano. Y
el terminal sigue siendo `gated` después de aprobar: el registro tiene que mostrar los
dos hechos, que hubo gate **y** que alguien lo autorizó. Ninguno reemplaza al otro.

### La ingesta muestra el veredicto del sensor

Antes de parsear se mide la cobertura de la capa de texto, y **eso** decide OCR. El
resultado queda escrito en cada documento (`capa de texto sana · 1347 chars/pág → sin
OCR`). Es una creencia `COMPUTED`, no una heurística escondida en una rama.

Los seis pasos son los de `../lab/ARQUITECTURA.es.md` §3: `en cola → sensor → parseo →
chunks → embeddings → indexado`. Cada documento avanza por su cuenta: subir cinco no
serializa nada.

---

## El contrato con el motor

> **Este contrato es una propuesta, no la API del motor.** Sale de
> `../lab/ARQUITECTURA.es.md` §6, que está rotulado PROPUESTA. Hoy el motor **no tiene
> streaming en ninguna parte** y su API no se parece a esto. Lo de abajo es lo que la
> consola necesita que exista; lo de la sección siguiente es lo que existe.

La consola consume **SSE tipado**, no un chorro de tokens. El backend tendría que emitir
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

### Lo que el motor tiene hoy

De `../lab/app/main.py`. Ninguno de estos endpoints streamea, y ninguno lleva prefijo
`/v1`:

| Endpoint real | Forma |
|---|---|
| `POST /answer` | Síncrono, devuelve JSON. Toma **`documents: dict[str, str]`**, `budget_tokens`, `irreversible`, `shared_writes`, `regulated`, `oracle`, `assurance`, `probe`. |
| `POST /decide` | Decide sin ejecutar, pero pide `corpus` + `task_id`: tiene forma de banco, no de producto. |
| `GET /health` · `GET /corpus/{name}` · `POST /run` · `GET /report/{corpus}` · `GET /policy` · `POST /policy/promote` | Banco y política. |

### Los tres desajustes, en orden de tamaño

**1. La consola manda `unit_ids`; el motor toma `documents`.** El real recibe los textos
completos del caller. Mandar ids presupone que hay un índice y que hay workspaces.

Actualizado 2026-08-29: **la ingesta ya existe como etapa** (`app/ingest.py`), con su gasto
en columna propia y la regla que impone —ningún paradigma construye estado derivado adentro
de un request—. Lo que sigue faltando es lo otro: **el índice y los workspaces**. Así que el
hueco se achicó y no se cerró, y no se cierra renombrando un campo.

**2. El streaming existe en el motor y no sale por HTTP.** Actualizado 2026-08-29:
`_answer_stream` (`serve.py:280`) **sí** emite los eventos tipados con `yield`, y
`Event.as_sse()` (`events.py:84`) los serializa. Lo que falta es el endpoint: `answer`
(`serve.py:168`) es `def`, no `async def`, y consume el generador entero para devolver un
dict.

O sea, la escalera que se dibuja por etapas ya tiene quién la produzca; le falta el caño.
Es `E-3` en `lab/PRODUCTO.es.md`, y viene con una guarda que ya está escrita en
`ARQUITECTURA.es.md`: **A3 buffea la respuesta hasta verificar las citas**, así que un
`token` no puede salir antes de que el contrato lo permita. Contra el motor de hoy, el modo
`motor` de esta consola sigue fallando.

**3. La consola no manda `oracle` ni `probe`.** `oracle` no es decorativo: su presencia
es lo que hace **admisible una cascada** —escalar ante un fallo observado necesita un
detector de fallo barato—. Omitirlo cambia calladamente qué puede elegir el motor.
`probe` decide si se paga una llamada de sonda, y quien la paga debería ser quien la pide.

### Endpoints que la consola necesitaría, y no existen

| Endpoint | Para qué |
|---|---|
| `POST /v1/answer` (SSE) | Decidir y ejecutar con la decisión emitida primero. |
| `POST /v1/replay` | Rederivar un plan **en el motor** y devolver su digest. |
| `POST /v1/workspaces/{id}/documents` | Ingesta real. |
| `GET /v1/workspaces/{id}/ingest` (SSE) | Progreso por documento. |

El más importante es `/v1/replay`: mientras no exista, el botón de rederivar prueba que
**la derivación** es determinista, no que el motor reproduzca. Son dos afirmaciones
distintas y sólo una está verificada.

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
                        ExplainDrawer (el certificado) · ErrorBoundary · Blank
  styles/tokens.css     la paleta y las tres semánticas de color
```

`lib/feasibility.ts` es una **vista previa**, no la autoridad: el veredicto que vale es
el del evento `decision`. La interfaz lo dice al pie del panel para que nadie confunda
una estimación con una decisión.

Los multiplicadores de costo ahí adentro son **priors, no mediciones**. Los números
reales están en `../lab/results/`.

> **Obligación de sincronía.** `lib/feasibility.ts` tiene un espejo del `CATALOG` de
> `../lab/app/paradigms/__init__.py`, con el mismo `Status` tipado
> (`active` / `retired` / `standby` / `infeasible` / `under_review`). Cuando se mueve un
> brazo allá, se mueve acá. Ya driftearon una vez: la consola tachaba `gist_reader` como
> "falsificado" cuando el catálogo lo tiene ACTIVE y único mejor en 9 celdas, y trataba
> `plan_execute` como candidato vivo después de que se retirara.
>
> El espejo existe **sólo para que el modo demo no mienta**. En modo `motor` los estados
> tienen que venir en el evento `decision`, y esa es la salida definitiva a este
> problema: la consola no debería tener opinión propia sobre el catálogo.
>
> Y las diferencias de estado importan, no son sinónimos de "no corre": `standby` tiene
> condiciones escritas para revivir, `retired` es una decisión con su motivo, e
> `infeasible` **no se bloquea acá** — lo poda la aritmética de costo y queda registrado,
> porque la infactibilidad ES el resultado.

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
arrastrar; `Escape` cierra el EXPLAIN.

**La escalera es accesible.** Es el contenido principal, y la tachadura que la hace
legible es puramente visual: un lector de pantalla oía el nombre y el motivo sin saber
que el motivo **era** un rechazo. Cada fila lleva `aria-label` con la lectura completa
—*"map_reduce, excluido: cardinalidad"*— y las etapas llevan roles de tabla.

**El scroll no le pelea al usuario.** Mientras algo streamea, el panel sigue el final:
antes los tokens llegaban abajo del fold y no se veían. Pero si scrolleaste para arriba a
leer una decisión anterior, deja de seguirte hasta que volvés al final. Una pregunta nueva
arranca arriba, porque lo primero que hay que ver es la decisión, no la respuesta.

**Un error de render no se lleva puesta la sesión.** `ErrorBoundary` envuelve el stream:
un evento con una forma que `types.ts` no espera deja un cartel con el mensaje y un botón
para reintentar, en vez de una pantalla en blanco cuyo único rastro está en la consola del
navegador — justo donde no vas a mirar mientras probás el motor.

---

## Pendiente

- Las tipografías se cargan desde Google Fonts. Para on-prem hay que self-hostearlas: es
  la única dependencia de red que queda fuera del motor.
- No hay router. Con más de dos workspaces conviene que el activo viva en la URL.
- La ingesta en modo `motor` no está cableada: hoy siempre simula. Falta
  `POST /v1/workspaces/{id}/documents` y un canal de progreso.
- **El replay rederiva con el `buildPlan` local**, que es el mismo que genera las trazas
  demo. Eso prueba que la derivación es determinista, no que el motor reproduzca: para
  eso hace falta `POST /v1/replay` y comparar contra el plan que devuelve el motor. Lo
  que hay hoy es la mitad honesta del claim.
- Nada persiste. Recargar pierde workspaces, unidades e intercambios.
