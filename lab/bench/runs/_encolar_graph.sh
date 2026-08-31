#!/usr/bin/env bash
# Espera a que la corrida de `w48` suelte el lock y recien ahi corre `graph_traverse`
# sobre `w4` y `w16`.
#
# POR QUE ENCOLAR Y NO LANZAR EN PARALELO. `fsio.exclusive` levanta excepcion si otro
# proceso tiene el `.jsonl`: dos corridas escriben las MISMAS celdas y `study()` promedia
# contando cada fila, asi que la celda duplicada pesa el doble y ninguna estadistica lo
# denuncia. El lock no es paranoia — es lo unico que impide un archivo perfectamente valido
# y silenciosamente mal ponderado.
#
# POR QUE HACE FALTA ESTA PASADA. Al arreglar `graph_traverse` (`GT-1`) se borraron sus 214
# filas de TODOS los anchos, y la corrida relanzada era `--anchos w48`. Asi que `w4` y `w16`
# quedaron en CERO filas del brazo, y el panel lo excluiria por cobertura — el mismo hueco
# que ya se pago con `rewoo`.
#
# Corre DESDE `lab/`:  nohup bash bench/runs/_encolar_graph.sh > results/_graph_w4w16.log 2>&1 &
set -u

LOCK="results/luna/.gold_h1_rows.jsonl.lock"

echo "esperando a que se libere $LOCK ..."
while [ -e "$LOCK" ]; do
  sleep 30
done
echo "lock liberado, arranca la pasada de graph_traverse sobre w4 y w16"
echo

exec py bench/runs/_run_homogenea.py \
  --patrones graph_traverse \
  --anchos w4,w16 \
  --modelo luna \
  --repeat 3 \
  --sin-chequeo
