# Makefile (root)
.PHONY: install api ui up clean

install:
	poetry install

api:
	poetry run uvicorn services.api.main:app --host 0.0.0.0 --port 8090 --reload

ui:
	poetry run streamlit run services/ui/app.py --server.port 8502 --server.address 0.0.0.0

up:
	make -j2 api ui

clean:
	rm -rf __pycache__ **/__pycache__ .pytest_cache .mypy_cache
