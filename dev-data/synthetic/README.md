# Synthetic test dataset

A committable, fake-location dataset that drives the full-pipeline CI test
(`back-end/tests/test_e2e_synthetic.py`). It is the only end-to-end coverage
test that runs in CI — the real prod golden (`test_prod_golden.py`) is
local-only (skip-if-absent), so this is CI's guard that the geometry/coverage
math does not silently change.

## What's here

| file                    | role                | techType |
| ----------------------- | ------------------- | -------- |
| `test_fabric.csv`       | 100k synthetic BSLs (Roanoke, VA footprint) | — |
| `fiber.geojson`         | wired fiber routes  | 50 |
| `wireless_5ghz.geojson` | wireless, unlicensed | 70 |
| `wireless_25ghz.geojson`| wireless, licensed  | 71 |

## How it's generated

`back-end/scripts/make_synthetic_dataset.py` takes **real** coverage/fiber
geometry from the prod extract (folder 13 inputs — the validated golden
filing) and applies a single shared affine transform (uniform scale +
translate) so it overlays the synthetic Roanoke fabric. One transform for all
layers preserves their spatial relationships; it also throws away the real
locations, so the transformed output is safe to commit. The raw wireless
polygons are then simplified to a ~30 m tolerance to keep the files lean and
under GDAL's per-feature GeoJSON size limit.

The real prod inputs live under `dev-data/real-do-not-commit/` and are **never**
committed. To regenerate (after re-dropping the prod extract):

```bash
cd back-end && uv run python scripts/make_synthetic_dataset.py
```

## Pinned served counts

`test_e2e_synthetic.py` pins the served-location counts the real pipeline
produces on this data (wired 96, wireless-70 10110, wireless-71 6273). If a
refactor changes those, the test breaks — which is the point. If you
intentionally regenerate the dataset, re-measure and update the pinned numbers.
