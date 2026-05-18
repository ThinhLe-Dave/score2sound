import unittest
import cv2
import numpy as np
import tempfile
import os
from pathlib import Path
from omr_engine.image_quality import assess_image_quality

class TestImageQuality(unittest.TestCase):
    """Unit tests for the image quality assessment logic."""

    def setUp(self):
        # Create a temporary directory for generating test images
        self.test_dir = tempfile.TemporaryDirectory()
        self.test_dir_path = Path(self.test_dir.name)

    def tearDown(self):
        # Cleanup the temporary directory
        self.test_dir.cleanup()

    def create_dummy_image(self, name: str, pixels: np.ndarray) -> str:
        """Helper to write a numpy array to a temporary image file."""
        path = self.test_dir_path / name
        cv2.imwrite(str(path), pixels)
        return str(path)

    def test_file_not_found(self):
        """Verify that the function handles missing files gracefully."""
        result = assess_image_quality("non_existent_file_12345.png")
        self.assertIn("error", result)
        self.assertTrue("not found" in result["error"])

    def test_invalid_image_decode(self):
        """Verify handling of files that are not valid images."""
        path = self.test_dir_path / "not_an_image.txt"
        path.write_text("This is just a text file, not a PNG/JPG.")
        result = assess_image_quality(str(path))
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Could not decode image.")

    def test_pass_quality_image(self):
        """Test an image that should pass basic quality checks."""
        # Create a high-contrast pattern on a neutral gray background.
        # Using a black background with thin lines makes the image too dark (mean < 30).
        size = 200
        img = np.full((size, size), 128, dtype=np.uint8)
        img[::20, :] = 255
        img[:, ::20] = 0
        path = self.create_dummy_image("pass_image.png", img)
        
        result = assess_image_quality(path)
        self.assertEqual(result["quality_score"], "Pass")
        self.assertFalse(result["flags"]["is_blurry"])
        self.assertFalse(result["flags"]["is_too_dark"])
        self.assertFalse(result["flags"]["is_too_light"])
        self.assertFalse(result["flags"]["is_low_contrast"])
        
        # Verify metric types
        self.assertIsInstance(result["metrics"]["sharpness"], float)
        self.assertIsInstance(result["metrics"]["brightness"], float)

    def test_blurry_image_detection(self):
        """Verify that low-detail/blurry images are flagged."""
        # A solid gray image has 0 variance (extremely blurry/no detail)
        img = np.full((100, 100), 128, dtype=np.uint8)
        path = self.create_dummy_image("blurry_image.png", img)
        
        result = assess_image_quality(path)
        self.assertTrue(result["flags"]["is_blurry"])
        self.assertEqual(result["quality_score"], "Fail")

    def test_low_contrast_detection(self):
        """Verify that low-contrast images are flagged."""
        # Create an image with very similar shades of gray (flat contrast)
        img = np.full((100, 100), 120, dtype=np.uint8)
        img[::2, ::2] = 125 
        path = self.create_dummy_image("low_contrast.png", img)
        
        result = assess_image_quality(path)
        self.assertTrue(result["flags"]["is_low_contrast"])
        self.assertEqual(result["quality_score"], "Fail")

    def test_dark_and_light_detection(self):
        """Test extreme brightness values."""
        # Very dark image
        dark_img = np.full((100, 100), 5, dtype=np.uint8)
        dark_path = self.create_dummy_image("dark.png", dark_img)
        dark_res = assess_image_quality(dark_path)
        self.assertTrue(dark_res["flags"]["is_too_dark"])

        # Very light image
        light_img = np.full((100, 100), 255, dtype=np.uint8)
        light_path = self.create_dummy_image("light.png", light_img)
        light_res = assess_image_quality(light_path)
        self.assertTrue(light_res["flags"]["is_too_light"])

    def test_resolution_reporting(self):
        """Check if dimensions are reported correctly."""
        img = np.zeros((150, 300), dtype=np.uint8)
        path = self.create_dummy_image("res_test.png", img)
        result = assess_image_quality(path)
        self.assertEqual(result["resolution"], "300x150")

if __name__ == "__main__":
    unittest.main()