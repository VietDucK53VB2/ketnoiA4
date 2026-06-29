from datetime import datetime, timezone
from typing import Annotated, Dict, List, Literal, Optional, Union
import logging
from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import AliasChoices, BaseModel, Field, HttpUrl

from app.vision import analyze_image, get_model_status

# The imports above provide:
# - datetime/timezone: handle request timestamps.
# - typing helpers: describe API models cleanly.
# - logging: print demo-friendly service logs.
# - uuid4: generate unique detection IDs.
# - httpx: download frame_url from Camera Stream.
# - FastAPI / HTTPException / HTMLResponse: serve API + dashboard.
# - Pydantic tools: validate request/response schemas.
# - app.vision: run YOLO or mock analysis.


class CameraFrameIn(BaseModel):
    """Legacy input model for backward-compatible callers."""
    camera_id: str = Field(..., examples=["cam-gate-01"])
    frame_url: HttpUrl = Field(
        ...,
        validation_alias=AliasChoices("frame_url", "image_url"),
        serialization_alias="frame_url",
        examples=["http://example.com/frame.jpg"],
    )
    timestamp: datetime = Field(..., examples=["2026-05-02T09:10:00"])


class VisionDetectRequest(BaseModel):
    """Primary contract used by Camera Stream -> AI Vision."""
    camera_id: str = Field(..., examples=["cam-gate-01"])
    frame_url: HttpUrl = Field(
        ...,
        validation_alias=AliasChoices("frame_url", "image_url"),
        serialization_alias="frame_url",
        examples=["http://example.com/frame.jpg"],
    )
    timestamp: datetime = Field(..., examples=["2026-05-02T09:10:00"])


class DetectionOut(BaseModel):
    """Legacy response kept for older callers using /analyze."""
    detected: bool
    object: str
    confidence: float
    risk_level: str
    camera_id: str
    timestamp: datetime
    model_mode: str
    notes: Optional[str] = None


class BatchDetectionOut(BaseModel):
    results: List[DetectionOut]


class ProblemDetails(BaseModel):
    """Simple RFC-style error payload for 4xx responses."""
    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: Optional[str] = None


class PersonFinding(BaseModel):
    """Finding model when YOLO detects a person."""
    finding_type: Literal["person"]
    object_name: Literal["person"] = "person"
    risk_level: Literal["low", "medium", "high"]
    description: Optional[str] = None


class ObjectFinding(BaseModel):
    """Finding model when YOLO detects a generic object."""
    finding_type: Literal["object"]
    object_name: str
    risk_level: Literal["low", "medium", "high"]
    description: Optional[str] = None


Finding = Annotated[Union[PersonFinding, ObjectFinding], Field(discriminator="finding_type")]


class DetectionResult(BaseModel):
    """Primary response model for /api/v1/vision/detect."""
    detection_id: str
    camera_id: str
    frame_url: HttpUrl
    timestamp: datetime
    anomaly_detected: bool
    confidence_score: Optional[float] = None
    finding: Optional[Finding] = None
    model_mode: str
    notes: Optional[str] = None


class CoreFinding(BaseModel):
    """A6-compatible finding summary for Core Business."""
    label: str
    confidence: float


class CoreCameraEvent(BaseModel):
    """A6-style camera event payload derived from AI Vision output."""
    event_id: str
    event_type: Literal["core.camera.evaluated"] = "core.camera.evaluated"
    timestamp: datetime
    camera_id: str
    location: Optional[str] = None
    motion_detected: bool
    motion_score: float
    detections: List[CoreFinding]
    unknown_person: bool
    risk_level: Literal["normal", "warning", "critical"]
    reason: str
    core_decision: Literal["no_alert", "alert_required"]


# Configure concise logs so demo reviewers can read the flow quickly.
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ai-vision-service")

# Create the FastAPI app object that exposes endpoints and the dashboard.
app = FastAPI(
    title="AI Vision Service",
    version="1.0.0",
    description="Service xu ly anh camera bang AI that hoac mo phong.",
)

# In-memory store for demo purposes so GET /detections/{id} can work.
DETECTION_STORE: Dict[str, DetectionResult] = {}


def _problem(title: str, detail: str, status: int = 422, instance: Optional[str] = None) -> ProblemDetails:
    """Build a consistent error object for client-side debugging."""
    return ProblemDetails(title=title, detail=detail, status=status, instance=instance)


async def _fetch_image_bytes(frame_url: str) -> bytes:
    """Download the frame from Camera Stream with redirects enabled."""
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        try:
            response = await client.get(frame_url)
            response.raise_for_status()
            return response.content
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail=_problem(
                    title="Unprocessable Image URL",
                    detail=f"Cannot fetch frame_url: {exc}",
                    status=422,
                ).model_dump(),
            )


def _build_finding(result: dict, object_name: str) -> Optional[Finding]:
    """Convert raw YOLO output into the declared union schema."""
    if not result.get("detected"):
        return None
    risk_level = result.get("risk_level", "low")
    if object_name == "person":
        return PersonFinding(
            finding_type="person",
            risk_level=risk_level,
            description="Human presence detected by YOLO.",
        )
    return ObjectFinding(
        finding_type="object",
        object_name=object_name,
        risk_level=risk_level,
        description=f"Detected object: {object_name}",
    )


def _store_detection(result: DetectionResult) -> DetectionResult:
    """Store the detection in memory for later lookup by detection_id."""
    DETECTION_STORE[result.detection_id] = result
    return result


def _map_to_core_camera_event(detection: DetectionResult) -> CoreCameraEvent:
    """Translate A4 AI Vision output into the A6 Core Business camera-event schema."""
    detections = []
    if detection.finding:
        detections.append(CoreFinding(label=detection.finding.object_name, confidence=detection.confidence_score or 0.0))

    unknown_person = bool(detection.finding and detection.finding.object_name == "person" and detection.confidence_score and detection.confidence_score >= 0.6)
    motion_detected = detection.anomaly_detected
    motion_score = detection.confidence_score or 0.0

    if not detection.anomaly_detected:
        core_risk = "normal"
        reason = "no_anomaly_detected"
        core_decision = "no_alert"
    elif unknown_person:
        core_risk = "warning"
        reason = "unknown_person_detected"
        core_decision = "alert_required"
    else:
        core_risk = "warning" if motion_score < 0.85 else "critical"
        reason = "object_detected"
        core_decision = "alert_required"

    return CoreCameraEvent(
        event_id=detection.detection_id,
        timestamp=detection.timestamp,
        camera_id=detection.camera_id,
        location=None,
        motion_detected=motion_detected,
        motion_score=motion_score,
        detections=detections,
        unknown_person=unknown_person,
        risk_level=core_risk,
        reason=reason,
        core_decision=core_decision,
    )


async def _run_detection(frame: VisionDetectRequest | CameraFrameIn) -> DetectionResult:
    """Shared detection flow used by the new endpoint and the legacy adapter."""
    # Normalize both new and legacy request payloads to one URL variable.
    frame_url = str(frame.frame_url if hasattr(frame, "frame_url") else frame.image_url)
    # Keep the camera id from the caller so analytics can group results later.
    camera_id = frame.camera_id
    # Store timestamps in UTC when timezone info exists; otherwise keep original value.
    timestamp = frame.timestamp.astimezone(timezone.utc) if frame.timestamp.tzinfo else frame.timestamp
    # Build a unique id that the caller can use to look up the detection later.
    detection_id = f"det-{uuid4().hex[:12]}"

    logger.info("[1/2] Dang gui yeu cau phan tich toi AI Vision: http://0.0.0.0:8000/api/v1/vision/detect")
    logger.info("Received analyze request from camera_id=%s", camera_id)
    logger.info("Gui frame_url cua camera de AI download: %s", frame_url)

    # Download the actual frame from Camera Stream before running inference.
    image_bytes = await _fetch_image_bytes(frame_url)
    logger.info("GET /frame.jpg HTTP/1.1 200 OK")
    logger.info("Image downloaded successfully: %s bytes", len(image_bytes))

    # Run YOLO or mock AI and map the result into the service contract.
    result = analyze_image(image_bytes)
    confidence = result["confidence"]
    anomaly_detected = bool(result["detected"])
    finding = _build_finding(result, result["object"])
    # Build the public response object that is returned to the consumer.
    response = DetectionResult(
        detection_id=detection_id,
        camera_id=camera_id,
        frame_url=frame_url,
        timestamp=timestamp,
        anomaly_detected=anomaly_detected,
        confidence_score=round(confidence, 2) if anomaly_detected else None,
        finding=finding,
        model_mode=result["model_mode"],
        notes=result.get("notes"),
    )
    _store_detection(response)
    logger.info(
        "AI Vision phan hoi ket qua thanh cong: anomaly_detected=%s object=%s confidence=%s mode=%s",
        response.anomaly_detected,
        getattr(finding, "object_name", "none") if finding else "none",
        response.confidence_score,
        response.model_mode,
    )
    logger.info("Da publish thanh cong su kien len topic: smart-campus/events/camera")
    return response


# Dashboard HTML lives in a Python string so the service stays single-file simple.
DASHBOARD_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>AI Vision Service Dashboard</title>
  <style>
    :root {
      --bg: #08111f;
      --panel: rgba(11, 18, 34, 0.78);
      --panel-strong: #0d172a;
      --text: #e6eefc;
      --muted: #9fb2d1;
      --line: rgba(148, 163, 184, 0.18);
      --accent: #6ee7ff;
      --accent-2: #8b5cf6;
      --good: #34d399;
      --warn: #fbbf24;
      --bad: #fb7185;
      --shadow: 0 22px 60px rgba(0,0,0,.45);
      --radius: 22px;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(110, 231, 255, 0.16), transparent 30%),
        radial-gradient(circle at top right, rgba(139, 92, 246, 0.18), transparent 26%),
        linear-gradient(180deg, #050914 0%, #09111d 55%, #08111f 100%);
      min-height: 100vh;
    }
    .wrap {
      max-width: 1200px;
      margin: 0 auto;
      padding: 32px 20px 44px;
    }
    .hero {
      display: grid;
      grid-template-columns: 1.25fr 0.75fr;
      gap: 18px;
      align-items: stretch;
    }
    .card {
      background: linear-gradient(180deg, rgba(19, 29, 51, 0.92), rgba(11, 18, 34, 0.88));
      border: 1px solid var(--line);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      backdrop-filter: blur(18px);
    }
    .hero-main {
      padding: 28px;
      position: relative;
      overflow: hidden;
    }
    .hero-main::after {
      content: "";
      position: absolute;
      inset: -20% auto auto 62%;
      width: 260px;
      height: 260px;
      background: radial-gradient(circle, rgba(110, 231, 255, 0.28), transparent 65%);
      pointer-events: none;
    }
    .eyebrow {
      display: inline-flex;
      gap: 8px;
      align-items: center;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(110, 231, 255, 0.1);
      color: #bff3ff;
      border: 1px solid rgba(110, 231, 255, 0.18);
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    h1 {
      margin: 18px 0 10px;
      font-size: clamp(32px, 5vw, 58px);
      line-height: 0.95;
      letter-spacing: -0.04em;
    }
    .sub {
      max-width: 760px;
      color: var(--muted);
      font-size: 15px;
      line-height: 1.7;
      margin: 0 0 22px;
    }
    .pill-row, .stat-row {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }
    .pill {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 10px 14px;
      border-radius: 999px;
      background: rgba(255,255,255,0.04);
      border: 1px solid var(--line);
      color: var(--text);
      font-size: 13px;
    }
    .dot {
      width: 9px; height: 9px; border-radius: 50%;
      background: var(--good);
      box-shadow: 0 0 0 4px rgba(52, 211, 153, 0.12);
    }
    .hero-side {
      display: grid;
      gap: 18px;
    }
    .mini {
      padding: 20px;
    }
    .mini h3 {
      margin: 0 0 10px;
      font-size: 16px;
      letter-spacing: -0.02em;
    }
    .mini p {
      margin: 0;
      color: var(--muted);
      line-height: 1.6;
      font-size: 14px;
    }
    .big-number {
      font-size: 34px;
      font-weight: 800;
      color: var(--accent);
      letter-spacing: -0.05em;
      margin-top: 10px;
    }
    .grid {
      margin-top: 18px;
      display: grid;
      grid-template-columns: repeat(12, 1fr);
      gap: 18px;
    }
    .panel {
      grid-column: span 6;
      padding: 22px;
    }
    .panel.full { grid-column: 1 / -1; }
    .panel h2 {
      margin: 0 0 8px;
      font-size: 18px;
    }
    .panel .desc {
      margin: 0 0 18px;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.6;
    }
    .stats {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }
    .stat {
      padding: 14px;
      border-radius: 16px;
      background: rgba(255,255,255,0.03);
      border: 1px solid var(--line);
    }
    .stat .label {
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
    }
    .stat .value {
      margin-top: 6px;
      font-size: 17px;
      font-weight: 700;
    }
    .status {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 600;
      background: rgba(255,255,255,0.04);
      border: 1px solid var(--line);
    }
    .status.ok { color: #b7f7d2; }
    .status.warn { color: #fde68a; }
    .status.bad { color: #fecdd3; }
    form {
      display: grid;
      gap: 12px;
    }
    label {
      display: grid;
      gap: 8px;
      font-size: 13px;
      color: #dce7fb;
    }
    input, textarea {
      width: 100%;
      border-radius: 14px;
      border: 1px solid rgba(148, 163, 184, 0.22);
      background: rgba(3, 7, 18, 0.68);
      color: var(--text);
      padding: 14px 15px;
      outline: none;
      font-size: 14px;
    }
    input:focus, textarea:focus {
      border-color: rgba(110, 231, 255, 0.55);
      box-shadow: 0 0 0 4px rgba(110, 231, 255, 0.12);
    }
    .row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }
    button {
      appearance: none;
      border: 0;
      border-radius: 14px;
      padding: 14px 18px;
      color: #08111f;
      font-weight: 800;
      cursor: pointer;
      background: linear-gradient(135deg, var(--accent), #a78bfa);
      box-shadow: 0 16px 40px rgba(110, 231, 255, 0.18);
    }
    button.secondary {
      background: rgba(255,255,255,0.06);
      color: var(--text);
      border: 1px solid var(--line);
      box-shadow: none;
    }
    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 2px;
    }
    .result {
      display: grid;
      grid-template-columns: 1.1fr 0.9fr;
      gap: 14px;
    }
    .stack {
      display: grid;
      gap: 12px;
    }
    .result-box {
      padding: 18px;
      border-radius: 18px;
      background: rgba(255,255,255,0.03);
      border: 1px solid var(--line);
      min-height: 160px;
    }
    pre {
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      color: #dbeafe;
      font-size: 13px;
      line-height: 1.6;
    }
    .footer {
      margin-top: 18px;
      color: var(--muted);
      font-size: 13px;
      text-align: center;
    }
    .small {
      font-size: 12px;
      color: var(--muted);
    }
    .kv {
      display: grid;
      gap: 8px;
      margin-top: 10px;
      font-size: 13px;
    }
    .kv div {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      padding-bottom: 8px;
      border-bottom: 1px solid rgba(148, 163, 184, 0.16);
    }
    .kv span:first-child {
      color: var(--muted);
    }
    @media (max-width: 980px) {
      .hero, .result { grid-template-columns: 1fr; }
      .panel { grid-column: span 12; }
      .stats, .row { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <section class="card hero-main">
        <div class="eyebrow">AI Vision Service Dashboard</div>
        <h1>Real-time vision checks with YOLO and a clean demo UI</h1>
        <p class="sub">
          Open this page to check the service health, inspect model status, and send a test frame to
          the AI Vision API without using Postman. This dashboard is intentionally simple, visual, and
          useful for demo day.
        </p>
        <div class="pill-row">
          <div class="pill"><span class="dot"></span><span id="pill-health">Health: loading</span></div>
          <div class="pill"><span class="dot" style="background: var(--accent); box-shadow: 0 0 0 4px rgba(110,231,255,0.12);"></span><span id="pill-model">Model: loading</span></div>
          <div class="pill"><span class="dot" style="background: var(--warn); box-shadow: 0 0 0 4px rgba(251,191,36,0.12);"></span><span>Endpoint: /analyze</span></div>
        </div>
      </section>
      <div class="hero-side">
        <section class="card mini">
          <h3>Current Mode</h3>
          <div class="big-number" id="mode-value">-</div>
          <p id="mode-note">Waiting for model status...</p>
        </section>
        <section class="card mini">
          <h3>Integration Status</h3>
          <p id="integration-note">Ready for Camera Stream and Core Business integration.</p>
        </section>
      </div>
    </div>

    <div class="grid">
      <section class="card panel">
        <h2>Service Snapshot</h2>
        <p class="desc">Quick indicators from /health and /model. This is the easiest place to show the service is alive.</p>
        <div class="stats">
          <div class="stat">
            <div class="label">Health</div>
            <div class="value" id="health-value">Loading...</div>
          </div>
          <div class="stat">
            <div class="label">Model</div>
            <div class="value" id="model-value">Loading...</div>
          </div>
          <div class="stat">
            <div class="label">Risk Engine</div>
            <div class="value">YOLOv8n</div>
          </div>
        </div>
      </section>

      <section class="card panel">
        <h2>Test Analyzer</h2>
          <p class="desc">Paste a Camera Stream frame URL, then run a real analysis or mock mode. The response will be shown below.</p>
        <form id="analyze-form">
          <label>
            Demo Route
            <select id="route-mode">
              <option value="vision">Camera Stream -> AI Vision</option>
              <option value="core">Camera Stream -> AI Vision -> A6 Adapter</option>
            </select>
          </label>
          <div class="row">
            <label>
              Camera ID
              <input id="camera-id" value="cam-gate-01" />
            </label>
            <label>
              Timestamp
              <input id="timestamp" />
            </label>
          </div>
          <label>
            Frame URL from Camera Stream
            <input id="frame-url" value="http://26.231.100.34:8080/frame.jpg" />
          </label>
          <div class="kv">
            <div><span>Primary endpoint</span><span id="endpoint-label">/api/v1/vision/detect</span></div>
            <div><span>A6 adapter</span><span>/api/v1/events/camera</span></div>
          </div>
          <div class="actions">
            <button type="submit">Run AI Vision</button>
            <button type="button" class="secondary" id="mock-btn">Run Mock Demo</button>
            <button type="button" class="secondary" id="reset-btn">Reset</button>
          </div>
          <div class="small">Tip: if you only want a live check, open <code>/health</code> and <code>/model</code>.</div>
        </form>
      </section>

      <section class="card panel full">
        <h2>Result Viewer</h2>
        <p class="desc">The JSON response and status label update here after each request.</p>
        <div class="result">
          <div class="result-box stack">
            <div id="result-status" class="status warn">Idle</div>
            <div class="kv">
              <div><span>detection_id</span><span id="detection-id-value">-</span></div>
              <div><span>model_mode</span><span id="model-mode-value">-</span></div>
              <div><span>route</span><span id="route-value">-</span></div>
            </div>
            <pre id="result-json">{}</pre>
          </div>
          <div class="result-box">
            <h3 style="margin-top:0">How it works</h3>
            <pre>
1. Camera Stream sends frame_url to /api/v1/vision/detect
2. AI Vision downloads the frame
3. YOLOv8n detects objects
4. Response returns detection_id, anomaly_detected, confidence_score, and finding
5. If needed, AI Vision can map the result to /api/v1/events/camera for Core Business
            </pre>
          </div>
        </div>
      </section>
    </div>

    <div class="footer">AI Vision Service Dashboard - FastAPI + YOLOv8n</div>
  </div>

  <script>
    const fmt = (obj) => JSON.stringify(obj, null, 2);
    const nowLocal = () => new Date().toISOString().slice(0, 19);

    const healthValue = document.getElementById("health-value");
    const modelValue = document.getElementById("model-value");
    const modeValue = document.getElementById("mode-value");
    const modeNote = document.getElementById("mode-note");
    const pillHealth = document.getElementById("pill-health");
    const pillModel = document.getElementById("pill-model");
    const integrationNote = document.getElementById("integration-note");
    const resultJson = document.getElementById("result-json");
    const resultStatus = document.getElementById("result-status");
    const detectionIdValue = document.getElementById("detection-id-value");
    const modelModeValue = document.getElementById("model-mode-value");
    const routeValue = document.getElementById("route-value");
    const routeModeInput = document.getElementById("route-mode");
    const timestampInput = document.getElementById("timestamp");
    const frameUrlInput = document.getElementById("frame-url");
    const cameraIdInput = document.getElementById("camera-id");
    const endpointLabel = document.getElementById("endpoint-label");

    timestampInput.value = nowLocal();

    // Fetch /health and /model to show the current service state.
    async function loadSnapshot() {
      try {
        const [healthRes, modelRes] = await Promise.all([
          fetch("/health"),
          fetch("/model"),
        ]);
        const health = await healthRes.json();
        const model = await modelRes.json();

        healthValue.textContent = health.status || "unknown";
        modelValue.textContent = model.mode || "unknown";
        modeValue.textContent = model.mode || "unknown";
        modeNote.textContent = model.loaded ? "YOLO model loaded successfully." : "Fallback mode is active.";
        pillHealth.textContent = `Health: ${health.status || "unknown"}`;
        pillModel.textContent = `Model: ${model.mode || "unknown"}`;
        integrationNote.textContent = model.loaded
          ? "Service is ready for Camera Stream integration."
          : "Service is running, but model is not fully loaded yet.";
      } catch (err) {
        healthValue.textContent = "error";
        modelValue.textContent = "error";
        modeValue.textContent = "error";
        modeNote.textContent = String(err);
        pillHealth.textContent = "Health: error";
        pillModel.textContent = "Model: error";
      }
    }

    // Send a frame_url to the main detect endpoint or the mock endpoint.
    async function runAnalyze(useMock) {
      // Build the payload expected by the API contract.
      const payload = {
        camera_id: cameraIdInput.value.trim(),
        frame_url: frameUrlInput.value.trim(),
        timestamp: timestampInput.value.trim() || new Date().toISOString(),
      };

      // Use the main endpoint by default; mock endpoint is for demos.
      const selectedRoute = routeModeInput.value;
      const endpoint = useMock
        ? "/analyze/mock"
        : (selectedRoute === "core" ? "/api/v1/events/camera" : "/api/v1/vision/detect");
      const routeName = useMock ? "Mock" : (selectedRoute === "core" ? "A6 adapter" : "Camera Stream");
      routeValue.textContent = routeName;
      endpointLabel.textContent = endpoint;
      resultStatus.className = "status warn";
      resultStatus.textContent = useMock ? "Running mock..." : "Running AI analysis...";
      resultJson.textContent = useMock ? "Sending mock request..." : "Sending frame from Camera Stream...";

      try {
        // Send JSON to the backend and wait for the synchronous response.
        const res = await fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        resultJson.textContent = fmt(data);
        resultStatus.className = res.ok ? "status ok" : "status bad";
        resultStatus.textContent = res.ok ? (useMock ? "Mock success" : "AI analysis success") : `Error ${res.status}`;
        detectionIdValue.textContent = data.detection_id || data.event_id || "-";
        modelModeValue.textContent = data.model_mode || "-";
      } catch (err) {
        resultStatus.className = "status bad";
        resultStatus.textContent = "Request failed";
        resultJson.textContent = String(err);
      }
    }

    // Wire the form button to the live detect call.
    document.getElementById("analyze-form").addEventListener("submit", (e) => {
      e.preventDefault();
      runAnalyze(false);
    });
    // Wire the mock button so you can demo without a real moving frame.
    document.getElementById("mock-btn").addEventListener("click", () => runAnalyze(true));
    document.getElementById("reset-btn").addEventListener("click", () => {
      cameraIdInput.value = "cam-gate-01";
      frameUrlInput.value = "http://26.231.100.34:8080/frame.jpg";
      timestampInput.value = nowLocal();
      routeModeInput.value = "vision";
      endpointLabel.textContent = "/api/v1/vision/detect";
      routeValue.textContent = "-";
      detectionIdValue.textContent = "-";
      modelModeValue.textContent = "-";
      resultStatus.className = "status warn";
      resultStatus.textContent = "Idle";
      resultJson.textContent = "{}";
    });

    routeModeInput.addEventListener("change", () => {
      endpointLabel.textContent = routeModeInput.value === "core"
        ? "/api/v1/events/camera"
        : "/api/v1/vision/detect";
      routeValue.textContent = routeModeInput.value === "core" ? "A6 adapter" : "Camera Stream";
    });

    // Load service status as soon as the dashboard is opened.
    loadSnapshot();
  </script>
</body>
</html>
"""


@app.on_event("startup")
def startup_log():
    """Print startup hints so demo reviewers can see the service is alive."""
    logger.info("AI Vision service starting...")
    logger.info("AI Vision Endpoint: http://0.0.0.0:8000")
    logger.info("Local Mock Mode: False")
    logger.info("Mock AI Response: False")
    logger.info("Force Trigger: False")
    logger.info("Health Check: http://0.0.0.0:8000/health")
    logger.info("Model Status: http://0.0.0.0:8000/model")


@app.get("/health")
def health():
    """Simple health endpoint for Docker Compose and integration checks."""
    return {"status": "ok", "service": "ai-vision-service"}


@app.get("/", response_class=HTMLResponse)
def dashboard():
    """Visual dashboard for quick manual verification in a browser."""
    return HTMLResponse(DASHBOARD_HTML)


@app.get("/info")
def info():
    return {
        "service": "AI Vision Service",
        "capabilities": [
            "receive camera frame",
            "simulate or run AI detection",
            "return detection confidence",
            "return risk level",
        ],
    }


@app.get("/model")
def model():
    """Expose YOLO load status so the team can verify real model readiness."""
    return get_model_status()


@app.post("/api/v1/vision/detect", response_model=DetectionResult)
async def vision_detect(frame: VisionDetectRequest):
    """Primary sync contract used by Camera Stream."""
    return await _run_detection(frame)


@app.get("/api/v1/vision/detections/{detection_id}", response_model=DetectionResult)
def get_detection(detection_id: str):
    """Lookup the previous result by detection_id for recovery/debugging."""
    detection = DETECTION_STORE.get(detection_id)
    if not detection:
        raise HTTPException(
            status_code=404,
            detail=_problem(
                title="Detection Not Found",
                detail=f"Detection '{detection_id}' was not found.",
                status=404,
                instance=f"/api/v1/vision/detections/{detection_id}",
            ).model_dump(),
        )
    return detection


@app.post("/api/v1/events/camera", response_model=CoreCameraEvent)
async def camera_event_adapter(frame: VisionDetectRequest):
    """A6-compatible adapter so Core Business can consume a camera event shape."""
    detection = await _run_detection(frame)
    return _map_to_core_camera_event(detection)


@app.post("/analyze", response_model=DetectionOut)
async def analyze(frame: CameraFrameIn):
    """Backward-compatible adapter for older consumers."""
    detection = await _run_detection(
        VisionDetectRequest(camera_id=frame.camera_id, frame_url=frame.frame_url, timestamp=frame.timestamp)
    )
    legacy = DetectionOut(
        detected=detection.anomaly_detected,
        object=detection.finding.object_name if detection.finding else "none",
        confidence=float(detection.confidence_score or 0.0),
        risk_level=detection.finding.risk_level if detection.finding else "low",
        camera_id=detection.camera_id,
        timestamp=detection.timestamp,
        model_mode=detection.model_mode,
        notes=detection.notes,
    )
    return legacy


@app.post("/analyze/mock", response_model=DetectionOut)
def analyze_mock(frame: CameraFrameIn):
    """Forced mock mode for demo runs when the team wants deterministic output."""
    logger.info("[1/2] Dang gui yeu cau phan tich toi AI Vision: http://0.0.0.0:8000/analyze/mock")
    logger.info("Received mock analyze request from camera_id=%s", frame.camera_id)
    logger.info("Force Trigger: True (mock mode)")
    result = analyze_image(None, force_mock=True)
    logger.info(
        "AI Vision phan hoi ket qua thanh cong: detected=%s object=%s confidence=%.2f",
        result["detected"],
        result["object"],
        result["confidence"],
    )
    logger.info("Da publish thanh cong su kien len topic: smart-campus/events/camera")
    return DetectionOut(
        detected=result["detected"],
        object=result["object"],
        confidence=round(result["confidence"], 2),
        risk_level=result["risk_level"],
        camera_id=frame.camera_id,
        timestamp=frame.timestamp,
        model_mode=result["model_mode"],
        notes="Mock AI mode was forced by caller.",
    )
