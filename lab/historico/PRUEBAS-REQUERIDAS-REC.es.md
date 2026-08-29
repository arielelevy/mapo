# Pruebas requeridas para REC — el plan, de cuando REC no existía

> **Archivado el 2026-08-29.** Esto vivía en `tests/README.es.md` y era un **plan**: la
> lista de lo que había que probar antes de poder decir que la Reparación Epistémica
> Contrafactual funcionaba, escrita cuando `rec.py` y `certify.py` **no existían**.
>
> Hoy existen, corren (`bench/runs/_run_rec.py`) y buena parte de esta lista está cubierta
> por `test_consolidation.py`. Dejarlo en el README de tests lo hacía leer como deuda
> abierta, y no lo es toda.
>
> **Se conserva porque dice qué se quiso probar**, y eso sigue siendo el criterio contra el
> cual se mide qué cobertura falta. Un plan cumplido a medias es más útil que un plan
> borrado: sin él no se sabe cuál mitad falta.
>
> Estado actual del ejecutable: `../DISENO.es.md`. Qué falta medir: `../PENDIENTES.es.md`.

---

## Diagnóstico

- contrafactuales que no cambian el plan no disparan sonda;
- el conjunto reportado es mínimo bajo el orden declarado;
- las hipótesis simuladas nunca aparecen en la base factual;
- la misma sesión reproduce diagnóstico y plan.

## Evidencia

- una clave literal entre unidades distintas gana `OBSERVED`;
- una clave inventada, ausente, autorreferente o fuera de scope no lo gana;
- una lectura negativa acotada no se transforma en negación global;
- hashes o versiones distintos invalidan replay;
- conflictos producen salida conservadora.

## Orquestación

- la región cambia después de evidencia aceptada;
- pre y post creencias permanecen en una única historia;
- sonda deshabilitada o agotada difiere y no ejecuta un placeholder;
- costo de sonda reduce presupuesto y entra en uso total;
- replay no invoca al modelo.

## Aprendizaje

- final no entra en entrenamiento ni selección;
- duplicar trials no aumenta el `n` de tareas;
- mundos relacionados no cruzan splits;
- una cláusula que no replica se rechaza;
- el incumbente queda byte a byte intacto ante rechazo;
- política y certificado deben corresponder exactamente.

## Frontera

- runtime no recibe gold, `cell`, `truth_*` ni `relevant_units`;
- un error de infraestructura se registra, se excluye y puede completarse después;
- siempre-`react` está presente en toda evaluación del claim principal.

## Orden de ejecución que se había planeado

1. Pruebas puras de creencias, región y diagnóstico.
2. Pruebas negativas de verificación.
3. Integración request-sonda-replan sin red.
4. Persistencia, tampering y certificados.
5. Suites científicas completas.
6. Verificación independiente del corpus.
7. Smoke pago.
8. Corrida preregistrada.

---

## Qué de esto pasó, al 2026-08-29

Lo que **sí** está, y dónde:

- **Aprendizaje** — casi entero en `test_consolidation.py`: el bloque final no entra al
  ajuste, un episodio es una celda y no un trial, el incumbente queda intacto ante rechazo,
  y editar una cláusula instalada invalida la firma del bundle.
- **Diagnóstico** — el orden de minimalidad es explícito y determinista en `rec.py`, y el
  esquema de intervenciones es cerrado y firmado: un solucionador que puede inventar la
  evidencia que le conviene siempre encuentra una reparación.
- **Certificación** — tres mundos con roles distintos, el final de un solo uso gastado
  ANTES de responder, y un segundo reclamo levanta `PermissionError`.

Lo que **no**, y es lo que hace que esta lista siga sirviendo:

- **la sonda sobre el corpus real** — es `S-5`, y depende de una corrida en A2 con la sonda
  encendida que nunca ocurrió;
- **frontera** — que runtime no reciba gold está parcialmente probado, pero `has_oracle`
  todavía se deriva de `bool(task["oracle"])` en dos sitios (paso 1 de `DISENO.es.md` §8);
- **evidencia** — los verificadores negativos están, la lectura negativa acotada no.
