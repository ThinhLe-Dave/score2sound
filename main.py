from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Internal modules
from omr_engine.omr_utils import process_full_pipeline, find_file_in_output_dir

app = FastAPI()

# Configuration
UPLOAD_DIR = Path("temp_uploads")
OUTPUT_DIR = Path("processed_scores")

# Ensure base directories exist
for d in [UPLOAD_DIR, OUTPUT_DIR]:
    d.mkdir(exist_ok=True)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="templates/static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("templates/index.html", "r") as f:
        return f.read()


@app.post("/process-score")
async def handle_process_score(file: UploadFile = File(...)):
    """API endpoint with fallback image refinement logic."""
    try:
        # Delegate core logic to the service layer
        result = await process_full_pipeline(
            file, 
            UPLOAD_DIR, 
            OUTPUT_DIR
        )

        return JSONResponse({
            "musicxml_url": f"/download/musicxml/{result['stem']}",
            "midi_url": f"/download/midi/{result['stem']}" if result['midi_created'] else None,
            "filename": result['stem']
        })

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        print(f"🔥 Server Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

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