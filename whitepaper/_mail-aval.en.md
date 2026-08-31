# Follow-up del pedido de aval

Es un **segundo** mail: nada de presentarse otra vez ni de volver a reconocer su trabajo — eso ya
se dijo. La razón para volver a escribir es que el paper está terminado y va adjunto.

Huecos: `{NOMBRE}`, `{SECCIÓN}`. **Asunto: `Re:` sobre el hilo del primer mail**, no uno nuevo.

**Dos cosas que este mail corrige del primero, sin señalarlas.**

El primero decía «~18,000 empirical **run traces**», y el error estaba en la unidad más que en la
magnitud: **corridas** hay 3.797 y **llamadas al modelo** 14.025 en lo que el paper reporta
—8.886 de campaña principal, 3.639 de held-out, 1.500 de la segunda familia—. Contando todo
`results/`, con corridas archivadas de un corpus y un analizador superados que el paper excluye
por diseño, las llamadas son 37.142. Acá va el número con su unidad y su denominador.

Y decía «using Policy-as-Code (OPA)» en presente, cuando §6 declara que nada corre sobre OPA:
acá OPA no se menciona.

---

Dear {NOMBRE},

Following up on my earlier note — the paper is finished, and I am attaching the pre-publication version.

What it establishes: putting the control plane in code and leaving the LLM as a typed sensor is implementable, and its effect is measurable. Absorbing four branch points takes one paradigm from **0.33 to 0.89** on the hardest cell and makes its replicates agree; otherwise **17–34%** of cells return a different answer at temperature zero with the same prompt and seed. And agreement between paradigms turns out to be a verifier with no oracle and no judge: full precision from four matches over **180 of 180** cells, replicated on a second model family against a criterion registered before the run. Measured with no LLM judge: 936 cells and **8,886 model calls** over 121M tokens in the main campaign (78 tasks × 12 paradigms × 3 replicates), plus a held-out world generated and verified independently and a replication on a second model family — **14,025 model calls** in total.

Given where your work sits, **{SECCIÓN}** is probably the part closest to what you are building, and it may be directly useful to it.

The one result that fits in a picture is below. Figure 1 of the paper, on page 2, is the whole decision path on one page — including the rejection branch and the feedback loop.

[ figuras/consenso-para-mail.png ]

I would be glad to have your review, or simply your opinion, at whatever length suits you.

Thank you,

**Ariel Edgardo Levy** — Independent Researcher · ORCID 0009-0007-5426-9864

---

## Qué sección pedirle a quién

| si su línea es | pedile | porque |
|---|---|---|
| andamiajes estructurados, DSPy, optimización de programas | **§5.3** | contradice el supuesto sobre el que se construyen los ruteadores |
| verificación, autoconsistencia, jueces LLM | **§5.4** | un verificador sin oráculo ni juez, replicado en otra familia |
| evaluación y reproducibilidad de agentes | **§5.2** | `pass^k`: una corrección barata a cómo se reportan los bancos |
| razonamiento simbólico, creencias, procedencia | **§4.1** | el aparato formal, donde una lectura externa más rinde |
| gobernanza, cumplimiento, IA de alto riesgo | **§1.1** | la instrucción contra la restricción, y su alcance declarado |

## El gráfico

`figuras/consenso-para-mail.png` — 1581×758, 86 KB, generado por
`lab/bench/analysis/_figura_consenso.py`. **PNG y no SVG**: ningún cliente de correo renderiza
SVG inline. Es la única figura del registro que se entiende sin leyenda ni contexto, y por eso
es la única que puede ir suelta.

**La curva baja de `0,424` a `0,389` entre `k=0` y `k=1`, y eso está a propósito.** `k=1`
significa que un solo brazo coincidió con otro, o sea desacuerdo en la práctica. Sacarlo seria
elegir los puntos que convienen; que esté es lo que hace creible el `1,000` del final.

Si el mail va sin imagen, borrar esa línea y dejar sólo el puntero a la Figura 1 del adjunto.

## Antes de mandar

- **Revisar el camino de cross-list primero, porque puede eliminar el pedido.** Enviar como
  primario al archivo donde ya hay habilitación y pedir cross-list a `cs.LG` no exige aval del
  secundario: lo deciden los moderadores. Hay alias —`cs.IT` ↔ `math.IT`, `math.ST` ↔ `stat.TH`—.
  **Confirmar en la página de política de arXiv**, no de memoria.
- **El aval es por archivo en las dos direcciones.** Quien publica en `cs.CL` no puede avalar
  `cs.LG`; y un paper en `math.XX` no habilita `cs.LG`. Revisar el archivo de cada destinatario
  antes de escribirle.
- **Adjuntar los dos PDF, no ofrecerlos.** Quien decide en diez minutos no pide un archivo.
- **DOI de Zenodo antes de la próxima ronda.** Convierte el mail en «acá está el preprint».
