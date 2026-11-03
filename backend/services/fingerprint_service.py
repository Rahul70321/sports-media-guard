"""
Multi-Algorithm Fingerprint Service
Generates phash, dhash, and color histogram fingerprints for images and videos.
For videos, extracts multiple frames for robust matching.
"""

import os
os.environ["OPENCV_OPENCL_RUNTIME"] = "disabled"
os.environ["OPENCV_OPENCL_DEVICE"] = "disabled"
os.environ["OPENCV_VIDEOIO_PRIORITY_MSMF"] = "0"

import imagehash
from PIL import Image
import numpy as np
import json
from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass
class FingerprintResult:
    """Container for all fingerprint signals generated from a media file."""
    phash: str = ""
    dhash: str = ""
    histogram: str = ""          # JSON-serialized histogram
    video_frame_hashes: str = "" # JSON array of per-frame phashes (videos only)
    primary_hash: str = ""       # Backward-compatible single hash (= phash)
    algorithm_version: str = "visual-v1"
    metadata: dict = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ─── Image Fingerprinting ───────────────────────────────────────────────────

def _generate_phash(pil_img: Image.Image) -> str:
    """Perceptual hash — robust to compression, color/contrast shifts."""
    try:
        return str(imagehash.phash(pil_img))
    except Exception as e:
        print(f"phash error: {e}")
        return ""


def _generate_dhash(pil_img: Image.Image) -> str:
    """Difference hash — captures edge/gradient patterns, robust to scaling."""
    try:
        return str(imagehash.dhash(pil_img))
    except Exception as e:
        print(f"dhash error: {e}")
        return ""


def _generate_histogram(cv2_img: np.ndarray) -> str:
    """
    Color histogram fingerprint using HSV color space.
    Returns a JSON-serialized normalized histogram.
    Robust to crops and spatial rearrangements.
    """
    import cv2
    try:
        hsv = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2HSV)
        # Compute histogram for H, S, V channels
        # H: 0-180 (OpenCV), S: 0-256, V: 0-256
        hist_h = cv2.calcHist([hsv], [0], None, [32], [0, 180])
        hist_s = cv2.calcHist([hsv], [1], None, [32], [0, 256])
        hist_v = cv2.calcHist([hsv], [2], None, [32], [0, 256])

        # Normalize each channel
        cv2.normalize(hist_h, hist_h, 0, 1, cv2.NORM_MINMAX)
        cv2.normalize(hist_s, hist_s, 0, 1, cv2.NORM_MINMAX)
        cv2.normalize(hist_v, hist_v, 0, 1, cv2.NORM_MINMAX)

        # Combine into a single feature vector (96 values)
        combined = np.concatenate([hist_h.flatten(), hist_s.flatten(), hist_v.flatten()])
        # Round to 4 decimal places to keep JSON compact
        combined_list = [round(float(v), 4) for v in combined]
        return json.dumps(combined_list)
    except Exception as e:
        print(f"histogram error: {e}")
        return ""


def generate_image_fingerprint(image_path: str) -> FingerprintResult:
    """Generates all fingerprint types for an image."""
    import cv2
    result = FingerprintResult()
    try:
        pil_img = Image.open(image_path)
        cv2_img = cv2.imread(image_path)
        result.metadata = {"width": pil_img.width, "height": pil_img.height, "format": pil_img.format}

        if cv2_img is None:
            print(f"cv2 failed to read image: {image_path}")
            # Fall back to PIL-only hashes
            result.phash = _generate_phash(pil_img)
            result.dhash = _generate_dhash(pil_img)
            result.primary_hash = result.phash
            return result

        result.phash = _generate_phash(pil_img)
        result.dhash = _generate_dhash(pil_img)
        result.histogram = _generate_histogram(cv2_img)
        result.primary_hash = result.phash

    except Exception as e:
        print(f"Error generating image fingerprints: {e}")

    return result


# ─── Video Fingerprinting ───────────────────────────────────────────────────

# Configuration
VIDEO_FRAME_INTERVAL_SEC = 5   # Extract a frame every N seconds
VIDEO_MAX_FRAMES = 20          # Cap on total frames to extract

def _extract_video_frames(video_path: str) -> List[tuple]:
    """
    Extracts frames at regular intervals from a video.
    Returns list of (frame_index, pil_image, cv2_image) tuples.
    """
    import cv2
    frames = []
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"Failed to open video: {video_path}")
            return frames

        fps = cap.get(cv2.CAP_PROP_FPS) or 24
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration_sec = total_frames / fps if fps > 0 else 0

        # Calculate frame indices to extract
        interval_frames = int(fps * VIDEO_FRAME_INTERVAL_SEC)
        if interval_frames <= 0:
            interval_frames = int(fps)  # fallback to 1-second intervals

        frame_indices = list(range(0, total_frames, interval_frames))
        # Always include the middle frame
        mid_frame = total_frames // 2
        if mid_frame not in frame_indices:
            frame_indices.append(mid_frame)
        frame_indices.sort()
        frame_indices = frame_indices[:VIDEO_MAX_FRAMES]

        for idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if ret and frame is not None:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(frame_rgb)
                frames.append((idx, pil_img, frame))

        cap.release()
    except Exception as e:
        print(f"Error extracting video frames: {e}")

    return frames


def generate_video_fingerprint(video_path: str) -> FingerprintResult:
    """
    Generates fingerprints for a video using multi-frame extraction.
    - phash/dhash/histogram from the middle frame (primary)
    - Per-frame phashes stored as JSON array for exhaustive matching
    """
    result = FingerprintResult()

    frames = _extract_video_frames(video_path)
    if not frames:
        result.warnings.append("No video frames could be extracted")
        print(f"No frames extracted from video: {video_path}")
        return result

    # Use middle frame as the primary fingerprint source
    mid_idx = len(frames) // 2
    _, mid_pil, mid_cv2 = frames[mid_idx]
    result.metadata = {"sampled_frame_count": len(frames)}

    result.phash = _generate_phash(mid_pil)
    result.dhash = _generate_dhash(mid_pil)
    result.histogram = _generate_histogram(mid_cv2)
    result.primary_hash = result.phash

    # Generate per-frame phashes for exhaustive video matching
    frame_hashes = []
    for idx, pil_img, _ in frames:
        h = _generate_phash(pil_img)
        if h:
            frame_hashes.append({"frame": idx, "phash": h})

    result.video_frame_hashes = json.dumps(frame_hashes)

    print(f"Video fingerprinted: {len(frame_hashes)} frames extracted")
    return result


# ─── Public API ─────────────────────────────────────────────────────────────

def generate_fingerprint(file_path: str, media_type: str) -> FingerprintResult:
    """
    Main entry point. Generates all fingerprint types for a given media file.
    Returns a FingerprintResult with all signals populated.
    """
    if media_type == 'image':
        return generate_image_fingerprint(file_path)
    elif media_type == 'video':
        return generate_video_fingerprint(file_path)
    return FingerprintResult()


def generate_fingerprint_simple(file_path: str, media_type: str) -> str:
    """
    Backward-compatible wrapper that returns just the primary hash string.
    Used by the crawler for quick fingerprinting.
    """
    result = generate_fingerprint(file_path, media_type)
    return result.primary_hash
