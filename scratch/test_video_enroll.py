import sys
sys.path.insert(0, ".")
import face_processor as fp

video_path = "uploads/nvr_enroll_33_1779360621.940326.mp4"
print(f"Testing video enrollment extraction on: {video_path}")
res = fp.process_enrollment_video(video_path, max_frames=30)
print("Result success:", res.get('success'))
print("Total frames:", res.get('total_frames'))
print("Valid faces:", res.get('valid_faces'))
print("Embeddings count:", len(res.get('embeddings', [])))
print("Avg quality:", res.get('avg_quality'))
print("Issues:", res.get('issues'))
