"""
Flask AI Attendance System
- Enrollment: Upload video, extract embeddings, store profile
- Recognition: Camera/RTSP feed, detect faces, match against profiles, log attendance
"""

from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import json
import numpy as np
from datetime import datetime
from pathlib import Path
import mimetypes

import database as db
import face_processor as fp
from download_models import verify_models
from logger_config import get_logger
from config import (
    UPLOAD_FOLDER, ALLOWED_EXTENSIONS, IMAGE_EXTENSIONS,
    MAX_CONTENT_LENGTH, FACE_MATCHING_THRESHOLD,
    MIN_ENROLLMENT_FRAMES, OPTIMAL_FACES_PER_VIDEO,
    MIN_VIDEO_DURATION, MAX_VIDEO_DURATION
)

logger = get_logger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configuration
UPLOAD_FOLDER.mkdir(exist_ok=True)

app.config['UPLOAD_FOLDER'] = str(UPLOAD_FOLDER)
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH


def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ============================================
# ENROLLMENT ENDPOINTS
# ============================================

@app.route('/api/enroll/create-user', methods=['POST'])
def create_user():
    """Create a new user for enrollment."""
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    
    if not name:
        return jsonify({'error': 'Name is required'}), 400
    
    user_id = db.add_user(name, email)
    if user_id:
        return jsonify({
            'success': True,
            'user_id': user_id,
            'name': name,
            'message': f'User {name} created successfully'
        }), 201
    else:
        return jsonify({'error': f'User {name} already exists'}), 409


@app.route('/api/enroll/upload-video', methods=['POST'])
def upload_enrollment_video():
    """Upload 15sec enrollment video and extract embeddings."""
    if 'video' not in request.files:
        return jsonify({'error': 'No video provided'}), 400
    
    user_id = request.form.get('user_id')
    if not user_id:
        return jsonify({'error': 'user_id is required'}), 400
    
    try:
        user_id = int(user_id)
    except ValueError:
        return jsonify({'error': 'Invalid user_id'}), 400
    
    video_file = request.files['video']
    
    if video_file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if not allowed_file(video_file.filename):
        return jsonify({'error': f'Allowed formats: {", ".join(ALLOWED_EXTENSIONS)}'}), 400
    
    # Save uploaded video
    filename = secure_filename(f"{user_id}_{datetime.now().timestamp()}.mp4")
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    video_file.save(filepath)
    
    print(f"[*] Processing enrollment video: {filepath}")
    
    try:
        # Extract embeddings from video
        embeddings = fp.process_enrollment_video(filepath, max_frames=60)
        
        if len(embeddings) == 0:
            return jsonify({
                'error': 'No faces detected in video. Please ensure faces are clearly visible.'
            }), 400
        
        # Store each embedding
        for embedding in embeddings:
            embedding_list = embedding.tolist()
            db.store_embedding(user_id, embedding_list, filename)
        
        # Get user info
        user = db.get_user_by_name(db.get_all_users()[0]['name'])
        
        return jsonify({
            'success': True,
            'user_id': user_id,
            'embeddings_count': len(embeddings),
            'message': f'Successfully stored {len(embeddings)} embeddings'
        }), 200
    
    except Exception as e:
        return jsonify({'error': f'Processing failed: {str(e)}'}), 500
    finally:
        # Clean up uploaded video after processing
        if os.path.exists(filepath):
            os.remove(filepath)


@app.route('/api/enroll/status/<int:user_id>', methods=['GET'])
def enrollment_status(user_id):
    """Check enrollment status for a user."""
    embeddings = db.get_embeddings_for_user(user_id)
    
    if len(embeddings) == 0:
        return jsonify({
            'enrolled': False,
            'user_id': user_id,
            'embeddings_count': 0,
            'message': 'User not yet enrolled'
        }), 200
    
    return jsonify({
        'enrolled': True,
        'user_id': user_id,
        'embeddings_count': len(embeddings),
        'created_at': embeddings[0]['created_at'],
        'message': f'User enrolled with {len(embeddings)} embeddings'
    }), 200


# ============================================
# RECOGNITION ENDPOINTS
# ============================================

@app.route('/api/recognize/frame', methods=['POST'])
def recognize_face_frame():
    """
    Recognize face in a single frame.
    POST image data (base64 or file) -> returns matched user or 'unknown'
    """
    if 'image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400
    
    image_file = request.files['image']
    
    try:
        import cv2
        # Read image
        image_bytes = image_file.read()
        nparr = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            return jsonify({'error': 'Invalid image'}), 400
        
        # Detect faces
        detections = fp.detect_faces_yolo(frame)
        
        if len(detections) == 0:
            return jsonify({
                'recognized': False,
                'detected_faces': 0,
                'message': 'No faces detected'
            }), 200
        
        results = []
        
        for x1, y1, x2, y2, conf in detections:
            # Extract embedding
            test_embedding = fp.extract_embeddings_insightface(frame, (x1, y1, x2, y2))
            
            if test_embedding is None:
                continue
            
            # Compare against all enrolled users
            best_match = None
            best_similarity = -1
            
            all_users = db.get_all_users()
            for user in all_users:
                user_embeddings = db.get_embeddings_for_user(user['id'])
                
                if len(user_embeddings) == 0:
                    continue
                
                # Compute aggregate embedding
                user_embs = [np.array(emb['embedding']) for emb in user_embeddings]
                aggregate_emb = fp.compute_aggregate_embedding(user_embs)
                
                # Compare
                similarity, is_match = fp.compare_embeddings(aggregate_emb, test_embedding, threshold=0.6)
                
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = user if is_match else None
            
            results.append({
                'face_bbox': [x1, y1, x2, y2],
                'detected_confidence': float(conf),
                'matched_user': best_match['name'] if best_match else 'Unknown',
                'similarity': float(best_similarity),
                'is_match': best_match is not None
            })
            
            # Log attendance if matched
            if best_match:
                db.log_attendance(
                    best_match['id'],
                    best_match['name'],
                    float(best_similarity),
                    'frame'
                )
        
        return jsonify({
            'recognized': len([r for r in results if r['is_match']]) > 0,
            'detections': results,
            'total_faces_detected': len(detections),
            'timestamp': datetime.now().isoformat()
        }), 200
    
    except Exception as e:
        return jsonify({'error': f'Recognition failed: {str(e)}'}), 500


@app.route('/api/recognize/rtsp', methods=['POST'])
def recognize_rtsp_stream():
    """
    Recognize faces from RTSP stream (e.g., NVR, DVR, IP camera).
    Run in background or return stream setup info.
    """
    data = request.get_json()
    rtsp_url = data.get('rtsp_url')
    frames_to_process = data.get('frames', 10)
    
    if not rtsp_url:
        return jsonify({'error': 'rtsp_url is required'}), 400
    
    try:
        import cv2
        cap = cv2.VideoCapture(rtsp_url)
        
        if not cap.isOpened():
            return jsonify({'error': 'Cannot connect to RTSP stream'}), 400
        
        results = []
        frame_count = 0
        
        while frame_count < frames_to_process:
            ret, frame = cap.read()
            
            if not ret:
                break
            
            # Detect faces
            detections = fp.detect_faces_yolo(frame)
            
            for x1, y1, x2, y2, conf in detections:
                test_embedding = fp.extract_embeddings_insightface(frame, (x1, y1, x2, y2))
                
                if test_embedding is None:
                    continue
                
                # Find best match
                best_match = None
                best_similarity = -1
                
                all_users = db.get_all_users()
                for user in all_users:
                    user_embeddings = db.get_embeddings_for_user(user['id'])
                    
                    if len(user_embeddings) == 0:
                        continue
                    
                    user_embs = [np.array(emb['embedding']) for emb in user_embeddings]
                    aggregate_emb = fp.compute_aggregate_embedding(user_embs)
                    similarity, is_match = fp.compare_embeddings(aggregate_emb, test_embedding, threshold=0.6)
                    
                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_match = user if is_match else None
                
                if best_match:
                    results.append(best_match['name'])
                    db.log_attendance(
                        best_match['id'],
                        best_match['name'],
                        float(best_similarity),
                        'rtsp'
                    )
            
            frame_count += 1
        
        cap.release()
        
        return jsonify({
            'status': 'completed',
            'recognized_users': results,
            'frames_processed': frame_count,
            'timestamp': datetime.now().isoformat()
        }), 200
    
    except Exception as e:
        return jsonify({'error': f'RTSP recognition failed: {str(e)}'}), 500


# ============================================
# ADMIN/DASHBOARD ENDPOINTS
# ============================================

@app.route('/api/users', methods=['GET'])
def get_users():
    """Get all enrolled users."""
    users = db.get_all_users()
    return jsonify({'users': users}), 200


@app.route('/api/attendance/logs', methods=['GET'])
def get_attendance_logs():
    """Get recent attendance logs."""
    limit = request.args.get('limit', 100, type=int)
    logs = db.get_attendance_logs(limit)
    return jsonify({'logs': logs}), 200


@app.route('/api/attendance/user/<int:user_id>', methods=['GET'])
def get_user_attendance(user_id):
    """Get attendance history for a specific user."""
    days = request.args.get('days', 7, type=int)
    logs = db.get_attendance_by_user(user_id, days)
    return jsonify({'user_id': user_id, 'logs': logs, 'days': days}), 200


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get overall attendance statistics."""
    users = db.get_all_users()
    all_logs = db.get_attendance_logs(10000)
    
    return jsonify({
        'total_users': len(users),
        'today_attendance': len([l for l in all_logs if l['timestamp'].startswith(datetime.now().strftime('%Y-%m-%d'))]),
        'total_logs': len(all_logs),
        'timestamp': datetime.now().isoformat()
    }), 200


# ============================================
# HEALTH & INITIALIZATION
# ============================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    }), 200


@app.route('/api/init', methods=['POST'])
def initialize_system():
    """Initialize system: download models and create database."""
    try:
        # Initialize database
        db.init_db()
        
        # Verify models
        models_ok = verify_models()
        
        if models_ok:
            return jsonify({
                'status': 'initialized',
                'database': 'ready',
                'models': 'ready',
                'message': 'System ready for enrollment and recognition'
            }), 200
        else:
            return jsonify({
                'status': 'partial',
                'database': 'ready',
                'models': 'incomplete',
                'message': 'Database ready but some models failed'
            }), 202
    
    except Exception as e:
        return jsonify({
            'status': 'failed',
            'error': str(e)
        }), 500


# ============================================
# ERROR HANDLERS
# ============================================

@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle file size limit exceeded."""
    return jsonify({'error': 'File too large. Max size: 500MB'}), 413


@app.errorhandler(404)
def not_found(error):
    """Handle 404."""
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500."""
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    # Initialize on startup
    db.init_db()
    
    print("\n" + "="*60)
    print("Flask AI Attendance System")
    print("="*60)
    print("Starting server on http://localhost:5000")
    print("Initialize: POST http://localhost:5000/api/init")
    print("="*60 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
