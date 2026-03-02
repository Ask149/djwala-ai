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
        this.playerState = 'hidden';

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
        this.els.playBtn.addEventListener('click', () => this.onPlayTap());
        this.els.nextBtn.addEventListener('click', () => this.onSkipTap());
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

    async refreshQueue() {
        try {
            const resp = await fetch(`/session/${this.sessionId}/queue`);
            const data = await resp.json();
            if (data.tracks && data.tracks.length > 0) {
                this.queue = data.tracks;
                this.currentIndex = data.current_index;
            }
        } catch {
            // Silently ignore — worst case is stale UI
        }
        this.updateNowPlaying();
        this.updateQueue();
        if (this.playerState === 'playing') {
            this.updatePlayerInfo();
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
        this.showPlayerBar('ready');
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
        } else if (this.playerState === 'playing') {
            this.engine.pause();
            this.showPlayerBar('paused');
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

            // Update progress bar
            if (duration > 0) {
                const pct = (currentTime / duration) * 100;
                this.els.progressFill.style.width = `${pct}%`;
                this.els.playerElapsed.textContent = this.formatTime(currentTime);
                this.els.playerRemaining.textContent = `-${this.formatTime(duration - currentTime)}`;
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
