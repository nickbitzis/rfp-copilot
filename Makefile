PORT ?= 8822

.PHONY: install test lint eval gate run data screenshot docker clean

install:
	uv sync --python 3.12

test:
	uv run pytest -q

lint:
	uvx ruff check .

eval:  ## bm25-only vs hybrid, plus the sample questionnaires
	uv run rfpcopilot eval --compare

gate:  ## the CI gate: outdated-source usage at most 2%, abstention at least 80%, recall@5 at least 90%
	uv run rfpcopilot eval --gate --max-outdated 0.02 --min-abstention 0.8 --min-recall 0.9

run:  ## API and UI on http://127.0.0.1:$(PORT)
	uv run rfpcopilot serve --port $(PORT)

data:  ## regenerate the knowledge base, sample questionnaires, and eval set under data/
	uv run rfpcopilot gen --out data

screenshot:  ## needs make run in another terminal, and Google Chrome
	uv run python scripts/screenshot.py --port $(PORT)

docker:
	docker build -t rfp-copilot .
	docker run --rm -p $(PORT):8822 rfp-copilot

clean:
	rm -rf .pytest_cache .ruff_cache reports
