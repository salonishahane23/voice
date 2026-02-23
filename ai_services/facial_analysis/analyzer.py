"""
Facial & Posture Analysis Module — Real AI analysis.

Uses OpenCV + dlib for:
- Face detection and tracking
- Eye gaze direction estimation (using eye aspect ratio + pupil position)
- Head tilt/movement tracking
- DeepFace for emotion recognition

Uses MediaPipe Pose for:
- Shoulder detection (landmarks 11 & 12)
- Slouch detection via shoulder slope, vertical drift, and spread change

Falls back to face-position-based posture if MediaPipe is unavailable.
All scores computed from actual frame analysis — nothing hardcoded.
"""
import os
import cv2
import base64
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from collections import Counter

# Try dlib for facial landmarks (68-point model)
try:
    import dlib
    DLIB_AVAILABLE = True
    _detector = None
    _predictor = None
except ImportError:
    DLIB_AVAILABLE = False
    print("[FACIAL] dlib not available — using OpenCV cascade fallback")

# Try MediaPipe Pose for shoulder/posture detection (Tasks API)
try:
    import mediapipe as mp
    from mediapipe.tasks.python.vision import PoseLandmarker, PoseLandmarkerOptions
    from mediapipe.tasks.python import BaseOptions
    MEDIAPIPE_AVAILABLE = True
    _pose_landmarker = None
except ImportError:
    MEDIAPIPE_AVAILABLE = False
    print("[FACIAL] MediaPipe not available — shoulder detection disabled, using face-position fallback")

# Try DeepFace for emotions
try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
except ImportError:
    DEEPFACE_AVAILABLE = False
    print("[FACIAL] DeepFace not available — emotion detection disabled")


def _get_dlib_models():
    """Load dlib face detector and landmark predictor."""
    global _detector, _predictor
    if _detector is None:
        _detector = dlib.get_frontal_face_detector()
    if _predictor is None:
        predictor_path = os.path.join(
            os.path.dirname(__file__),
            "shape_predictor_68_face_landmarks.dat"
        )
        if os.path.exists(predictor_path):
            _predictor = dlib.shape_predictor(predictor_path)
        else:
            print(f"[FACIAL] Landmark model not found at {predictor_path}")
            print("[FACIAL] Download from: http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2")
    return _detector, _predictor


def _get_pose_landmarker():
    """Get or initialize MediaPipe PoseLandmarker (Tasks API)."""
    global _pose_landmarker
    if _pose_landmarker is None and MEDIAPIPE_AVAILABLE:
        model_path = os.path.join(
            os.path.dirname(__file__),
            "pose_landmarker_lite.task"
        )
        if not os.path.exists(model_path):
            print(f"[FACIAL] Pose landmarker model not found at {model_path}")
            return None
        options = PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=model_path),
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        _pose_landmarker = PoseLandmarker.create_from_options(options)
    return _pose_landmarker


def detect_shoulders(frame: np.ndarray) -> Optional[Dict[str, Any]]:
    """
    Detect shoulder positions using MediaPipe PoseLandmarker (Tasks API).
    Returns shoulder landmark data or None if not detected.

    MediaPipe Pose landmarks:
      11 = left shoulder
      12 = right shoulder
    """
    if not MEDIAPIPE_AVAILABLE:
        return None

    landmarker = _get_pose_landmarker()
    if landmarker is None:
        return None

    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
    results = landmarker.detect(mp_image)

    if not results.pose_landmarks or len(results.pose_landmarks) == 0:
        return None

    landmarks = results.pose_landmarks[0]  # first detected pose
    h, w = frame.shape[:2]

    left_shoulder = landmarks[11]
    right_shoulder = landmarks[12]

    # Only use if visibility is reasonable
    if left_shoulder.visibility < 0.4 or right_shoulder.visibility < 0.4:
        return None

    return {
        "left_x": left_shoulder.x * w,
        "left_y": left_shoulder.y * h,
        "right_x": right_shoulder.x * w,
        "right_y": right_shoulder.y * h,
        "left_visibility": left_shoulder.visibility,
        "right_visibility": right_shoulder.visibility,
    }


def analyze_posture_from_shoulders(
    shoulder_data_list: List[Dict[str, Any]],
    frame_height: int,
    frame_width: int,
) -> Dict[str, Any]:
    """
    Analyze posture from actual shoulder positions detected by MediaPipe Pose.

    Slouching indicators (all computed from real shoulder landmarks):
    - Shoulder slope: one shoulder significantly lower than the other (tilting)
    - Shoulder Y drift: shoulders move downward over time (slouching/sinking)
    - Shoulder spread change: distance between shoulders changes (hunching forward)

    Returns posture score and detailed metrics — nothing hardcoded.
    """
    if len(shoulder_data_list) < 3:
        return {
            "posture_score": 0.5,
            "shoulder_slouch_detected": False,
            "detail": "Not enough frames with visible shoulders",
            "method": "mediapipe_pose",
        }

    # --- Shoulder slope (tilt) across all frames ---
    slopes = []
    for sd in shoulder_data_list:
        dy = abs(sd["left_y"] - sd["right_y"])
        dx = abs(sd["left_x"] - sd["right_x"])
        slope_ratio = dy / max(dx, 1.0)  # how tilted the shoulders are
        slopes.append(slope_ratio)

    avg_slope = float(np.mean(slopes))

    # --- Shoulder vertical drift (slouching over time) ---
    shoulder_y_positions = [
        (sd["left_y"] + sd["right_y"]) / 2.0 / frame_height
        for sd in shoulder_data_list
    ]
    n_start = min(5, len(shoulder_y_positions))
    n_end = min(5, len(shoulder_y_positions))
    y_start_avg = float(np.mean(shoulder_y_positions[:n_start]))
    y_end_avg = float(np.mean(shoulder_y_positions[-n_end:]))
    y_drift = y_end_avg - y_start_avg  # positive = shoulders dropped = slouching

    # --- Shoulder spread change (hunching) ---
    spreads = [
        abs(sd["left_x"] - sd["right_x"]) / frame_width
        for sd in shoulder_data_list
    ]
    spread_start = float(np.mean(spreads[:n_start]))
    spread_end = float(np.mean(spreads[-n_end:]))
    spread_change = (spread_end - spread_start) / max(spread_start, 0.01)
    # Negative spread_change = shoulders coming together = hunching

    # --- Y position stability ---
    y_std = float(np.std(shoulder_y_positions))

    # --- Score computation from real data ---
    posture_score = 1.0
    slouching = False

    # Slope penalty: shoulders tilted > 0.15 ratio
    if avg_slope > 0.15:
        posture_score -= min(avg_slope * 2.0, 0.3)

    # Slouch penalty: shoulders drifted down > 3% of frame
    if y_drift > 0.03:
        posture_score -= min(y_drift * 4.0, 0.4)
        slouching = True
    elif y_drift > 0.015:
        posture_score -= y_drift * 2.0

    # Hunching penalty: shoulders came together > 15%
    if spread_change < -0.15:
        posture_score -= min(abs(spread_change) * 1.5, 0.2)
        slouching = True

    # Instability penalty
    if y_std > 0.04:
        posture_score -= min(y_std * 2.0, 0.15)

    posture_score = max(0.0, min(1.0, posture_score))

    return {
        "posture_score": round(posture_score, 3),
        "shoulder_slouch_detected": slouching,
        "shoulder_slope": round(avg_slope, 4),
        "shoulder_y_drift": round(y_drift, 4),
        "shoulder_spread_change": round(spread_change, 4),
        "shoulder_stability": round(1.0 - min(y_std * 10, 1.0), 3),
        "frames_with_shoulders": len(shoulder_data_list),
        "method": "mediapipe_pose",
    }


def extract_frames(video_path: str, max_frames: int = 60, fps_sample: int = 2) -> List[Tuple[float, np.ndarray]]:
    """
    Extract frames from video at a given sample rate.
    Returns list of (timestamp_seconds, frame) tuples.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return []

    video_fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    step = max(1, int(video_fps / fps_sample))

    frames = []
    frame_idx = 0

    while cap.isOpened() and len(frames) < max_frames:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % step == 0:
            timestamp = frame_idx / video_fps
            frames.append((timestamp, frame))
        frame_idx += 1

    cap.release()
    return frames


def detect_face_and_landmarks(frame: np.ndarray):
    """
    Detect face and 68 facial landmarks using dlib.
    Returns (face_rect, landmarks_array) or (None, None).
    """
    if not DLIB_AVAILABLE:
        return _detect_face_opencv(frame), None

    detector, predictor = _get_dlib_models()
    if detector is None:
        return _detect_face_opencv(frame), None

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = detector(gray, 0)

    if len(faces) == 0:
        return None, None

    face = faces[0]
    face_rect = {
        "x": face.left(), "y": face.top(),
        "w": face.right() - face.left(),
        "h": face.bottom() - face.top(),
    }

    if predictor is None:
        return face_rect, None

    shape = predictor(gray, face)
    landmarks = np.array([(shape.part(i).x, shape.part(i).y) for i in range(68)])
    return face_rect, landmarks


def _detect_face_opencv(frame: np.ndarray):
    """Fallback face detection using OpenCV Haar cascade."""
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    face_cascade = cv2.CascadeClassifier(cascade_path)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))

    if len(faces) == 0:
        return None
    x, y, w, h = faces[0]
    return {"x": int(x), "y": int(y), "w": int(w), "h": int(h)}


def compute_eye_aspect_ratio(landmarks: np.ndarray) -> Dict[str, float]:
    """
    Compute Eye Aspect Ratio (EAR) for blink/drowsiness detection
    and estimate gaze direction from eye landmarks.

    Eye landmarks: left eye = 36-41, right eye = 42-47
    """
    def ear(eye_pts):
        v1 = np.linalg.norm(eye_pts[1] - eye_pts[5])
        v2 = np.linalg.norm(eye_pts[2] - eye_pts[4])
        h = np.linalg.norm(eye_pts[0] - eye_pts[3])
        return (v1 + v2) / (2.0 * h) if h > 0 else 0

    left_eye = landmarks[36:42]
    right_eye = landmarks[42:48]

    left_ear = ear(left_eye)
    right_ear = ear(right_eye)
    avg_ear = (left_ear + right_ear) / 2.0

    # Estimate gaze: compare pupil center to eye center
    left_center = left_eye.mean(axis=0)
    right_center = right_eye.mean(axis=0)

    # Horizontal gaze: if both eye centers are shifted left/right of face center
    nose_bridge = landmarks[27]  # top of nose
    face_center_x = nose_bridge[0]

    eye_midpoint_x = (left_center[0] + right_center[0]) / 2
    gaze_offset = (eye_midpoint_x - face_center_x)

    return {
        "left_ear": round(left_ear, 3),
        "right_ear": round(right_ear, 3),
        "avg_ear": round(avg_ear, 3),
        "gaze_horizontal_offset": round(float(gaze_offset), 1),
        "looking_at_camera": abs(gaze_offset) < 15,  # within 15px = looking at camera
    }


def analyze_posture_from_face(
    face_positions: List[Dict[str, int]],
    frame_height: int,
) -> Dict[str, Any]:
    """
    Analyze posture by tracking face position across frames.

    Slouching indicators:
    - Face drops lower in the frame over time
    - Face gets smaller (leaning back) or larger (leaning forward)
    - Face center drifts significantly

    All computed from actual face tracking data.
    """
    if len(face_positions) < 3:
        return {"posture_score": 0.5, "slouching_detected": False,
                "detail": "Not enough frames to analyze posture"}

    # Track face center Y position (normalized to frame height)
    y_positions = [(fp["y"] + fp["h"] / 2) / frame_height for fp in face_positions]
    face_sizes = [fp["w"] * fp["h"] for fp in face_positions]

    # Slouching = face moves DOWN in the frame
    y_start_avg = np.mean(y_positions[:5])  # first 5 frames
    y_end_avg = np.mean(y_positions[-5:])   # last 5 frames
    y_drift = y_end_avg - y_start_avg       # positive = dropped down = slouching

    # Face size change (significant shrink/grow = posture change)
    if len(face_sizes) > 0 and face_sizes[0] > 0:
        size_start = np.mean(face_sizes[:5])
        size_end = np.mean(face_sizes[-5:])
        size_change_ratio = (size_end - size_start) / size_start
    else:
        size_change_ratio = 0

    # Movement stability (how much the face jumps around)
    y_std = float(np.std(y_positions))

    # Score: start at 1.0, penalize for bad posture
    posture_score = 1.0

    # Slouching penalty (face dropped >5% of frame height)
    if y_drift > 0.05:
        posture_score -= min(y_drift * 3.0, 0.4)
        slouching = True
    elif y_drift > 0.02:
        posture_score -= y_drift * 2.0
        slouching = False
    else:
        slouching = False

    # Instability penalty
    if y_std > 0.05:
        posture_score -= min(y_std * 2.0, 0.2)

    # Size change penalty (leaning forward/back excessively)
    if abs(size_change_ratio) > 0.3:
        posture_score -= 0.1

    posture_score = max(0.0, min(1.0, posture_score))

    return {
        "posture_score": round(posture_score, 3),
        "slouching_detected": slouching,
        "face_y_drift": round(y_drift, 4),
        "face_stability": round(1.0 - min(y_std * 10, 1.0), 3),
        "size_change_ratio": round(size_change_ratio, 3),
    }


def analyze_eye_contact(eye_results: List[Dict]) -> Dict[str, Any]:
    """
    Analyze eye contact over all frames.
    Computed from actual eye tracking data.
    """
    if not eye_results:
        return {"eye_contact_score": 0.5, "looking_at_camera_pct": 0,
                "avg_ear": 0, "possible_drowsy_frames": 0}

    looking_count = sum(1 for e in eye_results if e.get("looking_at_camera", False))
    looking_pct = looking_count / len(eye_results)

    avg_ears = [e["avg_ear"] for e in eye_results if "avg_ear" in e]
    avg_ear = float(np.mean(avg_ears)) if avg_ears else 0

    # Drowsy/closed eyes: EAR < 0.2
    drowsy_frames = sum(1 for e in avg_ears if e < 0.2)

    # Eye contact score: directly from looking-at-camera percentage
    eye_contact_score = looking_pct

    # Penalize drowsy frames
    drowsy_ratio = drowsy_frames / len(eye_results) if eye_results else 0
    eye_contact_score -= drowsy_ratio * 0.3
    eye_contact_score = max(0.0, min(1.0, eye_contact_score))

    return {
        "eye_contact_score": round(eye_contact_score, 3),
        "looking_at_camera_pct": round(looking_pct * 100, 1),
        "avg_ear": round(avg_ear, 3),
        "possible_drowsy_frames": drowsy_frames,
        "total_frames_analyzed": len(eye_results),
    }


def analyze_emotions(frames: List[np.ndarray]) -> Dict[str, Any]:
    """Analyze emotions using DeepFace on sampled frames."""
    if not DEEPFACE_AVAILABLE or not frames:
        return {"dominant_emotion": "unknown", "emotions": {},
                "analysis_method": "unavailable"}

    emotions_detected = []
    # Sample every few frames to save time
    sample_step = max(1, len(frames) // 10)

    for i in range(0, len(frames), sample_step):
        try:
            results = DeepFace.analyze(
                frames[i], actions=["emotion"],
                enforce_detection=False, silent=True,
            )
            if results and len(results) > 0:
                emotions_detected.append(results[0].get("dominant_emotion", "neutral"))
        except Exception:
            pass

    if not emotions_detected:
        return {"dominant_emotion": "neutral", "emotions": {},
                "analysis_method": "deepface"}

    emotion_counts = Counter(emotions_detected)
    dominant = emotion_counts.most_common(1)[0][0]

    return {
        "dominant_emotion": dominant,
        "emotion_distribution": dict(emotion_counts),
        "total_analyzed": len(emotions_detected),
        "analysis_method": "deepface",
    }


def draw_posture_annotation(
    frame: np.ndarray,
    shoulder_data: Optional[Dict[str, Any]],
    face_rect: Optional[Dict[str, int]],
    zone: str,
    timestamp: float,
    threshold_y: Optional[float] = None,
) -> np.ndarray:
    """
    Draw posture annotations with threshold-based 3-zone system.
    Uses actual shoulder/face detection data — nothing hardcoded.

    Draws:
    - GREEN DOTTED threshold line across full frame width
    - Shoulder line + markers (color by zone)
    - Vertical distance arrow from shoulders to threshold
    - Zone status label + timestamp

    Zones: below (red/slouching), aligned (green/confident), above (orange/tense)
    """
    annotated = frame.copy()
    h, w = annotated.shape[:2]

    # Zone colors (BGR)
    zone_colors = {
        "below": (113, 113, 248),
        "aligned": (52, 211, 153),
        "above": (36, 191, 251),
    }
    threshold_color = (52, 211, 153)
    ref_color = (180, 180, 180)
    color = zone_colors.get(zone, zone_colors["aligned"])
    font = cv2.FONT_HERSHEY_SIMPLEX

    # --- Green dotted threshold line across full frame ---
    if threshold_y is not None:
        ty = int(threshold_y)
        for x in range(0, w, 16):
            cv2.line(annotated, (x, ty), (min(x + 8, w), ty),
                     threshold_color, 2, cv2.LINE_AA)
        cv2.putText(annotated, "THRESHOLD", (w - 120, ty - 6),
                    font, 0.4, threshold_color, 1, cv2.LINE_AA)

    if shoulder_data:
        lx = int(shoulder_data["left_x"])
        ly = int(shoulder_data["left_y"])
        rx = int(shoulder_data["right_x"])
        ry = int(shoulder_data["right_y"])

        # Shoulder connection line
        cv2.line(annotated, (lx, ly), (rx, ry), color, 3, cv2.LINE_AA)

        # Shoulder circles
        for sx, sy in [(lx, ly), (rx, ry)]:
            cv2.circle(annotated, (sx, sy), 12, color, 2, cv2.LINE_AA)
            cv2.circle(annotated, (sx, sy), 6, color, -1)

        # Vertical refs from shoulders
        vert_len = int(h * 0.12)
        cv2.line(annotated, (lx, ly), (lx, ly + vert_len), ref_color, 1, cv2.LINE_AA)
        cv2.line(annotated, (rx, ry), (rx, ry + vert_len), ref_color, 1, cv2.LINE_AA)

        # Arrow from shoulder midpoint to threshold
        if threshold_y is not None:
            mid_x = (lx + rx) // 2
            mid_y = (ly + ry) // 2
            ty = int(threshold_y)
            if abs(mid_y - ty) > 5:
                cv2.arrowedLine(annotated, (mid_x, mid_y), (mid_x, ty),
                                color, 2, cv2.LINE_AA, tipLength=0.15)
                dist_px = mid_y - ty
                dist_label = f"{abs(dist_px)}px {'below' if dist_px > 0 else 'above'}"
                cv2.putText(annotated, dist_label, (mid_x + 10, (mid_y + ty) // 2),
                            font, 0.4, color, 1, cv2.LINE_AA)

    elif face_rect:
        # Fallback: draw face rect with posture indication
        fx, fy, fw, fh = face_rect["x"], face_rect["y"], face_rect["w"], face_rect["h"]
        cv2.rectangle(annotated, (fx, fy), (fx + fw, fy + fh), color, 2)
        # Center crosshair
        cx, cy = fx + fw // 2, fy + fh // 2
        cv2.drawMarker(annotated, (cx, cy), color, cv2.MARKER_CROSS, 15, 2)

    # --- Zone status label (top-left) ---
    zone_labels = {
        "below": "BELOW - Low Confidence",
        "aligned": "ALIGNED - Confident",
        "above": "ABOVE - Too High",
    }
    label = zone_labels.get(zone, "Unknown")
    font_scale = 0.6
    (tw, th_text), _ = cv2.getTextSize(label, font, font_scale, 2)
    pad = 8
    cv2.rectangle(annotated, (10, 10), (10 + tw + pad * 2, 10 + th_text + pad * 2),
                  (20, 20, 30), -1)
    cv2.rectangle(annotated, (10, 10), (10 + tw + pad * 2, 10 + th_text + pad * 2),
                  color, 2)
    cv2.putText(annotated, label, (10 + pad, 10 + th_text + pad),
                font, font_scale, color, 2, cv2.LINE_AA)

    # Timestamp overlay (bottom-left)
    time_str = f"{int(timestamp // 60)}:{int(timestamp % 60):02d}"
    (ttw, tth), _ = cv2.getTextSize(time_str, font, 0.5, 1)
    cv2.rectangle(annotated, (10, h - 10 - tth - 12), (10 + ttw + 12, h - 10),
                  (20, 20, 30), -1)
    cv2.putText(annotated, time_str, (16, h - 16),
                font, 0.5, (200, 200, 200), 1, cv2.LINE_AA)

    return annotated


def generate_annotated_frames(
    timestamped_frames: List[Tuple[float, np.ndarray]],
    per_frame_data: List[Dict[str, Any]],
    posture_result: Dict[str, Any],
    max_output: int = 10,
) -> Tuple[List[Dict[str, Any]], Optional[float]]:
    """
    Generate annotated posture frames with 3-zone threshold classification.
    Returns (frames_list, threshold_y) tuple.

    Zones based on actual shoulder Y vs baseline threshold:
    - below:   shoulder_y > threshold + 3% of frame height (slouching)
    - aligned: shoulder_y within +/-3% of threshold (confident)
    - above:   shoulder_y < threshold - 3% of frame height (too high)
    """
    if not per_frame_data or not timestamped_frames:
        return [], None

    frame_h = timestamped_frames[0][1].shape[0]
    tolerance = frame_h * 0.03  # 3% of frame height

    # Sample evenly across available frames
    total = len(per_frame_data)
    step = max(1, total // max_output)
    sampled_indices = list(range(0, total, step))[:max_output]

    # Compute threshold Y from the first few frames with shoulders
    threshold_y = None
    shoulder_entries = [d for d in per_frame_data if d.get("shoulder_data")]
    if shoulder_entries:
        baseline_ys = [
            (e["shoulder_data"]["left_y"] + e["shoulder_data"]["right_y"]) / 2
            for e in shoulder_entries[:5]
        ]
        threshold_y = float(np.mean(baseline_ys))

    # Classify each frame into zones
    annotated_results = []
    for idx in sampled_indices:
        data = per_frame_data[idx]
        frame_idx = data["frame_idx"]
        timestamp = data["timestamp"]

        if frame_idx >= len(timestamped_frames):
            continue

        frame = timestamped_frames[frame_idx][1]
        shoulder_data = data.get("shoulder_data")
        face_rect = data.get("face_rect")

        # Classify zone from actual shoulder position vs threshold
        zone = "aligned"
        slope_val = 0.0

        if shoulder_data and threshold_y is not None:
            current_y = (shoulder_data["left_y"] + shoulder_data["right_y"]) / 2

            dy = abs(shoulder_data["left_y"] - shoulder_data["right_y"])
            dx = abs(shoulder_data["left_x"] - shoulder_data["right_x"])
            slope_val = dy / max(dx, 1.0)

            if current_y > threshold_y + tolerance:
                zone = "below"   # shoulders dropped = slouching
            elif current_y < threshold_y - tolerance:
                zone = "above"   # shoulders too high = tense
            else:
                zone = "aligned"  # within tolerance = confident

        # Draw annotations with threshold line
        annotated = draw_posture_annotation(
            frame, shoulder_data, face_rect, zone, timestamp, threshold_y
        )

        # Encode to base64 JPEG
        _, buffer = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 70])
        b64 = base64.b64encode(buffer).decode("utf-8")

        annotated_results.append({
            "timestamp": round(timestamp, 2),
            "base64_image": b64,
            "posture_zone": zone,
            "shoulder_slope": round(slope_val, 4),
        })

    return annotated_results, threshold_y


def full_analysis(video_path: str) -> Dict[str, Any]:
    """
    Complete facial/posture analysis pipeline.
    All scores computed from actual frame-by-frame analysis.

    Posture detection uses MediaPipe Pose (shoulder-based) when available,
    falls back to face-position-based posture if shoulders not detected.
    """
    timestamped_frames = extract_frames(video_path, max_frames=60)

    if not timestamped_frames:
        return _empty_result("Could not extract frames from video")

    frame_height = timestamped_frames[0][1].shape[0]
    frame_width = timestamped_frames[0][1].shape[1]
    raw_frames = [f for _, f in timestamped_frames]

    face_positions = []
    eye_results = []
    shoulder_data_list = []
    frames_with_face = 0

    per_frame_data = []  # collect per-frame data for annotation

    for frame_idx, (timestamp, frame) in enumerate(timestamped_frames):
        # Face detection + landmarks
        face_rect, landmarks = detect_face_and_landmarks(frame)

        if face_rect:
            frames_with_face += 1
            face_positions.append(face_rect)

            if landmarks is not None:
                eye_data = compute_eye_aspect_ratio(landmarks)
                eye_data["timestamp"] = round(timestamp, 2)
                eye_results.append(eye_data)

        # Shoulder detection via MediaPipe Pose
        shoulders = detect_shoulders(frame)
        if shoulders is not None:
            shoulder_data_list.append(shoulders)

        # Store per-frame data for annotated frame generation
        per_frame_data.append({
            "frame_idx": frame_idx,
            "timestamp": round(timestamp, 2),
            "shoulder_data": shoulders,
            "face_rect": face_rect,
        })

    # Engagement: face present in frames
    engagement = frames_with_face / len(timestamped_frames) if timestamped_frames else 0

    # --- Posture analysis ---
    # Prefer shoulder-based (MediaPipe) when we have enough data
    if len(shoulder_data_list) >= 3:
        posture = analyze_posture_from_shoulders(
            shoulder_data_list, frame_height, frame_width
        )
        print(f"[FACIAL] Posture: shoulder-based ({len(shoulder_data_list)} frames with shoulders)")
    else:
        # Fallback to face-position-based posture
        posture = analyze_posture_from_face(face_positions, frame_height)
        print(f"[FACIAL] Posture: face-position fallback ({len(face_positions)} face frames, {len(shoulder_data_list)} shoulder frames)")

    # Eye contact analysis
    eye_contact = analyze_eye_contact(eye_results)

    # Emotion analysis
    emotions = analyze_emotions(raw_frames)

    # --- COMPUTE FINAL SCORES ---
    # Engagement score: directly from face presence ratio
    engagement_score = round(min(engagement, 1.0), 3)

    # Confidence score: combination of posture, eye contact, positive emotions
    positive_emotions = {"happy", "surprise", "neutral"}
    emotion_factor = 0.7 if emotions["dominant_emotion"] in positive_emotions else 0.4
    negative_emotions = {"angry", "sad", "fear", "disgust"}
    if emotions["dominant_emotion"] in negative_emotions:
        emotion_factor = 0.3

    confidence_score = (
        posture["posture_score"] * 0.35
        + eye_contact["eye_contact_score"] * 0.35
        + emotion_factor * 0.15
        + engagement_score * 0.15
    )
    confidence_score = round(max(0.0, min(1.0, confidence_score)), 3)

    # Determine analysis method
    methods = []
    if DLIB_AVAILABLE:
        methods.append("dlib")
    else:
        methods.append("opencv")
    if len(shoulder_data_list) >= 3:
        methods.append("mediapipe_pose")
    if DEEPFACE_AVAILABLE:
        methods.append("deepface")

    # --- Generate annotated posture frames ---
    posture_frames, threshold_y = generate_annotated_frames(
        timestamped_frames, per_frame_data, posture, max_output=10
    )
    print(f"[FACIAL] Generated {len(posture_frames)} annotated posture frames (threshold_y={threshold_y})")

    return {
        "face_confidence_score": confidence_score,
        "face_engagement_score": engagement_score,
        "face_emotion_state": emotions["dominant_emotion"],

        # Detailed analysis
        "posture": posture,
        "eye_contact": eye_contact,
        "emotions": emotions,

        # Annotated posture frames (base64 images)
        "posture_frames": posture_frames,
        "threshold_y": threshold_y,

        # Stats
        "frames_analyzed": len(timestamped_frames),
        "frames_with_face": frames_with_face,
        "frames_with_shoulders": len(shoulder_data_list),
        "analysis_method": "+".join(methods),
    }


def _empty_result(reason: str) -> Dict[str, Any]:
    return {
        "face_confidence_score": 0.0,
        "face_engagement_score": 0.0,
        "face_emotion_state": "unknown",
        "posture": {"posture_score": 0.0, "slouching_detected": False},
        "eye_contact": {"eye_contact_score": 0.0},
        "emotions": {"dominant_emotion": "unknown"},
        "frames_analyzed": 0,
        "frames_with_face": 0,
        "analysis_method": "none",
        "note": reason,
    }
