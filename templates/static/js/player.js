/**
 * Handles Audio Context, Tone.js state, and MIDI Player events.
 */
window.baseBpm = 120; // Default fallback for MIDI tempo

window.updateAudioStatusUI = () => {
    if (typeof Tone !== 'undefined' && Tone.context) {
        const state = Tone.context.state;
        const statusEl = document.getElementById('audioStatus');
        if (statusEl) {
            statusEl.className = `audio-status ${state}`;
            const textEl = statusEl.querySelector('.status-text');
            if (textEl) textEl.textContent = `Audio: ${state.charAt(0).toUpperCase() + state.slice(1)}`;
        }
    }
};

window.resumeToneContext = async () => {
    if (typeof Tone !== 'undefined') {
        try {
            await Tone.start();
            if (Tone.context.state !== 'running') {
                await Tone.context.resume();
            }
            // Safari "poke"
            const osc = Tone.context.createOscillator();
            const silentGain = Tone.context.createGain();
            silentGain.gain.value = 0;
            osc.connect(silentGain);
            silentGain.connect(Tone.context.destination);
            osc.start(0);
            osc.stop(0.1);

            Tone.Destination.mute = false;
            window.updateAudioStatusUI();
        } catch (err) {
            console.error("[Audio] Failed to resume Tone.js context:", err);
        }
    }
};

window.addEventListener('load', () => {
    if (typeof Tone !== 'undefined' && Tone.context) {
        Tone.context.on('statechange', window.updateAudioStatusUI);
        window.updateAudioStatusUI();
    }

    const player = document.getElementById('midiPlayer');
    if (!player) return;

    const resumeAudio = async () => {
        await window.resumeToneContext();
        if (player && typeof player.resumeAudioContext === 'function') {
            try { await player.resumeAudioContext(); } catch (e) {}
        }
        if (typeof Tone !== 'undefined') {
            Tone.Destination.mute = false;
            if (Tone.Destination.volume.value < -80) Tone.Destination.volume.value = 0;
            if (Tone.context.state !== 'running') await Tone.context.resume();
        }
    };

    // Attach listeners safely
    ['pointerdown', 'click', 'touchstart', 'touchend', 'mousedown'].forEach(type => {
        player.addEventListener(type, resumeAudio);
    });

    // MIDI Player Event Listeners
    player.addEventListener('load', () => console.log("[Audio] MIDI loaded."));

    player.addEventListener('start', () => {
        if (typeof osmd !== 'undefined' && osmd && osmd.cursor) {
            osmd.cursor.reset();
            osmd.cursor.show();
        }

        if (typeof stopCursorSync === 'function') stopCursorSync();
        if (typeof startCursorSync === 'function') startCursorSync();

        if (typeof Tone !== 'undefined') {
            Tone.Destination.mute = false;
            if (Tone.context.state !== 'running') Tone.context.resume();

            if (Tone.Transport && Tone.Transport.bpm) {
                setTimeout(() => {
                    const detectedBpm = Tone.Transport.bpm.value;
                    if (detectedBpm > 0) window.baseBpm = detectedBpm;
                    
                    const tempoSlider = document.getElementById('tempoSlider');
                    const multiplier = tempoSlider ? parseFloat(tempoSlider.value) / 100 : 1.0;
                    Tone.Transport._customRate = multiplier;
                    Tone.Transport.bpm.value = window.baseBpm * multiplier;
                }, 50);
            }
        }
    });

    player.addEventListener('stop', () => {
        if (typeof stopCursorSync === 'function') stopCursorSync();
        if (typeof osmd !== 'undefined' && osmd && osmd.cursor) osmd.cursor.reset();
    });

    player.addEventListener('error', (e) => {
        console.error("[Audio] Player Error:", e);
    });
});