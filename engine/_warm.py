"""Precalentar el cache de embeddings en serie, antes de soltar los workers.

LA CAUSA RAIZ DEL 429. El retriever semantico necesita cada documento embebido. Con
workers=4, los cuatro hilos disparan ese mismo trabajo a la vez sobre 72 documentos de 8k
tokens y el endpoint corta. Respetar Retry-After hace que la corrida sobreviva; calentar
en serie hace que el burst no exista. Las dos cosas hacen falta: la primera para cuando
alguien mas esta usando la cuota, la segunda para no ser ese alguien.
"""
import json, pathlib, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from app.config import Settings
from app.embeddings import EmbeddingClient

corpus = sys.argv[1]
docs = json.loads((pathlib.Path("corpus")/corpus/"documents.json").read_text(encoding="utf-8"))
s = Settings.from_env()
e = EmbeddingClient(s, s.embedding_deployment)
t0 = time.perf_counter(); hits = 0
for i, (uid, text) in enumerate(sorted(docs.items()), 1):
    before = len(e._memo)
    e.embed(text)
    if len(e._memo) == before: hits += 1
    if i % 25 == 0 or i == len(docs):
        print(f"  {i}/{len(docs)}  {time.perf_counter()-t0:.0f}s", flush=True)
print(f"{corpus}: {len(docs)} documentos, {hits} ya cacheados, {time.perf_counter()-t0:.0f}s")
