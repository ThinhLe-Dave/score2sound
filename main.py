import os
import shutil
import subprocess
import sys
from pathlib import Path

import certifi
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
import uvicorn
from omr_processor import process_score
from music21 import converter, midi

app = FastAPI()

# Configuration
UPLOAD_DIR = Path("temp_uploads")
OUTPUT_DIR = Path("processed_scores")

# Ensure base directories exist
for d in [UPLOAD_DIR, OUTPUT_DIR]:
    d.mkdir(exist_ok=True)


@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("templates/index.html", "r") as f:
        return f.read()


def run_omr_engine(input_image_path, file_stem):
    """Safely invokes Homr and returns the generated MusicXML path and output directory."""
    request_output_dir = OUTPUT_DIR / file_stem
    request_output_dir.mkdir(exist_ok=True, parents=True)

    input_image_path = Path(input_image_path).resolve()
    image_in_output = request_output_dir / input_image_path.name
    shutil.copy(str(input_image_path), str(image_in_output))

    command = [
        "homr",
        str(image_in_output),
    ]

    print(f"🚀 Running OMR on {file_stem}...")
    print("\n--- DEBUG: HOMR COMMAND ---")
    print(subprocess.list2cmdline(command))
    print("----------------------------\n")

    env = dict(os.environ)
    env.setdefault("SSL_CERT_FILE", certifi.where())
    env.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
    venv_bin = Path(sys.executable).parent
    env["PATH"] = f"{venv_bin}:{env.get('PATH', '')}"

    result = subprocess.run(command, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        print(f"STDERR: {result.stderr}")
        print(f"STDOUT: {result.stdout}")
        return None, None

    musicxml_files = sorted(
        request_output_dir.glob("**/*.musicxml"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not musicxml_files:
        musicxml_files = sorted(
            request_output_dir.glob("**/*.xml"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

    if not musicxml_files:
        print(f"STDOUT: {result.stdout}")
        return None, None

    return musicxml_files[0], request_output_dir

def convert_musicxml_to_midi(musicxml_path, output_dir, file_stem):
    """Convert MusicXML to MIDI using music21."""
    try:
        # Load the MusicXML file
        score = converter.parse(musicxml_path)
        
        # Create MIDI file path
        midi_path = output_dir / f"{file_stem}.midi"
        
        # Convert to MIDI
        mf = midi.translate.music21ObjectToMidiFile(score)
        mf.open(str(midi_path), 'wb')
        mf.write()
        mf.close()
        
        return midi_path
    except Exception as e:
        print(f"Error converting to MIDI: {e}")
        return None

@app.post("/process-score")
async def handle_process_score(file: UploadFile = File(...)):
    """API endpoint with fallback image refinement logic."""
    file_stem = Path(file.filename).stem
    temp_raw_path = UPLOAD_DIR / file.filename
    
    # Save the upload
    with open(temp_raw_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        # --- PASS 1: Try Raw Image ---
        print(f"🔄 Pass 1: Attempting OMR on raw image...")
        mxl_path, request_output_dir = run_omr_engine(temp_raw_path, file_stem)
        
        # --- PASS 2: Fallback to Refined Image ---
        if not mxl_path:
            print(f"⚠️ Pass 1 failed. Refining image and retrying...")
            # This triggers your OpenCV cleanup pipeline
            cleaned_path = process_score(str(temp_raw_path), debug=True) 
            
            # Retry engine with the cleaned/healed image
            mxl_path, request_output_dir = run_omr_engine(Path(cleaned_path), f"{file_stem}_refined")

        # Final check
        if not mxl_path:
            raise HTTPException(
                status_code=404, 
                detail="Homr failed on both raw and refined image passes."
            )

        mxl_path = Path(mxl_path)
        if not mxl_path.exists():
            raise HTTPException(
                status_code=500,
                detail=f"MusicXML file was not created: {mxl_path}"
            )

        # Convert to MIDI for playback
        midi_path = convert_musicxml_to_midi(str(mxl_path), request_output_dir, file_stem)
        
        # Return JSON with file info
        return JSONResponse({
            "musicxml_url": f"/download/musicxml/{file_stem}",
            "midi_url": f"/download/midi/{file_stem}" if midi_path else None,
            "filename": file_stem
        })

    except Exception as e:
        print(f"🔥 Server Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        if temp_raw_path.exists():
            os.remove(temp_raw_path)

@app.get("/download/musicxml/{file_stem}")
async def download_musicxml(file_stem: str):
    """Download the MusicXML file."""
    # Find the MusicXML file in processed_scores
    for subdir in OUTPUT_DIR.iterdir():
        if subdir.is_dir():
            musicxml_files = list(subdir.glob("*.musicxml"))
            if musicxml_files:
                # Check if this matches the file_stem
                if file_stem in str(musicxml_files[0]):
                    return FileResponse(
                        path=str(musicxml_files[0]),
                        media_type='application/vnd.recordare.musicxml+xml',
                        filename=f"{file_stem}.musicxml"
                    )
    
    raise HTTPException(status_code=404, detail="MusicXML file not found")

@app.get("/download/midi/{file_stem}")
async def download_midi(file_stem: str):
    """Download the MIDI file."""
    # Find the MIDI file in processed_scores
    for subdir in OUTPUT_DIR.iterdir():
        if subdir.is_dir():
            midi_files = list(subdir.glob("*.midi"))
            if midi_files:
                # Check if this matches the file_stem
                if file_stem in str(midi_files[0]):
                    return FileResponse(
                        path=str(midi_files[0]),
                        media_type='audio/midi',
                        filename=f"{file_stem}.midi"
                    )
    
    raise HTTPException(status_code=404, detail="MIDI file not found")

# This block starts the local server
if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)