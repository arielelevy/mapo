# Registro de investigación: Reparación Epistémica Contrafactual

**Fecha:** 2026-08-27  
**Estado:** diseño posterior a P15; no implementado; no constituye preregistro final.

## Observación que origina el patrón

P15 refutó el claim de producto sobre `gold_transfer`: router `0,52747`, mejor fijo
`0,61488`, delta `-0,08740`. La decisión fue reproducible 26/26, pero la región no podía
representar la propiedad que distinguía C5. El sistema explicó de forma estable una
decisión tomada con vocabulario insuficiente.

## Hipótesis de diseño

Una explicación determinista puede servir como entrada de aprendizaje si el sistema
calcula qué cambio mínimo en una creencia habría alterado el plan, y aprende a adquirir
esa evidencia antes de repetir la clase de error.

Nombre de trabajo: **Reparación Epistémica Contrafactual (REC)**.

## Contribución provisional

La contribución no puede ser “adquisición de información”, “policy repair”, “reglas
legibles”, “LLM como sensor” ni “certificación”: todas tienen vecinos directos.

La conjunción bajo estudio es:

> déficit mínimo de valor/credencia/procedencia derivado de una traza determinista,
> convertido offline en una cláusula acotada de adquisición y parada, con evidencia
> verificada por código y promoción certificada sobre particiones independientes.

## Vecinos encontrados en la búsqueda inicial

| Línea | Vecino | Riesgo para el claim |
|---|---|---|
| Environment probing | EnvProbe, 2606.31422 | Ya formula reparación de creencias como selección de sondas. |
| Política externa de adquisición | FABLE, 2608.00215 | Ya aprende decisiones de adquisición fuera del agente congelado. |
| KB ejecutable reparada | Kintsugi, 2605.09487 | Ya compila fallos en ediciones tipadas ejecutadas sin LLM. |
| Reglas auditables autoevolutivas | SHARP, 2605.06822 | Ya aprende cambios atómicos sobre reglas legibles. |
| Trazas a reglas | Trace2Policy, 2606.10457 | Ya compila reglas de control y reporta ejecución determinista. |
| Reparación por experiencia | Polaris, 2603.23129 | Ya produce parches persistentes y auditables. |
| Aceptación exógena | SEAL, 2607.24300 | Ya demuestra que el verificador no debe quedar bajo control del reparador. |
| Certificación fresca | CARA, 2607.29465 | Ya separa propuesta adaptativa de certificación de un solo uso. |
| Conceptos consultables | Interactive CBM, 2212.07430 | Ya adquiere conceptos por incertidumbre e influencia. |
| Certificados de política | Dann et al., 1811.03056 | El concepto general de policy certificate no es nuevo. |

## Consecuencia académica

La afirmación de novedad previa sobre consolidar una política de control debe revisarse
contra Kintsugi, SHARP y Trace2Policy antes de una nueva versión del paper. No se modifica
el paper durante esta fase porque la regla del proyecto exige ejecutar primero.

## Correcciones necesarias antes de construir REC

1. Separar gold y verificador de runtime.
2. Eliminar fuga del final en consolidación.
3. Aprender desde agregados por tarea, no trials.
4. Retirar el peso Hebbiano inerte del relato operativo.
5. Conservar la historia de creencias pre/post sonda.
6. Verificar evidencia con spans, scope, hashes y versión.
7. Recalcular región después de observar.
8. Integrar costo de sonda en presupuesto y utilidad.
9. Inyectar calibración por proposición.
10. Instalar solo artefactos acompañados por certificado.

## Documento de diseño

El diseño normativo, invariantes y protocolo experimental están en
[`../PATRON_REC.es.md`](../PATRON_REC.es.md).
