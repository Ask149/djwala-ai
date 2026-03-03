// static/js/app.js
// Main application — connects UI, WebSocket, and MixEngine

// --- Waveform Renderer ---
// Generates simulated waveform bars from track metadata (BPM, energy, video_id)
// and animates a playhead + BPM-synced pulse

class WaveformRenderer {
    constructor(canvas) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.bars = [];
        this.bpm = 120;
        this.playheadPct = 0;
        this.color = { r: 102, g: 126, b: 234 }; // default purple-blue
        this.animId = null;
        this.startTime = 0;
    }

    // Deterministic hash from video_id for consistent waveform per track
    _hash(str) {
        let h = 0;
        for (let i = 0; i < str.length; i++) {
            h = ((h << 5) - h + str.charCodeAt(i)) | 0;
        }
        return Math.abs(h);
    }

    // Seeded pseudo-random from hash
    _seededRandom(seed) {
        const x = Math.sin(seed) * 10000;
        return x - Math.floor(x);
    }

    generate(track) {
        const { video_id, bpm, energy, duration } = track;
        this.bpm = bpm || 120;
        const numBars = Math.max(40, Math.floor((duration || 180) / 2));
        const seed = this._hash(video_id || 'default');
        const energyVal = energy || 0.6;

        this.bars = [];
        for (let i = 0; i < numBars; i++) {
            const r = this._seededRandom(seed + i * 7);
            // Scale height by energy: low energy = 0.2-0.5, high = 0.4-1.0
            const minH = 0.15 + energyVal * 0.15;
            const maxH = 0.4 + energyVal * 0.6;
            this.bars.push(minH + r * (maxH - minH));
        }

        this.startTime = performance.now();
        this.playheadPct = 0;
    }

    setColor(r, g, b) {
        this.color = { r, g, b };
    }

    setPlayhead(pct) {
        this.playheadPct = Math.max(0, Math.min(1, pct));
    }

    render() {
        const canvas = this.canvas;
        const ctx = this.ctx;
        const dpr = window.devicePixelRatio || 1;

        // Handle canvas sizing
        const rect = canvas.getBoundingClientRect();
        if (canvas.width !== rect.width * dpr || canvas.height !== rect.height * dpr) {
            canvas.width = rect.width * dpr;
            canvas.height = rect.height * dpr;
            ctx.scale(dpr, dpr);
        }

        const w = rect.width;
        const h = rect.height;
        ctx.clearRect(0, 0, w, h);

        if (this.bars.length === 0) return;

        const barW = Math.max(2, (w / this.bars.length) - 1);
        const gap = 1;
        const now = performance.now();
        const beatInterval = 60000 / this.bpm; // ms per beat
        const beatPhase = ((now - this.startTime) % beatInterval) / beatInterval;
        const pulse = 1 + 0.08 * Math.sin(beatPhase * Math.PI * 2);

        const { r, g, b } = this.color;

        for (let i = 0; i < this.bars.length; i++) {
            const x = i * (barW + gap);
            const barPct = i / this.bars.length;
            let barH = this.bars[i] * h * pulse;

            // Dim bars past the playhead
            let alpha = 0.6;
            if (barPct < this.playheadPct) {
                alpha = 0.25;
            } else if (Math.abs(barPct - this.playheadPct) < 0.02) {
                alpha = 1.0; // bright at playhead
                barH *= 1.15;
            }

            ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${alpha})`;

            // Draw bar centered vertically
            const y = (h - barH) / 2;
            ctx.fillRect(x, y, barW, barH);
        }

        // Playhead line
        const phX = this.playheadPct * w;
        ctx.fillStyle = `rgba(255, 255, 255, 0.8)`;
        ctx.fillRect(phX - 1, 0, 2, h);
    }

    startAnimation() {
        const loop = () => {
            this.render();
            this.animId = requestAnimationFrame(loop);
        };
        loop();
    }

    stopAnimation() {
        if (this.animId) {
            cancelAnimationFrame(this.animId);
            this.animId = null;
        }
    }

    destroy() {
        this.stopAnimation();
    }
}

// --- Color Extraction ---
// Extracts dominant color from YouTube thumbnails via /api/thumb proxy

class ColorExtractor {
    constructor() {
        this.cache = {};
        this.canvas = document.createElement('canvas');
        this.canvas.width = 10;
        this.canvas.height = 10;
        this.ctx = this.canvas.getContext('2d', { willReadFrequently: true });
    }

    async extract(videoId) {
        if (this.cache[videoId]) return this.cache[videoId];

        try {
            const img = new Image();
            img.crossOrigin = 'anonymous';

            const loaded = new Promise((resolve, reject) => {
                img.onload = resolve;
                img.onerror = reject;
            });

            img.src = `/api/thumb?v=${videoId}`;
            await loaded;

            this.ctx.drawImage(img, 0, 0, 10, 10);
            const data = this.ctx.getImageData(0, 0, 10, 10).data;

            // Find most saturated pixel cluster
            let bestR = 102, bestG = 126, bestB = 234; // fallback
            let bestSat = 0;

            for (let i = 0; i < data.length; i += 4) {
                const r = data[i], g = data[i + 1], b = data[i + 2];
                const max = Math.max(r, g, b);
                const min = Math.min(r, g, b);
                const sat = max === 0 ? 0 : (max - min) / max;
                const brightness = max / 255;

                // Prefer saturated, mid-brightness colors
                const score = sat * 0.7 + (brightness > 0.2 && brightness < 0.85 ? 0.3 : 0);
                if (score > bestSat) {
                    bestSat = score;
                    bestR = r; bestG = g; bestB = b;
                }
            }

            const result = { r: bestR, g: bestG, b: bestB };
            this.cache[videoId] = result;
            return result;
        } catch {
            const fallback = { r: 102, g: 126, b: 234 };
            this.cache[videoId] = fallback;
            return fallback;
        }
    }
}

class DjwalaApp {
    constructor() {
        this.sessionId = null;
        this.ws = null;
        this.queue = [];
        this.currentIndex = 0;
        this.mixCommand = null;
        this.positionTimer = null;
        this.playerState = 'hidden';
        this.consecutiveErrors = 0;

        this.engine = new MixEngine(
            () => this.onTrackEnded(),
            (errorCode) => this.onPlaybackError(errorCode)
        );

        this.els = {
            modeToggle: document.querySelector('.mode-toggle'),
            modeBtns: document.querySelectorAll('.mode-btn'),
            searchInput: document.querySelector('.search-input'),
            goBtn: document.querySelector('.go-btn'),
            shareBtn: document.querySelector('.share-btn'),
            nowPlaying: document.querySelector('.now-playing'),
            trackTitle: document.querySelector('.track-title'),
            trackMeta: document.querySelector('.track-meta'),
            nextUp: document.querySelector('.next-up'),
            statusBar: document.querySelector('.status-bar'),
            statusText: document.querySelector('.status-text'),
            queueSection: document.querySelector('.queue'),
            queueList: document.querySelector('.queue-list'),
            artistChips: document.querySelector('.artist-chips'),
            settingsOverlay: document.getElementById('settingsOverlay'),
            apiKeyInput: document.getElementById('apiKeyInput'),
            keyStatus: document.getElementById('keyStatus'),
            mixLengthSlider: document.getElementById('mixLengthSlider'),
            playerBar: document.getElementById('playerBar'),
            playerThumb: document.getElementById('playerThumb'),
            playerTitle: document.getElementById('playerTitle'),
            playerMeta: document.getElementById('playerMeta'),
            playBtn: document.getElementById('playBtn'),
            nextBtn: document.getElementById('nextBtn'),
            playerElapsed: document.getElementById('playerElapsed'),
            playerRemaining: document.getElementById('playerRemaining'),
            progressFill: document.getElementById('playerProgressFill'),
            crossfadeZone: document.getElementById('playerCrossfadeZone'),
            mixTimeline: document.getElementById('mixTimeline'),
            timelineTracks: document.getElementById('timelineTracks'),
            timelinePlayhead: document.getElementById('timelinePlayhead'),
            partyBtn: document.getElementById('partyBtn'),
            partyOverlay: document.getElementById('partyOverlay'),
            partyArt: document.getElementById('partyArt'),
            partyTitle: document.getElementById('partyTitle'),
            partyMeta: document.getElementById('partyMeta'),
            partyNext: document.getElementById('partyNext'),
            partyExit: document.getElementById('partyExit'),
            partyProgressFill: document.getElementById('partyProgressFill'),
            moodGrid: document.getElementById('moodGrid'),
            moodPills: document.querySelectorAll('.mood-pill'),
            lyricsBtn: document.getElementById('lyricsBtn'),
            lyricsPanel: document.getElementById('lyricsPanel'),
            lyricsPanelBody: document.getElementById('lyricsPanelBody'),
            lyricsPanelClose: document.getElementById('lyricsPanelClose'),
            partyLyrics: document.getElementById('partyLyrics'),
            // DJ Deck
            djDeck: document.getElementById('djDeck'),
            deckArtLeft: document.getElementById('deckArtLeft'),
            deckArtRight: document.getElementById('deckArtRight'),
            deckTitleLeft: document.getElementById('deckTitleLeft'),
            deckTitleRight: document.getElementById('deckTitleRight'),
            deckMetaLeft: document.getElementById('deckMetaLeft'),
            deckMetaRight: document.getElementById('deckMetaRight'),
            crossfaderKnob: document.getElementById('crossfaderKnob'),
            waveformLeft: document.getElementById('waveformLeft'),
            waveformRight: document.getElementById('waveformRight'),
            deckProgressFill: document.getElementById('deckProgressFill'),
            partyWaveformLeft: document.getElementById('partyWaveformLeft'),
            partyWaveformRight: document.getElementById('partyWaveformRight'),
        };

        this.mode = 'artists';
        this.moodId = null;
        this.lyricsData = null;      // parsed synced lyrics array [{time, text}]
        this.lyricsTrackId = null;    // video_id lyrics were fetched for
        this.lyricsFetched = false;   // true once fetch completes (even if not found)
        this.lyricsVisible = false;
        this.currentLyricIndex = -1;
        // DJ Deck state
        this.waveformL = new WaveformRenderer(document.getElementById('waveformLeft'));
        this.waveformR = new WaveformRenderer(document.getElementById('waveformRight'));
        this.colorExtractor = new ColorExtractor();
        this.deckActive = false;
        this.deckFading = false;
        this.partyWaveformL = new WaveformRenderer(document.getElementById('partyWaveformLeft'));
        this.partyWaveformR = new WaveformRenderer(document.getElementById('partyWaveformRight'));
        this.apiKey = localStorage.getItem('djwala_youtube_api_key') || null;
        this.mixLength = parseInt(localStorage.getItem('djwala_mix_length') || '50', 10);
        this.bindEvents();
        this.engine.init();
        this.initKeyboardShortcuts();
        this.updateKeyStatus();
        this.initRestore();
        this.trackEvent('page_view', { referrer: document.referrer || null });
    }

    // --- Analytics ---

    trackEvent(event, extra = {}) {
        try {
            const body = JSON.stringify({ event, ...extra });
            const blob = new Blob([body], { type: 'application/json' });
            navigator.sendBeacon('/analytics', blob);
        } catch { /* never break the app for analytics */ }
    }

    bindEvents() {
        this.els.modeBtns.forEach(btn => {
            btn.addEventListener('click', () => this.setMode(btn.dataset.mode));
        });
        this.els.goBtn.addEventListener('click', () => this.startSession());
        this.els.shareBtn.addEventListener('click', () => this.shareCurrentMix());
        this.els.searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') this.startSession();
        });
        this.els.mixLengthSlider.addEventListener('input', (e) => {
            this.mixLength = parseInt(e.target.value, 10);
            localStorage.setItem('djwala_mix_length', String(this.mixLength));
        });
        this.els.playBtn.addEventListener('click', () => this.onPlayTap());
        this.els.nextBtn.addEventListener('click', () => this.onSkipTap());
        this.els.partyBtn.addEventListener('click', () => this.togglePartyMode());
        this.els.partyExit.addEventListener('click', () => this.togglePartyMode());
        this.els.moodPills.forEach(pill => {
            pill.addEventListener('click', () => this.startMoodSession(pill.dataset.mood, pill.textContent.trim()));
        });
        this.els.lyricsBtn.addEventListener('click', () => this.openLyrics());
        this.els.lyricsPanelClose.addEventListener('click', () => this.closeLyrics());
    }

    setMode(mode) {
        this.mode = mode;
        this.els.modeBtns.forEach(btn => {
            btn.classList.toggle('active', btn.dataset.mode === mode);
        });
        if (mode === 'song') {
            this.els.searchInput.placeholder = 'Enter a song name... (e.g., "Tum Hi Ho", "Blinding Lights")';
        } else {
            this.els.searchInput.placeholder = 'Artist names, comma separated... (e.g., "Arijit Singh, Pritam, AP Dhillon")';
        }
    }

    startMoodSession(moodId, label) {
        this.mode = 'mood';
        this.moodId = moodId;
        this.els.searchInput.value = label;
        this.els.moodGrid.classList.add('hidden');
        this.trackEvent('mood_start', { mood: moodId });
        this.startSession();
    }

    parseArtists(query) {
        return query.split(',').map(a => a.trim()).filter(a => a.length > 0);
    }

    showArtistChips(artists) {
        this.els.artistChips.innerHTML = '';
        artists.forEach(artist => {
            const chip = document.createElement('span');
            chip.className = 'artist-chip';
            chip.textContent = artist;
            this.els.artistChips.appendChild(chip);
        });
    }

    async startSession() {
        const query = this.els.searchInput.value.trim();
        if (!query) return;

        this.clearSavedSession();

        if (this.mode === 'artists') {
            const artists = this.parseArtists(query);
            this.showArtistChips(artists);
        } else {
            this.showArtistChips([query]);  // Show song/mood name as single chip
        }

        this.els.goBtn.disabled = true;
        this.setStatus('Searching YouTube...', true);

        // Hide how-it-works and mood grid when session starts
        const hiw = document.getElementById('howItWorks');
        if (hiw) hiw.classList.add('hidden');
        this.els.moodGrid.classList.add('hidden');

        this.trackEvent('mix_start', { mode: this.mode, query });

        try {
            const body = {
                mode: this.mode,
                query: this.mode === 'mood' ? this.moodId : query,
            };
            if (this.apiKey) body.youtube_api_key = this.apiKey;
            body.mix_length = this.mixLength;

            const resp = await fetch('/session', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            const data = await resp.json();
            this.sessionId = data.session_id;
            this.saveSession();

            // Poll for queue readiness
            this.pollQueue();
        } catch (err) {
            this.setStatus('Error: ' + err.message);
            this.els.goBtn.disabled = false;
        }
    }

    async pollQueue() {
        const poll = async () => {
            try {
                const resp = await fetch(`/session/${this.sessionId}/queue`);
                const data = await resp.json();

                if (data.status === 'error') {
                    this.setStatus('Error: ' + data.error);
                    this.showErrorBanner(data.error);
                    this.els.goBtn.disabled = false;
                    return;
                }

                if (data.status === 'searching') {
                    this.setStatus('Searching YouTube...', true);
                    setTimeout(poll, 1000);
                    return;
                }

                if (data.status === 'analyzing') {
                    this.setStatus('Analyzing tracks...', true);
                    setTimeout(poll, 2000);
                    return;
                }

                if (data.status === 'ready' && data.tracks.length > 0) {
                    this.queue = data.tracks;
                    this.currentIndex = 0;
                    this.connectWebSocket();
                    this.startPlaying();
                    return;
                }

                setTimeout(poll, 1000);
            } catch {
                setTimeout(poll, 2000);
            }
        };
        poll();
    }

    async refreshQueue() {
        try {
            const resp = await fetch(`/session/${this.sessionId}/queue`);
            const data = await resp.json();
            if (data.tracks && data.tracks.length > 0) {
                this.queue = data.tracks;
                this.currentIndex = data.current_index;
                this.saveSession();
            }
        } catch {
            // Silently ignore — worst case is stale UI
        }
        this.updateNowPlaying();
        this.updateQueue();
        this.renderTimeline();
        this.updatePartyView();
        this.updatePageTitle();
        if (this.playerState === 'playing') {
            this.updatePlayerInfo();
        }
        // Refresh lyrics if panel is open and track changed
        if (this.lyricsVisible) {
            this.fetchAndShowLyrics();
        }
    }

    connectWebSocket() {
        if (this.ws) {
            this.ws.onclose = null; // prevent reconnect from old socket
            this.ws.close();
        }
        this._wsRetries = 0;
        this._connectWS();
    }

    _connectWS() {
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        this.ws = new WebSocket(`${protocol}//${location.host}/session/${this.sessionId}/live`);

        this.ws.onopen = () => {
            this._wsRetries = 0;
            console.log('[DjwalaAI] WebSocket connected');
            // Request mix command once connected (fixes race condition where
            // requestMixCommand() was called before WebSocket was OPEN)
            this.requestMixCommand();
        };

        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleWSMessage(data);
        };

        this.ws.onclose = (event) => {
            if (event.code === 4004) return; // session not found — don't retry
            this._scheduleReconnect();
        };

        this.ws.onerror = () => {
            // onclose will fire after onerror, which handles reconnect
        };
    }

    _scheduleReconnect() {
        const MAX_RETRIES = 8;
        if (this._wsRetries >= MAX_RETRIES) {
            this.setStatus('Connection lost. Refresh to reconnect.');
            return;
        }
        // Exponential backoff: 1s, 2s, 4s, 8s... capped at 30s
        const delay = Math.min(1000 * Math.pow(2, this._wsRetries), 30000);
        this._wsRetries++;
        console.log(`[DjwalaAI] WebSocket reconnecting in ${delay}ms (attempt ${this._wsRetries}/${MAX_RETRIES})`);
        setTimeout(() => this._connectWS(), delay);
    }

    handleWSMessage(data) {
        if (data.action === 'fade_to_next') {
            this.mixCommand = data;
        } else if (data.action === 'advanced') {
            this.refreshQueue();
        } else if (data.action === 'no_more_tracks') {
            this.setStatus('No more tracks -- set complete!');
        }
    }

    startPlaying() {
        this.hideStatus();
        this.els.goBtn.disabled = false;
        this.updateNowPlaying();
        this.updateQueue();
        this.renderTimeline();
        this.updatePageTitle();
        this.showPlayerBar('ready');

        // Show DJ deck
        const track = this.queue[this.currentIndex];
        const nextTrack = this.queue[this.currentIndex + 1] || null;
        this.showDeck(track, nextTrack);
    }

    showPlayerBar(state) {
        this.playerState = state;
        const bar = this.els.playerBar;
        const playBtn = this.els.playBtn;

        if (state === 'hidden') {
            bar.classList.remove('active', 'ready');
            return;
        }

        bar.classList.add('active');
        bar.classList.toggle('ready', state === 'ready');

        if (state === 'ready') {
            playBtn.textContent = '▶';
            this.els.playerTitle.textContent = 'Tap play to start';
            this.els.playerMeta.textContent = '';
            // Show thumbnail of first track
            const track = this.queue[this.currentIndex];
            if (track) {
                this.els.playerThumb.src = `https://img.youtube.com/vi/${track.video_id}/mqdefault.jpg`;
            }
        } else if (state === 'playing') {
            playBtn.textContent = '⏸';
            this.updatePlayerInfo();
        } else if (state === 'paused') {
            playBtn.textContent = '▶';
        }
    }

    updatePlayerInfo() {
        const track = this.queue[this.currentIndex];
        if (!track) return;
        this.els.playerTitle.textContent = track.title;
        this.els.playerMeta.textContent = `${track.bpm} BPM · ${track.camelot}`;
        this.els.playerThumb.src = `https://img.youtube.com/vi/${track.video_id}/mqdefault.jpg`;
    }

    // --- DJ Deck ---

    async showDeck(track, nextTrack) {
        // Hide the text-only now-playing when deck is visible
        this.els.nowPlaying.classList.remove('active');

        const deck = this.els.djDeck;
        deck.classList.add('active');
        this.deckActive = true;
        document.body.classList.add('deck-active');

        // Left deck = current track
        this.els.deckArtLeft.src = `/api/thumb?v=${track.video_id}`;
        this.els.deckTitleLeft.textContent = track.title;
        this.els.deckMetaLeft.textContent = `${track.bpm} BPM · ${track.camelot}`;
        this.els.deckArtLeft.classList.add('breathing');
        this.els.deckArtLeft.classList.add('glowing');

        // Right deck = next track (dimmed) or empty
        const right = this.els.djDeck.querySelector('.deck-right');
        if (nextTrack) {
            this.els.deckArtRight.src = `/api/thumb?v=${nextTrack.video_id}`;
            this.els.deckTitleRight.textContent = nextTrack.title;
            this.els.deckMetaRight.textContent = `${nextTrack.bpm} BPM · ${nextTrack.camelot}`;
            right.classList.add('dimmed');
            right.classList.remove('dimmed-hide');
        } else {
            this.els.deckTitleRight.textContent = '';
            this.els.deckMetaRight.textContent = '';
            this.els.deckArtRight.src = '';
            right.classList.add('dimmed');
        }

        // Generate waveforms
        this.waveformL.generate(track);
        if (nextTrack) this.waveformR.generate(nextTrack);
        this.waveformL.startAnimation();
        this.waveformR.startAnimation();

        // Extract color from current track
        const color = await this.colorExtractor.extract(track.video_id);
        this.waveformL.setColor(color.r, color.g, color.b);
        this.els.deckArtLeft.style.setProperty('--deck-color', `rgba(${color.r}, ${color.g}, ${color.b}, 0.5)`);
        document.body.style.setProperty('--bg-glow', `rgba(${color.r}, ${color.g}, ${color.b}, 0.1)`);

        // Mirror to party waveforms
        this.partyWaveformL.generate(track);
        if (nextTrack) this.partyWaveformR.generate(nextTrack);
        this.partyWaveformL.setColor(color.r, color.g, color.b);
        if (this.partyMode) {
            this.partyWaveformL.startAnimation();
            this.partyWaveformR.startAnimation();
        }

        // Crossfader to left
        this.els.crossfaderKnob.style.left = '0%';
    }

    async startDeckCrossfade(outTrack, inTrack) {
        this.deckFading = true;

        // Activate right deck
        const right = this.els.djDeck.querySelector('.deck-right');
        right.classList.remove('dimmed');
        this.els.deckArtRight.classList.add('breathing');

        // Extract incoming color
        const inColor = await this.colorExtractor.extract(inTrack.video_id);
        this.waveformR.setColor(inColor.r, inColor.g, inColor.b);
        this.els.deckArtRight.classList.add('glowing');
        this.els.deckArtRight.style.setProperty('--deck-color', `rgba(${inColor.r}, ${inColor.g}, ${inColor.b}, 0.5)`);
    }

    updateDeckCrossfade(progress) {
        // progress: 0 = start, 1 = complete
        if (!this.deckFading) return;

        // Move crossfader knob
        this.els.crossfaderKnob.style.left = `${progress * 100}%`;
    }

    completeDeckCrossfade(newTrack, nextTrack) {
        this.deckFading = false;

        // Shift: incoming becomes left deck, load next on right
        this.els.deckArtLeft.src = this.els.deckArtRight.src;
        this.els.deckTitleLeft.textContent = this.els.deckTitleRight.textContent;
        this.els.deckMetaLeft.textContent = this.els.deckMetaRight.textContent;
        this.els.deckArtLeft.classList.add('breathing', 'glowing');

        // Copy color from right to left
        const rightColor = this.els.deckArtRight.style.getPropertyValue('--deck-color');
        this.els.deckArtLeft.style.setProperty('--deck-color', rightColor);

        // Swap waveform data
        this.waveformL.bars = [...this.waveformR.bars];
        this.waveformL.bpm = this.waveformR.bpm;
        this.waveformL.color = { ...this.waveformR.color };
        this.waveformL.startTime = performance.now();
        this.waveformL.playheadPct = 0;

        // Update background
        const c = this.waveformR.color;
        document.body.style.setProperty('--bg-glow', `rgba(${c.r}, ${c.g}, ${c.b}, 0.1)`);

        // Reset crossfader
        this.els.crossfaderKnob.style.left = '0%';

        // Load next track on right (dimmed)
        const right = this.els.djDeck.querySelector('.deck-right');
        if (nextTrack) {
            this.els.deckArtRight.src = `/api/thumb?v=${nextTrack.video_id}`;
            this.els.deckTitleRight.textContent = nextTrack.title;
            this.els.deckMetaRight.textContent = `${nextTrack.bpm} BPM · ${nextTrack.camelot}`;
            right.classList.add('dimmed');
            this.waveformR.generate(nextTrack);
            this.els.deckArtRight.classList.remove('breathing', 'glowing');
        } else {
            this.els.deckTitleRight.textContent = '';
            this.els.deckMetaRight.textContent = '';
            this.els.deckArtRight.src = '';
            right.classList.add('dimmed');
        }
    }

    onPlayTap() {
        if (this.playerState === 'ready') {
            // First play — fresh user gesture for iOS
            const track = this.queue[this.currentIndex];
            this.engine.warmUpDecks(track.video_id, track.mix_in_point);
            this.requestMixCommand();
            this.startPositionMonitor();
            this.showPlayerBar('playing');
        } else if (this.playerState === 'paused') {
            this.engine.resume();
            this.showPlayerBar('playing');
            if (this.deckActive) {
                this.waveformL.startAnimation();
                this.waveformR.startAnimation();
            }
        } else if (this.playerState === 'playing') {
            this.engine.pause();
            this.showPlayerBar('paused');
            this.waveformL.stopAnimation();
            this.waveformR.stopAnimation();
        }
    }

    onSkipTap() {
        if (this.playerState === 'ready') return;
        if (this.engine.isFading) return;

        if (this.mixCommand) {
            this.engine.crossfadeTo(
                this.mixCommand.next_video_id,
                this.mixCommand.next_seek_to,
                this.mixCommand.fade_duration,
            );
            this.mixCommand = null;
        } else {
            // No mix command yet — tell backend to advance
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({ action: 'track_ended' }));
            }
        }
    }

    formatTime(seconds) {
        if (!seconds || seconds < 0) return '0:00';
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }

    requestMixCommand() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ action: 'get_mix_command' }));
        }
    }

    startPositionMonitor() {
        if (this.positionTimer) clearInterval(this.positionTimer);

        this.positionTimer = setInterval(() => {
            if (this.playerState !== 'playing') return;

            const currentTime = this.engine.getCurrentTime();
            const duration = this.engine.getDuration();

            // Reset consecutive error counter on successful playback
            if (currentTime > 1 && this.consecutiveErrors > 0) {
                this.consecutiveErrors = 0;
            }

            // Update progress bar
            if (duration > 0) {
                const pct = (currentTime / duration) * 100;
                this.els.progressFill.style.width = `${pct}%`;
                this.els.playerElapsed.textContent = this.formatTime(currentTime);
                this.els.playerRemaining.textContent = `-${this.formatTime(duration - currentTime)}`;
            }

            // Update timeline playhead
            this.updateTimelinePlayhead(currentTime, duration);

            // Update party mode progress
            if (this.partyMode && duration > 0) {
                const pct = (currentTime / duration) * 100;
                this.els.partyProgressFill.style.width = `${pct}%`;

                // Update party waveforms
                if (this.deckActive) {
                    this.partyWaveformL.setPlayhead(currentTime / duration);
                }
            }

            // Show crossfade zone when mix command is known
            if (this.mixCommand && duration > 0) {
                const fadeStartPct = (this.mixCommand.current_fade_start / duration) * 100;
                this.els.crossfadeZone.style.left = `${fadeStartPct}%`;
                this.els.crossfadeZone.style.width = `${100 - fadeStartPct}%`;
                this.els.crossfadeZone.style.display = 'block';
            }

            // Trigger crossfade at mix point
            if (this.mixCommand && !this.engine.isFading) {
                if (currentTime >= this.mixCommand.current_fade_start) {
                    // Start deck crossfade animation
                    if (this.deckActive) {
                        const nextTrack = this.queue[this.currentIndex + 1];
                        if (nextTrack) {
                            this.startDeckCrossfade(
                                this.queue[this.currentIndex],
                                nextTrack
                            );
                        }
                    }
                    this._fadeStartTime = performance.now();
                    this._lastFadeDuration = this.mixCommand.fade_duration;
                    this.engine.crossfadeTo(
                        this.mixCommand.next_video_id,
                        this.mixCommand.next_seek_to,
                        this.mixCommand.fade_duration,
                    );
                    this.mixCommand = null;
                }
            }

            // Update crossfade zone pulse
            this.els.crossfadeZone.classList.toggle('active', this.engine.isFading);

            // Animate crossfader during fade
            if (this.engine.isFading && this.deckFading && this.mixCommand === null) {
                const elapsed = (performance.now() - (this._fadeStartTime || performance.now())) / 1000;
                const fadeDur = this._lastFadeDuration || 5;
                const fadeProgress = Math.min(elapsed / fadeDur, 1);
                this.updateDeckCrossfade(fadeProgress);
            }

            // Sync lyrics with current playback position
            this.syncLyrics(currentTime);

            // Update DJ deck
            if (this.deckActive && duration > 0) {
                const pct = currentTime / duration;
                this.waveformL.setPlayhead(pct);
                this.els.deckProgressFill.style.width = `${pct * 100}%`;
            }
        }, 500);
    }

    onTrackEnded() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ action: 'track_ended' }));
            this.requestMixCommand();
        }
        // Reset crossfade zone and progress for next track
        this.els.crossfadeZone.style.display = 'none';
        this.els.crossfadeZone.classList.remove('active');
        this.els.progressFill.style.width = '0%';
        this.els.timelinePlayhead.classList.remove('active');
        this.els.partyProgressFill.style.width = '0%';
        this.updatePageTitle();
        // Refresh lyrics for new track if panel is open
        if (this.lyricsVisible) {
            this.fetchAndShowLyrics();
        }
        // Update DJ deck after track transition
        if (this.deckActive) {
            const newTrack = this.queue[this.currentIndex];
            const nextTrack = this.queue[this.currentIndex + 1] || null;
            if (newTrack) {
                this.completeDeckCrossfade(newTrack, nextTrack);
            }
        }
        this.saveSession();
    }

    onPlaybackError(errorCode) {
        this.consecutiveErrors++;
        console.warn(`[DjwalaAI] Playback error ${errorCode}, consecutive: ${this.consecutiveErrors}`);

        if (this.consecutiveErrors >= 3) {
            this.showToast('Multiple tracks unavailable. Try a different search.', 5000);
            this.showPlayerBar('ready');
            return;
        }

        const track = this.queue[this.currentIndex];
        const name = track ? track.title : 'Track';
        this.showToast(`${name} unavailable, skipping...`);

        // Auto-advance to next track
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ action: 'track_ended' }));
            this.requestMixCommand();
        }
    }

    showToast(message, duration = 3000) {
        // Remove existing toast
        const existing = document.querySelector('.toast');
        if (existing) existing.remove();

        const toast = document.createElement('div');
        toast.className = 'toast';
        toast.textContent = message;
        document.body.appendChild(toast);

        // Trigger animation
        requestAnimationFrame(() => toast.classList.add('visible'));

        setTimeout(() => {
            toast.classList.remove('visible');
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }

    updateNowPlaying() {
        const track = this.queue[this.currentIndex];
        if (!track) return;

        this.els.nowPlaying.classList.add('active');
        this.els.trackTitle.textContent = track.title;
        this.els.trackMeta.textContent = `${track.bpm} BPM · ${track.camelot}`;

        const next = this.queue[this.currentIndex + 1];
        if (next) {
            this.els.nextUp.textContent = `Next: ${next.title}`;
        } else {
            this.els.nextUp.textContent = 'Last track in queue';
        }
    }

    updateQueue() {
        this.els.queueSection.classList.add('active');
        this.els.queueList.innerHTML = '';

        this.queue.forEach((track, i) => {
            const item = document.createElement('div');
            item.className = 'queue-item' + (i === this.currentIndex ? ' current' : '');

            const idx = document.createElement('span');
            idx.className = 'idx';
            idx.textContent = i + 1;

            const title = document.createElement('span');
            title.className = 'title';
            title.textContent = track.title;

            const bpm = document.createElement('span');
            bpm.className = 'bpm';
            bpm.textContent = track.bpm;

            const key = document.createElement('span');
            key.className = 'key';
            key.textContent = track.camelot;

            item.appendChild(idx);
            item.appendChild(title);
            item.appendChild(bpm);
            item.appendChild(key);
            this.els.queueList.appendChild(item);
        });
    }

    renderTimeline() {
        const container = this.els.timelineTracks;
        container.innerHTML = '';
        this.els.mixTimeline.classList.add('active');

        // Color palette for tracks (cycles)
        const colors = [
            'rgba(102,126,234,0.35)', // blue
            'rgba(118,75,162,0.35)',   // purple
            'rgba(74,222,128,0.35)',   // green
            'rgba(251,191,36,0.35)',   // amber
            'rgba(244,114,182,0.35)', // pink
            'rgba(56,189,248,0.35)',  // sky
        ];

        // Calculate total duration for proportional widths
        const totalDuration = this.queue.reduce((sum, t) => sum + (t.duration || 180), 0);

        this.queue.forEach((track, i) => {
            const dur = track.duration || 180;
            const widthPct = (dur / totalDuration) * 100;

            const el = document.createElement('div');
            el.className = 'timeline-track';
            if (i < this.currentIndex) el.classList.add('past');
            if (i === this.currentIndex) el.classList.add('current');
            el.style.width = `${widthPct}%`;
            el.style.minWidth = '80px';
            el.style.background = colors[i % colors.length];

            const titleEl = document.createElement('div');
            titleEl.className = 'timeline-track-title';
            titleEl.textContent = track.title;

            const metaEl = document.createElement('div');
            metaEl.className = 'timeline-track-meta';
            metaEl.textContent = `${track.bpm} BPM · ${track.camelot}`;

            el.appendChild(titleEl);
            el.appendChild(metaEl);

            // Add crossfade zone indicator
            if (track.mix_out_point && track.duration) {
                const fadeStart = track.mix_out_point;
                const fadePct = ((track.duration - fadeStart) / track.duration) * 100;
                if (fadePct > 0 && fadePct < 50) {
                    const fadeEl = document.createElement('div');
                    fadeEl.className = 'timeline-crossfade';
                    fadeEl.style.width = `${fadePct}%`;
                    el.appendChild(fadeEl);
                }
            }

            container.appendChild(el);
        });
    }

    updateTimelinePlayhead(currentTime, duration) {
        const playhead = this.els.timelinePlayhead;
        const container = this.els.timelineTracks;
        if (!container.children.length) return;

        // Calculate position: sum of past tracks + current progress within current track
        let accWidth = 0;
        for (let i = 0; i < this.currentIndex; i++) {
            accWidth += container.children[i].offsetWidth;
        }

        const currentTrackEl = container.children[this.currentIndex];
        if (currentTrackEl && duration > 0) {
            const progress = Math.min(currentTime / duration, 1);
            accWidth += currentTrackEl.offsetWidth * progress;
        }

        playhead.style.left = `${accWidth}px`;
        playhead.classList.add('active');

        // Auto-scroll to keep playhead visible
        const timeline = this.els.mixTimeline;
        const scrollLeft = timeline.scrollLeft;
        const viewWidth = timeline.clientWidth;
        if (accWidth > scrollLeft + viewWidth - 40 || accWidth < scrollLeft) {
            timeline.scrollLeft = accWidth - viewWidth / 3;
        }
    }

    togglePartyMode() {
        this.partyMode = !this.partyMode;
        this.els.partyOverlay.classList.toggle('active', this.partyMode);

        if (this.partyMode) {
            this.updatePartyView();
            // Hide cursor after inactivity
            this._partyMouseTimer = null;
            this.els.partyOverlay.addEventListener('mousemove', this._partyMouseHandler = () => {
                this.els.partyOverlay.classList.add('show-controls');
                clearTimeout(this._partyMouseTimer);
                this._partyMouseTimer = setTimeout(() => {
                    this.els.partyOverlay.classList.remove('show-controls');
                }, 3000);
            });
            // ESC to exit
            this._partyEscHandler = (e) => { if (e.key === 'Escape') this.togglePartyMode(); };
            document.addEventListener('keydown', this._partyEscHandler);
        } else {
            this.els.partyOverlay.removeEventListener('mousemove', this._partyMouseHandler);
            document.removeEventListener('keydown', this._partyEscHandler);
        }

        // Start/stop party waveform animations
        if (this.partyMode && this.deckActive) {
            this.partyWaveformL.startAnimation();
            this.partyWaveformR.startAnimation();
        } else {
            this.partyWaveformL.stopAnimation();
            this.partyWaveformR.stopAnimation();
        }
    }

    updatePartyView() {
        if (!this.partyMode) return;
        const track = this.queue[this.currentIndex];
        if (!track) return;

        this.els.partyArt.src = `https://img.youtube.com/vi/${track.video_id}/maxresdefault.jpg`;
        this.els.partyArt.onerror = () => {
            this.els.partyArt.src = `https://img.youtube.com/vi/${track.video_id}/hqdefault.jpg`;
        };
        this.els.partyTitle.textContent = track.title;
        this.els.partyMeta.textContent = `${track.bpm} BPM · ${track.camelot}`;

        const next = this.queue[this.currentIndex + 1];
        this.els.partyNext.textContent = next ? `Next: ${next.title}` : '';

        // Dynamic party background
        if (this.deckActive) {
            const color = this.colorExtractor.cache[track.video_id];
            if (color) {
                this.els.partyOverlay.style.background = `radial-gradient(ellipse at 50% 40%, rgba(${color.r}, ${color.g}, ${color.b}, 0.2) 0%, #000 60%)`;
            }
        }
    }

    setStatus(text, loading = false) {
        this.els.statusBar.classList.add('active');
        this.els.statusBar.classList.toggle('loading', loading);
        this.els.statusText.textContent = text;
    }

    hideStatus() {
        this.els.statusBar.classList.remove('active');
    }

    openSettings() {
        this.els.settingsOverlay.classList.add('active');
        if (this.apiKey) {
            this.els.apiKeyInput.value = this.apiKey;
        }
        this.els.mixLengthSlider.value = this.mixLength;
    }

    closeSettings() {
        this.els.settingsOverlay.classList.remove('active');
    }

    saveApiKey() {
        const key = this.els.apiKeyInput.value.trim();
        if (!key) return;
        this.apiKey = key;
        localStorage.setItem('djwala_youtube_api_key', key);
        this.updateKeyStatus();
        this.closeSettings();
    }

    clearApiKey() {
        this.apiKey = null;
        localStorage.removeItem('djwala_youtube_api_key');
        this.els.apiKeyInput.value = '';
        this.updateKeyStatus();
    }

    updateKeyStatus() {
        const el = this.els.keyStatus;
        if (this.apiKey) {
            el.classList.add('saved');
        } else {
            el.classList.remove('saved');
        }
    }

    showErrorBanner(errorMsg) {
        // Remove existing banner if any
        const existing = document.querySelector('.error-banner');
        if (existing) existing.remove();

        const banner = document.createElement('div');
        banner.className = 'error-banner active';

        if (!this.apiKey) {
            banner.innerHTML = `
                <span>YouTube search failed. Add your API key for reliable access.</span>
                <button onclick="app.openSettings()">Add Key</button>
            `;
        } else {
            banner.innerHTML = `
                <span>Search failed. Your API key may be invalid or quota exceeded.</span>
                <button onclick="app.openSettings()">Check Key</button>
            `;
        }

        // Insert before the status bar
        this.els.statusBar.parentNode.insertBefore(banner, this.els.statusBar);
    }

    // --- Share / URL Params ---

    loadFromURLParams() {
        const params = new URLSearchParams(window.location.search);

        // Check for mood URL first
        const mood = params.get('mood');
        if (mood) {
            const pill = document.querySelector(`.mood-pill[data-mood="${mood}"]`);
            const label = pill ? pill.textContent.trim() : mood;
            window.history.replaceState({}, '', window.location.pathname);
            this.startMoodSession(mood, label);
            return;
        }

        const mode = params.get('mode');
        const query = params.get('q');

        if (!query) return;

        // Set mode if provided (default to artists)
        if (mode === 'song' || mode === 'artists') {
            this.setMode(mode);
        }

        // Pre-fill input
        this.els.searchInput.value = query;

        // Clean the URL so it doesn't re-trigger on refresh
        window.history.replaceState({}, '', window.location.pathname);

        // Auto-start the session
        this.startSession();
    }

    shareCurrentMix() {
        const query = this.els.searchInput.value.trim();
        if (!query) {
            this.showShareTooltip('Type something first!', false);
            return;
        }

        const url = new URL(window.location.origin);
        if (this.mode === 'mood') {
            url.searchParams.set('mood', this.moodId);
        } else {
            url.searchParams.set('mode', this.mode);
            url.searchParams.set('q', query);
        }

        const shareURL = url.toString();

        this.trackEvent('share', { mode: this.mode, query });

        // Try native share first (mobile)
        if (navigator.share) {
            navigator.share({
                title: 'DjwalaAI Mix',
                text: this.mode === 'mood'
                    ? `Listen to a ${query} DJ mix`
                    : this.mode === 'song'
                    ? `Listen to a DJ mix starting with "${query}"`
                    : `Listen to a DJ mix of ${query}`,
                url: shareURL,
            }).catch(() => {
                // User cancelled — fall back to clipboard
                this.copyToClipboard(shareURL);
            });
            return;
        }

        // Desktop fallback: copy to clipboard
        this.copyToClipboard(shareURL);
    }

    copyToClipboard(text) {
        navigator.clipboard.writeText(text).then(() => {
            this.showShareTooltip('Link copied!', true);
        }).catch(() => {
            // Fallback for older browsers
            const ta = document.createElement('textarea');
            ta.value = text;
            ta.style.position = 'fixed';
            ta.style.opacity = '0';
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
            this.showShareTooltip('Link copied!', true);
        });
    }

    showShareTooltip(message, success) {
        // Remove existing tooltip
        const existing = this.els.shareBtn.querySelector('.share-btn-tooltip');
        if (existing) existing.remove();

        const tooltip = document.createElement('span');
        tooltip.className = 'share-btn-tooltip' + (success ? ' copied' : '');
        tooltip.textContent = message;
        this.els.shareBtn.appendChild(tooltip);

        if (success) {
            this.els.shareBtn.classList.add('copied');
        }

        setTimeout(() => {
            tooltip.remove();
            this.els.shareBtn.classList.remove('copied');
        }, 2000);
    }

    // --- Lyrics ---

    cleanTrackTitle(title) {
        return title
            .replace(/\(official\s*(music\s*)?video\)/gi, '')
            .replace(/\(lyric(al)?\s*video\)/gi, '')
            .replace(/\(official\s*audio\)/gi, '')
            .replace(/\(audio\)/gi, '')
            .replace(/\[.*?\]/g, '')
            .replace(/\s*ft\.?\s*/gi, ' ')
            .replace(/\s*feat\.?\s*/gi, ' ')
            .replace(/\s{2,}/g, ' ')
            .trim();
    }

    openLyrics() {
        if (this.lyricsVisible) {
            this.closeLyrics();
            return;
        }
        this.lyricsVisible = true;
        this.els.lyricsPanel.classList.add('active');
        this.fetchAndShowLyrics();
        this.trackEvent('lyrics_open', { title: this.queue[this.currentIndex]?.title });
    }

    closeLyrics() {
        this.lyricsVisible = false;
        this.els.lyricsPanel.classList.remove('active');
    }

    async fetchAndShowLyrics() {
        const track = this.queue[this.currentIndex];
        if (!track) return;

        // Don't re-fetch if already loaded for this track
        if (this.lyricsTrackId === track.video_id && this.lyricsFetched) {
            return;
        }

        this.lyricsData = null;
        this.lyricsTrackId = track.video_id;
        this.lyricsFetched = false;
        this.currentLyricIndex = -1;
        this.els.lyricsPanelBody.innerHTML = '<div class="lyrics-loading">Searching for lyrics...</div>';
        this.els.partyLyrics.textContent = '';

        const clean = this.cleanTrackTitle(track.title);

        try {
            const resp = await fetch(`/api/lyrics?q=${encodeURIComponent(clean)}`);
            if (!resp.ok) throw new Error('LRCLIB search failed');
            const results = await resp.json();

            if (!results || results.length === 0) {
                this.lyricsFetched = true;
                this.showLyricsNotFound(clean);
                return;
            }

            // Pick best result — prefer one with synced lyrics
            const best = results.find(r => r.syncedLyrics) || results[0];

            if (best.syncedLyrics) {
                this.lyricsData = this.parseLRC(best.syncedLyrics);
                this.lyricsFetched = true;
                this.renderSyncedLyrics();
            } else if (best.plainLyrics) {
                this.lyricsData = null; // no synced data
                this.lyricsFetched = true;
                this.renderPlainLyrics(best.plainLyrics);
            } else {
                this.lyricsFetched = true;
                this.showLyricsNotFound(clean);
            }
        } catch (err) {
            console.warn('[DjwalaAI] Lyrics fetch error:', err);
            this.lyricsFetched = true;
            this.showLyricsNotFound(clean);
        }
    }

    parseLRC(lrcText) {
        const lines = [];
        const regex = /\[(\d{2}):(\d{2})\.(\d{2,3})\]\s*(.*)/;

        for (const line of lrcText.split('\n')) {
            const match = line.match(regex);
            if (match) {
                const mins = parseInt(match[1], 10);
                const secs = parseInt(match[2], 10);
                const ms = parseInt(match[3].padEnd(3, '0'), 10);
                const time = mins * 60 + secs + ms / 1000;
                const text = match[4].trim();
                lines.push({ time, text });
            }
        }

        return lines.sort((a, b) => a.time - b.time);
    }

    renderSyncedLyrics() {
        const body = this.els.lyricsPanelBody;
        body.innerHTML = '';

        this.lyricsData.forEach((line, i) => {
            const el = document.createElement('div');
            el.className = 'lyrics-line';
            if (!line.text) {
                el.classList.add('instrumental');
                el.textContent = '♪';
            } else {
                el.textContent = line.text;
            }
            el.dataset.index = i;
            body.appendChild(el);
        });
    }

    renderPlainLyrics(text) {
        const body = this.els.lyricsPanelBody;
        body.innerHTML = '';
        const el = document.createElement('div');
        el.className = 'lyrics-plain';
        el.textContent = text;
        body.appendChild(el);
    }

    showLyricsNotFound(cleanTitle) {
        const searchUrl = `https://www.google.com/search?q=${encodeURIComponent(cleanTitle + ' lyrics')}`;
        this.els.lyricsPanelBody.innerHTML = `
            <div class="lyrics-not-found">
                <p>No lyrics found for this track.</p>
                <a href="${searchUrl}" target="_blank">Search Google for lyrics →</a>
            </div>
        `;
        this.els.partyLyrics.textContent = '';
    }

    syncLyrics(currentTime) {
        if (!this.lyricsData || this.lyricsData.length === 0) return;

        // Find the current lyric line based on playback time
        let activeIndex = -1;
        for (let i = this.lyricsData.length - 1; i >= 0; i--) {
            if (currentTime >= this.lyricsData[i].time) {
                activeIndex = i;
                break;
            }
        }

        if (activeIndex === this.currentLyricIndex) return;
        this.currentLyricIndex = activeIndex;

        // Update panel lyrics
        if (this.lyricsVisible) {
            const lines = this.els.lyricsPanelBody.querySelectorAll('.lyrics-line');
            lines.forEach((el, i) => {
                el.classList.toggle('active', i === activeIndex);
                el.classList.toggle('past', i < activeIndex);
            });

            // Auto-scroll to active line
            const activeLine = this.els.lyricsPanelBody.querySelector('.lyrics-line.active');
            if (activeLine) {
                activeLine.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }

        // Update party mode lyrics
        if (this.partyMode && activeIndex >= 0) {
            const line = this.lyricsData[activeIndex];
            this.els.partyLyrics.textContent = line.text || '♪';
        }
    }

    // --- Keyboard Shortcuts ---

    initKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Don't trigger shortcuts when typing in input fields
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
            // Don't interfere with party mode ESC handler
            if (this.partyMode && e.key === 'Escape') return;

            switch (e.key) {
                case ' ':
                    e.preventDefault();
                    this.onPlayTap();
                    break;
                case 'n':
                case 'N':
                    this.onSkipTap();
                    break;
                case 'p':
                case 'P':
                    this.togglePartyMode();
                    break;
                case 'l':
                case 'L':
                    this.openLyrics();
                    break;
            }
        });
    }

    // --- Dynamic Page Title ---

    updatePageTitle() {
        const track = this.queue[this.currentIndex];
        if (track) {
            document.title = `▶ ${track.title} — DjwalaAI`;
        } else {
            document.title = 'DjwalaAI — AI-Powered Auto-DJ | Free Seamless Music Mixes';
        }
    }

    // --- Session Persistence ---

    saveSession() {
        if (!this.sessionId) return;
        const data = {
            sessionId: this.sessionId,
            mode: this.mode,
            query: this.els.searchInput.value.trim(),
            moodId: this.moodId || null,
            currentIndex: this.currentIndex,
        };
        localStorage.setItem('djwala_session', JSON.stringify(data));
    }

    clearSavedSession() {
        localStorage.removeItem('djwala_session');
    }

    async restoreSession() {
        const raw = localStorage.getItem('djwala_session');
        if (!raw) return false;

        let saved;
        try {
            saved = JSON.parse(raw);
        } catch {
            this.clearSavedSession();
            return false;
        }

        if (!saved.sessionId) {
            this.clearSavedSession();
            return false;
        }

        // Verify session still exists on backend
        try {
            const resp = await fetch(`/session/${saved.sessionId}/queue`);
            if (!resp.ok) {
                this.clearSavedSession();
                return false;
            }

            const data = await resp.json();
            if (data.status !== 'ready' || !data.tracks || data.tracks.length === 0) {
                this.clearSavedSession();
                return false;
            }

            // Restore state
            this.sessionId = saved.sessionId;
            this.mode = saved.mode || 'artists';
            this.moodId = saved.moodId || null;
            this.queue = data.tracks;
            this.currentIndex = data.current_index;

            // Restore UI
            if (saved.mode && saved.mode !== 'artists') {
                this.setMode(saved.mode);
            }
            if (saved.query) {
                this.els.searchInput.value = saved.query;
            }

            // Hide landing page elements
            const hiw = document.getElementById('howItWorks');
            if (hiw) hiw.classList.add('hidden');
            this.els.moodGrid.classList.add('hidden');

            // Show chips
            if (saved.mode === 'artists' && saved.query) {
                this.showArtistChips(this.parseArtists(saved.query));
            } else if (saved.query) {
                this.showArtistChips([saved.query]);
            }

            // Show queue, timeline, player bar
            this.connectWebSocket();
            this.startPlaying();
            return true;
        } catch {
            this.clearSavedSession();
            return false;
        }
    }

    async initRestore() {
        // URL params take priority (shared links)
        const params = new URLSearchParams(window.location.search);
        if (params.has('mood') || params.has('mode') || params.has('q')) {
            this.clearSavedSession();
            this.loadFromURLParams();
            return;
        }

        // Try to restore previous session
        const restored = await this.restoreSession();
        if (!restored) {
            // No session to restore — normal landing page
        }
    }
}

// Start the app
document.addEventListener('DOMContentLoaded', () => {
    window.app = new DjwalaApp();
});
