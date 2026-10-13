"""
License Management & Verification Module
Generates cryptographically signed, installation-specific license keys with expiration dates.
Validates license authenticity, hardware/installation bindings, and active expiry policy.
"""

import hmac
import hashlib
import json
import base64
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, Optional
from cloud.config import CLOUD_SECRET_KEY


def generate_license_key(
    org_id: str,
    branch_id: str,
    installation_id: str,
    expires_at_iso: str,
    max_employees: int = 50,
    max_cameras: int = 10,
    secret_key: str = CLOUD_SECRET_KEY
) -> str:
    """
    Generate a tamper-proof license string:
    Format: BASE64(PAYLOAD_JSON) + "." + HMAC_SHA256(PAYLOAD_JSON, SECRET)
    """
    payload = {
        "org_id": org_id,
        "branch_id": branch_id,
        "installation_id": installation_id,
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": expires_at_iso,
        "max_employees": max_employees,
        "max_cameras": max_cameras
    }
    
    payload_json = json.dumps(payload, sort_keys=True)
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode('utf-8')).decode('utf-8').rstrip('=')
    
    signature = hmac.new(
        secret_key.encode('utf-8'),
        payload_b64.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return f"QILIC-{payload_b64}.{signature}"


def verify_license_key(
    license_key: str,
    expected_installation_id: Optional[str] = None,
    secret_key: str = CLOUD_SECRET_KEY
) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """
    Verify signature, installation ID binding, and expiry date.
    
    Returns:
    (is_valid: bool, payload: Optional[dict], message: str)
    """
    if not license_key or not license_key.startswith("QILIC-"):
        return False, None, "Invalid license key format"
        
    try:
        token_body = license_key[len("QILIC-"):]
        if "." not in token_body:
            return False, None, "Malformed license key structure"
            
        payload_b64, signature = token_body.split(".", 1)
        
        # Verify HMAC signature
        expected_sig = hmac.new(
            secret_key.encode('utf-8'),
            payload_b64.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected_sig):
            return False, None, "License key signature verification failed (tampered key)"
            
        # Decode payload
        # Pad base64 if needed
        padding = 4 - (len(payload_b64) % 4)
        if padding != 4:
            payload_b64_padded = payload_b64 + ('=' * padding)
        else:
            payload_b64_padded = payload_b64
            
        payload_json = base64.urlsafe_b64decode(payload_b64_padded.encode('utf-8')).decode('utf-8')
        payload = json.loads(payload_json)
        
        # Verify installation binding
        if expected_installation_id and payload.get("installation_id") != expected_installation_id:
            return False, payload, f"License installation mismatch: bound to '{payload.get('installation_id')}', but request has '{expected_installation_id}'"
            
        # Verify expiration date
        expires_at_str = payload.get("expires_at")
        if not expires_at_str:
            return False, payload, "License missing expiry date"
            
        expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        
        # Ensure timezone compatibility
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
            
        if now > expires_at:
            return False, payload, f"License expired on {expires_at.strftime('%Y-%m-%d %H:%M:%S UTC')}"
            
        return True, payload, "License is active and valid"
    except Exception as e:
        return False, None, f"Error validating license key: {str(e)}"
