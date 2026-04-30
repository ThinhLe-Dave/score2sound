import cv2
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4


@dataclass
class OMRProcessingConfig:
    """Tunable parameters for score image preprocessing."""
    scale: float = 2.0
    minimal_mode: bool = True
    denoise_h: int = 0
    use_denoise: bool = False
    use_otsu_threshold: bool = True
    use_staff_heal: bool = False
    threshold_block_size: int = 21
    threshold_c: int = 4
    heal_kernel_divisor: int = 160
    min_heal_kernel_width: int = 1
    median_blur_ksize: int = 1

def load_and_resize(image_path, scale=2.0):
    """Loads image and upscales to fix 'low interline' errors in Audiveris."""
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Could not load image at {image_path}")
    # Upscaling helps define thin staff lines more clearly for the OMR engine
    # Nearest-neighbor keeps staff edges crisp during upscale.
    return cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)

def denoise_and_binarize(img, config: OMRProcessingConfig):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if config.use_denoise and config.denoise_h > 0:
        denoised = cv2.fastNlMeansDenoising(gray, h=config.denoise_h)
    else:
        denoised = gray

    if config.use_otsu_threshold:
        # Otsu keeps staff lines crisp on high-contrast scans.
        _, binary = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    else:
        block_size = max(3, int(config.threshold_block_size))
        # OpenCV requires odd block size for adaptiveThreshold.
        if block_size % 2 == 0:
            block_size += 1
        binary = cv2.adaptiveThreshold(
            denoised,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            block_size,
            config.threshold_c,
        )
    return gray, denoised, binary

def deskew_and_heal(binary_img, config: OMRProcessingConfig):
    """Straightens the image and repairs broken staff lines without creating white blocks."""
    (h, w) = binary_img.shape[:2]
    
    # 1. Deskew logic
    # Find coordinates of BLACK pixels (the actual music ink)
    coords = np.column_stack(np.where(binary_img == 0)) 
    if len(coords) == 0:
        return binary_img, binary_img, binary_img
        
    angle = cv2.minAreaRect(coords)[-1]
    angle = -(90 + angle) if angle < -45 else -angle
    
    M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    rotated = cv2.warpAffine(
        binary_img,
        M,
        (w, h),
        flags=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=255,
    )
    # Keep the image strictly binary after deskew to avoid anti-aliased edges.
    _, rotated = cv2.threshold(rotated, 127, 255, cv2.THRESH_BINARY)
    
    # 2. Heal staff lines (Morphology)
    # We briefly invert the image to perform the "Closing" on the ink
    # A wider kernel helps bridge gaps in scanned staff lines.
    kernel_w = max(config.min_heal_kernel_width, int(w // max(1, config.heal_kernel_divisor)))
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_w, 1))
    
    if config.use_staff_heal:
        temp_inverted = cv2.bitwise_not(rotated)
        healed = temp_inverted if kernel_w <= 1 else cv2.morphologyEx(temp_inverted, cv2.MORPH_CLOSE, kernel)
        final_cleaned = cv2.bitwise_not(healed)
    else:
        healed = cv2.bitwise_not(rotated)
        final_cleaned = rotated
    
    # 3. Final polish (optional): median blur can smooth tiny artifacts
    # but may also soften note heads/staff edges. Keep disabled by default.
    blur_ksize = max(1, int(config.median_blur_ksize))
    if blur_ksize % 2 == 0:
        blur_ksize += 1
    final_output = final_cleaned if blur_ksize <= 1 else cv2.medianBlur(final_cleaned, blur_ksize)
    return rotated, healed, final_output


def _build_output_path(output_folder: Path, image_path: str) -> Path:
    stem = Path(image_path).stem or "score"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    short_id = uuid4().hex[:6]
    return output_folder / f"{stem}_cleaned_{timestamp}_{short_id}.png"


def process_score(image_path, output_folder="temp_uploads/cleaned", config: OMRProcessingConfig | None = None, debug=False):
    """Orchestrates the pipeline and returns the path to the clear image."""
    output_dir = Path(output_folder)
    output_dir.mkdir(parents=True, exist_ok=True)
    config = config or OMRProcessingConfig()

    # Step-by-step processing to ensure a clean result for Audiveris
    resized = load_and_resize(image_path, scale=config.scale)
    if config.minimal_mode:
        # Minimal mode avoids destructive filters that can blur staff lines.
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        denoised = gray
        binary = gray
        rotated = gray
        healed = gray
        final_output = gray
    else:
        gray, denoised, binary = denoise_and_binarize(resized, config)
        rotated, healed, final_output = deskew_and_heal(binary, config)

    output_path = _build_output_path(output_dir, image_path)
    cv2.imwrite(str(output_path), final_output)

    if debug:
        debug_dir = output_dir / "debug"
        debug_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(debug_dir / "1_resized.png"), resized)
        cv2.imwrite(str(debug_dir / "2_gray.png"), gray)
        cv2.imwrite(str(debug_dir / "3_denoised.png"), denoised)
        cv2.imwrite(str(debug_dir / "4_binary.png"), binary)
        cv2.imwrite(str(debug_dir / "5_rotated.png"), rotated)
        cv2.imwrite(str(debug_dir / "6_healed.png"), healed)
        cv2.imwrite(str(debug_dir / "7_final.png"), final_output)

    print(f"✅ Cleaned image saved: {output_path}")
    return str(output_path)