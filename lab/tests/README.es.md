# Pruebas y alcance de evidencia

Son **dos scripts sin framework**, y eso es a propósito: verifican identidades y mecanismos
sobre datos sintéticos, y **no sustituyen** una evaluación held-out del producto. Un `PASS`
acá no es un resultado científico — es la condición para que un resultado científico pueda
significar algo.

**Tienen que pasar completas antes de gastar un token.** No hace falta API key.

```powershell
py tests\test_science.py
py tests\test_consolidation.py
```

---

## `test_science.py` — 69 chequeos, 684 aserciones

> El número sale de contar `ok = check_...(ok)` en `main()` y `[PASS]` en la corrida completa,
> no de acordarse. Decía
> «33 secciones» y hacía rato que no era cierto — un conteo a mano en un README es la
> primera cosa que se queda vieja.

Cubre la capa de medición y las guardas que impiden que dos experimentos se promedien.
Las que más se tocan:

| grupo | qué prueba |
|---|---|
| **álgebra** | brecha de oráculo, selección, cascada, riesgo-cobertura, grading exacto |
| **el registro** | que sea autodescriptivo: con qué modelo, qué brazo, qué tokenizador, qué vocabulario de región |
| **las cinco guardas de mezcla** (§42, §49, §64) | `load_rows` **levanta** si un archivo mezcla decodificaciones, brazos, analizadores léxicos, vocabularios de región o **versiones de superficie**. La del analizador es la única que ningún otro campo puede detectar; la de superficie es la única que es **por brazo**, porque el cambio que la motiva toca a dos de los doce |
| **el dial** (§27, §47) | que imponga lo que declara, y que `max(pedido, piso, aprendido)` sea la composición punto a punto menos restrictiva entre las que ninguna fuente puede bajar |
| **confinamiento** (§47b) | sobre brazos reales del catálogo con dos sensores que responden distinto: los cinco de flujo fijado por código recorren los mismos nodos con salidas distintas, los tres que delegan la lectura divergen, `pointer_chase` conserva su trayectoria tras la intervención de §6.1.4 del paper, y una clave `COMPUTED` no reabre el canal hacia la política |
| **soundness** (§46) | el teorema del ensamblador: si `fill` emite, toda ranura viene de una creencia vigente con procedencia ≥ piso |
| **la plata** (§41, §52, §53) | que sea una unidad y no un número; un cliente por modelo; los aranceles son datos |
| **el catálogo** (§39, §58, §59) | que los 15 paradigmas corran de punta a punta sin gastar, y que **ningún factor quede inalcanzable** |
| **el camino hasta el prompt** (§60–§64) | la familia de defectos que ninguna otra guarda ve: algo que se lee, se ejecuta, tiene test que pasa — y **no llega a donde tenía que llegar**. §60 que lo que no es medición no entre al aprendizaje y que un fracaso ejecutado **sí**; §61 que el board lleve lo que falta y llegue a **cualquier** agente, no sólo a `dag`; §62 que el guard acote por crecimiento y **rescate** lo que expulsa; §63 que el agotamiento del retriever sea de la **tarea** y no del sub-agente; §64 la quinta guarda de mezcla, **por brazo** y no por archivo |

| **las herramientas, de a una** (§68–§70) | lo que faltaba: los tests probaban paradigmas de punta a punta y las auditorías miraban el registro, y **ninguno probaba una herramienta sola**. Por ahí se coló que `rewoo` llamara a `read` en 130 de 138 celdas y leyera **cero** unidades. §68 que un argumento de identificador reciba ids y no el JSON de la búsqueda, y que el recorte conserve el ranking; §69 que un patrón que planifica **a ciegas** vea toda la recuperación, porque es el que menos puede recuperarse de elegir mal; §70 cada herramienta por su **efecto** —que `read` deje la unidad leída, que un id inventado se **cuente**, que un nombre desconocido degrade y no mate la celda |

| **las guardas, desafiadas** (§71–§73) | tres defectos que sólo se ven poniendo las guardas una al lado de la otra. §71 que **medir un largo no sea leer** —cinco sitios llamaban a `read_one` para quedarse con `len(...)`, y `pointer_chase` figuraba abriendo el alcance entero en 170/170 celdas— más las **siete formas de fallar contadas por tipo**, cuando se contaba una; §72 que los **quince** brazos tengan techo nombrado, incluidos los que no tienen techo fijo (faltaban los del brazo más caro y los del fallback); §73 que el balance de esfuerzo se pueda **encender** — sus funciones existían, estaban probadas, y no las llamaba nadie |

| **los contratos, desafiados** (§74) | que un contrato **admita algo**. `C-ABSENCE` exigía leer el dominio entero para aceptar una ausencia, y en **9 de 9** tareas de `B2_absence` ese dominio cuesta más que el presupuesto de la tarea: el contrato no era estricto, era **vacío**. La solidez se prueba con contraejemplos; la **no vacuidad** hay que probarla aparte, y no estaba. Ahora hay una segunda ruta al mismo dominio —si la cadena negada no aparece en ninguna unidad, la cobertura es aritmética y no lectura— con su límite fijado: prueba que el **término** no está, no que la **cosa** no esté |

| **el grader, desafiado** (§75) | que se puntue **la respuesta y no su redaccion**. `D1` tenia por oraculo UNA forma de rechazar una premisa falsa y los **nueve** brazos la rechazaron bien con nueve redacciones distintas, sacando cero; `C9` pide emparejar cada individuo con su cuenta y el grader leia el emparejamiento como error. Eran **9 de 78 tareas dando cero sobre todo el plantel** — y esas nueve no bajaban un promedio, **salian del conjunto que discrimina**. Los dos creditos nuevos se auto-limitan: el rechazo se lee del oraculo, y el emparejamiento exige frontera de palabra y uno a uno |

| **los predictores, cableados** (§76) | que los dos ejes que la medicion eligio LLEGUEN a la region — `payload_for` -> extractor -> `features_for` -> `region()`, tres sitios donde un campo se cae sin que nada se ponga rojo. Y que `literal` **no sea un disparador lexico**: la misma pregunta cambia de valor si cambia el material, cosa que un lexico no puede hacer. Es la guarda de §59 aplicada a las features en vez de a las herramientas |

| **el ciclo epistemico** (§77) | que un plan que pide sonda sea un **diferimiento** y no se puntue como decision. `report()` no le pasaba `coupling` a `router.plan`, asi que la regla de sonda disparaba en **23 de 46 tareas** y se puntuaba el placeholder — y `report()` es lo que produce los numeros con los que se refuto P15. La causa no era que faltara sondear: la campana ya habia pagado derivar `coupling` y el metodo lo tiraba. Se valida por lo que NO cambio — en `CERTIFIED` los 23 diferimientos siguen, porque una estimacion `ELICITED` no sostiene un piso `OBSERVED` |

| **el ciclo epistemico, ampliado** (§78) | que un hueco que **nadie puede cerrar** no cuente como hueco. Un eje `DERIVED` sin establecer acota la confianza y empuja al fallback, asi que `horizon_unknown` —sin sensor, sin regla que lo lea, fuera de la region y **constante en las 3.884 filas** que lo llevan— hacia abstenerse al motor por nada. `FEATURE_SENSOR` declara quien puede establecer cada eje y `None` es una respuesta valida. Mas `literal_absent` como creencia `COMPUTED`: la pieza existia y no estaba en el vocabulario de proposiciones, o sea que ninguna regla podia razonar sobre ella |

> **§59 es la que más veces salvó una corrida.** Prueba que cada factor booleano viaja
> desde el runner hasta la declaración de tools. Sin ella, `offer_board=True` se habría
> corrido entero y medido cero, porque la tool nunca aparecía en la lista que el modelo ve.
> Tenían test sobre `specs_for` y ninguno sobre el **camino**, que es como un factor pasa de
> estar implementado a estar ejecutado.

## `test_consolidation.py` — el ciclo de sueño, y sobre todo que no confabule

**La etapa peligrosa es la abstracción.** Una búsqueda sobre muchas particiones candidatas
encuentra algo en ruido puro si se la deja, y una «verdad» descubierta que en realidad es un
artefacto de comparaciones múltiples **es peor que no descubrir nada**: llega vestida con la
autoridad de la evidencia.

Por eso la prueba central es la **negativa**: dado un registro donde la utilidad es
independiente de todo atributo, el ciclo **tiene que no reportar nada**.

| grupo | qué prueba |
|---|---|
| particiones y guarda contra ruido | la negativa de arriba |
| validez del aprendizaje | la candidata se ajusta **sin** el bloque final; un episodio es una celda `(tarea, paradigma)`, no un trial |
| pisos de garantía aprendidos | que aprendan de estadísticas de rechazo tipado, y que **nunca** lleguen a `CERTIFIED` |
| certificación de cláusulas | tres mundos disjuntos, mundo final de **un solo uso**, instalación fail-closed, y que editar una cláusula instalada **invalide la firma del bundle** |
| copy-on-write | que el incumbente quede byte a byte intacto cuando la guarda rechaza |

---

## Lo que un PASS **no** demuestra

Esta lista importa más que la de arriba.

- que el motor le gane al mejor paradigma fijo;
- que la sonda funcione sobre el corpus real;
- que θ generalice a mundos nuevos;
- que la promoción actual no tenga leakage estadístico;
- que una partición descubierta llegue efectivamente al router;
- que la firma autentique al **emisor** (autentica el contenido, que no es lo mismo);
- que `A3` esté completamente sellado.

Cada una de esas se contesta con una corrida, no con un test. Dónde está cada una:
[`../PENDIENTES.es.md`](../PENDIENTES.es.md).

---

## Y una prueba que no está acá, pero es del mismo tipo

**La corrida light** (`bench/runs/_run_homogenea_light.py`) es un test de integración que
cuesta tokens: ejercita el plantel entero contra los 7 factores y verifica que **cada factor
llegue al modelo**, comparando cada uno contra la base. Un factor desconectado no da error
—da exactamente la base—, así que ningún test unitario lo ve. Va después de estas dos
suites y antes de cualquier campaña.

> La lista de pruebas que este documento pedía **antes** de que REC existiera —diagnóstico,
> evidencia, orquestación, aprendizaje, frontera, y un «orden de ejecución futuro» de ocho
> pasos— se mudó a [`../historico/PRUEBAS-REQUERIDAS-REC.es.md`](../historico/PRUEBAS-REQUERIDAS-REC.es.md)
> el 2026-08-29. Era un plan escrito cuando `rec.py` y `certify.py` no existían; hoy
> existen, corren, y buena parte de esa lista está cubierta por `test_consolidation.py`.
> Se conserva porque dice **qué se quiso probar**, que sigue siendo el criterio contra el
> cual falta cobertura.
