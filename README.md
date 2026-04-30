# score2sound

A Python tool that lets users upload a sheet music image and get generated sound output.

## Clone

```bash
git clone https://github.com/ThinhLe-Dave/score2sound.git
cd score2sound
```

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

## Prerequisites

This project calls the `audiveris` CLI from the backend, so Audiveris must be installed and available in your shell `PATH`.

Verify:

```bash
audiveris -version
```

If this command is not found, install Audiveris first, then rerun the service.

## Run the service

```bash
python3 main.py
```

## Test locally

Open:

`http://127.0.0.1:8000/`

## API usage

### Endpoint

- `POST /process-score`
- Accepts: multipart form with `file` (image of sheet music)
- Returns: generated `.mxl` file on success

### Example request

```bash
curl -X POST "http://127.0.0.1:8000/process-score" \
  -F "file=@/absolute/path/to/score.png" \
  --output result.mxl
```

### Success response

- HTTP `200 OK`
- Content-Type: `application/vnd.recordare.musicxml+xml`
- Body: MusicXML `.mxl` file (saved as `result.mxl` in the curl example)

### Error responses

- HTTP `404`: Audiveris failed on both raw and refined image passes
- HTTP `500`: unexpected server/runtime error
