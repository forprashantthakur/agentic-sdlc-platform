.PHONY: up down logs seed test fmt
up:    ; cp -n .env.example .env || true; docker compose up --build
down:  ; docker compose down -v
logs:  ; docker compose logs -f backend
seed:  ; curl -s -XPOST localhost:8000/api/projects/seed | python3 -m json.tool
test:  ; cd backend && python -m pytest -q
