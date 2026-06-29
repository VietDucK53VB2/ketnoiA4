# API Contract - A4 AI Vision Service

Tài liệu này mô tả hợp đồng API giữa nhóm A4 - AI Vision và các nhóm khác trong Smart Campus Operations Platform.

## 1. Vai trò service

- Provider: A4 - AI Vision
- Consumer chính: A2 - Camera Stream
- Consumer phụ: A6 - Core Business, A5 - Analytics

Service nhận ảnh/frame từ Camera Stream, chạy AI, rồi trả kết quả phát hiện để các nhóm khác dùng tiếp.

## 2. Base URL

Chạy local:

```text
http://127.0.0.1:8000
```

Chạy qua Radmin VPN:

```text
http://26.64.81.15:8000
```

## 3. Endpoint chính

### `POST /api/v1/vision/detect`

Dùng cho Camera Stream gọi trực tiếp vào AI Vision.

Request:

```json
{
  "camera_id": "cam-gate-01",
  "frame_url": "http://26.231.100.34:8080/frame.jpg",
  "timestamp": "2026-06-17T01:18:39"
}
```

Ý nghĩa field:

- `camera_id`: mã camera
- `frame_url`: link ảnh/frame mà Camera Stream expose
- `timestamp`: thời điểm frame được ghi nhận

Response 200:

```json
{
  "detection_id": "det-0ed98880e029",
  "camera_id": "cam-gate-01",
  "frame_url": "http://26.231.100.34:8080/frame.jpg",
  "timestamp": "2026-06-17T01:18:39",
  "anomaly_detected": true,
  "confidence_score": 0.87,
  "finding": {
    "finding_type": "object",
    "object_name": "bus",
    "risk_level": "medium",
    "description": "Detected object: bus"
  },
  "model_mode": "yolo",
  "notes": "YOLO model: yolov8n.pt"
}
```

### `GET /api/v1/vision/detections/{detection_id}`

Dùng để tra cứu lại kết quả đã xử lý bằng `detection_id`.

Response 200:

- Trả lại đúng `DetectionResult` đã lưu

Response 404:

```json
{
  "type": "about:blank",
  "title": "Detection Not Found",
  "status": 404,
  "detail": "Detection 'det-xxx' was not found.",
  "instance": "/api/v1/vision/detections/det-xxx"
}
```

## 4. Endpoint hỗ trợ

- `GET /health`
- `GET /model`
- `GET /`
- `POST /analyze`
- `POST /analyze/mock`
- `POST /api/v1/events/camera`
- Contract for A4 -> A5 analytics sync: [A4_TO_A5_ANALYTICS_CONTRACT.md](A4_TO_A5_ANALYTICS_CONTRACT.md)

Ghi chú:

- `POST /analyze` là endpoint tương thích ngược.
- `POST /api/v1/events/camera` là adapter để map sang format gần với A6 Core Business.

## 5. Quy ước dữ liệu

- `anomaly_detected`: boolean
- `confidence_score`: number hoặc `null`
- `finding`: object mô tả kết quả phát hiện
- `detection_id`: định danh duy nhất để tra cứu
- `model_mode`: `yolo` hoặc `mock-ai`

## 6. Lỗi chuẩn

### 422 Unprocessable Entity

Dùng khi link ảnh không hợp lệ, không tải được, hoặc không xử lý được.

```json
{
  "type": "about:blank",
  "title": "Unprocessable Image URL",
  "status": 422,
  "detail": "Cannot fetch frame_url: ...",
  "instance": null
}
```

### 404 Not Found

Dùng khi `detection_id` không tồn tại.

## 7. Luồng tích hợp

```text
Camera Stream -> POST /api/v1/vision/detect -> AI Vision
AI Vision -> JSON response -> Camera Stream / Core Business / Analytics
```

Nếu Core Business cần payload gần schema của họ hơn:

```text
Camera Stream -> POST /api/v1/vision/detect -> AI Vision -> POST /api/v1/events/camera -> Core Business
```

## 8. Thông tin triển khai

- Host: `26.64.81.15`
- Port: `8000`
- Dashboard: `http://26.64.81.15:8000/`
- Swagger/OpenAPI: `http://26.64.81.15:8000/openapi.json`

## 9. Ví dụ cURL

```bash
curl -X POST http://26.64.81.15:8000/api/v1/vision/detect \
  -H "Content-Type: application/json" \
  -d '{
    "camera_id": "cam-gate-01",
    "frame_url": "http://26.231.100.34:8080/frame.jpg",
    "timestamp": "2026-06-17T01:18:39"
  }'
```
