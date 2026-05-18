import unittest
import cv2
import numpy as np
import tempfile
from pathlib import Path

from omr_engine.tab_removal import (
    OMRProcessingConfig,
    _get_adaptive_inv_binary,
    _find_tab_regions,
    _remove_regions_from_image,
    remove_guitar_tabs,
)

class TestTabRemoval(unittest.TestCase):
    def setUp(self):
        self.temp_dir_obj = tempfile.TemporaryDirectory()
        self.temp_dir = Path(self.temp_dir_obj.name)
        self.debug_dir = self.temp_dir / "debug"
        self.debug_dir.mkdir()

        # Default config for most tests
        self.config = OMRProcessingConfig(
            debug_dir=str(self.debug_dir),
            tab_line_count=6,
            tab_line_spacing_tolerance=0.4,
            cluster_dist_threshold=5,
            row_projection_ratio=0.3,
            min_mean_spacing=3.0,
            min_projection_ratio=0.2,
            padding_ratio=0.4,
            kernel_min_len=10,
            kernel_divisor=32,
            threshold_block_size=21,
            threshold_c=4
        )

    def tearDown(self):
        self.temp_dir_obj.cleanup()

    def test_omr_processing_config_defaults(self):
        """Test that OMRProcessingConfig initializes with expected defaults."""
        config = OMRProcessingConfig()
        self.assertTrue(config.remove_tabs)
        self.assertEqual(config.tab_line_count, 6)
        self.assertEqual(config.pixel_white, 255)

    def test_get_adaptive_inv_binary(self):
        """Test _get_adaptive_inv_binary produces an inverted binary image."""
        # Create a simple grayscale image with some black and white areas
        gray_image = np.full((100, 100), 255, dtype=np.uint8)
        gray_image[30:35, :] = 0  # Thin black line (ink)
        gray_image[70:75, :] = 255 # White area (background)

        inv_binary = _get_adaptive_inv_binary(gray_image, block_size=21, c=4)

        self.assertEqual(inv_binary.shape, gray_image.shape)
        # Check that the black line in gray_image is white (255) in inv_binary
        self.assertEqual(inv_binary[32, 50], 255)
        # Check that the white area in gray_image is black (0) in inv_binary
        self.assertEqual(inv_binary[72, 50], 0)
        # Check a neutral area
        self.assertEqual(inv_binary[5, 5], 0) # Adaptive threshold makes background black

    def test_find_tab_regions_success(self):
        """Test _find_tab_regions correctly identifies a tab region."""
        # Create an inverse binary image with 6 distinct lines
        inv_binary = np.zeros((200, 200), dtype=np.uint8)
        line_spacing = 10
        start_y = 50
        for i in range(self.config.tab_line_count):
            # Make lines thick enough to survive morphology (e.g., 3 pixels)
            inv_binary[start_y + i * line_spacing - 1 : start_y + i * line_spacing + 2, :] = 255

        tab_regions = _find_tab_regions(inv_binary, self.config)
        self.assertEqual(len(tab_regions), 1)
        top_y, bottom_y = tab_regions[0]
        
        # Check that the detected region covers the lines with padding
        expected_top_y = start_y - int(line_spacing * self.config.padding_ratio)
        expected_bottom_y = start_y + (self.config.tab_line_count - 1) * line_spacing + int(line_spacing * self.config.padding_ratio)
        
        self.assertLessEqual(top_y, expected_top_y + 2) # Allow for slight variation due to mean calculation
        self.assertGreaterEqual(bottom_y, expected_bottom_y - 2)

    def test_find_tab_regions_no_lines(self):
        """Test _find_tab_regions returns empty list if no lines are present."""
        inv_binary = np.zeros((200, 200), dtype=np.uint8)
        tab_regions = _find_tab_regions(inv_binary, self.config)
        self.assertEqual(len(tab_regions), 0)

    def test_find_tab_regions_not_enough_lines(self):
        """Test _find_tab_regions returns empty list if fewer than tab_line_count lines."""
        inv_binary = np.zeros((200, 200), dtype=np.uint8)
        line_spacing = 10
        start_y = 50
        for i in range(self.config.tab_line_count - 1): # One line less than required
            inv_binary[start_y + i * line_spacing - 1 : start_y + i * line_spacing + 2, :] = 255
        
        tab_regions = _find_tab_regions(inv_binary, self.config)
        self.assertEqual(len(tab_regions), 0)

    def test_find_tab_regions_debug_output(self):
        """Test _find_tab_regions creates debug images when debug is True."""
        inv_binary = np.zeros((200, 200), dtype=np.uint8)
        inv_binary[50:53, :] = 255 # A single line
        _find_tab_regions(inv_binary, self.config, debug=True, image_stem="test_debug")
        self.assertTrue((self.debug_dir / "test_debug_lines.png").exists())

    def test_remove_regions_from_image(self):
        """Test _remove_regions_from_image clears specified regions."""
        img = np.zeros((100, 100), dtype=np.uint8) # All black image
        regions = [(10, 30), (60, 70)]
        
        result_img = _remove_regions_from_image(img.copy(), regions, self.config)
        
        # Check pixels within the first region are white
        self.assertEqual(result_img[15, 50], self.config.pixel_white)
        self.assertEqual(result_img[25, 50], self.config.pixel_white)
        # Check pixels within the second region are white
        self.assertEqual(result_img[65, 50], self.config.pixel_white)
        # Check pixels outside regions are still black
        self.assertEqual(result_img[5, 50], 0)
        self.assertEqual(result_img[40, 50], 0)
        self.assertEqual(result_img[80, 50], 0)

    def test_remove_guitar_tabs_integration(self):
        """Test the main remove_guitar_tabs function with a simulated tab."""
        binary_img = np.zeros((200, 200), dtype=np.uint8)
        gray_img = np.full((200, 200), 255, dtype=np.uint8)

        # Simulate 6 black lines in both gray and binary images
        line_spacing = 10
        start_y = 50
        for i in range(self.config.tab_line_count):
            gray_img[start_y + i * line_spacing - 1 : start_y + i * line_spacing + 2, :] = 0
            binary_img[start_y + i * line_spacing - 1 : start_y + i * line_spacing + 2, :] = 0

        cleaned_binary_img = remove_guitar_tabs(binary_img.copy(), gray_img.copy(), self.config, debug=True, image_stem="test_cleaned")

        # Verify that the tab region is now white in the cleaned image
        # The region should be from approx 50-4 (padding) to 100+4 (padding)
        self.assertEqual(cleaned_binary_img[50, 50], self.config.pixel_white)
        self.assertEqual(cleaned_binary_img[90, 50], self.config.pixel_white)
        # Verify areas outside the tab region are unchanged (still black in this case)
        self.assertEqual(cleaned_binary_img[20, 50], 0)
        self.assertEqual(cleaned_binary_img[150, 50], 0)
        self.assertTrue((self.debug_dir / "test_cleaned_lines.png").exists())

if __name__ == "__main__":
    unittest.main()