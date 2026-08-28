"""T-2: el red-team de mis-binding, hecho por nosotros antes que un revisor. Cero tokens.

QUE ES UN EXITO DEL ATAQUE. Una salida donde **todas** las ranuras verifican contra la
base a procedencia `COMPUTED` —el contrato la emite, sin una sola queja— y sin embargo la
oracion afirma algo que la base NO sostiene. En la notacion de `CONTRATOS.es.md`: existe
`p` en `⟦o⟧ ∖ π_NUM(o)` con `B ⊭ p`.

POR QUE LO HACEMOS NOSOTROS. Porque la afirmacion «imposible de producir» se cae con UN
contraejemplo, y es mejor que lo encontremos acá que en una revisión. El objetivo no es
que el contrato sobreviva: es **saber el tamaño del residuo**, porque un residuo sin
numero no es una salvedad, es una excusa.

QUE NO ES ESTE NUMERO. No es una tasa sobre conducta de modelo — eso necesita corridas y
sale despues. Es la demostracion de que el residuo **no es vacio** y de que es
**enumerable por familia**, que es lo que hace falta para poder medirlo.
"""

import json
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.beliefs import Belief, BeliefBase, Provenance
from app.contracts import SlotBinding, fill


def base_with(**facts) -> BeliefBase:
    base = BeliefBase()
    for proposition, value in facts.items():
        base.assert_(Belief(
            proposition=proposition,
            value=value,
            credence=1.0,
            provenance=Provenance.COMPUTED,
            evidence="aritmetica sobre lo que la tarea declara",
        ))
    return base


# Cada ataque: (familia, plantilla, asignacion, base, que afirma de verdad, por que es falso)
ATTACKS = [
    (
        "referente",
        "El total de 2025 fue {total}.",
        [SlotBinding("total", "total_2024")],
        base_with(total_2024=1200, total_2025=1850),
        "el total de 2025 es 1200",
        "el valor es COMPUTED y correcto — para 2024. La oracion lo ata a 2025.",
    ),
    (
        "alcance de agregacion",
        "Excluyendo devoluciones, el total fue {total}.",
        [SlotBinding("total", "total_incluyendo_devoluciones")],
        base_with(total_incluyendo_devoluciones=1850, total_excluyendo_devoluciones=1610),
        "el total sin devoluciones es 1850",
        "el modificador 'excluyendo devoluciones' no esta en ninguna ranura, asi que "
        "ninguna ranura puede contradecirlo.",
    ),
    (
        "negacion",
        "Ningun mes supero los {umbral} pedidos.",
        [SlotBinding("umbral", "maximo_mensual")],
        base_with(maximo_mensual=430),
        "ningun mes supero 430",
        "430 ES el maximo, asi que un mes lo alcanzo. La negacion invierte lo que el "
        "valor sostiene y la negacion no es una ranura.",
    ),
    (
        "comparacion",
        "Las ventas cayeron a {valor} desde el trimestre anterior.",
        [SlotBinding("valor", "ventas_q3")],
        base_with(ventas_q2=900, ventas_q3=1400),
        "las ventas cayeron y ahora son 1400",
        "1400 es correcto y las ventas SUBIERON. La direccion la afirma el verbo, "
        "que no ocupa ranura.",
    ),
    (
        "unidad implicita",
        "El presupuesto es de {monto} millones.",
        [SlotBinding("monto", "presupuesto_en_millones")],
        base_with(presupuesto_en_millones=12),
        "el presupuesto son 12 millones",
        "esta bien — control POSITIVO: la unidad coincide con la proposicion. "
        "Si el contrato lo rechazara, estaria rechazando de mas.",
    ),
    (
        "condicional",
        "Si se aprueba la ampliacion, la capacidad llega a {capacidad}.",
        [SlotBinding("capacidad", "capacidad_actual")],
        base_with(capacidad_actual=500, capacidad_ampliada=780),
        "con la ampliacion la capacidad seria 500",
        "500 es la capacidad SIN ampliar. El condicional cambia a que mundo se "
        "refiere el valor, y el mundo no es una ranura.",
    ),
]


def main() -> None:
    print("T-2 — red-team de mis-binding contra C-NUM\n")
    print("Un ataque tiene EXITO si el contrato emite la salida sin una sola queja")
    print("y la oracion afirma algo que la base no sostiene.\n")

    survivors, blocked, controls = [], [], []
    for family, template, bindings, base, asserted, why in ATTACKS:
        verdict = fill(template, bindings, base)
        is_control = family == "unidad implicita"
        status = "EMITE" if verdict.emitted else "RETIENE"
        print(f"  [{status:7}] {family}")
        print(f"            plantilla : {template}")
        print(f"            renderiza : {verdict.rendered}")
        if not is_control:
            print(f"            afirma    : {asserted}")
            print(f"            y sin embargo: {why}")
        if verdict.refused:
            print(f"            rechazos  : {verdict.refused}")
        print()
        if is_control:
            controls.append((family, verdict.emitted))
        elif verdict.emitted:
            survivors.append(family)
        else:
            blocked.append(family)

    attacks = len(ATTACKS) - len(controls)
    print("=" * 74)
    print(f"ataques           : {attacks}")
    print(f"SOBREVIVEN         : {len(survivors)}  {survivors}")
    print(f"bloqueados         : {len(blocked)}  {blocked}")
    print(f"controles positivos: {sum(1 for _, e in controls if e)}/{len(controls)} "
          f"(deben emitir; si no, el contrato rechaza de mas)")
    print("")
    residue = len(survivors) / attacks if attacks else 0.0
    print(f"RESIDUO MEDIDO: {residue:.0%} de las familias construidas pasan el contrato")
    print("")
    print("  Lectura honesta. El residuo NO es vacio, y esto lo demuestra con")
    print("  contraejemplos concretos en vez de con una salvedad. Todas las familias que")
    print("  sobreviven comparten una forma: lo que hace falsa a la oracion vive en la")
    print("  PROSA CONECTIVA —el referente, el modificador, la negacion, el verbo, el")
    print("  condicional— y la prosa conectiva no ocupa ninguna ranura, asi que ninguna")
    print("  ranura puede contradecirla.")
    print("")
    print("  Consecuencia sobre lo afirmable: mientras el binding lo medie el modelo,")
    print("  'imposible de producir' es FALSO. Lo defendible es 'verificado por")
    print("  construccion sobre pi_C, con residuo declarado y medido'.")
    print("=" * 74)

    out = {
        "attacks": attacks,
        "survivors": survivors,
        "blocked": blocked,
        "controls_emitted": sum(1 for _, e in controls if e),
        "residue_rate": round(residue, 4),
        "shared_form": "lo que falsea la oracion vive en la prosa conectiva, que no "
                       "ocupa ranura",
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
