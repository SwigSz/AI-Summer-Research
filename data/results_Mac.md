# bench results: Mac

- host: `Mac`
- os/arch: `macOS arm64 (M5 Max)`
- total ram: `128 GB`
- ctx: `8192`

| model | prompt_tag | temp | decode_tps | prefill_tps | ttft_ms | mem_mb | ctx | status |
|---|---|---|---|---|---|---|---|---|
| llama3.2:3b | short | 0.0 | 192.23 | 743.11 | 159.2 | 3174.4 | 8192 | ok |
| llama3.2:3b | medium | 0.0 | 188.58 | 1614.8 | 147.2 | 3174.4 | 8192 | ok |
| llama3.2:3b | long | 0.0 | 180.83 | 4967.38 | 391.5 | 3174.4 | 8192 | ok |
| llama3.2:3b | summarize | 0.0 | 189.36 | 2922.61 | 158.4 | 3174.4 | 8192 | ok |
| qwen2.5:7b | short | 0.0 | 106.28 | 618.15 | 155.5 | 5222.4 | 8192 | ok |
| qwen2.5:7b | medium | 0.0 | 103.67 | 1331.47 | 139.7 | 5222.4 | 8192 | ok |
| qwen2.5:7b | long | 0.0 | 101.42 | 2416.2 | 678.3 | 5222.4 | 8192 | ok |
| qwen2.5:7b | summarize | 0.0 | 103.63 | 2179.98 | 152.5 | 5222.4 | 8192 | ok |

## stats per model (status=ok only)

- `llama3.2:3b`: decode 187.75 tps, prefill 2561.97 tps, ttft 214.07 ms, mem 3174.4 mb
- `qwen2.5:7b`: decode 103.75 tps, prefill 1636.45 tps, ttft 281.50 ms, mem 5222.4 mb
