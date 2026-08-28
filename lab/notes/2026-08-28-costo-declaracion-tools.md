# El costo de declarar tools — medido, y qué dice la literatura

**2026-08-28.** Consultado a pedido del autor. **Nada implementado**: esto es el estado del
arte más la medición local, para decidir después.

---

## CORRECCIÓN — la primera medición estaba mal

La primera versión de esta nota estimó el sobrecosto como `llamadas × tokens_de_spec`. Eso
supone que **toda** llamada al modelo lleva la declaración encima, y es falso: de **27
sitios** que llaman al modelo, **uno** pasa `tools` — el bucle compartido. Planificar, triar,
sintetizar y criticar llaman sin declaración.

El absurdo lo delató antes de que el número saliera de acá: en 7 celdas la estimación daba
**más declaración que prompt entero**, que es imposible.

Instrumentado `tooled_calls` en el único sitio que manda la declaración, la medición real:

| brazo | llamadas | **con tools** | tokens | declaración | **real** | estimado |
|---|---:|---:|---:|---:|---:|---:|
| `dag_strategy` | 158 | 103 | 683.959 | 54.384 | **8,0%** | 12,2% |
| `react` | 27 | 27 | 318.630 | 14.256 | **4,5%** | 4,5% |
| `rewoo` | 18 | **0** | 18.839 | 0 | **0,0%** | 50,4% |
| **total** | | | 1.021.428 | 68.640 | **6,7%** | 10,5% |

> **Y la dirección se invierte.** Dije que el brazo *más barato* cargaba el costo fijo más
> alto. Es al revés: `rewoo` **nunca usa el bucle de tools** y no carga nada; el que más
> carga es `dag_strategy`, que es el más caro. La distorsión de la comparación entre brazos
> es **mucho menor** de lo que dije, y va en el otro sentido.

`react` es el único donde la estimación coincidió exactamente, y por una razón: **todas** sus
llamadas pasan por el bucle.

---

## Lo medido acá (primera versión, sobreestimada — se conserva para que la corrección se vea)

Aritmética exacta: tamaño de las specs × llamadas registradas, sobre `gold_p17` en la
variante `basic`.

| variante | tools | tokens de declaración |
|---|---:|---:|
| `basic` / `managed` | 4 | ~528 |
| `accounting` | 6 | ~771 |
| `cognitive` | 10 | ~1.245 |

| brazo | llamadas | tokens gastados | declaración | **%** |
|---|---:|---:|---:|---:|
| `rewoo` | 156 | 189.899 | 82.368 | **43,4%** |
| `map_reduce` | 120 | 518.263 | 63.360 | 12,2% |
| `dag_strategy` | 1.171 | 7.004.423 | 618.288 | 8,8% |
| `react` | 244 | 2.780.534 | 128.832 | 4,6% |
| `gist_reader` | 156 | 2.192.501 | 82.368 | 3,8% |
| **total** | | **12.685.620** | **975.216** | **7,7%** |

> **Lo que importa no es el 7,7%: es el 10× de dispersión.** El brazo **más barato** es el
> que más carga el costo fijo. El barrido de λ —que decide qué paradigma conviene— compara
> brazos cuyo sobrecosto de declaración difiere por un orden de magnitud, y ese sobrecosto
> **no es una propiedad del paradigma**: es una propiedad de cuántas veces llama.

Es la misma forma que un sesgo ya conocido en este banco: una exposición proporcional a la
cantidad de llamadas castiga a los que más llaman. Sólo que acá castiga al revés — al que
**menos** llama, en proporción a lo poco que gasta.

---

## Lo que hay afuera, y por qué no aplica

El patrón de 2026 es **diferir las definiciones detrás de una tool de búsqueda**: el modelo
recibe una sola tool, busca la capacidad que necesita y el sistema carga esa definición.
Los números publicados son grandes — reducciones del 80-95% del costo de tools, y mejoras
de acierto en selección (49%→74% en un caso, 79,5%→88,1% en otro). Aparece en la plataforma
de Anthropic, en la API de OpenAI, y como práctica en clientes de MCP donde las definiciones
llegan a consumir 82K–134K tokens antes de leer el pedido del usuario.

**Y la misma literatura da el umbral: por debajo de ~10 tools el sobrecosto de la búsqueda
no se paga.** MAPO tiene **4** en `basic` y **10** en `cognitive`.

Además, el gateo por variante **ya es** divulgación progresiva: `basic` no ofrece las seis
de contabilidad, y esa decisión ahora vive en una función con un test que impide que lo
ofrecido y lo despachable se separen.

> La optimización de moda resuelve un problema que este banco no tiene. Aplicarla acá
> agregaría una llamada de búsqueda por request para ahorrar 528 tokens.

---

## Lo que sí queda por mirar

**El orden importa, y no es el orden en que se me ocurrieron.** El punto 3 va **primero**:
es el único que puede cambiar un resultado ya publicado. Si al descontar el sobrecosto
ningún veredicto de λ se mueve, los otros dos son optimización y no corrección — y eso
cambia cuánto urgen.

1. **Caché de prompt del proveedor.** `llm.py` no manda ninguna directiva de caché. El
   bloque de tools es **idéntico entre llamadas** dentro de una corrida — el caso ideal. Hay
   que **verificar** si el caché del endpoint cubre el campo `tools` y no sólo `messages`;
   si no lo cubre, esta vía no existe, y eso se dice en vez de suponerse.
2. **Acortar las descripciones**, como **factor** y no como limpieza: cambia el payload que
   el modelo lee, así que puede cambiar qué tool elige. Con predicción registrada y la
   guarda de siempre — si la utilidad baja más que el piso de ruido, ahorrar tokens
   eligiendo peor no es ahorrar.
3. **Descontar la declaración del costo comparado** — `X-4d`, y **va primero**. No
   necesita correr nada: el sobrecosto es `llamadas × tokens_de_spec` y las dos cantidades
   ya están en la fila. El costo por brazo se puede reportar con y sin su sobrecosto fijo,
   y eso solo endereza una comparación que hoy está torcida 10×. Es el único de la familia
   que puede **cambiar un veredicto ya publicado**; los otros dos son optimización.

---

## Fuentes

- [Introducing advanced tool use on the Claude Developer Platform](https://www.anthropic.com/engineering/advanced-tool-use)
- [Tool search — OpenAI API](https://developers.openai.com/api/docs/guides/tools-tool-search)
- [How Tool Search Defers Tools to Save Tokens](https://oldeucryptoboi.substack.com/p/tool-search-deep-dive)
- [What is MCP Tool Search? — context pollution guide](https://www.atcyrus.com/stories/mcp-tool-search-claude-code-context-pollution-guide)
- [How MCP Tool Definitions Inflate Your AI Agent Token Costs](https://docs.bswen.com/blog/2026-04-24-mcp-token-overhead/)
- [The Over-Tooled Agent Problem](https://tianpan.co/blog/2026-04-19-over-tooled-agent-problem)
- [Progressive Disclosure in AI Agents](https://www.mindstudio.ai/blog/progressive-disclosure-ai-agents-context-management)
- [ToolRegistry (arXiv 2507.10593)](https://arxiv.org/pdf/2507.10593)
