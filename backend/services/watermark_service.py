"""
Forensic Watermark Service
Embeds and extracts LSB steganographic watermarks in images and videos.
Provides verification against registered assets.

Image watermarks: LSB steganography into image pixels (lossless PNG output).
Video watermarks: LSB steganography into sampled video frames, re-encoded
                  with a lossless/near-lossless codec to preserve bit data.
"""

import cv2
import numpy as np
import os
import shutil
from typing import Optional, List
from dataclasses import dataclass
from collections import Counter


class WatermarkEmbeddingError(RuntimeError):
    """Raised when a protected copy cannot be created and verified."""


@dataclass
class WatermarkVerification:
    """Result of watermark verification on discovered media."""
    extracted: str = ""              # The raw text extracted (may be empty/garbage)
    is_valid: bool = False           # Whether extracted text looks like a valid watermark
    verified: bool = False           # Whether it matched a registered asset's watermark_id
    matched_asset_id: Optional[int] = None  # The asset ID it matched (if any)
    confidence: str = "none"         # 'high', 'medium', 'low', 'none'


VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm'}

# How often (in frames) to embed the watermark payload in a video.
# Every Nth frame gets the steganographic payload; the rest pass through unchanged.
VIDEO_WATERMARK_FRAME_INTERVAL = 30


# ─── Low-Level LSB Helpers ──────────────────────────────────────────────────

def _text_to_binary(text: str) -> str:
    """Converts text to a binary string with a 16-bit end-of-message delimiter."""
    binary = ''.join(format(ord(c), '08b') for c in text)
    binary += '1111111111111110'  # delimiter
    return binary


def _embed_lsb_into_frame(frame: np.ndarray, binary_text: str) -> bool:
    """
    Embeds binary_text into the LSB of a BGR frame (in-place).
    Returns True if the frame was large enough to hold the payload, False otherwise.
    """
    max_bits = frame.shape[0] * frame.shape[1] * 3
    if len(binary_text) > max_bits:
        return False

    data_index = 0
    data_len = len(binary_text)

    for row in frame:
        for pixel in row:
            for channel in range(3):
                if data_index < data_len:
                    pixel[channel] = (pixel[channel] & 0xFE) | int(binary_text[data_index])
                    data_index += 1
                else:
                    return True
    return True


def _extract_lsb_from_frame(frame: np.ndarray) -> str:
    """
    Reads LSB bits from a BGR frame and decodes the hidden text.
    Returns the extracted string, or empty string if nothing valid is found.
    """
    binary_data = []
    for row in frame:
        for pixel in row:
            for channel in range(3):
                binary_data.append(str(pixel[channel] & 1))

    binary_str = ''.join(binary_data)
    decoded_chars = []

    for i in range(0, len(binary_str) - 8, 8):
        byte = binary_str[i:i + 8]
        char_val = int(byte, 2)

        # Check for delimiter: next 16 bits == 1111111111111110
        if i + 24 <= len(binary_str):
            next_16 = binary_str[i + 8:i + 24]
            if next_16 == '1111111111111110':
                decoded_chars.append(chr(char_val))
                break

        # Only accept printable ASCII
        if 32 <= char_val <= 126:
            decoded_chars.append(chr(char_val))
        else:
            if len(decoded_chars) < 3:
                return ""
            break

    result = ''.join(decoded_chars)
    if result and len(result) >= 4:
        return result
    return ""


# ─── Image Embedding / Extraction ──────────────────────────────────────────

def _embed_watermark_image(image_path: str, watermark_text: str, output_path: str = None) -> str:
    """Embeds LSB watermark into an image file. Returns path to watermarked image."""
    if not output_path:
        base, _ = os.path.splitext(image_path)
        output_path = f"{base}_watermarked.png"

    try:
        img = cv2.imread(image_path)
        if img is None:
            print(f"Watermark embed warning: cv2 could not read image at {image_path}")
            return image_path

        binary_text = _text_to_binary(watermark_text)
        if not _embed_lsb_into_frame(img, binary_text):
            raise WatermarkEmbeddingError(f"watermark too long for image ({len(binary_text)} bits needed)")

        if not cv2.imwrite(output_path, img) or _extract_watermark_image(output_path) != watermark_text:
            raise WatermarkEmbeddingError("image output verification failed")
        return output_path

    except Exception as e:
        print(f"Watermark embed error (image): {e}")
        if output_path and os.path.exists(output_path):
            try:
                os.remove(output_path)
            except OSError:
                pass
        raise WatermarkEmbeddingError(str(e)) from e


def _extract_watermark_image(image_path: str) -> str:
    """Extracts LSB watermark from an image file."""
    try:
        img = cv2.imread(image_path)
        if img is None:
            return ""
        return _extract_lsb_from_frame(img)
    except Exception as e:
        print(f"Watermark extraction error (image): {e}")
        return ""


# ─── Video Embedding / Extraction ──────────────────────────────────────────

def _embed_watermark_video(video_path: str, watermark_text: str, output_path: str = None) -> str:
    """
    Embeds an invisible LSB watermark into a video file.

    Strategy:
    - Decode every frame with OpenCV.
    - Every VIDEO_WATERMARK_FRAME_INTERVAL-th frame gets the LSB payload embedded.
    - Re-encode with FFV1 lossless video in an AVI container.
    - Re-open the output and extract the payload before returning success.

    Returns the path to the verified watermarked video file, or raises
    WatermarkEmbeddingError when protection cannot be verified.
    """
    if not output_path:
        base, _ = os.path.splitext(video_path)
        output_path = f"{base}_watermarked.avi"

    cap = None
    writer = None
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise WatermarkEmbeddingError(f"cannot open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if width <= 0 or height <= 0:
            raise WatermarkEmbeddingError("invalid video dimensions")

        binary_text = _text_to_binary(watermark_text)
        # FFV1 in AVI is lossless and preserves LSBs. Do not silently fall
        # back to a lossy codec: it would create an unverifiable watermark.
        fourcc = cv2.VideoWriter_fourcc(*"FFV1")
        writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        if not writer.isOpened():
            raise WatermarkEmbeddingError("FFV1 encoder is unavailable")

        frame_index = 0
        embedded_count = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_index % VIDEO_WATERMARK_FRAME_INTERVAL == 0:
                if not _embed_lsb_into_frame(frame, binary_text):
                    raise WatermarkEmbeddingError("watermark payload does not fit in frame")
                embedded_count += 1
            try:
                writer.write(frame)
            except Exception as write_error:
                raise WatermarkEmbeddingError(f"video frame write failed: {write_error}") from write_error
            frame_index += 1

        if frame_index == 0 or embedded_count == 0:
            raise WatermarkEmbeddingError("video contains no usable frames")
        cap.release()
        cap = None
        writer.release()
        writer = None

        # OpenCV may report a writer as open while the encoder later fails.
        if not os.path.isfile(output_path) or os.path.getsize(output_path) == 0:
            raise WatermarkEmbeddingError("video output was not created")
        extracted = _extract_watermark_video(output_path, max_sample_frames=10)
        if extracted != watermark_text:
            raise WatermarkEmbeddingError(
                f"output verification failed (extracted {extracted!r})"
            )

        print(
            f"Forensic Watermark (video): Embedded ID '{watermark_text}' into "
            f"{embedded_count}/{frame_index} frames of {os.path.basename(video_path)}"
        )
        return output_path

    except Exception as e:
        if cap is not None:
            cap.release()
        if writer is not None:
            writer.release()
        if output_path and os.path.exists(output_path):
            try:
                os.remove(output_path)
            except OSError:
                pass
        if isinstance(e, WatermarkEmbeddingError):
            raise
        print(f"Watermark embed error (video): {e}")
        raise WatermarkEmbeddingError(str(e)) from e


def _extract_watermark_video(video_path: str, max_sample_frames: int = 10) -> str:
    """
    Extracts an LSB watermark from a video by sampling watermarked frames.
    Uses majority voting across multiple sampled frames for robustness.

    Returns the most-common valid extraction, or empty string if none found.
    """
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return ""

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0:
            cap.release()
            return ""

        # Build list of frame indices that should contain the watermark
        candidate_indices = list(range(0, total_frames, VIDEO_WATERMARK_FRAME_INTERVAL))
        # Limit how many we actually read for speed
        candidate_indices = candidate_indices[:max_sample_frames]

        extractions: List[str] = []

        for idx in candidate_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if not ret or frame is None:
                continue

            text = _extract_lsb_from_frame(frame)
            if text:
                extractions.append(text)

        cap.release()

        if not extractions:
            return ""

        # Majority vote: pick the most common extraction
        counts = Counter(extractions)
        best, _ = counts.most_common(1)[0]
        return best

    except Exception as e:
        print(f"Watermark extraction error (video): {e}")
        return ""


# ─── Public API: Embedding ──────────────────────────────────────────────────

def embed_watermark(image_path: str, watermark_text: str, output_path: str = None) -> str:
    """
    Embeds an invisible forensic LSB watermark into a media file.
    - For images: steganographic LSB embedding, output as lossless PNG.
    - For videos: steganographic LSB embedding into sampled frames,
                  re-encoded with a lossless/near-lossless codec.
    """
    _, ext = os.path.splitext(image_path)
    if ext.lower() in VIDEO_EXTENSIONS:
        return _embed_watermark_video(image_path, watermark_text, output_path)
    else:
        return _embed_watermark_image(image_path, watermark_text, output_path)


# ─── Public API: Extraction ────────────────────────────────────────────────

def extract_watermark(image_path: str) -> str:
    """
    Extracts the hidden LSB watermark text from a media file.
    Returns the extracted text, or empty string if none found.
    """
    _, ext = os.path.splitext(image_path)
    if ext.lower() in VIDEO_EXTENSIONS:
        return _extract_watermark_video(image_path)
    else:
        return _extract_watermark_image(image_path)


# ─── Verification ───────────────────────────────────────────────────────────

def verify_watermark(image_path: str, db_session) -> WatermarkVerification:
    """
    Extracts watermark from discovered media and verifies it against
    registered assets in the database.

    Returns a WatermarkVerification result with match details.
    """
    from database.models import Asset

    result = WatermarkVerification()

    # Step 1: Extract watermark (handles both image and video)
    extracted = extract_watermark(image_path)
    result.extracted = extracted

    if not extracted:
        result.confidence = "none"
        return result

    # Step 2: Check if it looks like a valid organizational watermark
    if extracted.startswith("ORG-"):
        result.is_valid = True
        result.confidence = "medium"

        # Step 3: Check against registered assets
        try:
            assets = db_session.query(Asset).filter(
                Asset.watermark_id == extracted
            ).all()

            if assets:
                result.verified = True
                result.matched_asset_id = assets[0].id
                result.confidence = "high"
                print(f"Watermark VERIFIED: '{extracted}' -> Asset #{assets[0].id} ({assets[0].title})")
            else:
                # Valid format but no matching asset — could be from another org
                result.confidence = "medium"
                print(f"Watermark valid format but no asset match: '{extracted}'")

        except Exception as e:
            print(f"Watermark DB verification error: {e}")
    else:
        # Extracted something but doesn't match our format
        result.confidence = "low"

    return result
