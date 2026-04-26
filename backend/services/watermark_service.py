import cv2
import numpy as np
import os

def embed_watermark(image_path: str, watermark_text: str, output_path: str = None) -> str:
    """
    Simulates forensic watermarking using Least Significant Bit (LSB) steganography.
    Embeds the watermark_text into the image pixels.
    """
    if not output_path:
        base, ext = os.path.splitext(image_path)
        output_path = f"{base}_watermarked.png" # LSB requires lossless format like PNG
        
    img = cv2.imread(image_path)
    if img is None:
        return image_path
        
    # Convert text to binary string
    binary_text = ''.join(format(ord(i), '08b') for i in watermark_text)
    # Add a delimiter so we know when to stop reading during extraction
    binary_text += '1111111111111110'
    
    data_index = 0
    data_len = len(binary_text)
    
    for values in img:
        for pixel in values:
            for i in range(3): # RGB channels
                if data_index < data_len:
                    # Modify the least significant bit
                    pixel[i] = int(bin(pixel[i])[2:9] + binary_text[data_index], 2)
                    data_index += 1
                else:
                    break
                    
    cv2.imwrite(output_path, img)
    return output_path

def extract_watermark(image_path: str) -> str:
    """
    Extracts the hidden LSB watermark text from an image.
    """
    img = cv2.imread(image_path)
    if img is None:
        return ""
        
    binary_data = ""
    for values in img:
        for pixel in values:
            for i in range(3):
                binary_data += bin(pixel[i])[-1]
                
    # Split by 8-bits
    all_bytes = [binary_data[i: i+8] for i in range(0, len(binary_data), 8)]
    
    decoded_data = ""
    for byte in all_bytes:
        decoded_data += chr(int(byte, 2))
        if decoded_data[-2:] == "þ": # corresponds to our 1111111111111110 delimiter
            break
            
    return decoded_data[:-2]
