# AI Vision Service - Smart Campus

This repository contains the A4 AI Vision service and the final report for the Smart Campus Operations Platform.

## What is included

- FastAPI service for camera-frame analysis.
- YOLOv8n inference with mock fallback.
- API contract and OpenAPI spec.
- Postman collection and smoke test.
- Final report in LaTeX under `report/`.

## Key files

- Service entry point: [app/main.py](app/main.py)
- AI engine: [app/vision.py](app/vision.py)
- API contract: [API_CONTRACT.md](API_CONTRACT.md)
- Analytics contract: [A4_TO_A5_ANALYTICS_CONTRACT.md](A4_TO_A5_ANALYTICS_CONTRACT.md)
- OpenAPI spec: [openapi.yaml](openapi.yaml)
- Presentation notes: [PRESENTATION.md](PRESENTATION.md)
- Smoke test: [test_api.py](test_api.py)
- Postman collection: [postman/ai-vision.postman_collection.json](postman/ai-vision.postman_collection.json)
- Postman environment: [postman/ai-vision.postman_environment.json](postman/ai-vision.postman_environment.json)
- Report source: [report/main.tex](report/main.tex)
- Report PDF: [report/main.pdf](report/main.pdf)

## Team

- Nguyễn Quang Đạt - `1771020145`
- Trịnh Việt Đức - `1771020167`
- Lê Quang Dũng - `1771020177`

## Run the service

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open:

- Dashboard: `http://127.0.0.1:8000/`
- Health: `http://127.0.0.1:8000/health`
- Model: `http://127.0.0.1:8000/model`

## Run with Docker

```bash
docker build -t ai-vision-service .
docker run -p 8000:8000 ai-vision-service
```

## Run with Docker Compose

```bash
docker compose up --build
```

## Smoke test

```bash
python test_api.py --base-url http://127.0.0.1:8000 --image-url https://www.ultralytics.com/images/bus.jpg
```

## View the report

- Open [report/main.pdf](report/main.pdf) for the current report PDF.
- Open [report/main.tex](report/main.tex) if you want to edit the report source.

## Notes

- The service prefers YOLOv8n.
- If the model is not available, it automatically falls back to mock AI so the demo still works.
