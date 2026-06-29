from __future__ import annotations

import argparse
from datetime import datetime

import httpx


def main() -> int:
    """Smoke test the service end-to-end and print human-friendly hints."""
    parser = argparse.ArgumentParser(description="Smoke test for AI Vision Service")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--frame-url", "--image-url", dest="frame_url", default="https://www.ultralytics.com/images/bus.jpg")
    args = parser.parse_args()

    payload = {
        "camera_id": "cam-gate-01",
        "frame_url": args.frame_url,
        "timestamp": datetime.utcnow().isoformat(),
    }

    with httpx.Client(timeout=30) as client:
        # Health and model checks prove the service is alive before calling detect.
        print(f"[INFO] Dang kiem tra ket noi toi AI Vision: {args.base_url}")
        health = client.get(f"{args.base_url}/health")
        print("[INFO] Health check thanh cong" if health.status_code == 200 else "[ERROR] Health check that bai")
        model = client.get(f"{args.base_url}/model")
        print("[INFO] Da ket noi den model status")
        print(f"[INFO] Camera Stream gui frame_url toi AI Vision: {args.frame_url}")
        # Main integration call: Camera Stream -> AI Vision.
        detect = client.post(f"{args.base_url}/api/v1/vision/detect", json=payload)
        print("[INFO] AI Vision phan hoi ket qua thanh cong" if detect.status_code == 200 else "[ERROR] AI Vision phan hoi that bai")
        detection_id = None
        if detect.status_code == 200:
            try:
                detection_id = detect.json().get("detection_id")
            except Exception:
                detection_id = None
        lookup = None
        if detection_id:
            # Optional lookup step: verify the stored result can be retrieved again.
            print(f"[INFO] Dang tra cuu lai ket qua theo detection_id: {detection_id}")
            lookup = client.get(f"{args.base_url}/api/v1/vision/detections/{detection_id}")
            print("[INFO] Tra cuu ket qua thanh cong" if lookup.status_code == 200 else "[ERROR] Tra cuu that bai")
        print("[INFO] Dang chay mock demo")
        # Mock mode is useful when we want a deterministic demo path.
        mock = client.post(f"{args.base_url}/analyze/mock", json=payload)
        print("[INFO] Mock demo thanh cong" if mock.status_code == 200 else "[ERROR] Mock demo that bai")

    print("HEALTH:", health.status_code, health.text)
    print("MODEL:", model.status_code, model.text)
    print("DETECT:", detect.status_code, detect.text)
    if lookup is not None:
        print("LOOKUP:", lookup.status_code, lookup.text)
    print("MOCK:", mock.status_code, mock.text)

    if health.status_code != 200 or model.status_code != 200:
        return 1
    if detect.status_code != 200 or mock.status_code != 200:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
