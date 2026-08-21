.PHONY: sync check fetch-fixture fetch-wmap fixture wmap

sync:
	uv sync --frozen

check:
	uv run python -m py_compile src/*.py scripts/check_artifacts.py
	uv run python scripts/check_artifacts.py

fetch-fixture:
	bun scripts/fetch-data.ts --group fixture

fetch-wmap:
	bun scripts/fetch-data.ts --group wmap

fixture:
	uv run python src/cmb_fixture_repro.py --output results/fixture-reproduction.json

wmap:
	uv run python src/wmap_pilot.py --null-simulations 128 --output results/wmap-pilot.json
