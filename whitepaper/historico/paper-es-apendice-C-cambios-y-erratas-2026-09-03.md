# Apéndice C del paper largo, movido a histórico el 2026-09-03

Sale del cuerpo con el recorte del 2026-09-03. Se conserva entero porque un lector del borrador
anterior necesita la historia; un lector nuevo no.

# Apéndice C, Diferencias con los borradores anteriores

Qué cambió en v2. El título y la máquina son los mismos. Cambia qué se pone como
columna vertebral: el banco deja de leerse como torneo entre paradigmas y pasa a leerse
como fuente de episodios para un sistema que aprende. Lo que se aprende es qué exige un
request, qué puede hacer cada brazo, y qué predice su comportamiento. Los resultados negativos del borrador anterior siguen todos, con sus
números, pero reubicados como lo que fueron: los episodios que repararon el vocabulario
del sistema (§6.5).

Qué cambió en la revisión doctoral del 2026-09-01 (plan en `paper-es_PLAN.md`). El modelo
de cada medición está declarado (§5.4, §6.5.1): la campaña corre con `gpt-5.6-luna`, los
tres episodios de §6.5 con `gpt-5.4-nano`, y la celda de cadenas acopladas de §6.1.3 y
§6.1.4 con `gpt-5.6-terra`. Las dos tablas del plantel se reconciliaron contra el registro.
La agencia de la contribución 3 se corrigió: el ciclo lo ejecutaron personas dirigidas por
refutaciones preregistradas, y el sistema consume lo que el ciclo produjo. Entraron la
Proposición 5 (clave de la política), las definiciones de capacidad (§6.3.2), el régimen
de los episodios, el impacto amplio (§7.3) y la literatura que faltaba.

Y lo que cambió tras la segunda ronda de revisión, el mismo día, con dos revisores
externos de contexto limpio (`paper-es_REVIEW-A-2026-09-01.md` y `-B-`). El piso de ruido
de §6.2.3 y §6.2.6 se computaba con el bootstrap del propio estadístico, que por
construcción da piso igual o mayor que la brecha; se reemplazó por el estimador que el
texto siempre describió, pseudo-brazos del mismo paradigma emparejados por número de
brazos y por varianza, más el intervalo pareado de la brecha, con un test en la suite que
lo verifica sobre un sintético de premio conocido. Con eso el veredicto del held-out cambia
de signo: la brecha de oráculo es positiva y neta, y lo que no existe es una política que la
capture. Todos los paneles pasan al único rectángulo mecánico del registro, 64 × 8; la
inestabilidad se redefine como réplicas realmente distintas y baja a 12 a 28%; la
identidad aditiva entra como baseline y gana a las capacidades; la tabla de política 41 × 7
se retira por no tener script que la reproduzca; P30 se actualiza al registro re-puntuado.
Script de todos los recómputos: `lab/bench/analysis/_recomputo_revision.py`.

Y tras la revisión de narrativa del mismo día: «aprender» queda definido en §1.1 como
maduración auditable y no como optimización; §3.5 declara qué es fijo y qué es plástico y por
qué; §6.6 mide la trayectoria de θ sobre la campaña y muestra el artefacto que un auditor
lee. El título se mantiene: policy-as-code nombra el patrón que se usa.

Y el borrador 3.1 del 2026-09-02 reordena sin cambiar un número: el motor pasa adelante de la teoría y abre con un request real (§3.0); la teoría queda en lo que el argumento usa (§4) y lo auxiliar va al Apéndice B; el método se dice una vez (§5); los resultados siguen el orden del argumento (§6); el trabajo relacionado que el cuerpo sólo cita va al Apéndice D. Las definiciones, proposiciones, algoritmos y figuras se renumeran por orden de aparición. El mismo día el catálogo de capacidades pasa de diez a doce: `CONTEXT_VISION` (cada llamada ve el hilo entero, crudo o compactado; la tienen `direct`, `react`, `reflection` y `dag_strategy`) y `AUTOCOMPACTA` (el arnés reduce el hilo de forma determinista; implementada, sin brazo en la campaña). El leave-one-arm-out se recomputó: MAE de capacidades 0,233 → 0,229, `p` exacto 0,080 → 0,066; la identidad aditiva sigue ganando por 0,004.

## C.1 Erratas respecto del borrador 2.0

Lo que el borrador del 2026-08-31 decía y esta versión no, con el motivo. Va en un apéndice y
no en el cuerpo porque un lector nuevo no necesita la historia para entender el resultado, y un
lector del borrador anterior la necesita entera. Las cuatro correcciones con contenido
científico (el estimador de piso, el empate en el Teorema 1, la definición de inestable y la cota
del ratchet) quedan además dichas en el cuerpo, en positivo.

| dónde | decía | dice ahora | por qué |
|---|---|---|---|
| §6.2.3, §6.2.6 | brecha neta negativa en muestra (−0,008) y en los tres estratos del held-out (−0,028 a −0,034) | entre contendientes apenas se separa del piso; sobre ocho brazos y held-out es positiva y neta | el piso era el bootstrap del propio estadístico, con media igual o mayor que la brecha por construcción; test §60 |
| §6.1.2, resumen | 17 a 34% de celdas inestables | al menos 12 a 28% | «inestable» se definía como `0 < media < 1`, que cuenta réplicas idénticas y parciales |
| §6.1.3, §6.1.4, resumen, §1.1, §9 | 0,33 a 0,89 y «12 correctas, 3 abstenciones, cero equivocadas» como campaña | los mismos números declarados como `terra` sobre nueve celdas, con los de `luna` al lado, y la corrección declarada como desarrollada sobre esas celdas | eran de otro modelo y el texto afirmaba que ninguna estadística mezclaba modelos |
| §6.1.2, §6.2 | panel de 59 tareas × 8 brazos «con criterio mecánico» | rectángulo de 64 × 8 | el 59 excluía cinco tareas a mano sin declararlo |
| §6.3.3, resumen, §9 | «las capacidades superan a la identidad incluso cuando ésta ve la respuesta» | la identidad aditiva (tarea más brazo) da 0,225 contra 0,233 de capacidades (0,229 con el catálogo de doce) | la comparación era contra una identidad sin término de tarea |
| §6.4.1, §6.5.4, resumen | política sobre 41 × 7 con 0,951 y 46% de ahorro; señal con 42% a −0,017 sobre un panel de 59 tareas con cinco exclusiones a mano, y 69% a +0,008 sobre uno más chico | `_plasticidad.py` sobre el rectángulo: 68% a −0,063 con la clave completa, 31% a −0,104 con la computada; la señal da 58% a +0,000 | la tabla 41 × 7 no la produce ningún script del repositorio; los 42% eran sobre el panel de 59 |
| §6.3.5, resumen | «la ontología separa 40% más por segmento» (`1,74` por eje contra `1,84` la región, sobre 46 tareas) | ontología por eje: `S/R` 2,53 con cinco segmentos contra nulo p95 1,46; región 2,59 con trece contra 2,12 | la tabla venía de 46 tareas, sin script y con un control lineal ad hoc; ahora nulo por permutación |
| §6.3.4 | `p = 0,065` con 400 barajadas | `p` exacto sobre 40.320 permutaciones (0,080 con diez capacidades; 0,066 con las doce del catálogo vigente) | se podía computar exacto |
| §6.4.3, resumen | «el paradigma determina el recall seis veces más que la tarea»; brecha 4,2× | R² ajustado: paradigma 60%, región 0,8%, tarea 0; brecha 2,5× la distancia mejor-peor | R² crudo con 21 grupos contra 5; el 4,2× comparaba contra la desviación de un brazo respecto de la media |
| §6.4.3 | utilidad 0,540 con y sin herramienta | 0,822 y 0,825, con 7 de 63 celdas que cambian | veredicto anterior al re-puntuado del 2026-08-30 |
| §6.5.5, resumen | «cada refutación produjo un sensor `COMPUTED`»; «el ciclo que repara su propio vocabulario» | un LLM, una corrección de valuación y un corpus; el vocabulario lo repararon personas, y §3.5 declara la frontera | dos de tres episodios no produjeron LLMs; la plasticidad medida es la de las tablas (§6.6) |
| §6.5.3 | sin el neto de P17 | −0,146 a λ = 0, −1,04 a λ = 0,05 | estaba en el registro y no en el paper |
| §6.4.2 | terra: 23 tareas, 374 filas, 209 celdas | 26 tareas, 350 filas, 200 celdas, curva completa | el registro creció y la predicción exigía la curva entera |
| §1.3, §5.4 | 78 × 12 × 3, 121,4M tokens | 2.511 filas, 123,3M tokens, nueve brazos sobre 67 tareas | conteo contra el registro |
| §5.2, §5.2.1 | dos tablas del plantel con números distintos | una, recomputada contra el registro | snapshots distintos |
| §6.2.1 | α 41%, β 10%, γ 48%, S/R 5,30 | α 45/50%, β 9/11%, γ 45/39%, S/R 3,02 | ddof = 1 y ruido descontado en las tres componentes, sobre 64 × 8 |
| §2.5, referencias | HADD como «la base de la que §3.4 toma sus invariantes», con EVR como mecanismo | antecedente de vocabulario; EVR no disponible en Zenodo | verificado el 2026-09-01 |
| §5.1.1 | «59,4% de los fallos eran defectos del arnés», sin fuente | auditoría de OpenAI sobre SWE-bench Verified: 59,4% de 138 tareas con defectos en tests o enunciado | fuente encontrada; el denominador y el objeto eran otros |
| §8.1, §8.2 | párrafos sobre un corpus de 16k tokens, celdas «†» y P8 sin contexto | retirados o reescritos con contexto | texto heredado de un borrador anterior a la campaña |
| §3.4.2 | la cota del ratchet importaba un teorema sobre varianza bajo oscilación | Proposición 2: el daño total acotado por conteo, `≤ 2R` endurecimientos | una secuencia monótona y acotada tiene varianza que tiende a cero, así que la cota se cumplía vacuamente |
| §4.3.1 | `β` definida sobre el complemento de `S₊`, cobrando los empates como misruteo | `β` sobre `S₋`; los empates aportan cero a los dos lados | un ruteador que sólo rutea donde gana o empata registraba una tasa de misruteo alta sin daño, y el Corolario 2 usa `β` y `L` por separado |
| §6.2.6 | held-out medido sobre una corrida anterior al cambio de tokenizador, sin `analyzer`, huella ni vocabulario de región estampados | held-out re-corrido por el mismo camino de código de la campaña | la corrida anterior no era replayable |

---

---


Y el recorte del 2026-09-03: el paper largo pasa de unas 4.100 líneas a la mitad sin cambiar un
número. Lo que sale del cuerpo va al Apéndice D (§D.6 ruteo en RAG y cascadas, §D.7 jueces y
varianza) o a este archivo. §9.1 pasa de «lo que sigue» a apuestas registradas `P31` a `P36`, con
criterio numérico y lo que se retira si fallan. Las dos figuras de arquitectura se redibujaron
(`_figuras_arquitectura.py`); las anteriores están en `historico/` con sufijo `-v1-2026-09-03`.
