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
        };

        this.mode = 'artists';
        this.apiKey = localStorage.getItem('djwala_youtube_api_key') || null;
        this.mixLength = parseInt(localStorage.getItem('djwala_mix_length') || '50', 10);
        this.bindEvents();
        this.engine.init();
        this.updateKeyStatus();
        this.loadFromURLParams();
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

        if (this.mode === 'artists') {
            const artists = this.parseArtists(query);
            this.showArtistChips(artists);
        } else {
            this.showArtistChips([query]);  // Show song name as single chip
        }

        this.els.goBtn.disabled = true;
        this.setStatus('Searching YouTube...', true);

        // Hide how-it-works when session starts
        const hiw = document.getElementById('howItWorks');
        if (hiw) hiw.classList.add('hidden');

        this.trackEvent('mix_start', { mode: this.mode, query });

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
        this.renderTimeline();
        this.updatePartyView();
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
        this.renderTimeline();
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

            // Update timeline playhead
            this.updateTimelinePlayhead(currentTime, duration);

            // Update party mode progress
            if (this.partyMode && duration > 0) {
                const pct = (currentTime / duration) * 100;
                this.els.partyProgressFill.style.width = `${pct}%`;
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
        this.els.timelinePlayhead.classList.remove('active');
        this.els.partyProgressFill.style.width = '0%';
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
        url.searchParams.set('mode', this.mode);
        url.searchParams.set('q', query);

        const shareURL = url.toString();

        this.trackEvent('share', { mode: this.mode, query });

        // Try native share first (mobile)
        if (navigator.share) {
            navigator.share({
                title: 'DjwalaAI Mix',
                text: this.mode === 'song'
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
}

// Start the app
document.addEventListener('DOMContentLoaded', () => {
    window.app = new DjwalaApp();
});
