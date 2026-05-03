# score2sound

A Python tool that lets users upload a sheet music image and get generated sound output.

## Clone

```bash
git clone https://github.com/ThinhLe-Dave/score2sound.git
cd score2sound
```

## Setup

```bash
python3.11 -m venv venv
source venv/bin/activate
python3.11 -m pip install --upgrade pip
python3.11 -m pip install -r requirements.txt
```

> Note: This project uses `homr` for OMR, so a Python 3.11 virtual environment is still recommended for compatibility with all dependencies.

## Prerequisites

Optical music recognition runs through **[Homr](https://github.com/liebharc/homr)** (`homr` CLI), installed with the Python dependencies below. The package may download model checkpoints on first run.

Verify after setup:

```bash
homr --help
```

On first run, Homr may download model checkpoints into its package directory.

### macOS SSL certificate note (common)

If you see `ssl.SSLCertVerificationError: CERTIFICATE_VERIFY_FAILED` while Homr is downloading checkpoints, run the service with a CA bundle from `certifi`:

```bash
source venv/bin/activate
export SSL_CERT_FILE="$(python -m certifi)"
export REQUESTS_CA_BUNDLE="$SSL_CERT_FILE"
python main.py
```

When running through `python3 main.py`, the service automatically sets SSL cert env vars for Homr.

### Manual checkpoint download (fallback)

If you cannot fix SSL on your machine, Homr will download its model files automatically. You do not need to manually download Homr checkpoint files for this project.

## Run the service

```bash
python3 main.py
```

### Run helper script

```bash
chmod +x run.sh
./run.sh serve
```

To install dependencies or run tests with the helper script:

```bash
./run.sh install
./run.sh test
```

## Test locally

Open:

`http://127.0.0.1:8000/`

## API usage

### Endpoint

- `POST /process-score`
- Accepts: multipart form with `file` (image of sheet music)
- Returns: generated `.musicxml` file on success

### Example request

```bash
curl -X POST "http://127.0.0.1:8000/process-score" \
  -F "file=@/absolute/path/to/score.png" \
  --output result.musicxml
```

### Success response

- HTTP `200 OK`
- Content-Type: `application/vnd.recordare.musicxml+xml`
- Body: MusicXML `.musicxml` file (saved as `result.musicxml` in the curl example)

### Error responses

- HTTP `404`: Homr failed on both raw and refined image passes
- HTTP `500`: unexpected server/runtime error
