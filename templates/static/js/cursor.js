/**
 * Handles the synchronization loop between the MIDI player and OSMD cursor.
 */
let cursorAnimationId = null;

const syncOSMDCursor = () => {
    const player = document.getElementById('midiPlayer');
    if (osmd && osmd.cursor && player && player.playing) {
        // Use global baseBpm from player.js and current Transport BPM
        const bpm = (window.Tone && Tone.Transport && Tone.Transport.bpm) ? Tone.Transport.bpm.value : window.baseBpm;
        const currentWholeNotes = (player.currentTime * bpm / 60) / 4;

        // Reset cursor if user sought backwards
        if (currentWholeNotes < osmd.cursor.iterator.CurrentTimestamp.RealValue) {
            osmd.cursor.reset();
        }   

        // Advance cursor to match current playback time
        while (!osmd.cursor.iterator.EndReached && 
               osmd.cursor.iterator.CurrentTimestamp.RealValue < currentWholeNotes) {
            osmd.cursor.next();
        }
    }
    cursorAnimationId = requestAnimationFrame(syncOSMDCursor);
};

const startCursorSync = () => {
    syncOSMDCursor();
};

const stopCursorSync = () => {
    if (cursorAnimationId) cancelAnimationFrame(cursorAnimationId);
};