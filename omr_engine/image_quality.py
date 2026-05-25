import cv2
import numpy as np
from pathlib import Path

def assess_image_quality(img: np.ndarray, filename: str = "unknown"):
    """
    Assess the quality of an image for OMR processing.
    Analyzes sharpness, brightness, and contrast.
    """
    if img is None:
        return {"error": "Could not decode image."}

    # 1. Sharpness/Blur Detection (Variance of Laplacian)
    # A low variance indicates a lack of high-frequency content (blur).
    sharpness = cv2.Laplacian(img, cv2.CV_64F).var()

    # 2. Brightness (Mean pixel intensity)
    # 0 is black, 255 is white.
    brightness = np.mean(img)

    # 3. Contrast (Standard deviation of pixel intensity)
    contrast = np.std(img)

    # 4. Dimensions
    height, width = img.shape

    # Basic thresholding for recommendations
    # Adjusted for sheet music: mostly white background with black ink.
    # A typical clear scan has brightness > 200 and high contrast.
    is_blurry = sharpness < 100        # Variance of Laplacian
    is_too_dark = brightness < 40      # Heavy shadows or underexposure
    is_too_light = brightness > 250    # Nearly blank or washed out
    is_low_contrast = contrast < 20    # Flat image (e.g., light gray on dark gray)

    return {
        "filename": filename,
        "resolution": f"{width}x{height}",
        "metrics": {
            "sharpness": round(sharpness, 2),
            "brightness": round(brightness, 2),
            "contrast": round(contrast, 2),
        },
        "flags": {
            "is_blurry": bool(is_blurry),
            "is_too_dark": bool(is_too_dark),
            "is_too_light": bool(is_too_light),
            "is_low_contrast": bool(is_low_contrast),
        },
        "quality_score": "Pass" if not any([is_blurry, is_too_dark, is_too_light, is_low_contrast]) else "Fail"
    }

def fix_blurry_image(gray_img: np.ndarray) -> np.ndarray:
    """Applies sharpening filters to enhance a blurry image."""
    # Unsharp masking: original + (original - blurred)
    blurred = cv2.GaussianBlur(gray_img, (0, 0), sigmaX=3)
    sharpened = cv2.addWeighted(gray_img, 1.5, blurred, -0.5, 0)
    return sharpened

def enhance_contrast(gray_img: np.ndarray) -> np.ndarray:
    """Applies CLAHE to enhance contrast in low-contrast images."""
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray_img)

def enhance_brightness(gray_img: np.ndarray) -> np.ndarray:
    """Increases brightness using histogram equalization."""
    return cv2.equalizeHist(gray_img)

def enhance_image_quality(image_path: str):
    """Enhances the image quality by applying sharpening, contrast, and brightness adjustments."""
    path = Path(image_path)
    if not path.exists():
        return {"error": f"File {image_path} not found."}

    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return {"error": "Could not decode image."}

    # Assess once and reuse flags
    assessment = assess_image_quality(img, path.name)
    flags = assessment.get("flags", {})

    if flags.get("is_blurry", False):
        print("Image is blurry. Applying sharpening filter.")
        img = fix_blurry_image(img)

    if flags.get("is_low_contrast", False):
        print("Image has low contrast. Applying enhancement.")
        img = enhance_contrast(img)

    if flags.get("is_too_dark", False) or flags.get("is_too_light", False):
        print("Image brightness needs adjustment.")
        img = enhance_brightness(img)

    # Save the enhanced image (optional)
    enhanced_path = path.with_name(f"{path.stem}_enhanced{path.suffix}")
    cv2.imwrite(str(enhanced_path), img)

    return {
        "original_image": str(path),
        "enhanced_image": str(enhanced_path),
        "message": "Image quality enhanced and saved."
    }

if __name__ == "__main__":
    import sys
    import json
    if len(sys.argv) < 2:
        print("Usage: python image_quality.py <image_path>")
    else:
        quality_report = assess_image_quality(sys.argv[1])
        print(json.dumps(quality_report, indent=4))