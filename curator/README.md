# Curator v2

Personalized cyber/AI news + CVE feed. Fetches items from RSS/Atom feeds, embeds them,
dedupes near-duplicate stories, ranks per-member against interest profiles, and serves a
web UI with semantic search over the corpus.

## Pipeline

1. **Fetch** (`fetch.py`) - stdlib RSS/Atom parser over a seeded feed list (HN, Ars, Krebs,
   The Verge). Edit `FEEDS` to change sources.
2. **Index** (`curator_index.py`) - embeds each item's title+summary with Ollama
   `nomic-embed-text`, stores in a Chroma collection `curator` with metadata
   (source, url, published, title). Dedupe: skips items whose embedding cosine-similarity
   to an existing item is > 0.95 (near-duplicate stories from different outlets).
3. **Rank** (`curator_rank.py`) - each member has an interest profile (a sentence). The
   profile is embedded, all items ranked by cosine similarity, top-20 re-ranked with a
   cross-encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`, reused from `~/rag/rerank.py`)
   into a sharper top-10.
4. **Serve** (`curator_app.py`) - Flask UI + JSON endpoints.

## Endpoints

- `GET /` - dark technical UI: member selector, personalized ranked cards
  (title, source, published, relevance score, one-line summary), and a live search box.
- `GET /feed?member=X` - that member's personalized ranked top-10 as JSON.
  `X` is a profile key (`sec-eng`, `founder`).
- `GET /search?q=...` - semantic search over the corpus, top-10 matches as JSON.

## Run

```bash
python3 curator_index.py     # build/update the corpus (fetch, embed, dedupe)
python3 curator_app.py       # start the web app
# open http://localhost:5050
```

Requires Ollama running locally (`nomic-embed-text` pulled) and a populated `curator`
Chroma collection. The app loads the corpus, cross-encoder, and profiles once at startup,
so re-run `curator_index.py` then restart the app to pick up new items or profile changes.

## Observability

All operations (index runs, feed requests, searches) append JSON lines to
`logs/curator.jsonl`.

## Notes

- Cross-encoder scores are ms-marco logits: ordering is meaningful, absolute values are not
  bounded to positive. Top matches lead the tail clearly; treat scores as relative rank.
- Dedupe is O(new x existing) per run; fine at this scale. For a large corpus, query
  Chroma's ANN for the nearest neighbor instead of scanning all embeddings.
