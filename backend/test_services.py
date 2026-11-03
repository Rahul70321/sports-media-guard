import os
import cv2
import numpy as np
from services.watermark_service import embed_watermark, extract_watermark
from services.fingerprint_service import generate_image_fingerprint

def run_tests():
    print("Creating a dummy image...")
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    img[:] = (255, 0, 0) # Blue image
    cv2.imwrite("dummy.png", img)

    print("\n--- Testing Watermark Service ---")
    watermark_text = "ORG-12345678"
    print(f"Embedding watermark: {watermark_text}")
    watermarked_path = embed_watermark("dummy.png", watermark_text, "dummy_watermarked.png")
    
    extracted = extract_watermark(watermarked_path)
    print(f"Extracted watermark: '{extracted}'")
    
    if extracted == watermark_text:
        print("Watermark test PASSED.")
    else:
        print("Watermark test FAILED.")

    print("\n--- Testing Fingerprint Service ---")
    result = generate_image_fingerprint("dummy.png")
    print(f"pHash: {result.phash}")
    print(f"dHash: {result.dhash}")
    print(f"Histogram available: {bool(result.histogram)}")
    
    if result.phash:
        print("Fingerprint test PASSED.")
    else:
        print("Fingerprint test FAILED.")
        
    print("\nCleaning up...")
    if os.path.exists("dummy.png"): os.remove("dummy.png")
    if os.path.exists("dummy_watermarked.png"): os.remove("dummy_watermarked.png")

if __name__ == "__main__":
    run_tests()
