.PHONY: dev down test

dev:
	docker compose up --build

down:
	docker compose down

test:
	cd server && go test ./...
	cd ai && python -m pytest
