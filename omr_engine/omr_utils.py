import os
import shutil
import subprocess
import sys
from pathlib import Path

import certifi
from music21 import converter, midi
from .omr_processor import process_score


async def process_full_pipeline(upload_file, upload_dir, output_dir):
    """Service logic to orchestrate the OMR process (Raw Pass -> Refined Pass)."""
    file_stem = Path(upload_file.filename).stem
    temp_raw_path = upload_dir / upload_file.filename
    cleaned_path = None
    
    with open(temp_raw_path, "wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)

    try:
        print(f"🔄 Pass 1: Raw image OMR...")
        mxl_path, req_out_dir = run_omr_engine(temp_raw_path, file_stem, output_dir)
        
        if not mxl_path:
            print(f"⚠️ Pass 1 failed. Refining image...")
            cleaned_path = process_score(str(temp_raw_path), debug=True) 
            mxl_path, req_out_dir = run_omr_engine(Path(cleaned_path), f"{file_stem}_refined", output_dir)

        if not mxl_path or not Path(mxl_path).exists():
            raise FileNotFoundError("OMR Engine failed to produce MusicXML on both passes.")

        midi_path = convert_musicxml_to_midi(str(mxl_path), req_out_dir, file_stem)
        
        return {
            "stem": file_stem,
            "mxl_path": str(mxl_path),
            "midi_created": midi_path is not None
        }

    finally:
        _cleanup_files([temp_raw_path, cleaned_path])


def _cleanup_files(paths):
    for p in paths:
        if p:
            path_obj = Path(p)
            if path_obj.exists():
                os.remove(path_obj)


def run_omr_engine(input_image_path, file_stem, output_dir):
    request_output_dir = output_dir / file_stem
    request_output_dir.mkdir(exist_ok=True, parents=True)

    input_image_path = Path(input_image_path).resolve()
    image_in_output = request_output_dir / input_image_path.name
    shutil.copy(str(input_image_path), str(image_in_output))

    command = ["homr", str(image_in_output)]

    env = dict(os.environ)
    env.setdefault("SSL_CERT_FILE", certifi.where())
    env.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
    venv_bin = Path(sys.executable).parent
    env["PATH"] = f"{venv_bin}:{env.get('PATH', '')}"

    result = subprocess.run(command, capture_output=True, text=True, env=env)
    if result.returncode != 0:
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
        return None, None

    return musicxml_files[0], request_output_dir


def convert_musicxml_to_midi(musicxml_path, output_dir, file_stem):
    try:
        score = converter.parse(musicxml_path)
        midi_path = output_dir / f"{file_stem}.midi"
        mf = midi.translate.music21ObjectToMidiFile(score)
        mf.open(str(midi_path), 'wb')
        mf.write()
        mf.close()
        return midi_path
    except Exception as e:
        print(f"Error converting to MIDI: {e}")
        return None


def find_file_in_output_dir(output_dir, file_stem, extension):
    for subdir in output_dir.iterdir():
        if subdir.is_dir():
            files = list(subdir.glob(f"*.{extension}"))
            if files and file_stem in str(files[0]):
                return files[0]
    return None