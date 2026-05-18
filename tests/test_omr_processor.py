import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from omr_engine.omr_processor import process_score
from omr_engine.tab_removal import OMRProcessingConfig


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

    def test_process_score_writes_output(self):
        output_path_str = process_score(self.raw_image)
        output_path = Path(output_path_str)
        self.assertTrue(output_path.exists())
        self.assertEqual(output_path.name, "score_cleaned.png")


if __name__ == "__main__":
    unittest.main()
