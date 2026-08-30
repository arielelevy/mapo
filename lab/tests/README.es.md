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

## `test_science.py` — 52 chequeos, 524 aserciones

> El número sale de contar `ok = check_...(ok)` en `main()` y `[PASS]` en la corrida,
> no de acordarse. Decía «33 secciones» y hacía rato que no era cierto — un conteo a
> mano en un README es la primera cosa que se queda vieja.

Cubre la capa de medición y las guardas que impiden que dos experimentos se promedien.
Las que más se tocan:

| grupo | qué prueba |
|---|---|
| **álgebra** | brecha de oráculo, selección, cascada, riesgo-cobertura, grading exacto |
| **el registro** | que sea autodescriptivo: con qué modelo, qué brazo, qué tokenizador, qué vocabulario de región |
| **las cinco guardas de mezcla** (§42, §49, §64) | `load_rows` **levanta** si un archivo mezcla decodificaciones, brazos, analizadores léxicos, vocabularios de región o **versiones de superficie**. La del analizador es la única que ningún otro campo puede detectar; la de superficie es la única que es **por brazo**, porque el cambio que la motiva toca a dos de los doce |
| **el dial** (§27, §47) | que imponga lo que declara, y que `max(pedido, piso, aprendido)` sea la única composición donde cada fuente sólo endurece |
| **soundness** (§46) | el teorema del ensamblador: si `fill` emite, toda ranura viene de una creencia vigente con procedencia ≥ piso |
| **la plata** (§41, §52, §53) | que sea una unidad y no un número; un cliente por modelo; los aranceles son datos |
| **el catálogo** (§39, §58, §59) | que los 15 paradigmas corran de punta a punta sin gastar, y que **ningún factor quede inalcanzable** |
| **el camino hasta el prompt** (§60–§64) | la familia de defectos que ninguna otra guarda ve: algo que se lee, se ejecuta, tiene test que pasa — y **no llega a donde tenía que llegar**. §60 que lo que no es medición no entre al aprendizaje y que un fracaso ejecutado **sí**; §61 que el board lleve lo que falta y llegue a **cualquier** agente, no sólo a `dag`; §62 que el guard acote por crecimiento y **rescate** lo que expulsa; §63 que el agotamiento del retriever sea de la **tarea** y no del sub-agente; §64 la quinta guarda de mezcla, **por brazo** y no por archivo |

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
