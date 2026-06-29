# AI Vision Service

Service A4 - AI Vision for Smart Campus Operations Platform.

## Purpose

- Receive `frame_url` from Camera Stream.
- Run YOLOv8n or fallback mock AI when needed.
- Return detection results with `confidence`, `risk_level`, and `detection_id`.
- Expose data that Core Business and Analytics can reuse.

## Main documents

- API contract: [API_CONTRACT.md](API_CONTRACT.md)
- A4 -> A5 contract: [A4_TO_A5_ANALYTICS_CONTRACT.md](A4_TO_A5_ANALYTICS_CONTRACT.md)
- OpenAPI: [openapi.yaml](openapi.yaml)
- Presentation notes: [PRESENTATION.md](PRESENTATION.md)
- Smoke test: [test_api.py](test_api.py)
- Postman collection: [postman/ai-vision.postman_collection.json](postman/ai-vision.postman_collection.json)
- Postman environment: [postman/ai-vision.postman_environment.json](postman/ai-vision.postman_environment.json)

## Main APIs

- `GET /health`
- `GET /model`
- `POST /api/v1/vision/detect`
- `GET /api/v1/vision/detections/{detection_id}`
- `POST /api/v1/events/camera`
- `POST /analyze`
- `POST /analyze/mock`

## Run locally

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

## Integration

- Camera Stream sends frame data to `POST /api/v1/vision/detect`.
- Core Business can use `POST /api/v1/events/camera`.
- Analytics can consume detection logs for statistics and dashboards.

## Notes

- The service prefers YOLOv8n.
- If the model is not available, it automatically falls back to mock AI so the demo still works.
