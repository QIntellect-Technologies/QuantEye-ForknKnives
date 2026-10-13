"""
Quick test script to verify the system works end-to-end.
"""

import os
import sys
import json
import numpy as np
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

import database as db
import face_processor as fp
from download_models import verify_models


def test_database():
    """Test database operations."""
    print("\n[TEST] Database Operations")
    print("-" * 50)
    
    # Initialize DB
    db.init_db()
    
    # Add test user
    user_id = db.add_user("Test User", "test@example.com")
    if user_id:
        print("✓ User created")
    else:
        print("✗ User creation failed")
        return False
    
    # Retrieve user
    user = db.get_user_by_name("Test User")
    if user and user['id'] == user_id:
        print("✓ User retrieved")
    else:
        print("✗ User retrieval failed")
        return False
    
    # Store test embedding
    test_embedding = np.random.randn(512).tolist()
    db.store_embedding(user_id, test_embedding, "test_video.mp4")
    print("✓ Embedding stored")
    
    # Retrieve embeddings
    embeddings = db.get_embeddings_for_user(user_id)
    if len(embeddings) > 0:
        print(f"✓ Embeddings retrieved ({len(embeddings)} total)")
    else:
        print("✗ Embedding retrieval failed")
        return False
    
    # Log attendance
    db.log_attendance(user_id, "Test User", 0.95, "test")
    print("✓ Attendance logged")
    
    # Get logs
    logs = db.get_attendance_logs(10)
    if len(logs) > 0:
        print(f"✓ Logs retrieved ({len(logs)} total)")
    else:
        print("✗ Log retrieval failed")
        return False
    
    return True


def test_models():
    """Test model loading."""
    print("\n[TEST] Model Loading")
    print("-" * 50)
    
    if verify_models():
        print("✓ All models loaded successfully")
        return True
    else:
        print("✗ Model loading failed")
        return False


def test_embedding_comparison():
    """Test embedding comparison."""
    print("\n[TEST] Embedding Comparison")
    print("-" * 50)
    
    # Create similar embeddings
    emb1 = np.random.randn(512)
    emb2 = emb1 + np.random.randn(512) * 0.1  # Similar with noise
    emb3 = np.random.randn(512)  # Completely different
    
    # Compare
    sim12, match12 = fp.compare_embeddings(emb1, emb2, threshold=0.6)
    sim13, match13 = fp.compare_embeddings(emb1, emb3, threshold=0.6)
    
    print(f"✓ Similar embeddings: {sim12:.3f} (match: {match12})")
    print(f"✓ Different embeddings: {sim13:.3f} (match: {match13})")
    
    if match12 and not match13:
        print("✓ Comparison logic correct")
        return True
    else:
        print("✗ Comparison logic issue")
        return False


def test_aggregate_embedding():
    """Test embedding aggregation."""
    print("\n[TEST] Embedding Aggregation")
    print("-" * 50)
    
    # Create multiple embeddings
    embeddings = [np.random.randn(512) for _ in range(10)]
    
    # Aggregate
    aggregate = fp.compute_aggregate_embedding(embeddings)
    
    if aggregate is not None and len(aggregate) == 512:
        norm = np.linalg.norm(aggregate)
        print(f"✓ Aggregate embedding computed")
        print(f"✓ Embedding norm: {norm:.3f} (should be ~1.0)")
        if 0.9 <= norm <= 1.1:
            print("✓ Embedding normalized correctly")
            return True
    
    print("✗ Aggregation failed")
    return False


def run_all_tests():
    """Run all tests."""
    print("\n" + "=" * 50)
    print("Flask AI Attendance System - Test Suite")
    print("=" * 50)
    
    results = []
    
    # Test 1: Models
    try:
        results.append(("Model Loading", test_models()))
    except Exception as e:
        print(f"✗ Model test error: {e}")
        results.append(("Model Loading", False))
    
    # Test 2: Database
    try:
        results.append(("Database Operations", test_database()))
    except Exception as e:
        print(f"✗ Database test error: {e}")
        results.append(("Database Operations", False))
    
    # Test 3: Embedding Comparison
    try:
        results.append(("Embedding Comparison", test_embedding_comparison()))
    except Exception as e:
        print(f"✗ Comparison test error: {e}")
        results.append(("Embedding Comparison", False))
    
    # Test 4: Aggregation
    try:
        results.append(("Embedding Aggregation", test_aggregate_embedding()))
    except Exception as e:
        print(f"✗ Aggregation test error: {e}")
        results.append(("Embedding Aggregation", False))
    
    # Summary
    print("\n" + "=" * 50)
    print("Test Summary")
    print("=" * 50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} passed")
    print("=" * 50)
    
    return passed == total


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
