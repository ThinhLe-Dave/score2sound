import unittest
import io
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi import UploadFile

# Internal modules
from omr_engine.omr_utils import find_file_in_output_dir, process_full_pipeline

class TestOmrUtils(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        """Set up temporary directories for uploads and processed outputs."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.upload_dir = self.test_dir / "temp_uploads"
        self.output_dir = self.test_dir / "processed_scores"
        self.upload_dir.mkdir()
        self.output_dir.mkdir()

    def tearDown(self):
        """Remove temporary directories after tests."""
        shutil.rmtree(self.test_dir)

    def test_find_file_in_output_dir_exists(self):
        """Test that find_file_in_output_dir returns the correct path when a file exists."""
        stem = "test_score_abc"
        ext = "musicxml"
        # The utility iterates through subdirectories, so we create one
        request_dir = self.output_dir / "request_1"
        request_dir.mkdir()
        # Use a name that contains the stem to satisfy find_file_in_output_dir logic
        # The utility checks: if files and file_stem in str(files[0])
        target_file = request_dir / f"{stem}.{ext}" 
        target_file.touch()

        result = find_file_in_output_dir(self.output_dir, stem, ext)
        self.assertEqual(result, target_file)

    def test_find_file_in_output_dir_missing(self):
        """Test that find_file_in_output_dir returns None when a file is missing."""
        result = find_file_in_output_dir(self.output_dir, "nonexistent", "midi")
        self.assertIsNone(result)

    @patch("omr_engine.omr_utils.process_score")
    @patch("subprocess.run")
    @patch("omr_engine.omr_utils.convert_musicxml_to_midi")
    async def test_process_full_pipeline_success(self, mock_convert_midi, mock_run, mock_process_score):
        """Test the full pipeline successfully processes an image and finds outputs."""

        cleaned_file = self.upload_dir / "cleaned_score.png"
        cleaned_file.touch()
        mock_process_score.return_value = str(cleaned_file)    

        # Mock a successful shell execution of the OMR engine (homr)
        mock_run.return_value = MagicMock(returncode=0)

        # Mock MIDI conversion to return a fake path
        mock_convert_midi.return_value = self.output_dir / "fake.midi"

        # Create a mock UploadFile instance
        file_content = b"not-a-real-image"
        filename = "my_sheet_music.png"
        file = UploadFile(filename=filename, file=io.BytesIO(file_content))

        # Simulate the creation of output files by the OMR engine in the correct subdirectory
        stem = "my_sheet_music"
        refined_dir = self.output_dir / f"{stem}_refined"
        refined_dir.mkdir()
        (refined_dir / f"{stem}_refined.musicxml").touch()

        # Execute the pipeline
        result = await process_full_pipeline(file, self.upload_dir, self.output_dir)

        # Verify the returned structure matches what main.py expects
        self.assertEqual(result["stem"], stem)
        self.assertTrue(result["midi_created"])
        
        # Verify internal calls
        mock_process_score.assert_called_once()
        mock_run.assert_called()

    @patch("omr_engine.omr_utils.process_score")
    @patch("subprocess.run")
    async def test_process_full_pipeline_failure(self, mock_run, mock_process_score):
        """Test pipeline behavior when the OMR engine fails to produce output."""
        cleaned_file = self.upload_dir / "cleaned_score.png"
        cleaned_file.touch()
        mock_process_score.return_value = str(cleaned_file)
        
        # Simulate an OMR engine failure (non-zero return code)
        mock_run.return_value = MagicMock(returncode=1)

        file = UploadFile(filename="fail.png", file=io.BytesIO(b"data"))

        # The pipeline should raise an error if critical output (MusicXML) is missing
        with self.assertRaises(Exception):
            await process_full_pipeline(file, self.upload_dir, self.output_dir)

if __name__ == "__main__":
    unittest.main()
