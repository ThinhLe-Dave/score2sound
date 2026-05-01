import os
import shutil
import subprocess
import sys
import zipfile
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
OEMER_WRAPPER = (
    "import sys\n"
    "import numpy as np\n"
    "if not hasattr(np, 'int'):\n"
    "    np.int = int\n"
    "if not hasattr(np, 'float'):\n"
    "    np.float = float\n"
    "if not hasattr(np, 'bool'):\n"
    "    np.bool = bool\n"
    "from oemer.ete import main\n"
    "sys.argv = ['oemer', *sys.argv[1:]]\n"
    "raise SystemExit(main())\n"
)

# Ensure base directories exist
for d in [UPLOAD_DIR, OUTPUT_DIR]:
    d.mkdir(exist_ok=True)


def _musicxml_to_mxl(musicxml_path: Path, mxl_path: Path) -> None:
    """Wrap an uncompressed MusicXML file in a standard .mxl (zip) container."""
    inner_name = musicxml_path.name
    container = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
        "  <rootfiles>\n"
        f'    <rootfile full-path="{inner_name}" '
        'media-type="application/vnd.recordare.musicxml+xml"/>\n'
        "  </rootfiles>\n"
        "</container>\n"
    )
    mxl_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(mxl_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("META-INF/container.xml", container)
        zf.write(musicxml_path, inner_name)


def run_omr_engine(input_image_path, file_stem):
    """Safely invokes Oemer and returns a packaged .mxl path."""
    request_output_dir = OUTPUT_DIR / file_stem
    request_output_dir.mkdir(exist_ok=True, parents=True)

    command = [
        sys.executable,
        "-c",
        OEMER_WRAPPER,
        str(input_image_path),
        "-o",
        str(request_output_dir),
    ]

    print(f"🚀 Running OMR on {file_stem}...")
    print("\n--- DEBUG: OEMER COMMAND ---")
    print(subprocess.list2cmdline(command))
    print("----------------------------\n")

    env = dict(os.environ)
    # Fixes SSL_CERTIFICATE_VERIFY_FAILED on some macOS Python installs when Oemer
    # downloads checkpoints via urllib.
    env.setdefault("SSL_CERT_FILE", certifi.where())
    env.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
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
        print(f"STDOUT: {result.stdout}")
        return None

    mxl_out = request_output_dir / f"{file_stem}.mxl"
    _musicxml_to_mxl(musicxml_files[0], mxl_out)
    return mxl_out

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
                detail="Oemer failed on both raw and refined image passes."
            )

        return FileResponse(
            path=mxl_path, 
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