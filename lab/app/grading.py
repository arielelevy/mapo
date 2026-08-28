"""Correccion del banco: F1 exacto contra el gold, sin juez.

Es la cara del BANCO sobre el primitivo de acuerdo, que vive en `verify.py` porque el
producto tambien lo necesita —para la cascada— y el producto no puede importar al banco.
Reexportar en vez de duplicar es deliberado: dos copias de una puntuacion no fallan cuando
se separan, siguen dando numeros, solo que distintos.

La ausencia de juez LLM es requisito de diseno, no comodidad. El efecto bajo estudio son
unos pocos puntos porcentuales; el ruido de un juez en ese orden seria indistinguible del
efecto, que es exactamente lo que vuelve infalsificables las mejoras chicas que reporta
esta literatura.
"""

from .verify import normalise, score, split_items

__all__ = ["normalise", "score", "split_items"]
