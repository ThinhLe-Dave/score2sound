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

> Note: This project depends on `numpy==1.23.5`, which does not have prebuilt wheels for Python 3.12. Use Python 3.11 for best compatibility with `oemer` and the pinned requirements.

## Prerequisites

Optical music recognition runs through **[Oemer](https://github.com/BreezeWhite/oemer)** (`oemer` CLI), installed with the Python dependencies below. ONNXRuntime is used by default; optionally install `oemer[tf]` for TensorFlow inference.

Verify after setup:

```bash
oemer -h
```

On first run, Oemer may download model checkpoints into its package directory.

### macOS SSL certificate note (common)

If you see `ssl.SSLCertVerificationError: CERTIFICATE_VERIFY_FAILED` while Oemer is downloading checkpoints, run the service (and `oemer`) with a CA bundle from `certifi`:

```bash
source .venv/bin/activate
export SSL_CERT_FILE="$(python -m certifi)"
export REQUESTS_CA_BUNDLE="$SSL_CERT_FILE"
oemer /absolute/path/to/score.png -o processed_scores/test_run
```

When running through `python3 main.py`, the service automatically sets SSL cert env vars for Oemer and applies NumPy alias compatibility for current Oemer releases.

### Manual checkpoint download (fallback)

If you cannot fix SSL on your machine, you can download the 4 checkpoint files and place them here:

- `.venv/lib/python3.12/site-packages/oemer/checkpoints/unet_big/model.onnx`
- `.venv/lib/python3.12/site-packages/oemer/checkpoints/unet_big/weights.h5`
- `.venv/lib/python3.12/site-packages/oemer/checkpoints/seg_net/model.onnx`
- `.venv/lib/python3.12/site-packages/oemer/checkpoints/seg_net/weights.h5`

The URLs Oemer uses are:

- `https://github.com/BreezeWhite/oemer/releases/download/checkpoints/1st_model.onnx`
- `https://github.com/BreezeWhite/oemer/releases/download/checkpoints/1st_weights.h5`
- `https://github.com/BreezeWhite/oemer/releases/download/checkpoints/2nd_model.onnx`
- `https://github.com/BreezeWhite/oemer/releases/download/checkpoints/2nd_weights.h5`

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

- HTTP `404`: Oemer failed on both raw and refined image passes
- HTTP `500`: unexpected server/runtime error
