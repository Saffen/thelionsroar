"use strict";
const STORAGE_KEYS = {
    best: 'protect-the-outhouse-best',
    music: 'protect-the-outhouse-music',
};
const GAME_CONFIG = {
    width: 960,
    height: 600,
    maxHealth: 100,
    spawnBaseInterval: 1.18,
    spawnMinInterval: 0.36,
    waveEverySeconds: 14,
    waveSpeedBonus: 5,
    waveSpawnFactor: 0.07,
    enemyRadius: 24,
    enemyHitFlash: 0.12,
    comboResetSeconds: 1.8,
    clickDamage: 1,
    bestLeaderboardSize: 10,
};
const ENEMY_CONFIGS = {
    goblin: {
        id: 'goblin',
        name: 'Goblin Saboteur',
        health: 2,
        speed: 68,
        damage: 8,
        score: 70,
        wobble: 0.4,
        tint: '#77d46b',
        unlockWave: 1,
        sprite: 'assets/enemy-goblin.svg',
        scale: 1,
    },
    murloc: {
        id: 'murloc',
        name: 'Murloc Marauder',
        health: 1,
        speed: 102,
        damage: 6,
        score: 80,
        wobble: 0.3,
        tint: '#4fd0cb',
        unlockWave: 1,
        sprite: 'assets/enemy-murloc.svg',
        scale: 0.95,
    },
    druid: {
        id: 'druid',
        name: 'Druid Reclaimer',
        health: 4,
        speed: 48,
        damage: 12,
        score: 130,
        wobble: 0.1,
        tint: '#dca44f',
        unlockWave: 3,
        sprite: 'assets/enemy-druid.svg',
        scale: 1.1,
    },
    drunk: {
        id: 'drunk',
        name: 'Drunken Festivalgoer',
        health: 2,
        speed: 58,
        damage: 9,
        score: 95,
        wobble: 1.3,
        tint: '#d47ab5',
        unlockWave: 2,
        sprite: 'assets/enemy-drunk.svg',
        scale: 1,
    },
    jumper: {
        id: 'jumper',
        name: 'Queue Jumper',
        health: 2,
        speed: 88,
        damage: 10,
        score: 115,
        wobble: 0,
        tint: '#f3df6b',
        unlockWave: 2,
        sprite: 'assets/enemy-jumper.svg',
        scale: 1,
    },
    engineer: {
        id: 'engineer',
        name: 'Suspicious Engineer',
        health: 5,
        speed: 38,
        damage: 18,
        score: 170,
        wobble: 0.2,
        tint: '#c7704a',
        unlockWave: 4,
        sprite: 'assets/enemy-engineer.svg',
        scale: 1.12,
    },
};
const SPAWN_TABLE = [
    { id: 'goblin', weight: 26 },
    { id: 'murloc', weight: 28 },
    { id: 'drunk', weight: 20 },
    { id: 'jumper', weight: 18 },
    { id: 'druid', weight: 16 },
    { id: 'engineer', weight: 10 },
];
const HIT_WORDS = ['Bonk!', 'Thunk!', 'Denied!', 'Nope!', 'Shoo!'];
const BREACH_WORDS = ['Breach!', 'Clatter!', 'Not the door!', 'Hold it together!'];
const EMPTY_LEADERBOARD_TEXT = 'No defenders logged yet. Be the first to preserve public dignity.';
class LeaderboardAPI {
    async fetchScores() {
        try {
            const response = await fetch('api/score.php', { cache: 'no-store' });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const payload = (await response.json());
            return Array.isArray(payload.scores) ? payload.scores : [];
        }
        catch (error) {
            console.warn('Leaderboard fetch failed.', error);
            return [];
        }
    }
    async submitScore(entry) {
        var _a;
        try {
            const response = await fetch('api/score.php', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(entry),
            });
            const payload = (await response.json());
            if (!response.ok || !payload.success) {
                return {
                    success: false,
                    message: (_a = payload.error) !== null && _a !== void 0 ? _a : 'Submission failed.',
                    scores: Array.isArray(payload.scores) ? payload.scores : [],
                };
            }
            return {
                success: true,
                message: 'Score submitted to the festival ledger.',
                scores: Array.isArray(payload.scores) ? payload.scores : [],
            };
        }
        catch (error) {
            console.warn('Leaderboard submission failed.', error);
            return {
                success: false,
                message: 'Could not reach the leaderboard. Your run still counts in spirit.',
                scores: [],
            };
        }
    }
}
class Enemy {
    constructor(config, x, y) {
        this.hitFlash = 0;
        this.config = config;
        this.x = x;
        this.y = y;
        this.health = config.health;
        this.radius = GAME_CONFIG.enemyRadius * config.scale;
        this.wobbleSeed = Math.random() * Math.PI * 2;
    }
    takeHit(amount) {
        this.health -= amount;
        this.hitFlash = GAME_CONFIG.enemyHitFlash;
        return this.health <= 0;
    }
    update(delta, time, targetX, targetY, wave) {
        const dx = targetX - this.x;
        const dy = targetY - this.y;
        const distance = Math.max(1, Math.hypot(dx, dy));
        const wobbleX = Math.sin(time * 5 + this.wobbleSeed) * this.config.wobble * 8;
        const wobbleY = Math.cos(time * 4 + this.wobbleSeed) * this.config.wobble * 5;
        const speed = this.config.speed + (wave - 1) * GAME_CONFIG.waveSpeedBonus;
        this.x += (dx / distance) * speed * delta + wobbleX * delta;
        this.y += (dy / distance) * speed * delta + wobbleY * delta;
        this.hitFlash = Math.max(0, this.hitFlash - delta);
    }
    reached(targetX, targetY, threshold) {
        return Math.hypot(this.x - targetX, this.y - targetY) <= threshold + this.radius * 0.65;
    }
    containsPoint(x, y) {
        return Math.hypot(this.x - x, this.y - y) <= this.radius;
    }
}
class Game {
    constructor(canvas) {
        var _a;
        this.scoreValue = this.getElement('scoreValue');
        this.healthValue = this.getElement('healthValue');
        this.timeValue = this.getElement('timeValue');
        this.waveValue = this.getElement('waveValue');
        this.bestValue = this.getElement('bestValue');
        this.healthBar = this.getElement('healthBar');
        this.startOverlay = this.getElement('startOverlay');
        this.gameOverOverlay = this.getElement('gameOverOverlay');
        this.startButton = this.getElement('startButton');
        this.restartButton = this.getElement('restartButton');
        this.musicToggle = this.getElement('musicToggle');
        this.finalScoreValue = this.getElement('finalScoreValue');
        this.finalTimeValue = this.getElement('finalTimeValue');
        this.recordStatus = this.getElement('recordStatus');
        this.gameOverTitle = this.getElement('gameOverTitle');
        this.gameOverText = this.getElement('gameOverText');
        this.scoreForm = this.getElement('scoreForm');
        this.playerNameInput = this.getElement('playerName');
        this.submitMessage = this.getElement('submitMessage');
        this.leaderboardList = this.getElement('leaderboardList');
        this.gameOverLeaderboard = this.getElement('gameOverLeaderboard');
        this.submitScoreButton = this.getElement('submitScoreButton');
        this.api = new LeaderboardAPI();
        this.music = new Audio('assets/music.mp3');
        this.images = new Map();
        this.floatingTexts = [];
        this.enemies = [];
        this.lastFrameTime = 0;
        this.animationHandle = 0;
        this.spawnTimer = 0;
        this.survivalSeconds = 0;
        this.wave = 1;
        this.score = 0;
        this.combo = 0;
        this.comboTimer = 0;
        this.health = GAME_CONFIG.maxHealth;
        this.playing = false;
        this.submittedScore = false;
        this.shakeTimer = 0;
        this.outhouseFlash = 0;
        this.bestScore = 0;
        this.leaderboard = [];
        this.musicEnabled = true;
        this.musicFailed = false;
        const context = canvas.getContext('2d');
        if (!context) {
            throw new Error('2D canvas context not available.');
        }
        this.canvas = canvas;
        this.ctx = context;
        this.canvas.width = GAME_CONFIG.width;
        this.canvas.height = GAME_CONFIG.height;
        this.ctx.imageSmoothingEnabled = false;
        this.music.loop = true;
        this.music.volume = 0.5;
        this.music.preload = 'auto';
        this.music.addEventListener('error', () => {
            this.musicFailed = true;
            this.updateMusicButton();
        });
        this.bestScore = Number((_a = localStorage.getItem(STORAGE_KEYS.best)) !== null && _a !== void 0 ? _a : '0') || 0;
        this.musicEnabled = localStorage.getItem(STORAGE_KEYS.music) !== 'off';
        this.bindEvents();
        this.preloadAssets();
        this.updateMusicButton();
        this.updateHud();
        void this.loadLeaderboard();
        this.render(0);
        this.loop = this.loop.bind(this);
        this.animationHandle = requestAnimationFrame(this.loop);
    }
    bindEvents() {
        this.startButton.addEventListener('click', () => this.startGame());
        this.restartButton.addEventListener('click', () => this.startGame());
        this.musicToggle.addEventListener('click', () => this.toggleMusic());
        this.canvas.addEventListener('click', (event) => this.handleCanvasClick(event));
        this.scoreForm.addEventListener('submit', (event) => {
            event.preventDefault();
            void this.handleScoreSubmit();
        });
    }
    preloadAssets() {
        const files = ['assets/outhouse.svg'];
        for (const config of Object.values(ENEMY_CONFIGS)) {
            files.push(config.sprite);
        }
        files.forEach((path) => {
            const image = new Image();
            image.src = path;
            this.images.set(path, image);
        });
    }
    async loadLeaderboard() {
        this.leaderboard = await this.api.fetchScores();
        if (this.leaderboard.length > 0) {
            this.bestScore = Math.max(this.bestScore, this.leaderboard[0].score);
            localStorage.setItem(STORAGE_KEYS.best, String(this.bestScore));
            this.updateHud();
        }
        this.renderLeaderboard();
    }
    getElement(id) {
        const element = document.getElementById(id);
        if (!element) {
            throw new Error(`Missing required element: ${id}`);
        }
        return element;
    }
    startGame() {
        this.playing = true;
        this.submittedScore = false;
        this.spawnTimer = 0;
        this.survivalSeconds = 0;
        this.wave = 1;
        this.score = 0;
        this.combo = 0;
        this.comboTimer = 0;
        this.health = GAME_CONFIG.maxHealth;
        this.shakeTimer = 0;
        this.outhouseFlash = 0;
        this.enemies.length = 0;
        this.floatingTexts.length = 0;
        this.submitMessage.textContent = '';
        this.submitMessage.className = 'submit-message';
        this.playerNameInput.value = '';
        this.startOverlay.classList.remove('visible');
        this.gameOverOverlay.classList.remove('visible');
        this.updateHud();
        void this.playMusic();
    }
    endGame() {
        this.playing = false;
        this.pauseMusic();
        const isRecord = this.score > this.bestScore;
        if (isRecord) {
            this.bestScore = this.score;
            localStorage.setItem(STORAGE_KEYS.best, String(this.bestScore));
        }
        this.finalScoreValue.textContent = String(this.score);
        this.finalTimeValue.textContent = `${this.survivalSeconds.toFixed(1)}s`;
        this.recordStatus.textContent = isRecord ? 'New Record' : 'No';
        this.gameOverTitle.textContent = 'The last outhouse has fallen.';
        this.gameOverText.textContent = 'The outhouse has been overrun. Roaring Days is now a sanitation incident.';
        this.gameOverOverlay.classList.add('visible');
        this.updateHud();
        this.renderLeaderboard();
    }
    async handleScoreSubmit() {
        if (this.submittedScore) {
            this.setSubmitMessage('This run is already in the ledger.', false);
            return;
        }
        const playerName = this.playerNameInput.value.trim();
        if (playerName.length < 2 || playerName.length > 20) {
            this.setSubmitMessage('Name must be between 2 and 20 characters.', false);
            return;
        }
        this.submitScoreButton.disabled = true;
        const result = await this.api.submitScore({
            playerName,
            score: this.score,
            survivalSeconds: Number(this.survivalSeconds.toFixed(1)),
        });
        this.submitScoreButton.disabled = false;
        if (!result.success) {
            this.setSubmitMessage(result.message, false);
            return;
        }
        this.submittedScore = true;
        this.leaderboard = result.scores;
        if (this.leaderboard.length > 0) {
            this.bestScore = Math.max(this.bestScore, this.leaderboard[0].score);
            localStorage.setItem(STORAGE_KEYS.best, String(this.bestScore));
        }
        this.updateHud();
        this.renderLeaderboard();
        this.setSubmitMessage(result.message, true);
    }
    setSubmitMessage(message, success) {
        this.submitMessage.textContent = message;
        this.submitMessage.className = `submit-message ${success ? 'success' : 'error'}`;
    }
    toggleMusic() {
        this.musicEnabled = !this.musicEnabled;
        localStorage.setItem(STORAGE_KEYS.music, this.musicEnabled ? 'on' : 'off');
        if (this.musicEnabled && this.playing) {
            void this.playMusic();
        }
        else {
            this.pauseMusic();
        }
        this.updateMusicButton();
    }
    updateMusicButton() {
        if (this.musicFailed) {
            this.musicToggle.textContent = 'Music: Missing';
            return;
        }
        this.musicToggle.textContent = `Music: ${this.musicEnabled ? 'ON' : 'OFF'}`;
    }
    async playMusic() {
        if (!this.musicEnabled || this.musicFailed) {
            return;
        }
        try {
            this.music.currentTime = 0;
            await this.music.play();
        }
        catch (error) {
            console.warn('Music playback did not start.', error);
        }
    }
    pauseMusic() {
        try {
            this.music.pause();
        }
        catch (error) {
            console.warn('Music pause failed.', error);
        }
    }
    handleCanvasClick(event) {
        if (!this.playing) {
            return;
        }
        const rect = this.canvas.getBoundingClientRect();
        const scaleX = this.canvas.width / rect.width;
        const scaleY = this.canvas.height / rect.height;
        const x = (event.clientX - rect.left) * scaleX;
        const y = (event.clientY - rect.top) * scaleY;
        for (let index = this.enemies.length - 1; index >= 0; index -= 1) {
            const enemy = this.enemies[index];
            if (!enemy.containsPoint(x, y)) {
                continue;
            }
            const defeated = enemy.takeHit(GAME_CONFIG.clickDamage);
            this.spawnFloatingText(enemy.x, enemy.y - enemy.radius, HIT_WORDS[Math.floor(Math.random() * HIT_WORDS.length)], '#fff0a6', 18);
            if (defeated) {
                this.enemies.splice(index, 1);
                this.combo += 1;
                this.comboTimer = GAME_CONFIG.comboResetSeconds;
                const comboBonus = Math.max(0, this.combo - 1) * 5;
                this.score += enemy.config.score + comboBonus;
                this.spawnFloatingText(enemy.x, enemy.y - 28, `+${enemy.config.score + comboBonus}`, '#d6ff8f', 20);
            }
            this.updateHud();
            return;
        }
    }
    loop(timestamp) {
        const delta = Math.min(0.033, (timestamp - this.lastFrameTime) / 1000 || 0);
        this.lastFrameTime = timestamp;
        if (this.playing) {
            this.update(delta);
        }
        this.render(timestamp / 1000);
        this.animationHandle = requestAnimationFrame(this.loop);
    }
    update(delta) {
        this.survivalSeconds += delta;
        this.wave = Math.floor(this.survivalSeconds / GAME_CONFIG.waveEverySeconds) + 1;
        this.spawnTimer -= delta;
        this.shakeTimer = Math.max(0, this.shakeTimer - delta);
        this.outhouseFlash = Math.max(0, this.outhouseFlash - delta);
        this.comboTimer = Math.max(0, this.comboTimer - delta);
        if (this.comboTimer === 0) {
            this.combo = 0;
        }
        const spawnInterval = Math.max(GAME_CONFIG.spawnMinInterval, GAME_CONFIG.spawnBaseInterval - (this.wave - 1) * GAME_CONFIG.waveSpawnFactor);
        if (this.spawnTimer <= 0) {
            this.spawnEnemy();
            this.spawnTimer = spawnInterval * (0.78 + Math.random() * 0.46);
        }
        const target = this.getOuthouseCenter();
        for (let index = this.enemies.length - 1; index >= 0; index -= 1) {
            const enemy = this.enemies[index];
            enemy.update(delta, this.survivalSeconds, target.x, target.y, this.wave);
            if (enemy.reached(target.x, target.y, 52)) {
                this.health = Math.max(0, this.health - enemy.config.damage);
                this.enemies.splice(index, 1);
                this.shakeTimer = 0.24;
                this.outhouseFlash = 0.18;
                this.combo = 0;
                this.comboTimer = 0;
                this.spawnFloatingText(target.x, target.y - 84, BREACH_WORDS[Math.floor(Math.random() * BREACH_WORDS.length)], '#ff9078', 22);
                if (this.health <= 0) {
                    this.updateHud();
                    this.endGame();
                    return;
                }
            }
        }
        for (let index = this.floatingTexts.length - 1; index >= 0; index -= 1) {
            const text = this.floatingTexts[index];
            text.life -= delta;
            text.y -= 24 * delta;
            if (text.life <= 0) {
                this.floatingTexts.splice(index, 1);
            }
        }
        this.updateHud();
    }
    spawnEnemy() {
        const config = this.pickEnemyType();
        const side = Math.floor(Math.random() * 4);
        let x = 0;
        let y = 0;
        const padding = 36;
        if (side === 0) {
            x = -padding;
            y = 40 + Math.random() * (this.canvas.height * 0.55);
        }
        else if (side === 1) {
            x = this.canvas.width + padding;
            y = 40 + Math.random() * (this.canvas.height * 0.55);
        }
        else if (side === 2) {
            x = 40 + Math.random() * (this.canvas.width - 80);
            y = -padding;
        }
        else {
            x = 40 + Math.random() * (this.canvas.width - 80);
            y = this.canvas.height * 0.15 + Math.random() * 40;
        }
        this.enemies.push(new Enemy(config, x, y));
    }
    pickEnemyType() {
        const unlocked = SPAWN_TABLE.filter((entry) => ENEMY_CONFIGS[entry.id].unlockWave <= this.wave);
        const totalWeight = unlocked.reduce((sum, entry) => sum + entry.weight, 0);
        let roll = Math.random() * totalWeight;
        for (const entry of unlocked) {
            roll -= entry.weight;
            if (roll <= 0) {
                return ENEMY_CONFIGS[entry.id];
            }
        }
        return ENEMY_CONFIGS.goblin;
    }
    spawnFloatingText(x, y, text, color, size) {
        this.floatingTexts.push({
            x,
            y,
            text,
            color,
            size,
            life: 0.8,
            maxLife: 0.8,
        });
    }
    getOuthouseRect() {
        return {
            x: this.canvas.width / 2 - 84,
            y: this.canvas.height - 214,
            width: 168,
            height: 196,
        };
    }
    getOuthouseCenter() {
        const rect = this.getOuthouseRect();
        return {
            x: rect.x + rect.width / 2,
            y: rect.y + rect.height * 0.7,
        };
    }
    updateHud() {
        this.scoreValue.textContent = String(this.score);
        this.healthValue.textContent = `${Math.round(this.health)}%`;
        this.timeValue.textContent = `${this.survivalSeconds.toFixed(1)}s`;
        this.waveValue.textContent = String(this.wave);
        this.bestValue.textContent = String(this.bestScore);
        const healthRatio = this.health / GAME_CONFIG.maxHealth;
        this.healthBar.style.width = `${Math.max(0, healthRatio) * 100}%`;
        if (healthRatio > 0.55) {
            this.healthBar.style.background = 'linear-gradient(90deg, #5dbb63, #a8de69)';
        }
        else if (healthRatio > 0.25) {
            this.healthBar.style.background = 'linear-gradient(90deg, #f2b84b, #ffe083)';
        }
        else {
            this.healthBar.style.background = 'linear-gradient(90deg, #dd5d4a, #ff8f73)';
        }
    }
    renderLeaderboard() {
        this.fillLeaderboardElement(this.leaderboardList, this.leaderboard);
        this.fillLeaderboardElement(this.gameOverLeaderboard, this.leaderboard);
    }
    fillLeaderboardElement(list, entries) {
        list.innerHTML = '';
        if (entries.length === 0) {
            const item = document.createElement('li');
            item.textContent = EMPTY_LEADERBOARD_TEXT;
            list.appendChild(item);
            return;
        }
        entries.slice(0, GAME_CONFIG.bestLeaderboardSize).forEach((entry) => {
            const item = document.createElement('li');
            item.textContent = `${entry.playerName} - ${entry.score} pts - ${entry.survivalSeconds.toFixed(1)}s`;
            list.appendChild(item);
        });
    }
    render(time) {
        const { ctx } = this;
        ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        this.drawBackground(time);
        this.drawStageDecor(time);
        this.drawEnemies();
        this.drawOuthouse(time);
        this.drawFloatingTexts();
        if (this.playing && this.combo > 1) {
            this.drawComboBanner();
        }
    }
    drawBackground(time) {
        const { ctx } = this;
        const gradient = ctx.createLinearGradient(0, 0, 0, this.canvas.height);
        gradient.addColorStop(0, '#ffcf7a');
        gradient.addColorStop(0.35, '#ea8a60');
        gradient.addColorStop(0.72, '#65517d');
        gradient.addColorStop(1, '#233040');
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
        ctx.fillStyle = 'rgba(255, 243, 204, 0.14)';
        for (let index = 0; index < 8; index += 1) {
            const x = 90 + index * 105 + Math.sin(time + index) * 8;
            const y = 88 + (index % 3) * 16;
            ctx.fillRect(x, y, 8, 8);
            ctx.fillRect(x + 16, y + 8, 8, 8);
            ctx.fillRect(x + 8, y + 16, 8, 8);
        }
        ctx.fillStyle = '#405536';
        ctx.fillRect(0, this.canvas.height - 164, this.canvas.width, 164);
        ctx.fillStyle = '#56753f';
        for (let x = 0; x < this.canvas.width; x += 32) {
            ctx.fillRect(x, this.canvas.height - 164 + ((x / 32) % 2) * 6, 24, 164);
        }
        ctx.fillStyle = '#2f4227';
        for (let x = 0; x < this.canvas.width; x += 16) {
            ctx.fillRect(x, this.canvas.height - 42 + (x % 32 === 0 ? 2 : 0), 12, 40);
        }
    }
    drawStageDecor(time) {
        const { ctx } = this;
        const bannerY = 250;
        ctx.fillStyle = '#6b3c22';
        ctx.fillRect(86, bannerY, 12, 168);
        ctx.fillRect(this.canvas.width - 98, bannerY, 12, 168);
        ctx.fillStyle = '#dd8b52';
        ctx.fillRect(98, bannerY + 10, this.canvas.width - 196, 26);
        ctx.fillStyle = '#f0d37f';
        for (let index = 0; index < 9; index += 1) {
            const x = 126 + index * 88;
            const bob = Math.sin(time * 2.2 + index) * 6;
            ctx.fillRect(x, bannerY + 36 + bob, 12, 18);
            ctx.fillRect(x - 8, bannerY + 46 + bob, 28, 8);
        }
        ctx.fillStyle = '#a0c06b';
        for (let index = 0; index < 18; index += 1) {
            const x = 20 + index * 54;
            const y = this.canvas.height - 144 + (index % 3) * 8;
            ctx.fillRect(x, y, 8, 28);
            ctx.fillRect(x - 6, y + 8, 8, 16);
            ctx.fillRect(x + 6, y + 12, 8, 18);
        }
    }
    drawEnemies() {
        const { ctx } = this;
        for (const enemy of this.enemies) {
            const image = this.images.get(enemy.config.sprite);
            const size = enemy.radius * 2;
            ctx.save();
            if (enemy.hitFlash > 0) {
                ctx.globalAlpha = 0.6 + enemy.hitFlash * 2;
            }
            ctx.translate(enemy.x, enemy.y);
            ctx.drawImage(image !== null && image !== void 0 ? image : this.makeFallbackSprite(enemy.config.tint), -size / 2, -size / 2, size, size);
            if (enemy.hitFlash > 0) {
                ctx.fillStyle = 'rgba(255,255,255,0.28)';
                ctx.fillRect(-size / 2, -size / 2, size, size);
            }
            ctx.restore();
            ctx.fillStyle = '#2c1d13';
            ctx.fillRect(enemy.x - enemy.radius, enemy.y + enemy.radius - 4, enemy.radius * 2, 6);
            ctx.fillStyle = '#87d964';
            ctx.fillRect(enemy.x - enemy.radius, enemy.y + enemy.radius - 4, (enemy.health / enemy.config.health) * enemy.radius * 2, 6);
        }
    }
    drawOuthouse(time) {
        const { ctx } = this;
        const rect = this.getOuthouseRect();
        const shakeX = this.shakeTimer > 0 ? Math.sin(time * 42) * 6 : 0;
        const shakeY = this.shakeTimer > 0 ? Math.cos(time * 35) * 4 : 0;
        const image = this.images.get('assets/outhouse.svg');
        ctx.save();
        ctx.translate(shakeX, shakeY);
        ctx.drawImage(image !== null && image !== void 0 ? image : this.makeFallbackSprite('#8c5a35'), rect.x, rect.y, rect.width, rect.height);
        if (this.outhouseFlash > 0) {
            ctx.fillStyle = `rgba(255, 149, 110, ${this.outhouseFlash * 2.6})`;
            ctx.fillRect(rect.x, rect.y, rect.width, rect.height);
        }
        ctx.restore();
    }
    drawFloatingTexts() {
        const { ctx } = this;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        for (const text of this.floatingTexts) {
            const alpha = Math.max(0, text.life / text.maxLife);
            ctx.globalAlpha = alpha;
            ctx.fillStyle = '#2b1c11';
            ctx.font = `bold ${text.size}px Georgia`;
            ctx.fillText(text.text, text.x + 2, text.y + 2);
            ctx.fillStyle = text.color;
            ctx.fillText(text.text, text.x, text.y);
        }
        ctx.globalAlpha = 1;
    }
    drawComboBanner() {
        const { ctx } = this;
        ctx.fillStyle = 'rgba(45, 28, 16, 0.78)';
        ctx.fillRect(18, 92, 172, 50);
        ctx.strokeStyle = '#f0d37f';
        ctx.lineWidth = 4;
        ctx.strokeRect(18, 92, 172, 50);
        ctx.fillStyle = '#fef0a2';
        ctx.font = 'bold 18px Georgia';
        ctx.textAlign = 'left';
        ctx.fillText(`Combo x${this.combo}`, 32, 123);
    }
    makeFallbackSprite(color) {
        const fallback = document.createElement('canvas');
        fallback.width = 32;
        fallback.height = 32;
        const context = fallback.getContext('2d');
        if (!context) {
            return fallback;
        }
        context.fillStyle = color;
        context.fillRect(4, 4, 24, 24);
        context.fillStyle = '#2c1d13';
        context.fillRect(8, 8, 6, 6);
        context.fillRect(18, 8, 6, 6);
        context.fillRect(12, 18, 8, 6);
        return fallback;
    }
}
window.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('gameCanvas');
    if (!(canvas instanceof HTMLCanvasElement)) {
        throw new Error('Game canvas missing.');
    }
    new Game(canvas);
});
