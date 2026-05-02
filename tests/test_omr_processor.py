import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from omr_processor import (
    OMRProcessingConfig,
    _build_output_path,
    denoise_and_binarize,
    deskew_and_heal,
    load_and_resize,
    process_score,
)


class TestOmrProcessor(unittest.TestCase):
    def setUp(self):
        self.temp_dir_obj = tempfile.TemporaryDirectory()
        self.temp_dir = Path(self.temp_dir_obj.name)
        self.raw_image = self.temp_dir / "score.png"

        # Create a simple test image with a horizontal score-like line.
        img = np.full((10, 20, 3), 255, dtype=np.uint8)
        cv2.line(img, (1, 5), (18, 5), (0, 0, 0), 1)
        cv2.imwrite(str(self.raw_image), img)

    def tearDown(self):
        self.temp_dir_obj.cleanup()

    def test_load_and_resize_missing_file_raises(self):
        missing = self.temp_dir / "missing.png"
        with self.assertRaises(FileNotFoundError):
            load_and_resize(missing, scale=2.0)

    def test_load_and_resize_scales_image(self):
        resized = load_and_resize(self.raw_image, scale=2.0)
        self.assertEqual(resized.shape, (20, 40, 3))

    def test_denoise_and_binarize_returns_expected_shapes(self):
        img = load_and_resize(self.raw_image, scale=1.0)
        config = OMRProcessingConfig(use_denoise=False, use_otsu_threshold=True)
        gray, denoised, binary = denoise_and_binarize(img, config)

        self.assertEqual(gray.shape, img.shape[:2])
        self.assertEqual(denoised.shape, img.shape[:2])
        self.assertEqual(binary.shape, img.shape[:2])
        self.assertTrue(set(np.unique(binary)).issubset({0, 255}))

    def test_deskew_and_heal_blank_image_returns_same(self):
        blank = np.full((10, 10), 255, dtype=np.uint8)
        config = OMRProcessingConfig(use_staff_heal=False)
        rotated, healed, final = deskew_and_heal(blank, config)

        self.assertTrue(np.array_equal(rotated, blank))
        self.assertTrue(np.array_equal(healed, blank))
        self.assertTrue(np.array_equal(final, blank))

    def test_build_output_path_contains_stem_suffix_and_extension(self):
        config = OMRProcessingConfig(output_stem_suffix="_cleaned", output_extension=".png")
        output_path = _build_output_path(self.temp_dir, self.raw_image, config)

        self.assertTrue(output_path.name.startswith("score_cleaned_"))
        self.assertEqual(output_path.suffix, ".png")

    def test_process_score_writes_output_and_debug_files(self):
        output_dir = self.temp_dir / "cleaned"
        output_path = process_score(self.raw_image, output_folder=output_dir, debug=True)

        self.assertTrue(Path(output_path).exists())
        self.assertTrue(output_dir.exists())

        debug_dir = output_dir / "debug"
        self.assertTrue(debug_dir.exists())

        expected_debug_names = [
            "1_resized.png",
            "2_gray.png",
            "3_denoised.png",
            "4_binary.png",
            "5_rotated.png",
            "6_healed.png",
            "7_final.png",
        ]
        for name in expected_debug_names:
            self.assertTrue((debug_dir / name).exists(), f"Missing debug file: {name}")


if __name__ == "__main__":
    unittest.main()
