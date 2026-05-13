import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from omr_engine.omr_processor import (
    OMRProcessingConfig,
    _get_adaptive_inv_binary,
    _find_tab_regions,
    _remove_regions_from_image,
    remove_guitar_tabs,
    process_score,
)


class TestOmrProcessor(unittest.TestCase):
    def setUp(self):
        self.temp_dir_obj = tempfile.TemporaryDirectory()
        self.temp_dir = Path(self.temp_dir_obj.name)
        self.raw_image = self.temp_dir / "score.png"

        # Create a simple test image
        img = np.full((100, 100, 3), 255, dtype=np.uint8)
        cv2.imwrite(str(self.raw_image), img)

    def tearDown(self):
        self.temp_dir_obj.cleanup()

    def test_process_score_missing_file_raises(self):
        missing = self.temp_dir / "missing.png"
        with self.assertRaises(FileNotFoundError):
            process_score(missing)

    def test_get_adaptive_inv_binary(self):
        gray = np.full((100, 100), 255, dtype=np.uint8)
        gray[10:20, :] = 0
        inv_bin = _get_adaptive_inv_binary(gray, 21, 4)
        self.assertEqual(inv_bin.shape, (100, 100))
        # Black regions in original should become 255 in inv_bin
        self.assertEqual(inv_bin[15, 50], 255)

    def test_find_tab_regions(self):
        # Create an inverse binary image with 6 lines
        inv = np.zeros((200, 200), dtype=np.uint8)
        config = OMRProcessingConfig(tab_line_count=6)
        
        # Add 6 lines with spacing of 10
        start_y = 50
        for i in range(6):
            # A line thicker than 1 pixel to survive morphology opening
            inv[start_y + i * 10 - 1 : start_y + i * 10 + 2, :] = 255
            
        regions = _find_tab_regions(inv, config)
        self.assertEqual(len(regions), 1)
        top_y, bottom_y = regions[0]
        self.assertLessEqual(top_y, 50)
        self.assertGreaterEqual(bottom_y, 100)

    def test_remove_regions_from_image(self):
        img = np.zeros((100, 100), dtype=np.uint8)
        regions = [(10, 30)]
        config = OMRProcessingConfig()
        result = _remove_regions_from_image(img, regions, config)
        self.assertEqual(result[20, 50], config.pixel_white) # Area should be wiped (255)
        self.assertEqual(result[5, 50], 0)   # Outside area remains 0

    def test_remove_guitar_tabs(self):
        binary = np.zeros((200, 200), dtype=np.uint8)
        gray = np.full((200, 200), 255, dtype=np.uint8)
        config = OMRProcessingConfig()
        
        # Add 6 lines to gray image
        start_y = 50
        for i in range(6):
            gray[start_y + i * 10 - 1 : start_y + i * 10 + 2, :] = 0
            binary[start_y + i * 10 - 1 : start_y + i * 10 + 2, :] = 0
            
        result = remove_guitar_tabs(binary, gray, config)
        self.assertEqual(result.shape, binary.shape)
        # Should be wiped
        self.assertEqual(result[55, 50], 255)

    def test_process_score_writes_output(self):
        output_path_str = process_score(self.raw_image)
        output_path = Path(output_path_str)
        self.assertTrue(output_path.exists())
        self.assertEqual(output_path.name, "score_cleaned.png")


if __name__ == "__main__":
    unittest.main()
