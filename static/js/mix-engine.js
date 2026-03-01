// static/js/mix-engine.js
// Mix Engine — manages two YouTube IFrame players and crossfading

class MixEngine {
    constructor(onTrackChange) {
        this.deckA = null;
        this.deckB = null;
        this.activeDeck = 'A';
        this.isFading = false;
        this.fadeInterval = null;
        this.onTrackChange = onTrackChange || (() => {});
        this._playersReady = { A: false, B: false };
        this._pendingPlay = null;
    }

    init() {
        // Create player divs
        const container = document.querySelector('.players-container');
        const divA = document.createElement('div');
        divA.id = 'yt-player-a';
        const divB = document.createElement('div');
        divB.id = 'yt-player-b';
        container.appendChild(divA);
        container.appendChild(divB);

        // Load YouTube IFrame API
        const tag = document.createElement('script');
        tag.src = 'https://www.youtube.com/iframe_api';
        document.head.appendChild(tag);

        window.onYouTubeIframeAPIReady = () => {
            this.deckA = new YT.Player('yt-player-a', {
                height: '1', width: '1',
                playerVars: { autoplay: 0, controls: 0 },
                events: {
                    onReady: () => { this._playersReady.A = true; this._checkPending(); },
                    onStateChange: (e) => this._onStateChange('A', e),
                },
            });
            this.deckB = new YT.Player('yt-player-b', {
                height: '1', width: '1',
                playerVars: { autoplay: 0, controls: 0 },
                events: {
                    onReady: () => { this._playersReady.B = true; this._checkPending(); },
                    onStateChange: (e) => this._onStateChange('B', e),
                },
            });
        };
    }

    _checkPending() {
        if (this._pendingPlay && this._playersReady.A && this._playersReady.B) {
            const { videoId, seekTo } = this._pendingPlay;
            this._pendingPlay = null;
            this.playOnDeck(videoId, seekTo);
        }
    }

    getActiveDeck() {
        return this.activeDeck === 'A' ? this.deckA : this.deckB;
    }

    getInactiveDeck() {
        return this.activeDeck === 'A' ? this.deckB : this.deckA;
    }

    playOnDeck(videoId, seekTo = 0) {
        if (!this._playersReady.A || !this._playersReady.B) {
            this._pendingPlay = { videoId, seekTo };
            return;
        }

        const deck = this.getActiveDeck();
        deck.setVolume(100);
        deck.loadVideoById({ videoId, startSeconds: seekTo });
    }

    getCurrentTime() {
        const deck = this.getActiveDeck();
        return deck ? deck.getCurrentTime() : 0;
    }

    crossfadeTo(nextVideoId, seekTo, fadeDuration) {
        if (this.isFading) return;
        this.isFading = true;

        const outgoing = this.getActiveDeck();
        const incoming = this.getInactiveDeck();

        // Load next track on inactive deck
        incoming.setVolume(0);
        incoming.loadVideoById({ videoId: nextVideoId, startSeconds: seekTo });

        const steps = 50; // number of volume steps
        const interval = (fadeDuration * 1000) / steps;
        let step = 0;

        this.fadeInterval = setInterval(() => {
            step++;
            const progress = step / steps;

            // Cosine curve for smooth crossfade
            const outVol = Math.round(Math.cos(progress * Math.PI / 2) * 100);
            const inVol = Math.round(Math.sin(progress * Math.PI / 2) * 100);

            outgoing.setVolume(outVol);
            incoming.setVolume(inVol);

            if (step >= steps) {
                clearInterval(this.fadeInterval);
                outgoing.stopVideo();
                this.activeDeck = this.activeDeck === 'A' ? 'B' : 'A';
                this.isFading = false;
                this.onTrackChange();
            }
        }, interval);
    }

    _onStateChange(deck, event) {
        // YT.PlayerState.ENDED = 0
        if (event.data === 0 && !this.isFading) {
            const deckLabel = deck;
            const isActive = (deckLabel === this.activeDeck);
            if (isActive) {
                this.onTrackChange();
            }
        }
    }

    destroy() {
        if (this.fadeInterval) clearInterval(this.fadeInterval);
        if (this.deckA) this.deckA.destroy();
        if (this.deckB) this.deckB.destroy();
    }
}
