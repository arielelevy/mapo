# `bench/` — el banco de medición

**Esto no es el producto.** El producto es la capa de decisión en `app/`; esto es lo que la
mide. La regla que evita que se vuelvan a mezclar: **el banco importa al producto, y el
producto no sabe que el banco existe.** Estaba escrita en `CLAUDE.md` y no se veía en el
árbol — 72 scripts sueltos en la raíz de `lab/`, al lado de `app/`.

| | | |
|---|---:|---|
| `analysis/` | 27 | interrogan el registro ya pagado. **Cero llamadas al modelo** |
| `runs/` | 22 | gastan cuota. Cada uno declara su estimación antes de correr |
| `audits/` | 9 | barridos sobre el código y sobre el cruce código × corpus |
| `oneoff/` | 13 | migraciones y arreglos que ya corrieron. Arqueología, no herramientas |
| `_sanity.py` | | cotas que un número derivado tiene que pasar **antes** de reportarse |

---

## Cómo se corren

**Desde `lab/`, siempre:**

```
cd lab
py bench/analysis/_analyze_money.py
py bench/audits/_audit_inerte.py
```

Las rutas de datos (`results/nano`, `corpus/…`) son **relativas al CWD** y quedaron así a
propósito. Cada script lleva un prólogo de tres líneas que resuelve los **imports** —eso es
lo que se rompe al salir de la raíz— y nada más. Reescribir setenta archivos de rutas de
datos arriesgaba romper en silencio a cambio de nada hoy, y el silencio es justo lo que este
repo no acepta.

---

## Los dos barridos, que buscan la misma falla por caminos distintos

Aparecen juntos porque la segunda vez que cometí la falla, el primer barrido **no podía
verla**.

**`_audit_declarado.py` — léxico.** Nombres que se definen y cuyo único uso es su propia
serialización o un `print`. Encontró `REGION_VOCABULARY`, que llevaba escrito al lado *«un θ
ajustado bajo un vocabulario nunca debe consumir regiones de otro»* y **nada lo estampaba**.

**`_audit_inerte.py` — de ejecución.** Guardas cuyo disparador **no lo satisface ningún
corpus del repo**. El barrido léxico no las ve porque el nombre **sí** se lee y **sí**
gobierna: lo que falta es el *dato* que hace verdadera la condición, y eso es una propiedad
del cruce entre el código y los corpus.

> Encontró cuatro de siete disparadores que **nunca dispararon** — uno de ellos una
> precondición que yo había cerrado como hecha el mismo día.

La lista de los dos **no es un veredicto**. Cada caso se decide leyendo: un campo que sólo
se serializa puede estar bien, y una guarda para un corpus que todavía no existe es
legítima. Lo que no puede pasar es que sea una **sorpresa**.

---

## Antes de gastar un token

```
py tests/test_science.py           # completo
py tests/test_consolidation.py     # completo
py corpus/verify.py --corpus corpus/<nombre>
```

Más: predicciones falsables **registradas con fecha en `README.md` antes de correr**,
`repeat >= 3`, piso de ruido **por celda**, decisiones sobre la brecha **neta**.

**Y estimar contra el corpus, nunca contra el registro.** Un archivo de resultados **no
declara si está completo**: estimé una corrida en 362k tokens leyendo un `.jsonl` de 90
filas que cubría 6 de 32 tareas, y gastó **12,2 millones** — 34× de error. La aritmética
correcta es `len(tasks.json) × brazos × repeat`, cuesta lo mismo, y no se puede equivocar
así.

---

## Dónde vive cada cosa

```
lab/
  app/        el PRODUCTO — capa de decisión y paradigmas
  bench/      esto
  corpus/     generación y verificación del mundo
  tests/      test_science.py, test_consolidation.py
  results/    MEDICIÓN — evidencia de lo que se corrió        (fuera de git)
  state/      ESTADO — lo que el sistema aprendió             (fuera de git)
  cache/      completions content-addressed                   (fuera de git)
```

`results/` y `state/` son **dos árboles y no se mezclan**: un `rglob("*.jsonl")` sobre
resultados levantaba el ledger de creencias como si fueran filas medidas. La distinción es
de **vida útil** — una medición sin su ledger sigue siendo una medición; el ledger se
reconstruye entero volviendo a consolidar. Los tres están fuera de git por tamaño, no por
importancia: la integridad del ledger la sostiene su **cadena de hashes**
(`store.verify_chain`), no el control de versiones.
