"""Face detection and embedding extraction using YOLO + InsightFace."""

import cv2
import numpy as np
import insightface
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from ultralytics import YOLO
from logger_config import get_logger
from config import (
    YOLO_MODEL, INSIGHTFACE_MODEL, MODELS_DIR,
    FACE_DETECTION_CONFIDENCE, FACE_QUALITY_THRESHOLD,
    ANTI_SPOOFING_ENABLED, ENABLE_GPU
)

logger = get_logger(__name__)

# Global models (lazy loaded)
_yolo_model = None
_insightface_model = None


def get_yolo_model():
    """Lazy load YOLO model with GPU support."""
    global _yolo_model
    if _yolo_model is None:
        try:
            logger.info(f"Loading YOLO model: {YOLO_MODEL}")
            _yolo_model = YOLO(YOLO_MODEL)
            logger.info("✓ YOLO model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            raise
    return _yolo_model


def get_insightface_model():
    """Lazy load InsightFace model with GPU support."""
    global _insightface_model
    if _insightface_model is None:
        try:
            logger.info(f"Loading InsightFace model: {INSIGHTFACE_MODEL}")
            
            # Auto-detect providers
            providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
            if not ENABLE_GPU:
                providers = ['CPUExecutionProvider']
            
            _insightface_model = insightface.app.FaceAnalysis(
                name=INSIGHTFACE_MODEL,
                root=str(MODELS_DIR),
                providers=providers
            )
            ctx_id = 0 if ENABLE_GPU else -1
            _insightface_model.prepare(ctx_id=ctx_id, det_thresh=FACE_DETECTION_CONFIDENCE, det_size=(640, 640))
            logger.info("✓ InsightFace model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load InsightFace model: {e}")
            raise
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
    Detect faces using YOLOv8 with enhanced validation.
    
    Args:
        frame: Input image
    
    Returns:
        List of [x1, y1, x2, y2, confidence]
    """
    try:
        yolo = get_yolo_model()
        results = yolo(frame, verbose=False, conf=FACE_DETECTION_CONFIDENCE)
        
        detections = []
        if len(results) > 0:
            boxes = results[0].boxes
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                conf = float(box.conf[0].cpu().numpy())
                
                # Validate detection
                if conf >= FACE_DETECTION_CONFIDENCE:
                    detections.append((x1, y1, x2, y2, conf))
        
        return detections
    except Exception as e:
        logger.error(f"YOLO detection failed: {e}")
        return []


def assess_face_quality(frame: np.ndarray, face_bbox: Tuple[int, int, int, int]) -> Dict:
    """
    Assess quality of detected face.
    
    Args:
        frame: Input image
        face_bbox: [x1, y1, x2, y2]
    
    Returns:
        Quality assessment dict with score 0-1
    """
    try:
        x1, y1, x2, y2 = face_bbox
        
        # Validate bbox
        if x1 < 0 or y1 < 0 or x2 > frame.shape[1] or y2 > frame.shape[0]:
            return {'score': 0, 'issues': ['bbox_out_of_bounds']}
        
        cropped = frame[y1:y2, x1:x2]
        h, w = cropped.shape[:2]
        
        issues = []
        score = 1.0
        
        # Check face size (too small = low quality)
        if h < 40 or w < 40:
            issues.append('face_too_small')
            score -= 0.3
        
        # Check lighting (using Laplacian for focus/blur detection)
        gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        
        if laplacian_var < 100:  # Blurry image
            issues.append('blurry')
            score -= 0.2
        
        # Check brightness (avoid extreme dark/bright)
        mean_brightness = np.mean(gray)
        if mean_brightness < 30 or mean_brightness > 220:
            issues.append('poor_lighting')
            score -= 0.1
        
        # Check aspect ratio
        aspect_ratio = w / h
        if aspect_ratio < 0.6 or aspect_ratio > 1.4:
            issues.append('poor_aspect_ratio')
            score -= 0.15
        
        return {
            'score': max(0, min(1, score)),
            'issues': issues,
            'laplacian_var': float(laplacian_var),
            'brightness': float(mean_brightness),
            'aspect_ratio': float(aspect_ratio)
        }
    except Exception as e:
        logger.warning(f"Face quality assessment failed: {e}")
        return {'score': 0.5, 'issues': ['assessment_error']}


def detect_spoofing(frame: np.ndarray, face_bbox: Tuple[int, int, int, int]) -> Dict:
    """
    Detect if face is a spoof (photo, video, mask).
    Uses texture analysis and frequency domain techniques.
    
    Args:
        frame: Input image
        face_bbox: [x1, y1, x2, y2]
    
    Returns:
        Spoof assessment dict
    """
    if not ANTI_SPOOFING_ENABLED:
        return {'is_spoof': False, 'confidence': 1.0, 'method': 'disabled'}
    
    try:
        x1, y1, x2, y2 = face_bbox
        cropped = frame[y1:y2, x1:x2]
        gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
        
        # Method 1: Texture Analysis (LBP-like)
        # Real faces have more texture variation than photos
        h, w = gray.shape
        if h < 20 or w < 20:
            return {'is_spoof': False, 'confidence': 0.5, 'method': 'skip_too_small'}
        
        # Compute local binary patterns (simplified)
        edges = cv2.Canny(gray, 100, 200)
        edge_density = np.sum(edges > 0) / (h * w)
        
        # Method 2: Frequency Domain (FFT)
        # Photos often have less high-frequency content
        fft = np.fft.fft2(gray)
        fft_shift = np.fft.fftshift(fft)
        magnitude = np.abs(fft_shift)
        
        # Compute spectrum ratio (high-freq / low-freq)
        center = (h // 2, w // 2)
        region_size = min(h, w) // 4
        
        low_freq = magnitude[
            center[0]-region_size:center[0]+region_size,
            center[1]-region_size:center[1]+region_size
        ].sum()
        
        high_freq = magnitude.sum() - low_freq
        spectrum_ratio = high_freq / (low_freq + 1e-6)
        
        # Real faces have higher spectrum ratio
        is_spoof = spectrum_ratio < 0.5
        confidence = min(1.0, abs(spectrum_ratio - 0.5) / 0.5)
        
        return {
            'is_spoof': is_spoof,
            'confidence': float(confidence),
            'method': 'frequency_domain',
            'spectrum_ratio': float(spectrum_ratio),
            'edge_density': float(edge_density)
        }
    except Exception as e:
        logger.warning(f"Spoof detection failed: {e}")
        return {'is_spoof': False, 'confidence': 0.5, 'method': 'error'}


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


def process_enrollment_video(video_path: str, max_frames: int = 60) -> Dict:
    """
    Process enrollment video with quality checks and filtering.
    
    Args:
        video_path: Path to enrollment video
        max_frames: Max frames to process
    
    Returns:
        Dict with embeddings, quality metrics, and issues
    """
    try:
        frames = extract_frames_from_video(video_path, max_frames)
        
        if not frames:
            logger.warning(f"No frames extracted from {video_path}")
            return {
                'success': False,
                'embeddings': [],
                'error': 'No frames extracted',
                'total_frames': 0
            }
        
        embeddings = []
        quality_scores = []
        spoof_detections = []
        issues = []
        
        for i, frame in enumerate(frames):
            # Detect faces
            detections = detect_faces_yolo(frame)
            
            if len(detections) == 0:
                continue
            
            # Get largest face (primary face in frame)
            largest_det = max(detections, key=lambda d: (d[2] - d[0]) * (d[3] - d[1]))
            x1, y1, x2, y2, conf = largest_det
            face_bbox = (x1, y1, x2, y2)
            
            # Assess face quality
            quality_info = assess_face_quality(frame, face_bbox)
            quality_scores.append(quality_info['score'])
            
            if quality_info['score'] < FACE_QUALITY_THRESHOLD:
                issues.append(f"Frame {i}: Low quality - {quality_info['issues']}")
                continue
            
            # Detect spoofing
            spoof_info = detect_spoofing(frame, face_bbox)
            spoof_detections.append(spoof_info)
            
            if spoof_info['is_spoof']:
                issues.append(f"Frame {i}: Possible spoof detected")
                continue
            
            # Extract embedding
            embedding = extract_embeddings_insightface(frame, face_bbox)
            
            if embedding is not None:
                embeddings.append(embedding)
        
        logger.info(f"Processed {len(frames)} frames: {len(embeddings)} valid embeddings")
        
        return {
            'success': len(embeddings) > 0,
            'embeddings': embeddings,
            'total_frames': len(frames),
            'valid_embeddings': len(embeddings),
            'avg_quality': float(np.mean(quality_scores)) if quality_scores else 0,
            'spoof_issues': sum(1 for s in spoof_detections if s['is_spoof']),
            'issues': issues
        }
    
    except Exception as e:
        logger.error(f"Video processing failed: {e}")
        return {
            'success': False,
            'embeddings': [],
            'error': str(e),
            'total_frames': 0
        }


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
