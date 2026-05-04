import os
import shutil
import subprocess
import sys
from pathlib import Path

import certifi
from music21 import converter, midi


def run_omr_engine(input_image_path, file_stem, output_dir):
    """Safely invokes Homr and returns the generated MusicXML path and output directory."""
    request_output_dir = output_dir / file_stem
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


def find_file_in_output_dir(output_dir, file_stem, extension):
    """Find a file with the given stem and extension in the output directory."""
    for subdir in output_dir.iterdir():
        if subdir.is_dir():
            files = list(subdir.glob(f"*.{extension}"))
            if files:
                # Check if this matches the file_stem
                if file_stem in str(files[0]):
                    return files[0]
    return None