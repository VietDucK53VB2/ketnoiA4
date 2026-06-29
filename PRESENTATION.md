# A4 - AI Vision Service

Tài liệu này dùng để thuyết trình nhanh và đúng rubric.

## 1. Vai trò của nhóm

- Nhóm mình là **A4 - AI Vision**.
- Service của nhóm nhận **frame từ Camera Stream**, phân tích chuyển động bằng AI, rồi trả về kết quả phát hiện.
- Nhóm mình là **provider** trong hệ thống Smart Campus vì mình cung cấp kết quả cho các nhóm khác dùng tiếp.
- Các nhóm liên quan:
  - **A2 - Camera Stream** là bên gọi chính
  - **A6 - Core Business** là bên nhận kết quả để ra quyết định
  - **A5 - Analytics** là bên nhận log để thống kê

### Câu nói ngắn khi trình bày

> Nhóm mình là A4 - AI Vision. Nhiệm vụ của nhóm là nhận frame từ Camera Stream, phân tích chuyển động bằng AI, rồi trả kết quả phát hiện cho các nhóm khác dùng tiếp.

## 2. Input

- Dữ liệu đầu vào gồm:
  - `camera_id`
  - `frame_url`
  - `timestamp`
- Camera Stream sẽ gửi **link ảnh/frame** sang AI Vision khi phát hiện có chuyển động.
- Mình không nhận ảnh Base64 để tránh payload quá nặng.

### Ví dụ request

```json
{
  "camera_id": "cam-gate-01",
  "frame_url": "http://26.231.100.34:8080/frame.jpg",
  "timestamp": "2026-06-17T01:18:39"
}
```

### Câu nói ngắn khi trình bày

> Input của nhóm mình là frame_url lấy từ Camera Stream khi có chuyển động, kèm camera_id và timestamp. Mình nhận URL ảnh để service nhẹ hơn và dễ tích hợp hơn.

## 3. Xử lý nghiệp vụ

- Service kiểm tra dữ liệu đầu vào.
- Service tải ảnh từ `frame_url`.
- Service chạy **YOLOv8n** để phân tích chuyển động và nhận diện đối tượng trong ảnh.
- Nếu không chạy được model thật thì tự fallback sang **mock AI** để vẫn demo được.
- Nếu ảnh lỗi hoặc không đọc được thì trả lỗi `422`.
- Kết quả sau xử lý được chuẩn hóa thành JSON thống nhất.
- Kết quả có thể được lưu tạm theo `detection_id` để tra cứu lại.

### Câu nói ngắn khi trình bày

> Service sẽ kiểm tra input, tải ảnh từ frame_url, chạy YOLOv8n để phân tích chuyển động, nếu model thật lỗi thì fallback sang mock AI, còn nếu ảnh không hợp lệ thì trả 422.

## 4. Output

- Output chính là JSON kết quả phát hiện.
- Các field quan trọng:
  - `detection_id`
  - `anomaly_detected`
  - `confidence_score`
  - `finding`
  - `model_mode`

### Ví dụ response

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

### Câu nói ngắn khi trình bày

> Output của nhóm mình là một JSON có detection_id, anomaly_detected, confidence_score, finding và model_mode. Đây là kết quả phân tích chuyển động mà các nhóm khác có thể dùng tiếp.

### Mức độ cảnh báo

| Điều kiện | `risk_level` |
|---|---|
| Không phát hiện gì đáng chú ý | `low` |
| Có phát hiện và mức tin cậy trung bình | `medium` |
| Có người hoặc intruder, độ tin cậy cao | `high` |

### Câu nói ngắn khi trình bày

> Nhóm mình có bảng mức độ cảnh báo gồm low, medium và high. Low là không đáng chú ý, medium là cần theo dõi, còn high là cảnh báo cao.

## 5. Output gửi cho ai

- **A2 - Camera Stream** là bên gọi chính vào AI Vision.
- **A6 - Core Business** có thể nhận dữ liệu qua adapter để ra quyết định nghiệp vụ.
- **A5 - Analytics** nhận detection log để thống kê và dựng dashboard.

### Endpoint chính

- `POST /api/v1/vision/detect`

### Endpoint tra cứu kết quả

- `GET /api/v1/vision/detections/{detection_id}`

### Endpoint adapter cho Core Business

- `POST /api/v1/events/camera`

### Hợp đồng cho Analytics

- [A4_TO_A5_ANALYTICS_CONTRACT.md](A4_TO_A5_ANALYTICS_CONTRACT.md)

### Câu nói ngắn khi trình bày

> Camera Stream là bên gọi chính, Core Business nhận kết quả để xử lý tiếp, còn Analytics nhận log để thống kê. Ngoài luồng chính, nhóm mình còn có hợp đồng riêng cho A5.

## 6. Minh chứng demo

Các minh chứng nên đưa khi bảo vệ:

- `docker compose ps` để chứng minh container đang chạy
- `GET /health` trả `200 OK`
- `GET /model` hiển thị model đã load
- log thật từ `POST /api/v1/vision/detect`
- screenshot dashboard
- file [openapi.yaml](openapi.yaml)
- file [Postman collection](postman/ai-vision.postman_collection.json)
- script [test_api.py](test_api.py)

### Link demo

- Dashboard: `http://26.64.81.15:8000/`
- Health: `http://26.64.81.15:8000/health`
- Model: `http://26.64.81.15:8000/model`
- OpenAPI: `http://26.64.81.15:8000/openapi.json`

### Câu nói ngắn khi trình bày

> Mình có đủ minh chứng chạy thật bằng Docker, có health check, model status, request/response thật, log tích hợp, OpenAPI và Postman.

## 7. Kịch bản nói nhanh 1 phút

> Nhóm mình là A4 - AI Vision. Service của nhóm nhận frame từ Camera Stream khi có chuyển động, sau đó tải ảnh về và chạy YOLOv8n để phân tích chuyển động và phát hiện đối tượng. Kết quả trả về là JSON có detection_id, anomaly_detected, confidence_score, finding và model_mode. Camera Stream là bên gọi chính vào endpoint /api/v1/vision/detect. Nếu cần tra cứu lại kết quả thì dùng /api/v1/vision/detections/{detection_id}. Nhóm mình cũng có adapter /api/v1/events/camera để map dữ liệu sang schema phù hợp cho Core Business. Ngoài ra nhóm mình còn có hợp đồng riêng với A5 Analytics để gửi detection log sang thống kê.

## 8. Thứ tự demo đề xuất

1. Mở dashboard: `http://26.64.81.15:8000/`
2. Mở `GET /health`
3. Mở `GET /model`
4. Chạy `test_api.py`
5. Mở log `docker logs -f ai-vision-service`
6. Nếu cần, demo `POST /api/v1/events/camera`
