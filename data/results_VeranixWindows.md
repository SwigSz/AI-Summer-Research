# bench results: VeranixWindows

- host: `VeranixWindows`
- os/arch: `Windows AMD64`
- total ram: `63.8 GB`
- ctx: `8192`

| model | prompt_tag | temp | decode_tps | prefill_tps | ttft_ms | mem_mb | ctx | status |
|---|---|---|---|---|---|---|---|---|
| llama3.2:3b | short | 0.0 | 87.06 | 135.61 | 3606.4 | 3174.4 | 8192 | ok |
| llama3.2:3b | medium | 0.0 | 84.65 | 562.69 | 3393.2 | 3174.4 | 8192 | ok |
| llama3.2:3b | long | 0.0 | 85.61 | 2681.37 | 3902.3 | 3174.4 | 8192 | ok |
| llama3.2:3b | summarize | 0.0 | 90.5 | 761.52 | 3568.7 | 3174.4 | 8192 | ok |
| qwen2.5:7b | short | 0.0 | 47.54 | 1121.67 | 3026.4 | 5120.0 | 8192 | ok |
| qwen2.5:7b | medium | 0.0 | 47.12 | 1659.61 | 3074.1 | 5120.0 | 8192 | ok |
| qwen2.5:7b | long | 0.0 | 45.54 | 1527.88 | 4045.6 | 5120.0 | 8192 | ok |
| qwen2.5:7b | summarize | 0.0 | 45.0 | 619.42 | 3367.7 | 5120.0 | 8192 | ok |

## stats per model (status=ok only)

- `llama3.2:3b`: decode 86.95 tps, prefill 1035.3 tps, ttft 3617.65 ms, mem 3174.4 mb
- `qwen2.5:7b`: decode 46.3 tps, prefill 1232.14 tps, ttft 3378.45 ms, mem 5120.0 mb
