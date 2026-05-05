let currentResult = null;
let osmd = null;
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const imagePreview = document.getElementById('image-preview');
const previewContainer = document.getElementById('preview-container');
const fileNameDisplay = document.getElementById('file-name');
let progressInterval;

// Handle click on drop zone
dropZone.addEventListener('click', () => fileInput.click());

// Handle drag and drop
['dragover', 'dragleave', 'drop'].forEach(eventName => {
    dropZone.addEventListener(eventName, e => {
        e.preventDefault();
        e.stopPropagation();
    });
});

dropZone.addEventListener('dragover', () => dropZone.classList.add('drag-over'));
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', (e) => {
    dropZone.classList.remove('drag-over');
    const files = e.dataTransfer.files;
    if (files.length) {
        fileInput.files = files;
        handleFileSelect(files[0]);
    }
});

fileInput.addEventListener('change', (e) => {
    if (e.target.files.length) handleFileSelect(e.target.files[0]);
});

function handleFileSelect(file) {
    fileNameDisplay.textContent = file.name;
    const reader = new FileReader();
    reader.onload = (e) => {
        imagePreview.src = e.target.result;
        previewContainer.style.display = 'block';
    };
    reader.readAsDataURL(file);
}

async function initPlayback(xmlUrl, midiUrl) {
    const loadingText = document.getElementById('loadingText');
    loadingText.textContent = "Rendering sheet music...";
    
    try {
        if (!osmd) {
            osmd = new opensheetmusicdisplay.OpenSheetMusicDisplay("osmd-container", {
                autoResize: true,
                drawTitle: false
            });
        }
        
        const response = await fetch(xmlUrl);
        const xmlText = await response.text();
        await osmd.load(xmlText);
        osmd.render();
        
        // Set the MIDI source for the player
        if (midiUrl) {
            const player = document.getElementById('midiPlayer');
            player.src = midiUrl;
        }
    } catch (err) {
        console.error("Playback initialization failed:", err);
    }
}

function startProgress() {
    const bar = document.getElementById('progressBar');
    const text = document.getElementById('loadingText');
    let width = 0;
    bar.style.width = '0%';
    text.textContent = "Analyzing sheet music...";
    
    clearInterval(progressInterval);
    progressInterval = setInterval(() => {
        if (width < 95) {
            // Mimic progress slowing down as it reaches the end of detection
            const increment = Math.max(0.1, (95 - width) / 60);
            width += increment;
            bar.style.width = width + '%';
            
            if (width > 80) text.textContent = "Finalizing digital score and MIDI...";
            else if (width > 50) text.textContent = "Detecting notes and rhythms...";
            else if (width > 20) text.textContent = "Scanning staff lines...";
        }
    }, 200);
}

document.getElementById('uploadForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    // Resume Tone.js AudioContext on user interaction to comply with browser policy
    if (typeof Tone !== 'undefined') {
        await Tone.start();
    }

    if (!fileInput.files.length) return;

    // Clear previous MIDI source to stop playback
    document.getElementById('midiPlayer').src = null;

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    
    const submitBtn = document.getElementById('submitBtn');
    submitBtn.disabled = true;
    document.getElementById('loading').style.display = 'block';
    document.getElementById('result').style.display = 'none';
    startProgress();
    
    fetch('/process-score', {
        method: 'POST',
        body: formData
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Processing failed');
        }
        return response.json();
    })
    .then(data => {
        clearInterval(progressInterval);
        document.getElementById('progressBar').style.width = '100%';
        document.getElementById('loadingText').textContent = "Processing complete!";
        currentResult = data;
        
        // Show results before rendering to ensure container width is detected correctly
        document.getElementById('loading').style.display = 'none';
        document.getElementById('result').style.display = 'block';
        initPlayback(data.musicxml_url, data.midi_url);
        
        // Enable/disable buttons based on available files
        document.getElementById('downloadMusicXmlBtn').disabled = false;
        document.getElementById('downloadMidiBtn').disabled = !data.midi_url;
    })
    .catch(error => {
        clearInterval(progressInterval);
        document.getElementById('loading').style.display = 'none';
        submitBtn.disabled = false;
        alert('Error processing the score: ' + error.message);
    })
    .finally(() => {
        submitBtn.disabled = false;
    });
});

// Download MusicXML
document.getElementById('downloadMusicXmlBtn').addEventListener('click', function() {
    if (currentResult) {
        window.open(currentResult.musicxml_url, '_blank');
    }
});

// Download MIDI
document.getElementById('downloadMidiBtn').addEventListener('click', function() {
    if (currentResult && currentResult.midi_url) {
        window.open(currentResult.midi_url, '_blank');
    }
});