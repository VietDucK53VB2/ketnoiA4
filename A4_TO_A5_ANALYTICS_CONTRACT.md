# A4 -> A5 Analytics API Contract

Tài liệu này mô tả hợp đồng dữ liệu giữa:

- Provider: **A4 - AI Vision**
- Consumer: **A5 - Analytics**

Mục tiêu của luồng này là gửi log phát hiện từ AI Vision sang Analytics để tổng hợp thống kê, biểu đồ và báo cáo theo thời gian.

## 1. Vai trò kết nối

- A4 tạo ra kết quả phát hiện từ frame camera.
- A5 nhận detection log để phân tích xu hướng.
- Luồng này là **luồng thống kê phụ**, không thay thế luồng chính A2 -> A4 -> A6.

## 2. Dữ liệu A4 gửi sang A5

A4 nên gửi các field sau:

- `detection_id`
- `camera_id`
- `frame_url`
- `timestamp`
- `anomaly_detected`
- `confidence_score`
- `finding`
- `model_mode`
- `notes`

## 3. Endpoint đề xuất cho A5

### `POST /api/v1/analytics/vision-detections`

Mục đích:

- A4 đẩy detection log sang A5.
- A5 lưu log để thống kê số lần phát hiện, loại đối tượng, mức risk, và độ tin cậy.

Request body:

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

## 4. Schema đề xuất

### `VisionDetectionLog`

```json
{
  "detection_id": "string",
  "camera_id": "string",
  "frame_url": "string",
  "timestamp": "string",
  "anomaly_detected": true,
  "confidence_score": 0.87,
  "finding": {
    "finding_type": "person | object",
    "object_name": "string",
    "risk_level": "low | medium | high",
    "description": "string"
  },
  "model_mode": "yolo | mock-ai",
  "notes": "string"
}
```

### Ý nghĩa field

- `detection_id`: mã định danh duy nhất cho mỗi lần phát hiện
- `camera_id`: camera tạo ra frame
- `frame_url`: link frame để trace lại nếu cần
- `timestamp`: thời điểm phát hiện
- `anomaly_detected`: có phát hiện bất thường hay không
- `confidence_score`: độ tin cậy, có thể `null` nếu không có dị thường
- `finding`: thông tin chi tiết về đối tượng phát hiện
- `model_mode`: chế độ xử lý hiện tại
- `notes`: ghi chú bổ sung

## 5. Response đề xuất từ A5

### `200 OK`

```json
{
  "status": "received",
  "message": "Detection log stored successfully",
  "detection_id": "det-0ed98880e029"
}
```

### `202 Accepted`

Nếu A5 muốn xử lý bất đồng bộ:

```json
{
  "status": "accepted",
  "message": "Detection log queued for analytics processing",
  "detection_id": "det-0ed98880e029"
}
```

## 6. Lỗi chuẩn

### 400 Bad Request

Dùng khi thiếu field bắt buộc hoặc sai format JSON.

### 422 Unprocessable Entity

Dùng khi payload đúng JSON nhưng không hợp lệ về mặt nghiệp vụ.

### 500 Internal Server Error

Dùng khi A5 lỗi trong quá trình lưu hoặc xử lý thống kê.

## 7. Dùng để làm gì

A5 có thể dùng payload này để:

- đếm số detection theo camera
- thống kê theo `risk_level`
- thống kê theo loại đối tượng trong `finding`
- tính tỷ lệ cảnh báo theo ngày/tuần/tháng
- tạo dashboard giám sát camera

## 8. Luồng tích hợp

```text
Camera Stream -> A4 AI Vision -> A5 Analytics
```

Luồng gợi ý:

1. Camera Stream gửi `frame_url` cho A4.
2. A4 xử lý xong và trả response cho bên gọi chính.
3. A4 đồng thời gửi detection log sang A5 qua REST.
4. A5 lưu log và dựng thống kê.

## 9. Ví dụ mô tả ngắn để gửi nhóm A5

> Nhóm A4 sẽ gửi sang A5 detection log đã chuẩn hóa sau mỗi lần AI Vision xử lý ảnh. Payload gồm detection_id, camera_id, frame_url, timestamp, anomaly_detected, confidence_score, finding, model_mode và notes. Endpoint đề xuất là POST /api/v1/analytics/vision-detections. A5 chỉ cần lưu log và dùng để thống kê theo camera, risk_level và loại phát hiện.
