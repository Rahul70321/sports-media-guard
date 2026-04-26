import cv2
import imagehash
from PIL import Image
import tempfile
import os

def generate_image_fingerprint(image_path: str) -> str:
    """Generates a perceptual hash for an image."""
    try:
        img = Image.open(image_path)
        # Using phash (perceptual hash) which is robust to slight edits like color/contrast/compression
        hash_val = imagehash.phash(img)
        return str(hash_val)
    except Exception as e:
        print(f"Error generating image fingerprint: {e}")
        return ""

def generate_video_fingerprint(video_path: str) -> str:
    """
    Generates a fingerprint for a video by taking a representative frame 
    (e.g., at the 1-second mark or middle) and generating a phash.
    For MVP, we just take one frame. In a real system, we'd hash multiple frames.
    """
    try:
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        
        # Read a frame at approx 1 second
        frame_idx = int(fps) if fps > 0 else 24
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        
        ret, frame = cap.read()
        cap.release()
        
        if not ret:
            print("Failed to extract frame from video")
            return ""
        
        # Convert cv2 image (BGR) to PIL image (RGB)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(frame_rgb)
        
        hash_val = imagehash.phash(pil_img)
        return str(hash_val)
    except Exception as e:
        print(f"Error generating video fingerprint: {e}")
        return ""

def generate_fingerprint(file_path: str, media_type: str) -> str:
    if media_type == 'image':
        return generate_image_fingerprint(file_path)
    elif media_type == 'video':
        return generate_video_fingerprint(file_path)
    return ""
