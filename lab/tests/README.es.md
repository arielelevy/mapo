# Pruebas y alcance de evidencia

Las suites actuales son scripts sin framework. Verifican identidades y mecanismos sobre
datos sintéticos; no sustituyen una evaluación held-out del producto.

## Suites actuales

| Suite | Qué cubre |
|---|---|
| `test_science.py` | Álgebra de brecha de oráculo, selección, cascada, grading, bundle, retries, throttle, sonda básica y request de producto. |
| `test_consolidation.py` | Particiones sintéticas, guarda contra ruido, replay, homeostasis, calibración, pisos de garantía y copy-on-write. |

## Lo que un PASS no demuestra

- que el motor supere al mejor fijo;
- que la sonda funcione sobre el corpus real;
- que theta generalice a mundos nuevos;
- que la promoción actual no tenga leakage;
- que una partición descubierta llegue al router;
- que la firma autentique al emisor;
- que A3 esté completamente sellado.

## Pruebas requeridas para REC

### Diagnóstico

- contrafactuales que no cambian el plan no disparan sonda;
- el conjunto reportado es mínimo bajo el orden declarado;
- las hipótesis simuladas nunca aparecen en la base factual;
- la misma sesión reproduce diagnóstico y plan.

### Evidencia

- una clave literal entre unidades distintas gana `OBSERVED`;
- una clave inventada, ausente, autorreferente o fuera de scope no lo gana;
- una lectura negativa acotada no se transforma en negación global;
- hashes o versiones distintos invalidan replay;
- conflictos producen salida conservadora.

### Orquestación

- la región cambia después de evidencia aceptada;
- pre y post creencias permanecen en una única historia;
- sonda deshabilitada o agotada difiere y no ejecuta un placeholder;
- costo de sonda reduce presupuesto y entra en uso total;
- replay no invoca al modelo.

### Aprendizaje

- final no entra en entrenamiento ni selección;
- duplicar trials no aumenta el `n` de tareas;
- mundos relacionados no cruzan splits;
- una cláusula que no replica se rechaza;
- el incumbente queda byte a byte intacto ante rechazo;
- política y certificado deben corresponder exactamente.

### Frontera

- runtime no recibe gold, `cell`, `truth_*` ni `relevant_units`;
- un error de infraestructura se registra, se excluye y puede completarse después;
- siempre-`react` está presente en toda evaluación del claim principal.

## Orden de ejecución futuro

1. Pruebas puras de creencias, región y diagnóstico.
2. Pruebas negativas de verificación.
3. Integración request-sonda-replan sin red.
4. Persistencia, tampering y certificados.
5. Suites científicas completas.
6. Verificación independiente del corpus.
7. Smoke pago.
8. Corrida preregistrada.
