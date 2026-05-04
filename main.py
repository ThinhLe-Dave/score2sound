import os
import shutil
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
import uvicorn
from omr_processor import process_score
from omr_utils import run_omr_engine, convert_musicxml_to_midi, find_file_in_output_dir

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


@app.post("/process-score")
async def handle_process_score(file: UploadFile = File(...)):
    """API endpoint with fallback image refinement logic."""
    file_stem = Path(file.filename).stem
    temp_raw_path = UPLOAD_DIR / file.filename
    cleaned_path = None
    
    # Save the upload
    with open(temp_raw_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        # --- PASS 1: Try Raw Image ---
        print(f"🔄 Pass 1: Attempting OMR on raw image...")
        mxl_path, request_output_dir = run_omr_engine(temp_raw_path, file_stem, OUTPUT_DIR)
        
        # --- PASS 2: Fallback to Refined Image ---
        if not mxl_path:
            print(f"⚠️ Pass 1 failed. Refining image and retrying...")
            # This triggers your OpenCV cleanup pipeline
            cleaned_path = process_score(str(temp_raw_path), debug=True) 
            
            # Retry engine with the cleaned/healed image
            mxl_path, request_output_dir = run_omr_engine(Path(cleaned_path), f"{file_stem}_refined", OUTPUT_DIR)

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
        if cleaned_path and Path(cleaned_path).exists():
            os.remove(cleaned_path)

@app.get("/download/musicxml/{file_stem}")
async def download_musicxml(file_stem: str):
    """Download the MusicXML file."""
    musicxml_file = find_file_in_output_dir(OUTPUT_DIR, file_stem, "musicxml")
    if musicxml_file:
        return FileResponse(
            path=str(musicxml_file),
            media_type='application/vnd.recordare.musicxml+xml',
            filename=f"{file_stem}.musicxml"
        )
    
    raise HTTPException(status_code=404, detail="MusicXML file not found")

@app.get("/download/midi/{file_stem}")
async def download_midi(file_stem: str):
    """Download the MIDI file."""
    midi_file = find_file_in_output_dir(OUTPUT_DIR, file_stem, "midi")
    if midi_file:
        return FileResponse(
            path=str(midi_file),
            media_type='audio/midi',
            filename=f"{file_stem}.midi"
        )
    
    raise HTTPException(status_code=404, detail="MIDI file not found")

# This block starts the local server
if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)