"""
Configuration and constants for the attendance system.
"""

import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent
UPLOAD_FOLDER = BASE_DIR / 'uploads'
MODELS_DIR = BASE_DIR / 'models'
DB_PATH = BASE_DIR / 'attendance.db'
LOG_DIR = BASE_DIR / 'logs'

# Create directories
for folder in [UPLOAD_FOLDER, MODELS_DIR, LOG_DIR]:
    folder.mkdir(exist_ok=True)

# Face Detection & Embedding
YOLO_MODEL = 'yolov8n.pt'
INSIGHTFACE_MODEL = 'buffalo_l'
FACE_DETECTION_CONFIDENCE = 0.5
FACE_MATCHING_THRESHOLD = 0.6  # Cosine similarity threshold
FACE_QUALITY_THRESHOLD = 0.7  # Face quality score (0-1)
MIN_EMBEDDINGS_PER_USER = 5  # Minimum embeddings for robust profile

# Enrollment Settings
MAX_ENROLLMENT_FRAMES = 120  # Max frames to extract from video
MIN_ENROLLMENT_FRAMES = 10   # Minimum faces to detect
OPTIMAL_FACES_PER_VIDEO = 40  # Target number of faces
MIN_VIDEO_DURATION = 5  # Seconds
MAX_VIDEO_DURATION = 300  # Seconds (5 minutes)

# RTSP/Camera Settings
RTSP_CONNECTION_TIMEOUT = 10  # Seconds
RTSP_READ_TIMEOUT = 5  # Seconds
RTSP_MAX_FRAMES_PER_STREAM = 500  # Safety limit
RTSP_FRAME_SKIP = 5  # Process every Nth frame (for performance)

# Flask Settings
MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500 MB
UPLOAD_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'flv', 'wmv'}
IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'bmp', 'webp'}

# Recognition Settings
ATTENDANCE_LOG_RETENTION_DAYS = 365  # Keep 1 year of logs
RECOGNITION_CONFIDENCE_THRESHOLD = 0.6  # Only log if above this
ANTI_SPOOFING_ENABLED = True  # Enable spoof detection
DUPLICATE_LOG_TIMEOUT = 30  # Seconds - don't log same person twice

# Performance
BATCH_PROCESSING_ENABLED = True
BATCH_SIZE = 5  # Process N users at a time
ENABLE_GPU = True  # Auto-detect CUDA

# Logging
LOG_LEVEL = 'INFO'
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_MAX_SIZE = 10 * 1024 * 1024  # 10 MB
LOG_BACKUP_COUNT = 5

# Security
ALLOW_LOCALHOST_ONLY = False  # Set True for local-only access
CORS_ENABLED = True
REQUEST_TIMEOUT = 60  # Seconds

# Database Queries
BATCH_QUERY_SIZE = 1000
AUTO_VACUUM_INTERVAL = 1000  # Optimize DB every N operations
