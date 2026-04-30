import subprocess
import os
import shutil
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
import uvicorn
from omr_processor import process_score

app = FastAPI()

# Configuration
AUDIVERIS_CMD = "audiveris"
UPLOAD_DIR = Path("temp_uploads")
OUTPUT_DIR = Path("processed_scores")

# Ensure base directories exist
for d in [UPLOAD_DIR, OUTPUT_DIR]:
    d.mkdir(exist_ok=True)

def run_omr_engine(input_image_path, file_stem):
    """Safely invokes the OMR engine and handles the file search."""
    request_output_dir = OUTPUT_DIR / file_stem
    request_output_dir.mkdir(exist_ok=True, parents=True)

    command = [
        AUDIVERIS_CMD, "-batch", "-export",
        "-option", "org.audiveris.omr.sheet.grid.GridBuilder.threads=1", # Fixes Java crash
        "-output", str(request_output_dir),
        str(input_image_path)
    ]
    
    print(f"🚀 Running OMR on {file_stem}...")
    # This prints the command exactly as it would be typed in a terminal
    print("\n--- DEBUG: AUDIVERIS COMMAND ---")
    print(subprocess.list2cmdline(command))
    print("--------------------------------\n")
    # ---------------------
    result = subprocess.run(command, capture_output=True, text=True)

    # Search for the generated .mxl file
    mxl_files = list(request_output_dir.glob("**/*.mxl"))
    if not mxl_files:
        print(f"STDOUT: {result.stdout}")
        return None
    return mxl_files[0]

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
        mxl_path = run_omr_engine(temp_raw_path, file_stem)
        
        # --- PASS 2: Fallback to Refined Image ---
        if not mxl_path:
            print(f"⚠️ Pass 1 failed. Refining image and retrying...")
            # This triggers your OpenCV cleanup pipeline
            cleaned_path = process_score(str(temp_raw_path), debug=True) 
            
            # Retry engine with the cleaned/healed image
            mxl_path = run_omr_engine(cleaned_path, f"{file_stem}_refined")

        # Final check
        if not mxl_path:
            raise HTTPException(
                status_code=404, 
                detail="Audiveris failed on both raw and refined image passes."
            )

        return FileResponse(
            path=mxl_path, 
            media_type='application/vnd.recordare.musicxml+xml', 
            filename=f"{file_stem}.mxl"
        )

    except Exception as e:
        print(f"🔥 Server Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        if temp_raw_path.exists():
            os.remove(temp_raw_path)

# This block starts the local server
if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)