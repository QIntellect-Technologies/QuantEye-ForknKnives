"""Face detection and embedding extraction using YOLO + InsightFace."""

import cv2
import numpy as np
import insightface
from pathlib import Path
from typing import List, Tuple, Optional
from ultralytics import YOLO


# Global models (lazy loaded)
_yolo_model = None
_insightface_model = None


def get_yolo_model():
    """Lazy load YOLO model."""
    global _yolo_model
    if _yolo_model is None:
        _yolo_model = YOLO('yolov8n.pt')
    return _yolo_model


def get_insightface_model():
    """Lazy load InsightFace model."""
    global _insightface_model
    if _insightface_model is None:
        _insightface_model = insightface.app.FaceAnalysis(
            name='buffalo_l',
            root='./models',
            providers=['CUDAExecutionProvider', 'CPUExecutionProvider']
        )
        _insightface_model.prepare(ctx_id=0, det_thresh=0.5, det_size=(640, 640))
    return _insightface_model


def extract_frames_from_video(video_path: str, max_frames: int = 60) -> List[np.ndarray]:
    """
    Extract frames from a video file.
    
    Args:
        video_path: Path to video file
        max_frames: Maximum frames to extract (spread evenly across video)
    
    Returns:
        List of frame arrays
    """
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frames = []
    
    if total_frames == 0:
        cap.release()
        return frames
    
    # Calculate frame interval to spread extraction evenly
    frame_interval = max(1, total_frames // max_frames)
    frame_idx = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        if frame_idx % frame_interval == 0:
            frames.append(frame)
        
        frame_idx += 1
    
    cap.release()
    print(f"✓ Extracted {len(frames)} frames from video")
    return frames


def detect_faces_yolo(frame: np.ndarray) -> List[Tuple[int, int, int, int, float]]:
    """
    Detect faces using YOLOv8.
    
    Args:
        frame: Input image
    
    Returns:
        List of [x1, y1, x2, y2, confidence]
    """
    yolo = get_yolo_model()
    results = yolo(frame, verbose=False)
    
    detections = []
    if len(results) > 0:
        boxes = results[0].boxes
        for box in boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
            conf = float(box.conf[0].cpu().numpy())
            detections.append((x1, y1, x2, y2, conf))
    
    return detections


def extract_embeddings_insightface(frame: np.ndarray, face_bbox: Optional[Tuple] = None) -> Optional[np.ndarray]:
    """
    Extract face embedding using InsightFace.
    
    Args:
        frame: Input image
        face_bbox: Optional [x1, y1, x2, y2] to crop face first
    
    Returns:
        Face embedding (512-dim vector) or None if no face detected
    """
    insightface_model = get_insightface_model()
    
    # Crop to bbox if provided
    if face_bbox:
        x1, y1, x2, y2 = face_bbox
        cropped = frame[y1:y2, x1:x2]
    else:
        cropped = frame
    
    # Ensure frame is in RGB
    if len(cropped.shape) == 3 and cropped.shape[2] == 3:
        cropped_rgb = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB)
    else:
        cropped_rgb = cropped
    
    faces = insightface_model.get(cropped_rgb)
    
    if len(faces) > 0:
        # Return largest face embedding
        face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
        return face.embedding
    
    return None


def process_enrollment_video(video_path: str, max_frames: int = 60) -> List[np.ndarray]:
    """
    Process enrollment video: extract frames, detect faces, compute embeddings.
    Aggregate embeddings to get a robust user profile.
    
    Args:
        video_path: Path to enrollment video
        max_frames: Max frames to process
    
    Returns:
        List of valid embeddings
    """
    frames = extract_frames_from_video(video_path, max_frames)
    
    if not frames:
        print("✗ No frames extracted from video")
        return []
    
    embeddings = []
    
    for i, frame in enumerate(frames):
        # Detect faces
        detections = detect_faces_yolo(frame)
        
        if len(detections) == 0:
            continue
        
        # Get largest face (primary face in frame)
        largest_det = max(detections, key=lambda d: (d[2] - d[0]) * (d[3] - d[1]))
        x1, y1, x2, y2, conf = largest_det
        
        # Extract embedding
        embedding = extract_embeddings_insightface(frame, (x1, y1, x2, y2))
        
        if embedding is not None:
            embeddings.append(embedding)
    
    print(f"✓ Extracted {len(embeddings)} valid embeddings from {len(frames)} frames")
    return embeddings


def compute_aggregate_embedding(embeddings: List[np.ndarray]) -> np.ndarray:
    """
    Compute aggregate embedding from multiple face embeddings.
    
    Args:
        embeddings: List of embedding vectors
    
    Returns:
        Mean embedding normalized
    """
    if len(embeddings) == 0:
        return None
    
    embeddings = np.array(embeddings)
    aggregate = np.mean(embeddings, axis=0)
    
    # Normalize
    aggregate = aggregate / (np.linalg.norm(aggregate) + 1e-6)
    
    return aggregate


def compare_embeddings(embedding1: np.ndarray, embedding2: np.ndarray, threshold: float = 0.6) -> Tuple[float, bool]:
    """
    Compare two embeddings using cosine similarity.
    
    Args:
        embedding1: Reference embedding
        embedding2: Test embedding
        threshold: Similarity threshold for match
    
    Returns:
        (similarity_score, is_match)
    """
    # Normalize
    emb1 = embedding1 / (np.linalg.norm(embedding1) + 1e-6)
    emb2 = embedding2 / (np.linalg.norm(embedding2) + 1e-6)
    
    # Cosine similarity
    similarity = np.dot(emb1, emb2)
    is_match = similarity >= threshold
    
    return float(similarity), is_match


if __name__ == '__main__':
    # Test models load
    print("[*] Testing model loading...")
    yolo = get_yolo_model()
    insightface_model = get_insightface_model()
    print("✓ All models loaded successfully")
