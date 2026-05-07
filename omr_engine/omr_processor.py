import cv2
import numpy as np
from pathlib import Path
from dataclasses import dataclass

@dataclass
class OMRProcessingConfig:
    """Simplified config for tab removal."""
    remove_tabs: bool = True
    tab_line_count: int = 6
    tab_line_spacing_tolerance: float = 0.4
    threshold_block_size: int = 21
    threshold_c: int = 4

#region remove guitar tabs

def _get_adaptive_inv_binary(gray_image, block_size, c):
    adaptive_bin = cv2.adaptiveThreshold(
        gray_image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block_size, c
    )
    inv = cv2.bitwise_not(adaptive_bin)
    return inv

def _find_tab_regions(adaptive_inv_binary, config):
    kernel_len = max(10, adaptive_inv_binary.shape[1] // 32)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_len, 1))
    lines_img = cv2.morphologyEx(adaptive_inv_binary, cv2.MORPH_OPEN, kernel)
    proj = np.sum(lines_img == 255, axis=1)
    row_threshold = lines_img.shape[1] * 0.1
    peak_rows = np.where(proj > row_threshold)[0]
    if len(peak_rows) == 0:
        return []
    lines_y = []
    current_cluster = [peak_rows[0]]
    for y in peak_rows[1:]:
        if y - current_cluster[-1] <= 3:  # Group lines within 3 pixels
            current_cluster.append(y)
        else:
            lines_y.append(int(np.mean(current_cluster)))
            current_cluster = [y]
    if current_cluster:
        lines_y.append(int(np.mean(current_cluster)))
    lines_y = sorted(lines_y)
    tab_regions = []
    i = 0
    while i <= len(lines_y) - config.tab_line_count:
        group = lines_y[i:i+config.tab_line_count]
        spacings = [group[j+1] - group[j] for j in range(len(group)-1)]
        mean_spacing = np.mean(spacings)
        if mean_spacing > 3:
            is_tab = True
            for s in spacings:
                if abs(s - mean_spacing) > mean_spacing * config.tab_line_spacing_tolerance:
                    is_tab = False
                    break
            if is_tab:
                group_projs = [proj[y] for y in group]
                max_proj = max(group_projs)
                min_proj = min(group_projs)
                if min_proj < max_proj * 0.4:
                    is_tab = False
            if is_tab:
                print(f"Found tab group at {group} with spacing {mean_spacing}")
                padding = int(mean_spacing * 1.5)
                top_y = int(group[0]) - padding
                bottom_y = int(group[-1]) + padding
                tab_regions.append((top_y, bottom_y))
                i += config.tab_line_count
                continue
        i += 1
    return tab_regions

def _remove_regions_from_image(image, regions):
    if not regions:
        return image
    result = image.copy()
    for top_y, bottom_y in regions:
        top_y = max(0, top_y)
        bottom_y = min(result.shape[0], bottom_y)
        result[top_y:bottom_y, :] = 255
    return result

def remove_guitar_tabs(binary_img: np.ndarray, gray_img: np.ndarray, config: OMRProcessingConfig) -> np.ndarray:
    """
    Detects and removes guitar tabs (identified by groups of `tab_line_count` equidistant horizontal lines).
    Uses the grayscale image to reliably detect lines even if global binarization degraded them.
    Returns the cleaned binary image.
    """
    block_size = max(3, int(config.threshold_block_size))
    if block_size % 2 == 0:
        block_size += 1
        
    inv = _get_adaptive_inv_binary(gray_img, block_size, config.threshold_c)
    tab_regions = _find_tab_regions(inv, config)
    
    return _remove_regions_from_image(binary_img, tab_regions)

#endregion

def process_score(
    image_path: str | Path,
    config: OMRProcessingConfig | None = None,
    debug: bool = False,
) -> str:
    """Orchestrates the pipeline and returns the path to the clear image."""
    config = config or OMRProcessingConfig()

    img = cv2.imread(str(image_path))
    if img is None:
        raise FileNotFoundError(f"Could not load image at {image_path}")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    if config.remove_tabs:
        binary = remove_guitar_tabs(binary, gray, config)

    output_dir = Path("temp_uploads/cleaned")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{Path(image_path).stem}_cleaned.png"
    cv2.imwrite(str(output_path), binary)

    return str(output_path)
