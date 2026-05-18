import cv2
import numpy as np
from pathlib import Path
from .image_quality import (
    assess_image_quality,
    fix_blurry_image,
    enhance_contrast,
    enhance_brightness,
    enhance_image_quality
)
from .tab_removal import OMRProcessingConfig, remove_guitar_tabs


def process_score(
    image_path: str | Path,
    config: OMRProcessingConfig | None = None,
    debug: bool = False,
) -> str:
    """Orchestrates the pipeline and returns the path to the clear image."""
    config = config or OMRProcessingConfig()
    image_stem = Path(image_path).stem

    img = cv2.imread(str(image_path))
    if img is None:
        raise FileNotFoundError(f"Could not load image at {image_path}")
    
    # Ensure the image is grayscale safely before quality assessment and processing
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    if(failed := assess_image_quality(str(image_path)).get("quality_score") == "Fail"):
        print(f"Image quality assessment failed for {image_path}. Attempting enhancement.")
        enhancement_result = enhance_image_quality(str(image_path))
        if "error" in enhancement_result:
            print(f"Enhancement failed: {enhancement_result['error']}")
            return str(image_path)  # Return original path if enhancement fails
        else:
            print(enhancement_result["message"])
            gray = cv2.imread(enhancement_result["enhanced_image"], cv2.IMREAD_GRAYSCALE)

    # Use adaptive thresholding for the main binary image.
    # Global Otsu thresholding often destroys thin staff lines in notation staves.
    block_size = max(3, int(config.threshold_block_size))
    if block_size % 2 == 0:
        block_size += 1
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block_size, config.threshold_c
    )

    if config.remove_tabs:
        binary = remove_guitar_tabs(binary, gray, config, debug=debug, image_stem=image_stem)

    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{Path(image_path).stem}{config.cleaned_suffix}.png"
    cv2.imwrite(str(output_path), binary)

    return str(output_path)
