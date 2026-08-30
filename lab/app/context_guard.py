"""El guard de contexto: acota la ventana por CRECIMIENTO y rescata lo que expulsa.

POR QUE EXISTE, Y ES LA MITAD QUE FALTABA. El banco tiene dos compactaciones y **ninguna
extrae nada**:

  `compact_history`  reemplaza por un stub SOLO las unidades que el modelo anoto — y el
                     modelo escribio 1 nota en 28 filas, asi que casi nunca dispara
  `manage_history`   degrada incondicionalmente a un stub con el id — medido: 61 llamadas
                     sobre `w4`, 0 mensajes degradados

Las dos DEGRADAN. Ninguna PRODUCE. Y esa diferencia es exactamente lo que le da al board
algo que sostener: sin extraccion, los hallazgos del board son lo que el modelo se acuerde
de postear, y postea 1 de cada 125 llamadas.

EL GUARD Y EL BOARD SON UN SOLO MECANISMO. El guard acota la ventana y genera el hallazgo;
el board lo conserva y con eso dirige lo que sigue. Medir uno sin el otro mide media
maquina, y por eso este modulo entra junto con `board_queue` y no despues.

TRES DECISIONES QUE NO SON DE ESTILO:

1. DISPARA POR CRECIMIENTO, NO POR TAMANO ABSOLUTO. Un umbral absoluto castiga a los
   paradigmas que leen mucho de entrada y no toca a los que crecen despacio hasta el
   mismo lugar. El crecimiento entre iteraciones es lo que distingue «esta juntando
   material» de «ya lo tenia».

2. EXPULSA DE A UNO. Vaciar la ventana de golpe le saca al modelo el batch sobre el que
   todavia no razono, y el sintoma —una respuesta peor— no se parece en nada a la causa.

3. LA EXTRACCION ES UNA LLAMADA AL MODELO Y SE COBRA. No es gratis y no se puede reportar
   como si lo fuera: su `Usage` se mergea igual que cualquier otra. Un mecanismo de
   ahorro que no cuenta lo que gasta no se puede evaluar.

QUE NO TOCA, y la lista es parte del contrato: el prompt de sistema, la pregunta, los
mensajes del board, y el batch corriente —el que sigue al ultimo mensaje del asistente con
tool calls—, que el modelo no vio todavia.
"""

from __future__ import annotations

from typing import Any

from .board import Blackboard
from .llm import LLMClient, Usage

# Crecimiento en caracteres dentro de UNA iteracion que dispara la expulsion. Heredado de
# la capa congelada, donde 20k caracteres era el escalon que separaba «leyo un fragmento»
# de «leyo un documento entero». Es un parametro del banco, no una constante de la
# naturaleza: si se lo mueve, se declara.
GROWTH_THRESHOLD_CHARS = 20_000

# NO HAY MARGEN DE RECENCIA APARTE, y sacarlo fue una correccion que encontro el test.
#
# La primera version protegia el batch corriente **y ademas** los ultimos 4 mensajes. Los
# dos criterios miden lo mismo con distinta precision, y el segundo es el peor: en un
# bucle corto —y los del banco lo son, `max_iterations` es chico— los ultimos 4 mensajes
# SON toda la conversacion, asi que el guard no encontraba nunca un candidato. Corria,
# no fallaba, y media cero: la forma exacta que este repo ya pago cuatro veces.
#
# La proteccion correcta es UNA y es principiada: el batch corriente es lo que el modelo
# **todavia no razono**, y sacarselo le quita evidencia que no llego a usar. Todo lo
# anterior ya fue razonado, asi que su texto crudo es redundante con lo que el modelo
# concluyo — que es exactamente la premisa de expulsar y dejar el hallazgo.

# El encabezado de la conversacion nunca se expulsa: sistema + pregunta. Se cuenta por
# TIPO y no por posicion — `range(3, ...)` supone una forma de prompt, y cambiar el prompt
# hace que la guarda se coma las instrucciones o deje de expulsar, callada.
PROTECTED_PREFIX = 2

EXTRACT_PROMPT = (
    "Extract ONLY the facts in the text below that bear on this question. "
    "Discard everything else — ids, codes, boilerplate — unless the question asks for "
    "them. Answer with the facts alone, no preamble, at most 400 characters. "
    "If nothing in the text bears on the question, answer exactly: NOTHING.\n\n"
    "QUESTION: {question}\n\nTEXT:\n{text}"
)


class ContextGuard:
    """ACOTA LA VENTANA POR CRECIMIENTO Y RESCATA LO QUE EXPULSA.

    Es la mitad que le faltaba al board. Las dos compactaciones que ya había **degradan**
    —`compact_history` a un stub y sólo para lo que el modelo anotó, `manage_history` a un
    gist incondicional— y ninguna **produce** contenido nuevo. Sin producción, el board
    sostiene sólo lo que el modelo se acuerde de postear, y postea 1 de cada 125 llamadas.

    TRES DECISIONES QUE NO SON DE ESTILO:

      **dispara por crecimiento, no por tamaño absoluto.** Un umbral absoluto castiga al
      que lee mucho de entrada y no toca al que crece despacio hasta el mismo lugar. El
      crecimiento entre iteraciones es lo que distingue «está juntando material» de «ya lo
      tenía»

      **expulsa de a uno**, y nunca toca el prompt, la pregunta, ni el batch corriente —lo
      que el modelo todavía no razonó—. Vaciar la ventana de golpe le saca evidencia que no
      llegó a usar, y el síntoma no se parece a la causa

      **la extracción es una llamada al modelo y SE COBRA.** Su `Usage` se mergea como
      cualquier otra: un mecanismo de ahorro que no cuenta lo que gasta no se puede evaluar

    CUATRO CONTADORES Y NO TRES, y la separación la encontró una prueba sobre el corpus:
    «el modelo no devolvió texto» y «el texto no aportaba nada a la pregunta» caían en el
    mismo casillero, y son opuestas —la segunda habla del RETRIEVER, la primera del
    extractor—. Y una extracción fallida **deja el texto donde estaba**: perder evidencia
    por una falla del extractor es el daño exacto que esto existe para evitar.
    """

    def __init__(self, threshold: int = GROWTH_THRESHOLD_CHARS) -> None:
        self.threshold = threshold
        self._last_size = 0
        self.evictions = 0
        self.extracted = 0
        self.nothing = 0
        # CUATRO NUMEROS Y NO TRES, y la separacion la encontro el probe sobre el corpus.
        # «el modelo no devolvio texto» y «el texto no aportaba nada a la pregunta» caian
        # en el mismo contador, y son cosas opuestas: la segunda es informacion sobre la
        # RECUPERACION —trajo 8k que no servian— y la primera es una falla de la
        # extraccion. Mezcladas, el numero que existe para hablar del retriever queda
        # contaminado por fallas del extractor, y nadie puede separarlas despues.
        self.failed = 0

    @staticmethod
    def _size(messages: list[dict[str, Any]]) -> int:
        return sum(len(str(m.get("content") or "")) for m in messages)

    def _current_batch_starts(self, messages: list[dict[str, Any]]) -> int:
        ultimo = 0
        for i, m in enumerate(messages):
            if m.get("role") == "assistant" and m.get("tool_calls"):
                ultimo = i
        return ultimo

    def needs_eviction(self, messages: list[dict[str, Any]]) -> bool:
        tamano = self._size(messages)
        crecio = tamano - self._last_size
        self._last_size = tamano
        return crecio > self.threshold

    def evict(
        self,
        messages: list[dict[str, Any]],
        board: Blackboard,
        client: LLMClient,
        question: str,
        usage: Usage,
    ) -> bool:
        """Expulsar el resultado de herramienta grande mas viejo, dejando su hallazgo.

        Devuelve si expulso. La extraccion se cobra: su `Usage` se mergea en `usage`.
        """
        limite = self._current_batch_starts(messages)
        candidatos = [
            i for i in range(PROTECTED_PREFIX, max(PROTECTED_PREFIX, limite))
            if messages[i].get("role") == "tool"
            and len(str(messages[i].get("content") or "")) > 1_000
            and not str(messages[i].get("content") or "").startswith("[gist")
        ]
        if not candidatos:
            return False
        i = candidatos[0]
        texto = str(messages[i].get("content") or "")

        completion = client.complete(
            messages=[{"role": "user",
                       "content": EXTRACT_PROMPT.format(question=question,
                                                        text=texto[:12_000])}],
        )
        usage.merge(completion.usage)
        hallazgo = (completion.text or "").strip()
        self.evictions += 1

        if not hallazgo:
            # LA EXTRACCION FALLO — no dijo NOTHING, no dijo nada. Y el texto NO se
            # descarta: expulsar sin haber rescatado seria perder evidencia por una falla
            # del extractor, que es exactamente el dano que este mecanismo existe para
            # evitar. Se deja el mensaje como estaba y se cuenta el fallo.
            self.failed += 1
            return True

        if hallazgo.upper().startswith("NOTHING"):
            # NO HABER ENCONTRADO NADA TAMBIEN SE REGISTRA. Un texto de 8k que no aporta
            # a la pregunta es informacion sobre la RECUPERACION, no sobre el modelo, y
            # borrarlo en silencio la pierde.
            self.nothing += 1
            messages[i] = {**messages[i],
                           "content": "[evicted: nothing relevant to the question]"}
            return True

        self.extracted += 1
        board.add_finding("evicted", hallazgo[:400])
        messages[i] = {**messages[i], "content": f"[evicted — finding on the board]"}
        return True

    def as_dict(self) -> dict[str, int]:
        return {"evictions": self.evictions, "extracted": self.extracted,
                "evicted_nothing": self.nothing, "extraction_failed": self.failed}
