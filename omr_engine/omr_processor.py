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

    # Advanced detection and file path parameters
    cluster_dist_threshold: int = 5
    row_projection_ratio: float = 0.3
    min_mean_spacing: float = 3.0
    min_projection_ratio: float = 0.2
    padding_ratio: float = 0.4
    kernel_min_len: int = 10
    kernel_divisor: int = 32
    debug_dir: str = "temp_uploads/debug"
    output_dir: str = "temp_uploads/cleaned"
    cleaned_suffix: str = "_cleaned"

    # Logic and visual constants
    pixel_white: int = 255
    vis_color_bgr: tuple = (0, 0, 255)
    vis_thickness: int = 2

#region remove guitar tabs

def _get_adaptive_inv_binary(gray_image, block_size, c):
    adaptive_bin = cv2.adaptiveThreshold(
        gray_image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block_size, c
    )
    inv = cv2.bitwise_not(adaptive_bin)
    return inv

def _find_tab_regions(adaptive_inv_binary, config, debug=False, image_stem="score"):
    kernel_len = max(config.kernel_min_len, adaptive_inv_binary.shape[1] // config.kernel_divisor)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_len, 1))
    lines_img = cv2.morphologyEx(adaptive_inv_binary, cv2.MORPH_OPEN, kernel)

    if debug:
        debug_dir = Path(config.debug_dir)
        debug_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(debug_dir / f"{image_stem}_lines.png"), lines_img)

    proj = np.sum(lines_img == config.pixel_white, axis=1)

    row_threshold = lines_img.shape[1] * config.row_projection_ratio
    peak_rows = np.where(proj > row_threshold)[0]
    if len(peak_rows) == 0:
        return []

    lines_y = []
    current_cluster = [peak_rows[0]]
    for y in peak_rows[1:]:
        if y - current_cluster[-1] <= config.cluster_dist_threshold:
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
        if mean_spacing > config.min_mean_spacing:
            is_tab = True
            for s in spacings:
                if abs(s - mean_spacing) > mean_spacing * config.tab_line_spacing_tolerance:
                    is_tab = False
                    break
            if is_tab:
                group_projs = [proj[y] for y in group]
                max_proj = max(group_projs)
                min_proj = min(group_projs)
                if min_proj < max_proj * config.min_projection_ratio:
                    is_tab = False
            if is_tab:
                top_padding = int(mean_spacing * config.padding_ratio)
                bottom_padding = int(mean_spacing * config.padding_ratio)
                top_y = int(group[0]) - top_padding
                bottom_y = int(group[-1]) + bottom_padding
                tab_regions.append((top_y, bottom_y))
                i += config.tab_line_count
                continue
        i += 1
    return tab_regions

def _remove_regions_from_image(result, regions, config):
    """Clears detected regions (sets pixels to white)."""
    print(f"🔍 [Debug] Removing {len(regions)} tab regions from image. tab regions: {regions}")
    for top_y, bottom_y in regions:
        top_y = max(0, top_y)
        bottom_y = min(result.shape[0], bottom_y)
        result[top_y:bottom_y, :] = config.pixel_white
    return result

def remove_guitar_tabs(binary_img: np.ndarray, gray_img: np.ndarray, config: OMRProcessingConfig, debug: bool = False, image_stem: str = "score") -> np.ndarray:
    """
    Detects and removes guitar tabs (identified by groups of `tab_line_count` equidistant horizontal lines).
    Uses the grayscale image to reliably detect lines even if global binarization degraded them.
    Returns the cleaned binary image.
    """
    block_size = max(3, int(config.threshold_block_size))
    if block_size % 2 == 0:
        block_size += 1
        
    inv = _get_adaptive_inv_binary(gray_img, block_size, config.threshold_c)

    if debug:
        debug_dir = Path(config.debug_dir)
        debug_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(debug_dir / f"{image_stem}_inv.png"), inv)

    tab_regions = _find_tab_regions(inv, config, debug=debug, image_stem=image_stem)

    if debug and tab_regions:
        # Create visualization of detections on the binary image
        vis = cv2.cvtColor(binary_img, cv2.COLOR_GRAY2BGR)
        for top_y, bottom_y in tab_regions:
            cv2.rectangle(vis, (0, top_y), (vis.shape[1], bottom_y), config.vis_color_bgr, config.vis_thickness)
        debug_dir = Path(config.debug_dir)
        cv2.imwrite(str(debug_dir / f"{image_stem}_detections.png"), vis)

    print(f"🔍 [Debug] Detected {len(tab_regions)} potential tab regions: {tab_regions}")
    
    return _remove_regions_from_image(binary_img, tab_regions, config)

#endregion

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

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

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
