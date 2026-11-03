# M1 spike: separation benchmark

Measures separation time, peak VRAM/RAM and a synthetic SDR sanity check for
the catalogue models on the local machine. Each configuration runs in its own
subprocess so out-of-memory errors are isolated. Results for the reference
machine are in `docs/data/benchmarks/`.

```bash
uv sync
uv run python bench.py --seconds 60 --only cuda
uv run python bench.py --seconds 30 --only cpu
```

The input is a deterministic synthetic multitrack (`synth.py`, CC0). Its SDR
only shows that separation runs; real models are trained on real music, so
quality must be judged on real recordings (listening test) and public
leaderboards. This spike is deleted before 1.0.
