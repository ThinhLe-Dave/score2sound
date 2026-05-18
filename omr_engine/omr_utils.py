import os
import shutil
import subprocess
import sys
from pathlib import Path

import certifi
from music21 import converter, midi
from .omr_processor import process_score
from .tab_removal import OMRProcessingConfig


async def process_full_pipeline(upload_file, upload_dir, output_dir):
    """Service logic to orchestrate the OMR process (Always refine before engine)."""
    file_stem = Path(upload_file.filename).stem
    temp_raw_path = upload_dir / upload_file.filename
    
    with open(temp_raw_path, "wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)

    cleaned_path = None
    try:
        # Step 1: Image Processing (Tab removal, etc.)
        print(f"🔄 Processing score image (refinement)...")
        cleaned_path = process_score(str(temp_raw_path), config=OMRProcessingConfig(remove_tabs=True), debug=False)
        
        # Step 2: Run OMR Engine on the processed image
        print(f"🎹 Running OMR engine...")
        mxl_path, req_out_dir = run_omr_engine(Path(cleaned_path), file_stem, output_dir)
        
        if not mxl_path or not mxl_path.exists():
            raise FileNotFoundError("OMR Engine failed to produce MusicXML.")

        midi_path = convert_musicxml_to_midi(str(mxl_path), req_out_dir, file_stem)
        
        print(f"✅ [Debug] Pipeline complete for {file_stem}. MusicXML: {mxl_path}, MIDI created: {midi_path is not None}")
        return {
            "stem": file_stem,
            "processed_stem": Path(cleaned_path).stem,
            "mxl_path": str(mxl_path),
            "midi_created": midi_path is not None
        }

    finally:
        _cleanup_files([temp_raw_path, cleaned_path])

def _cleanup_files(paths):
    for p in paths:
        if p and (path_obj := Path(p)).exists():
            path_obj.unlink()


def run_omr_engine(input_image_path, file_stem, output_dir):
    request_output_dir = output_dir / file_stem
    request_output_dir.mkdir(exist_ok=True, parents=True)
    print(f"📁 [Debug] OMR output directory: {request_output_dir}")

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
        print(f"❌ [Debug] OMR engine failed with return code {result.returncode}.")
        print(f"   STDOUT: {result.stdout}")
        print(f"   STDERR: {result.stderr}")
        return None, None

    musicxml_files = sorted(
        request_output_dir.glob("**/*.musicxml"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not musicxml_files:
        print(f"🔄 [Debug] No .musicxml files found, falling back to .xml search.")
        musicxml_files = sorted(
            request_output_dir.glob("**/*.xml"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

    if not musicxml_files:
        print(f"🔍 [Debug] No MusicXML files found in {request_output_dir}.")
        return None, None
    print(f"🎶 [Debug] Found MusicXML file: {musicxml_files[0]}")
    return musicxml_files[0], request_output_dir


def convert_musicxml_to_midi(musicxml_path, output_dir, file_stem):
    try:
        print(f"🎼 [Debug] Converting MusicXML to MIDI: {musicxml_path}")
        score = converter.parse(musicxml_path)

        # Force all instruments to Piano (MIDI Program 0) for reliable web playback
        # as web soundfonts often lack complete General MIDI patch sets (like Voice).
        from music21 import instrument
        for part in score.parts:
            for inst in part.recurse().getElementsByClass(instrument.Instrument):
                inst.midiProgram = 0
            if not part.getInstruments():
                part.insert(0, instrument.Piano())

        # Log time signature information
        time_signatures = score.recurse().getElementsByClass('TimeSignature')

        # Log track information
        for i, part in enumerate(score.parts):
            print(f"   Track {i} ({part.partName}): {len(part.flatten().notes)} notes")
        
        midi_path = output_dir / f"{file_stem}.midi"
        mf = midi.translate.music21ObjectToMidiFile(score)
        mf.open(str(midi_path), 'wb')
        mf.write()
        mf.close()
        return midi_path
    except Exception as e:
        print(f"❌ [Debug] Error converting to MIDI: {e}", file=sys.stderr)
        return None


def find_file_in_output_dir(output_dir, file_stem, extension):
    for subdir in output_dir.iterdir():
        if subdir.is_dir():
            files = list(subdir.glob(f"*.{extension}"))
            if files:
                # Prefer exact match, then variants, then first found
                targets = [file_stem, f"{file_stem}_refined", f"{file_stem}_cleaned"]
                for t in targets:
                    for f in files:
                        if f.stem == t:
                            return f
                if any(t in f.stem for t in targets for f in files):
                    return files[0]
    return None