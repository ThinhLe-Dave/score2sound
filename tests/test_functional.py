import pytest
from starlette.testclient import TestClient
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile

# Import the FastAPI app from main.py
from main import app

client = TestClient(app)

def test_read_root():
    """Test that the homepage loads correctly and returns HTML."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

@patch("main.process_full_pipeline")
def test_handle_process_score_success(mock_process):
    """Test the score processing endpoint with a successful pipeline simulation."""
    # Mock the return value of the pipeline service
    mock_process.return_value = {
        "stem": "test_score",
        "mxl_path": "/fake/path/test_score.musicxml",
        "midi_created": True
    }
    
    # Simulate uploading a file
    files = {"file": ("test.png", b"fake_image_content", "image/png")}
    response = client.post("/process-score", files=files)
    
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["filename"] == "test_score"
    assert "/download/musicxml/test_score" in json_data["musicxml_url"]
    assert "/download/midi/test_score" in json_data["midi_url"]

@patch("main.process_full_pipeline")
def test_handle_process_score_not_found(mock_process):
    """Test that 404 is returned if the OMR engine fails to find/produce output."""
    mock_process.side_effect = FileNotFoundError("OMR Engine failed to produce MusicXML")
    
    files = {"file": ("fail.png", b"fake_image_content", "image/png")}
    response = client.post("/process-score", files=files)
    
    assert response.status_code == 404
    assert "OMR Engine failed" in response.json()["detail"]

@patch("main.find_file_in_output_dir")
def test_download_musicxml_success(mock_find):
    """Test that the MusicXML download endpoint serves a file correctly."""
    with tempfile.NamedTemporaryFile(suffix=".musicxml") as tf:
        mock_find.return_value = Path(tf.name)
        response = client.get("/download/musicxml/test_score")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/vnd.recordare.musicxml+xml"

def test_download_musicxml_404():
    """Test MusicXML download for a missing file."""
    with patch("main.find_file_in_output_dir", return_value=None):
        response = client.get("/download/musicxml/nonexistent")
        assert response.status_code == 404

@patch("main.find_file_in_output_dir")
def test_download_midi_success(mock_find):
    """Test that the MIDI download endpoint serves a file correctly."""
    with tempfile.NamedTemporaryFile(suffix=".midi") as tf:
        mock_find.return_value = Path(tf.name)
        response = client.get("/download/midi/test_score")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/midi"

def test_download_midi_404():
    """Test MIDI download for a missing file."""
    with patch("main.find_file_in_output_dir", return_value=None):
        response = client.get("/download/midi/nonexistent")
        assert response.status_code == 404

if __name__ == "__main__":
    # This allows running the functional tests directly via python
    import pytest
    pytest.main([__file__])