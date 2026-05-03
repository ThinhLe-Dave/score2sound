import os
import shutil
import subprocess
import sys
from pathlib import Path

import certifi
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
import uvicorn
from omr_processor import process_score

app = FastAPI()

# Configuration
UPLOAD_DIR = Path("temp_uploads")
OUTPUT_DIR = Path("processed_scores")

# Ensure base directories exist
for d in [UPLOAD_DIR, OUTPUT_DIR]:
    d.mkdir(exist_ok=True)


def run_omr_engine(input_image_path, file_stem):
    """Safely invokes Homr and returns the generated MusicXML path."""
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
        return None

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
        return None

    return musicxml_files[0]

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
            mxl_path = run_omr_engine(Path(cleaned_path), f"{file_stem}_refined")

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

        return FileResponse(
            path=str(mxl_path), 
            media_type='application/vnd.recordare.musicxml+xml', 
            filename=f"{file_stem}.musicxml"
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