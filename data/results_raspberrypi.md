# bench results: raspberrypi

- host: `raspberrypi`
- os/arch: `Linux aarch64`
- total ram: `15.8 GB`
- ctx: `8192`

| model | prompt_tag | temp | decode_tps | prefill_tps | ttft_ms | mem_mb | ctx | status |
|---|---|---|---|---|---|---|---|---|
| llama3.2:3b | short | 0.0 | 5.68 | 22.57 | 1918.1 | 3072.0 | 8192 | ok |
| llama3.2:3b | medium | 0.0 | 5.53 | 13.92 | 5642.0 | 3072.0 | 8192 | ok |
| llama3.2:3b | long | 0.0 | 3.32 | 6.98 | 205606.3 | 3072.0 | 8192 | ok |
| llama3.2:3b | summarize | 0.0 | 5.09 | 11.79 | 12018.9 | 3072.0 | 8192 | ok |
| qwen2.5:7b | short | 0.0 | 2.6 | 11.11 | 3865.5 | 4915.2 | 8192 | ok |
| qwen2.5:7b | medium | 0.0 | 2.47 | 6.46 | 12329.6 | 4915.2 | 8192 | ok |
| qwen2.5:7b | long | 0.0 | 2.01 | 4.03 | 356598.2 | 4915.2 | 8192 | ok |
| qwen2.5:7b | summarize | 0.0 | 2.48 | 5.35 | 26977.8 | 4915.2 | 8192 | ok |

## stats per model (status=ok only)

- `llama3.2:3b`: decode 4.91 tps, prefill 13.81 tps, ttft 56296.32 ms, mem 3072.0 mb
- `qwen2.5:7b`: decode 2.39 tps, prefill 6.74 tps, ttft 99942.78 ms, mem 4915.2 mb
