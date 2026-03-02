// static/js/app.js
// Main application — connects UI, WebSocket, and MixEngine

class DjwalaApp {
    constructor() {
        this.sessionId = null;
        this.ws = null;
        this.queue = [];
        this.currentIndex = 0;
        this.mixCommand = null;
        this.positionTimer = null;

        this.engine = new MixEngine(() => this.onTrackEnded());

        this.els = {
            searchInput: document.querySelector('.search-input'),
            goBtn: document.querySelector('.go-btn'),
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
        };

        this.mode = 'artists';
        this.apiKey = localStorage.getItem('djwala_youtube_api_key') || null;
        this.mixLength = parseInt(localStorage.getItem('djwala_mix_length') || '50', 10);
        this.bindEvents();
        this.engine.init();
        this.updateKeyStatus();
    }

    bindEvents() {
        this.els.goBtn.addEventListener('click', () => this.startSession());
        this.els.searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') this.startSession();
        });
        this.els.mixLengthSlider.addEventListener('input', (e) => {
            this.mixLength = parseInt(e.target.value, 10);
            localStorage.setItem('djwala_mix_length', String(this.mixLength));
        });
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

        const artists = this.parseArtists(query);
        this.showArtistChips(artists);

        this.els.goBtn.disabled = true;
        this.setStatus('Searching YouTube...', true);

        try {
            const body = { mode: this.mode, query };
            if (this.apiKey) body.youtube_api_key = this.apiKey;
            body.mix_length = this.mixLength;

            const resp = await fetch('/session', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            const data = await resp.json();
            this.sessionId = data.session_id;

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
            this.currentIndex++;
            this.updateNowPlaying();
            this.updateQueue();
        } else if (data.action === 'no_more_tracks') {
            this.setStatus('No more tracks -- set complete!');
        }
    }

    startPlaying() {
        this.hideStatus();
        this.els.goBtn.disabled = false;

        const track = this.queue[0];
        this.engine.playOnDeck(track.video_id, track.mix_in_point);
        this.updateNowPlaying();
        this.updateQueue();

        // Request first mix command
        this.requestMixCommand();

        // Start position monitoring
        this.startPositionMonitor();
    }

    requestMixCommand() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ action: 'get_mix_command' }));
        }
    }

    startPositionMonitor() {
        if (this.positionTimer) clearInterval(this.positionTimer);

        this.positionTimer = setInterval(() => {
            if (!this.mixCommand || this.engine.isFading) return;

            const currentTime = this.engine.getCurrentTime();
            if (currentTime >= this.mixCommand.current_fade_start) {
                // Time to crossfade!
                this.engine.crossfadeTo(
                    this.mixCommand.next_video_id,
                    this.mixCommand.next_seek_to,
                    this.mixCommand.fade_duration,
                );
                this.mixCommand = null;
            }
        }, 500);
    }

    onTrackEnded() {
        // Tell backend we've moved to next track
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ action: 'track_ended' }));
            this.requestMixCommand();
        }
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
}

// Start the app
document.addEventListener('DOMContentLoaded', () => {
    window.app = new DjwalaApp();
});
