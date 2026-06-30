# bench results: spark-8040

- host: `spark-8040`
- os/arch: `Linux aarch64`
- total ram: `119.7 GB`
- ctx: `8192`

| model | prompt_tag | temp | decode_tps | prefill_tps | ttft_ms | mem_mb | ctx | status |
|---|---|---|---|---|---|---|---|---|
| llama3.2:3b | short | 0.0 | 93.27 | 2203.86 | 248.9 | 3174.4 | 8192 | ok |
| llama3.2:3b | medium | 0.0 | 92.84 | 3877.59 | 236.6 | 3174.4 | 8192 | ok |
| llama3.2:3b | long | 0.0 | 87.27 | 7175.03 | 439.2 | 3174.4 | 8192 | ok |
| llama3.2:3b | summarize | 0.0 | 93.62 | 5628.75 | 282.7 | 3174.4 | 8192 | ok |
| qwen2.5:7b | short | 0.0 | 46.4 | 1326.08 | 200.5 | 5222.4 | 8192 | ok |
| qwen2.5:7b | medium | 0.0 | 45.66 | 1999.85 | 218.5 | 5222.4 | 8192 | ok |
| qwen2.5:7b | long | 0.0 | 45.01 | 3427.83 | 597.5 | 5222.4 | 8192 | ok |
| qwen2.5:7b | summarize | 0.0 | 45.84 | 3016.5 | 253.6 | 5222.4 | 8192 | ok |

## stats per model (status=ok only)

- `llama3.2:3b`: decode 91.75 tps, prefill 4721.31 tps, ttft 301.85 ms, mem 3174.4 mb
- `qwen2.5:7b`: decode 45.73 tps, prefill 2442.57 tps, ttft 317.52 ms, mem 5222.4 mb
