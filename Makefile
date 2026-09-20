.PHONY: install test pipeline serve

install:
	pip install -e ".[dev]"

test:
	pytest -q

pipeline:
	python -m pulse pipeline --offline

serve:
	python -m pulse serve
