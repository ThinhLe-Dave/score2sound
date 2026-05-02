import os
import cv2
import numpy as np
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4


def _default_cleaned_output_dir() -> str:
    return os.environ.get("SCORE2SOUND_OMR_CLEANED_DIR", "temp_uploads/cleaned")


@dataclass(frozen=True)
class OMRDebugFilenames:
    """Basenames for optional debug dumps (under ``debug`` subfolder)."""

    resized: str = "1_resized.png"
    gray: str = "2_gray.png"
    denoised: str = "3_denoised.png"
    binary: str = "4_binary.png"
    rotated: str = "5_rotated.png"
    healed: str = "6_healed.png"
    final: str = "7_final.png"


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
    # Deskew / warp (values match previous literals in deskew_and_heal)
    deskew_angle_branch_deg: float = -45.0
    rotation_scale: float = 1.0
    warp_border_value: int = 255
    post_deskew_binary_threshold: int = 127
    post_deskew_binary_max: int = 255
    ink_pixel_value: int = 0
    # Output naming
    output_stem_fallback: str = "score"
    output_stem_suffix: str = "_cleaned"
    output_timestamp_format: str = "%Y%m%d_%H%M%S"
    output_id_hex_length: int = 6
    output_extension: str = ".png"
    debug_subdir_name: str = "debug"
    debug_filenames: OMRDebugFilenames = field(default_factory=OMRDebugFilenames)


def load_and_resize(image_path: str | Path, *, scale: float) -> np.ndarray:
    """Loads image and upscales thin staff lines for the downstream OMR model."""
    path = str(image_path)
    img = cv2.imread(path)
    if img is None:
        raise FileNotFoundError(f"Could not load image at {path}")
    # Upscaling helps define thin staff lines more clearly for the OMR engine
    # Nearest-neighbor keeps staff edges crisp during upscale.
    return cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)


def denoise_and_binarize(img: np.ndarray, config: OMRProcessingConfig) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
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


def deskew_and_heal(
    binary_img: np.ndarray, config: OMRProcessingConfig
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Straightens the image and repairs broken staff lines without creating white blocks."""
    (h, w) = binary_img.shape[:2]

    # 1. Deskew logic
    # Find coordinates of ink pixels (default: black)
    coords = np.column_stack(np.where(binary_img == config.ink_pixel_value))
    if len(coords) == 0:
        return binary_img, binary_img, binary_img

    angle = cv2.minAreaRect(coords)[-1]
    branch = config.deskew_angle_branch_deg
    angle = -(90 + angle) if angle < branch else -angle

    M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, config.rotation_scale)
    rotated = cv2.warpAffine(
        binary_img,
        M,
        (w, h),
        flags=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=config.warp_border_value,
    )
    # Keep the image strictly binary after deskew to avoid anti-aliased edges.
    _, rotated = cv2.threshold(
        rotated,
        config.post_deskew_binary_threshold,
        config.post_deskew_binary_max,
        cv2.THRESH_BINARY,
    )

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


def _build_output_path(output_folder: Path, image_path: str | Path, config: OMRProcessingConfig) -> Path:
    stem = Path(image_path).stem or config.output_stem_fallback
    timestamp = datetime.now().strftime(config.output_timestamp_format)
    n = max(1, min(32, int(config.output_id_hex_length)))
    short_id = uuid4().hex[:n]
    name = f"{stem}{config.output_stem_suffix}_{timestamp}_{short_id}{config.output_extension}"
    return output_folder / name


def process_score(
    image_path: str | Path,
    output_folder: str | Path | None = None,
    config: OMRProcessingConfig | None = None,
    debug: bool = False,
) -> str:
    """Orchestrates the pipeline and returns the path to the clear image."""
    out = output_folder if output_folder is not None else _default_cleaned_output_dir()
    output_dir = Path(out)
    output_dir.mkdir(parents=True, exist_ok=True)
    config = config or OMRProcessingConfig()

    # Step-by-step processing to ensure a clean result for the OMR pass
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

    output_path = _build_output_path(output_dir, image_path, config)
    cv2.imwrite(str(output_path), final_output)

    if debug:
        dbg = config.debug_filenames
        debug_dir = output_dir / config.debug_subdir_name
        debug_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(debug_dir / dbg.resized), resized)
        cv2.imwrite(str(debug_dir / dbg.gray), gray)
        cv2.imwrite(str(debug_dir / dbg.denoised), denoised)
        cv2.imwrite(str(debug_dir / dbg.binary), binary)
        cv2.imwrite(str(debug_dir / dbg.rotated), rotated)
        cv2.imwrite(str(debug_dir / dbg.healed), healed)
        cv2.imwrite(str(debug_dir / dbg.final), final_output)

    print(f"✅ Cleaned image saved: {output_path}")
    return str(output_path)
