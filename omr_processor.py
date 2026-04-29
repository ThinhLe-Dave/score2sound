import cv2
import numpy as np
import os
from pathlib import Path

def load_and_resize(image_path, scale=2):
    """Loads image and upscales to fix 'low interline' errors in Audiveris."""
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Could not load image at {image_path}")
    # Upscaling helps define thin staff lines more clearly for the OMR engine
    return cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

def denoise_and_binarize(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray, h=10)
    
    # INCREASE BLOCK SIZE: Since we upscaled, we need a larger neighborhood (21 instead of 11)
    # to distinguish between ink and paper.
    return cv2.adaptiveThreshold(denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                   cv2.THRESH_BINARY, 21, 4)

def deskew_and_heal(binary_img):
    """Straightens the image and repairs broken staff lines without creating white blocks."""
    (h, w) = binary_img.shape[:2]
    
    # 1. Deskew logic
    # Find coordinates of BLACK pixels (the actual music ink)
    coords = np.column_stack(np.where(binary_img == 0)) 
    if len(coords) == 0:
        return binary_img
        
    angle = cv2.minAreaRect(coords)[-1]
    angle = -(90 + angle) if angle < -45 else -angle
    
    M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    rotated = cv2.warpAffine(binary_img, M, (w, h), 
                             flags=cv2.INTER_CUBIC, 
                             borderMode=cv2.BORDER_REPLICATE)
    
    # 2. Heal staff lines (Morphology)
    # We briefly invert the image to perform the "Closing" on the ink
    # A wider kernel (w // 200) helps bridge gaps in scanned staff lines.
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (w /30, 1))
    
    temp_inverted = cv2.bitwise_not(rotated)
    healed = cv2.morphologyEx(temp_inverted, cv2.MORPH_CLOSE, kernel)
    final_cleaned = cv2.bitwise_not(healed)
    
    # 3. Final Polish: Median blur removes single-pixel noise artifacts
    return cv2.medianBlur(final_cleaned, 3)

def process_score(image_path, output_folder="temp_uploads/cleaned"):
    """Orchestrates the pipeline and returns the path to the clear image."""
    Path(output_folder).mkdir(parents=True, exist_ok=True)
    
    # Step-by-step processing to ensure a clean result for Audiveris
    img = load_and_resize(image_path)
    binary = denoise_and_binarize(img)
    final_output = deskew_and_heal(binary)
    
    # Rename to 2_rotated.png to match your desired output flow
    output_path = f"{output_folder}/2_rotated.png"
    cv2.imwrite(output_path, final_output)
    
    print(f"✅ Cleaned image saved: {output_path}")
    return output_path