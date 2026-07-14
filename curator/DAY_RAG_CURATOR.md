# RAG Re-ranking and Curator v2

Two builds today: a cross-encoder re-ranking stage for the NIST RAG corpus in the morning,
and Curator v2 (personalized news ranking) in the afternoon. Both run against local models.

## Morning: cross-encoder re-ranking

`rerank.py` retrieves the top-20 chunks by vector similarity, reorders them with the
`cross-encoder/ms-marco-MiniLM-L-6-v2` cross-encoder, and returns the top-5.

Query: "What are the main categories of adversarial attacks on AI systems?" (NIST.AI.100-2e2023).
The top-5 pages before and after:

| Rank | Pure vector (page) | Re-ranked (page) |
|------|--------------------|------------------|
| 1 | 13 | 8 |
| 2 | 42 | 13 |
| 3 | 3  | 14 |
| 4 | 9  | 3  |
| 5 | 0  | 18 |

Re-ranking pulled the taxonomy page (p14) into the top-5, which pure vector missed, and
moved the executive summary (p8) to #1.

Latency:

| Stage | ms |
|-------|-----|
| Retrieval | 1821 |
| Re-rank | 2272 |
| Total | 4093 |

The cross-encoder ran on CPU. It sharpened relevance ordering at about 2x the latency of
retrieval alone.

## Afternoon: Curator v2

Four scripts, each reusing the one before it.

**`curator_index.py`** fetches cyber/AI news, embeds each item's title and summary with
`nomic-embed-text`, and stores the vectors in a Chroma collection with source, url, published,
and title metadata. Near-duplicate stories get skipped at cosine similarity above 0.95. Two
index runs today:

| Run | Fetched | Added | Deduped | Collection size |
|-----|---------|-------|---------|-----------------|
| 1 | 50 | 50 | 0 | 50 |
| 2 | 50 | 3  | 0 | 53 |

The second run skipped 47 items already indexed by URL. Zero near-duplicates surfaced in
either batch, so I checked the dedupe path directly with a paraphrased headline pair: it
fired at 0.967, and an unrelated pair scored 0.336 and stayed.

**`curator_rank.py`** ranks the collection for a given member. It embeds the member's interest
profile to a vector, ranks all items by cosine similarity, then re-ranks the top-20 with the
same cross-encoder down to a top-10.

The calibration tradeoff, stated straight: keyword-list profiles gave 3/10 feed overlap
between the two members but negative cross-encoder logits. Sentence profiles gave saner
separation from the tail and moved the top item well clear (founder top1 -9.1 to -2.95), at
the cost of more overlap (6/10). ms-marco emits raw logits, not 0-1 scores, so negative
values are expected here rather than a bug. Rank order is what carries the signal.

**`curator_app.py`** serves the whole thing from Flask on port 5050:

| Endpoint | Returns |
|----------|---------|
| `GET /` | Dark technical UI: member selector, ranked cards, search box |
| `GET /feed?member=X` | That member's personalized top-10 as JSON |
| `GET /search?q=...` | Semantic search over the corpus, top-10 as JSON |

Every index run, feed request, and search appends a JSON line to `logs/curator.jsonl`.

## Quality gate

All seven items pass: end-to-end, personalization, dedupe, observability, documentation,
re-ranking, calibration. The done-when condition holds: retrieval runs through a local model
and is wired into Curator.
