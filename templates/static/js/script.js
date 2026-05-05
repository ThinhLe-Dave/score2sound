let currentResult = null;
let currentMidiUrl = null;
let osmd = null;
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const imagePreview = document.getElementById('image-preview');
const previewContainer = document.getElementById('preview-container');
const fileNameDisplay = document.getElementById('file-name');
const tempoSlider = document.getElementById('tempoSlider');
const tempoValue = document.getElementById('tempoValue');
let progressInterval;
let baseBpm = 120; // Default fallback for MIDI tempo

// Debug: Monitor global Tone.js volume
if (typeof Tone !== 'undefined') {
    setInterval(() => {
        if (Tone.Destination) {
            const transportBPM = (Tone.Transport && Tone.Transport.bpm) ? Tone.Transport.bpm.value.toFixed(1) : 'N/A';
            
            // Check our custom tracking property for the multiplier
            const playRate = (Tone.Transport && typeof Tone.Transport._customRate === 'number')
                ? Tone.Transport._customRate.toFixed(2)
                : '1.00';
            console.log(`[Debug] Volume: ${Tone.Destination.volume.value}dB | Tone State: ${Tone.context.state} | Transport BPM: ${transportBPM} | Rate: ${playRate}x`);
        }
    }, 5000);
}

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

// Handle tempo adjustment
tempoSlider.addEventListener('input', (e) => {
    const val = e.target.value;
    console.log(`[Debug] Tempo slider changed to: ${val}`);
    tempoValue.textContent = `${val} BPM`;
    const player = document.getElementById('midiPlayer');
    if (player) {
        // html-midi-player expects a numeric multiplier.
        // Converting the BPM slider to a multiplier (e.g., 100 BPM = 1.0x)
        const multiplier = (parseFloat(val) / 100).toFixed(2);

        // Update both the property for logic and attribute for reactivity
        player.tempo = parseFloat(multiplier);
        player.setAttribute('tempo', multiplier);

        // Real-time speed adjustment via Tone.js Transport BPM scaling
        if (window.Tone && Tone.Transport && Tone.Transport.bpm) {
            Tone.Transport._customRate = parseFloat(multiplier);
            Tone.Transport.bpm.value = baseBpm * parseFloat(multiplier);
            console.log(`[Debug] Audio Engine BPM adjusted to: ${Tone.Transport.bpm.value.toFixed(1)} (Rate: ${multiplier}x)`);
        }
    }
});

async function initPlayback(xmlUrl, midiUrl) {
    console.log("[Debug] Initializing playback. XML:", xmlUrl, "MIDI:", midiUrl);
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
            try {
                const midiResponse = await fetch(midiUrl);
                const midiBlob = await midiResponse.blob();
                
                const player = document.getElementById('midiPlayer');
                const visualizer = document.getElementById('midiVisualizer');
                
                // Check Tone.js context before setting source
                if (Tone.context.state !== 'running') {
                    console.warn("[Debug] Tone.js is not running. Resuming...");
                    await Tone.start();
                }

                console.log(`[Debug] Setting player source. Blob size: ${midiBlob.size} bytes`);
                
                // Reset player internal state
                player.stop();
                
                // Clean up previous object URL to prevent memory leaks
                if (currentMidiUrl) {
                    URL.revokeObjectURL(currentMidiUrl);
                }
                currentMidiUrl = URL.createObjectURL(midiBlob);
                
                player.src = currentMidiUrl;
                if (visualizer) visualizer.src = currentMidiUrl;
                
                // Apply tempo with a slight delay to ensure component has parsed MIDI header
                setTimeout(() => {
                    const multiplier = parseFloat(tempoSlider.value) / 100;
                    player.tempo = multiplier;
                    if (typeof Tone !== 'undefined' && Tone.Transport && Tone.Transport.bpm) {
                        Tone.Transport._customRate = parseFloat(multiplier);
                        // baseBpm will be captured on 'start', but we apply initial scale here
                        Tone.Transport.bpm.value = baseBpm * multiplier;
                    }
                }, 100);

                // Re-resume audio context after setting source to ensure it's ready for playback
                if (typeof player.resumeAudioContext === 'function') {
                    await player.resumeAudioContext();
                }
            } catch (midiErr) {
                console.error("[Debug] Failed to load MIDI blob:", midiErr);
            }
        }
    } catch (err) {
        console.error("[Debug] Playback initialization failed:", err);
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
        console.log("[Debug] Attempting to start Tone.js...");
        await Tone.start();
        await Tone.context.resume();
        await Tone.getContext().resume();
        
        if (Tone.Transport && typeof Tone.Transport._customRate === 'undefined') {
            Tone.Transport._customRate = 1.0;
        }
        console.log("[Debug] Tone state after start/resume:", Tone.context.state);
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

// Player Specific Event Listeners
const player = document.getElementById('midiPlayer');

// CRITICAL: Listen for interaction on the player itself to resume AudioContext.
// Browsers often require the gesture to be on the actual playing element or its container.
const resumeAudio = async () => {
    if (Tone.context.state !== 'running' || Tone.context.state === 'interrupted') {
        await Tone.start();
        await Tone.context.resume();
        if (typeof player.resumeAudioContext === 'function') {
            await player.resumeAudioContext();
        }
        console.log(`[Debug] AudioContext resumed via Interaction (${Tone.context.state})`);
    }
};

['pointerdown', 'click', 'touchstart'].forEach(type => player.addEventListener(type, resumeAudio));

player.addEventListener('load', () => console.log("[Debug] MIDI Player successfully loaded the source."));
player.addEventListener('start', (e) => {
    // Inspect the note sequence being played
    console.log("[Debug] Note Sequence Object:", player.noteSequence);

    // Capture the base BPM set by Magenta for this MIDI and apply current multiplier
    if (Tone.Transport && Tone.Transport.bpm) {
        // Small delay to let Magenta finish its internal start logic which often resets BPM
        setTimeout(() => {
            // Magenta sets the Transport BPM when it starts a sequence based on MIDI metadata
            baseBpm = Tone.Transport.bpm.value;
            const multiplier = parseFloat(tempoSlider.value) / 100;
            Tone.Transport._customRate = parseFloat(multiplier);
            Tone.Transport.bpm.value = baseBpm * multiplier;
            console.log(`[Debug] Base BPM captured: ${baseBpm.toFixed(1)} | Adjusted BPM: ${Tone.Transport.bpm.value.toFixed(1)}`);
            
            if (Tone.context.state !== 'running') {
                Tone.context.resume();
            }
        }, 50);
    }
    
    console.log("[Debug] Playback started. Tone state:", Tone.context.state);
    if (Tone.Destination.mute) console.warn("[Debug] Warning: Tone.js is MUTED!");
});
player.addEventListener('stop', () => console.log("[Debug] Playback stopped."));

// Download MusicXML
document.getElementById('downloadMusicXmlBtn').addEventListener('click', function() {
    if (currentResult) {
        window.open(currentResult.musicxml_url, '_blank');
    }
});

// Listen for player errors
document.getElementById('midiPlayer').addEventListener('error', (e) => {
    console.error("[Debug] MIDI Player encountered an error:", e);
});

// Download MIDI
document.getElementById('downloadMidiBtn').addEventListener('click', function() {
    if (currentResult && currentResult.midi_url) {
        window.open(currentResult.midi_url, '_blank');
    }
});