
type EnemyTypeId =
  | 'goblin'
  | 'murloc'
  | 'druid'
  | 'drunk'
  | 'jumper'
  | 'engineer';

interface EnemyConfig {
  id: EnemyTypeId;
  name: string;
  health: number;
  speed: number;
  damage: number;
  score: number;
  wobble: number;
  tint: string;
  unlockWave: number;
  sprite: string;
  scale: number;
}

interface SpawnWeights {
  id: EnemyTypeId;
  weight: number;
}

interface ScoreEntry {
  playerName: string;
  score: number;
  survivalSeconds: number;
  createdAt: string;
}

interface FloatingText {
  x: number;
  y: number;
  text: string;
  color: string;
  life: number;
  maxLife: number;
  size: number;
}

const STORAGE_KEYS = {
  best: 'protect-the-outhouse-best',
  music: 'protect-the-outhouse-music',
  sfx: 'protect-the-outhouse-sfx',
  musicVolume: 'protect-the-outhouse-music-volume',
  sfxVolume: 'protect-the-outhouse-sfx-volume',
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
  defaultMusicVolume: 0.5,
  defaultSfxVolume: 0.6,
};

const ENEMY_CONFIGS: Record<EnemyTypeId, EnemyConfig> = {
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

const SPAWN_TABLE: SpawnWeights[] = [
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
const SOUND_EFFECTS = {
  hit: ['assets/sfx-hit-1.wav', 'assets/sfx-hit-2.wav', 'assets/sfx-hit-3.wav'],
  breach: ['assets/sfx-breach-1.wav', 'assets/sfx-breach-2.wav', 'assets/sfx-breach-3.wav'],
};

class LeaderboardAPI {
  async fetchScores(): Promise<ScoreEntry[]> {
    try {
      const response = await fetch('api/score.php', { cache: 'no-store' });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const payload = (await response.json()) as { success: boolean; scores?: ScoreEntry[] };
      return Array.isArray(payload.scores) ? payload.scores : [];
    } catch (error) {
      console.warn('Leaderboard fetch failed.', error);
      return [];
    }
  }

  async submitScore(entry: Pick<ScoreEntry, 'playerName' | 'score' | 'survivalSeconds'>): Promise<{ success: boolean; message: string; scores: ScoreEntry[] }> {
    try {
      const response = await fetch('api/score.php', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(entry),
      });

      const payload = (await response.json()) as { success?: boolean; error?: string; scores?: ScoreEntry[] };
      if (!response.ok || !payload.success) {
        return {
          success: false,
          message: payload.error ?? 'Submission failed.',
          scores: Array.isArray(payload.scores) ? payload.scores : [],
        };
      }

      return {
        success: true,
        message: 'Score submitted to the festival ledger.',
        scores: Array.isArray(payload.scores) ? payload.scores : [],
      };
    } catch (error) {
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
  config: EnemyConfig;
  x: number;
  y: number;
  health: number;
  radius: number;
  wobbleSeed: number;
  hitFlash = 0;

  constructor(config: EnemyConfig, x: number, y: number) {
    this.config = config;
    this.x = x;
    this.y = y;
    this.health = config.health;
    this.radius = GAME_CONFIG.enemyRadius * config.scale;
    this.wobbleSeed = Math.random() * Math.PI * 2;
  }

  takeHit(amount: number): boolean {
    this.health -= amount;
    this.hitFlash = GAME_CONFIG.enemyHitFlash;
    return this.health <= 0;
  }

  update(delta: number, time: number, targetX: number, targetY: number, wave: number): void {
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

  reached(targetX: number, targetY: number, threshold: number): boolean {
    return Math.hypot(this.x - targetX, this.y - targetY) <= threshold + this.radius * 0.65;
  }

  containsPoint(x: number, y: number): boolean {
    return Math.hypot(this.x - x, this.y - y) <= this.radius;
  }
}

class Game {
  private readonly canvas: HTMLCanvasElement;
  private readonly ctx: CanvasRenderingContext2D;
  private readonly scoreValue = this.getElement<HTMLElement>('scoreValue');
  private readonly healthValue = this.getElement<HTMLElement>('healthValue');
  private readonly timeValue = this.getElement<HTMLElement>('timeValue');
  private readonly waveValue = this.getElement<HTMLElement>('waveValue');
  private readonly bestValue = this.getElement<HTMLElement>('bestValue');
  private readonly healthBar = this.getElement<HTMLElement>('healthBar');
  private readonly startOverlay = this.getElement<HTMLElement>('startOverlay');
  private readonly gameOverOverlay = this.getElement<HTMLElement>('gameOverOverlay');
  private readonly startButton = this.getElement<HTMLButtonElement>('startButton');
  private readonly restartButton = this.getElement<HTMLButtonElement>('restartButton');
  private readonly musicToggle = this.getElement<HTMLButtonElement>('musicToggle');
  private readonly sfxToggle = this.getElement<HTMLButtonElement>('sfxToggle');
  private readonly pauseToggle = this.getElement<HTMLButtonElement>('pauseToggle');
  private readonly musicVolumeSlider = this.getElement<HTMLInputElement>('musicVolume');
  private readonly sfxVolumeSlider = this.getElement<HTMLInputElement>('sfxVolume');
  private readonly finalScoreValue = this.getElement<HTMLElement>('finalScoreValue');
  private readonly finalTimeValue = this.getElement<HTMLElement>('finalTimeValue');
  private readonly recordStatus = this.getElement<HTMLElement>('recordStatus');
  private readonly gameOverTitle = this.getElement<HTMLElement>('gameOverTitle');
  private readonly gameOverText = this.getElement<HTMLElement>('gameOverText');
  private readonly scoreForm = this.getElement<HTMLFormElement>('scoreForm');
  private readonly playerNameInput = this.getElement<HTMLInputElement>('playerName');
  private readonly submitMessage = this.getElement<HTMLElement>('submitMessage');
  private readonly leaderboardList = this.getElement<HTMLOListElement>('leaderboardList');
  private readonly gameOverLeaderboard = this.getElement<HTMLOListElement>('gameOverLeaderboard');
  private readonly submitScoreButton = this.getElement<HTMLButtonElement>('submitScoreButton');
  private readonly api = new LeaderboardAPI();
  private readonly music = new Audio('assets/music.mp3');
  private readonly images = new Map<string, HTMLImageElement>();
  private readonly soundEffects = {
    hit: SOUND_EFFECTS.hit.map((path) => this.createAudio(path)),
    breach: SOUND_EFFECTS.breach.map((path) => this.createAudio(path)),
  };
  private readonly floatingTexts: FloatingText[] = [];
  private readonly enemies: Enemy[] = [];
  private lastFrameTime = 0;
  private animationHandle = 0;
  private spawnTimer = 0;
  private survivalSeconds = 0;
  private wave = 1;
  private score = 0;
  private combo = 0;
  private comboTimer = 0;
  private health = GAME_CONFIG.maxHealth;
  private playing = false;
  private paused = false;
  private submittedScore = false;
  private shakeTimer = 0;
  private outhouseFlash = 0;
  private bestScore = 0;
  private leaderboard: ScoreEntry[] = [];
  private musicEnabled = true;
  private musicFailed = false;
  private sfxEnabled = true;
  private musicVolume = GAME_CONFIG.defaultMusicVolume;
  private sfxVolume = GAME_CONFIG.defaultSfxVolume;

  constructor(canvas: HTMLCanvasElement) {
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
    this.music.volume = GAME_CONFIG.defaultMusicVolume;
    this.music.preload = 'auto';
    this.music.addEventListener('error', () => {
      this.musicFailed = true;
      this.updateMusicButton();
    });

    this.bestScore = Number(localStorage.getItem(STORAGE_KEYS.best) ?? '0') || 0;
    this.musicEnabled = localStorage.getItem(STORAGE_KEYS.music) !== 'off';
    this.sfxEnabled = localStorage.getItem(STORAGE_KEYS.sfx) !== 'off';
    this.musicVolume = this.readStoredVolume(STORAGE_KEYS.musicVolume, GAME_CONFIG.defaultMusicVolume);
    this.sfxVolume = this.readStoredVolume(STORAGE_KEYS.sfxVolume, GAME_CONFIG.defaultSfxVolume);
    this.music.volume = this.musicVolume;

    this.bindEvents();
    this.preloadAssets();
    this.updateMusicButton();
    this.updateSfxButton();
    this.updatePauseButton();
    this.syncVolumeControls();
    this.updateHud();
    void this.loadLeaderboard();
    this.render(0);
    this.loop = this.loop.bind(this);
    this.animationHandle = requestAnimationFrame(this.loop);
  }

  private bindEvents(): void {
    this.startButton.addEventListener('click', () => this.startGame());
    this.restartButton.addEventListener('click', () => this.startGame());
    this.musicToggle.addEventListener('click', () => this.toggleMusic());
    this.sfxToggle.addEventListener('click', () => this.toggleSfx());
    this.pauseToggle.addEventListener('click', () => this.togglePause());
    this.musicVolumeSlider.addEventListener('input', () => this.setMusicVolume(Number(this.musicVolumeSlider.value) / 100));
    this.sfxVolumeSlider.addEventListener('input', () => this.setSfxVolume(Number(this.sfxVolumeSlider.value) / 100));
    this.canvas.addEventListener('click', (event) => this.handleCanvasClick(event));
    this.scoreForm.addEventListener('submit', (event) => {
      event.preventDefault();
      void this.handleScoreSubmit();
    });
  }

  private preloadAssets(): void {
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

  private async loadLeaderboard(): Promise<void> {
    this.leaderboard = await this.api.fetchScores();
    if (this.leaderboard.length > 0) {
      this.bestScore = Math.max(this.bestScore, this.leaderboard[0].score);
      localStorage.setItem(STORAGE_KEYS.best, String(this.bestScore));
      this.updateHud();
    }
    this.renderLeaderboard();
  }

  private readStoredVolume(key: string, fallback: number): number {
    const raw = Number(localStorage.getItem(key));
    if (Number.isFinite(raw) && raw >= 0 && raw <= 1) {
      return raw;
    }
    return fallback;
  }

  private syncVolumeControls(): void {
    this.musicVolumeSlider.value = String(Math.round(this.musicVolume * 100));
    this.sfxVolumeSlider.value = String(Math.round(this.sfxVolume * 100));
  }


  private getElement<T extends HTMLElement>(id: string): T {
    const element = document.getElementById(id);
    if (!element) {
      throw new Error(`Missing required element: ${id}`);
    }
    return element as T;
  }

  private startGame(): void {
    this.playing = true;
    this.paused = false;
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

  private endGame(): void {
    this.playing = false;
    this.paused = false;
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
    this.updatePauseButton();
    this.updateHud();
    this.renderLeaderboard();
  }
  private async handleScoreSubmit(): Promise<void> {
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
    this.updatePauseButton();
    this.updateHud();
    this.renderLeaderboard();
    this.setSubmitMessage(result.message, true);
  }

  private setSubmitMessage(message: string, success: boolean): void {
    this.submitMessage.textContent = message;
    this.submitMessage.className = `submit-message ${success ? 'success' : 'error'}`;
  }

  private createAudio(path: string): HTMLAudioElement {
    const audio = new Audio(path);
    audio.preload = 'auto';
    return audio;
  }

  private setMusicVolume(value: number): void {
    this.musicVolume = Math.max(0, Math.min(1, value));
    this.music.volume = this.musicVolume;
    localStorage.setItem(STORAGE_KEYS.musicVolume, this.musicVolume.toFixed(2));
    this.syncVolumeControls();
  }

  private setSfxVolume(value: number): void {
    this.sfxVolume = Math.max(0, Math.min(1, value));
    localStorage.setItem(STORAGE_KEYS.sfxVolume, this.sfxVolume.toFixed(2));
    this.syncVolumeControls();
  }

  private toggleMusic(): void {
    this.musicEnabled = !this.musicEnabled;
    localStorage.setItem(STORAGE_KEYS.music, this.musicEnabled ? 'on' : 'off');
    if (this.musicEnabled && this.playing) {
      void this.playMusic();
    } else {
      this.pauseMusic();
    }
    this.updateMusicButton();
  }

  private toggleSfx(): void {
    this.sfxEnabled = !this.sfxEnabled;
    localStorage.setItem(STORAGE_KEYS.sfx, this.sfxEnabled ? 'on' : 'off');
    this.updateSfxButton();
  }

  private updateMusicButton(): void {
    if (this.musicFailed) {
      this.musicToggle.textContent = 'Music: Missing';
      return;
    }
    this.musicToggle.textContent = `Music: ${this.musicEnabled ? 'ON' : 'OFF'}`;
  }

  private updateSfxButton(): void {
    this.sfxToggle.textContent = `SFX: ${this.sfxEnabled ? 'ON' : 'OFF'}`;
  }


  private updatePauseButton(): void {
    this.pauseToggle.textContent = this.paused ? 'Resume' : 'Pause';
  }

  private togglePause(): void {
    if (!this.playing) {
      return;
    }

    this.paused = !this.paused;
    if (this.paused) {
      this.pauseMusic();
    } else if (this.musicEnabled) {
      void this.playMusic(false);
    }
    this.updatePauseButton();
  }

  private playRandomSound(group: 'hit' | 'breach'): void {
    if (!this.sfxEnabled) {
      return;
    }

    const pool = this.soundEffects[group];
    if (pool.length === 0) {
      return;
    }

    const source = pool[Math.floor(Math.random() * pool.length)];
    const sound = source.cloneNode(true) as HTMLAudioElement;
    sound.volume = this.sfxVolume * (group === 'hit' ? 0.76 : 1); 
    void sound.play().catch((error) => {
      console.warn(`Unable to play ${group} sound effect.`, error);
    });
  }

  private async playMusic(resetTime = true): Promise<void> {
    if (!this.musicEnabled || this.musicFailed) {
      return;
    }

    try {
      if (resetTime) {
        this.music.currentTime = 0;
      }
      await this.music.play();
    } catch (error) {
      console.warn('Music playback did not start.', error);
    }
  }

  private pauseMusic(): void {
    try {
      this.music.pause();
    } catch (error) {
      console.warn('Music pause failed.', error);
    }
  }

  private handleCanvasClick(event: MouseEvent): void {
    if (!this.playing || this.paused) {
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
      this.playRandomSound('hit');
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

  private loop(timestamp: number): void {
    const delta = Math.min(0.033, (timestamp - this.lastFrameTime) / 1000 || 0);
    this.lastFrameTime = timestamp;

    if (this.playing && !this.paused) {
      this.update(delta);
    }

    this.render(timestamp / 1000);
    this.animationHandle = requestAnimationFrame(this.loop);
  }

  private update(delta: number): void {
    this.survivalSeconds += delta;
    this.wave = Math.floor(this.survivalSeconds / GAME_CONFIG.waveEverySeconds) + 1;
    this.spawnTimer -= delta;
    this.shakeTimer = Math.max(0, this.shakeTimer - delta);
    this.outhouseFlash = Math.max(0, this.outhouseFlash - delta);
    this.comboTimer = Math.max(0, this.comboTimer - delta);
    if (this.comboTimer === 0) {
      this.combo = 0;
    }

    const spawnInterval = Math.max(
      GAME_CONFIG.spawnMinInterval,
      GAME_CONFIG.spawnBaseInterval - (this.wave - 1) * GAME_CONFIG.waveSpawnFactor
    );

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
        this.playRandomSound('breach');
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

  private spawnEnemy(): void {
    const config = this.pickEnemyType();
    const side = Math.floor(Math.random() * 4);
    let x = 0;
    let y = 0;
    const padding = 36;

    if (side === 0) {
      x = -padding;
      y = 40 + Math.random() * (this.canvas.height * 0.55);
    } else if (side === 1) {
      x = this.canvas.width + padding;
      y = 40 + Math.random() * (this.canvas.height * 0.55);
    } else if (side === 2) {
      x = 40 + Math.random() * (this.canvas.width - 80);
      y = -padding;
    } else {
      x = 40 + Math.random() * (this.canvas.width - 80);
      y = this.canvas.height * 0.15 + Math.random() * 40;
    }

    this.enemies.push(new Enemy(config, x, y));
  }

  private pickEnemyType(): EnemyConfig {
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

  private spawnFloatingText(x: number, y: number, text: string, color: string, size: number): void {
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

  private getOuthouseRect(): { x: number; y: number; width: number; height: number } {
    return {
      x: this.canvas.width / 2 - 84,
      y: this.canvas.height - 214,
      width: 168,
      height: 196,
    };
  }

  private getOuthouseCenter(): { x: number; y: number } {
    const rect = this.getOuthouseRect();
    return {
      x: rect.x + rect.width / 2,
      y: rect.y + rect.height * 0.7,
    };
  }
  private updateHud(): void {
    this.scoreValue.textContent = String(this.score);
    this.healthValue.textContent = `${Math.round(this.health)}%`;
    this.timeValue.textContent = `${this.survivalSeconds.toFixed(1)}s`;
    this.waveValue.textContent = String(this.wave);
    this.bestValue.textContent = String(this.bestScore);

    const healthRatio = this.health / GAME_CONFIG.maxHealth;
    this.healthBar.style.width = `${Math.max(0, healthRatio) * 100}%`;
    if (healthRatio > 0.55) {
      this.healthBar.style.background = 'linear-gradient(90deg, #5dbb63, #a8de69)';
    } else if (healthRatio > 0.25) {
      this.healthBar.style.background = 'linear-gradient(90deg, #f2b84b, #ffe083)';
    } else {
      this.healthBar.style.background = 'linear-gradient(90deg, #dd5d4a, #ff8f73)';
    }
  }

  private renderLeaderboard(): void {
    this.fillLeaderboardElement(this.leaderboardList, this.leaderboard);
    this.fillLeaderboardElement(this.gameOverLeaderboard, this.leaderboard);
  }

  private fillLeaderboardElement(list: HTMLOListElement, entries: ScoreEntry[]): void {
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

  private render(time: number): void {
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

  private drawBackground(time: number): void {
    const { ctx } = this;
    const gradient = ctx.createLinearGradient(0, 0, 0, this.canvas.height);
    gradient.addColorStop(0, '#a8d6ff');
    gradient.addColorStop(0.34, '#f0c97d');
    gradient.addColorStop(0.72, '#8d623d');
    gradient.addColorStop(1, '#3a2d27');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

    ctx.fillStyle = '#7896b6';
    ctx.fillRect(118, 154, 96, 26);
    ctx.fillRect(702, 140, 124, 34);
    ctx.fillStyle = '#b9c4cb';
    ctx.fillRect(148, 126, 66, 54);
    ctx.fillRect(728, 104, 104, 70);

    ctx.fillStyle = '#648448';
    ctx.fillRect(0, 186, this.canvas.width, 54);
    ctx.fillStyle = '#8bb05a';
    for (let x = 0; x < this.canvas.width; x += 20) {
      const top = 176 + Math.sin(x * 0.02 + time * 0.4) * 8;
      ctx.fillRect(x, top, 16, 36);
    }

    ctx.fillStyle = '#8f562b';
    ctx.beginPath();
    ctx.moveTo(0, 250);
    ctx.lineTo(182, 170);
    ctx.lineTo(368, 240);
    ctx.lineTo(574, 184);
    ctx.lineTo(760, 224);
    ctx.lineTo(960, 178);
    ctx.lineTo(960, 430);
    ctx.lineTo(0, 430);
    ctx.closePath();
    ctx.fill();

    ctx.fillStyle = '#6d4328';
    for (let y = 336; y < this.canvas.height; y += 34) {
      ctx.fillRect(0, y, this.canvas.width, 16);
    }
    ctx.fillStyle = '#3d6a2a';
    for (let x = 18; x < this.canvas.width; x += 42) {
      for (let y = 334; y < this.canvas.height; y += 34) {
        ctx.fillRect(x, y + (x % 3), 10, 6);
      }
    }
  }

  private drawStageDecor(time: number): void {
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

    ctx.fillStyle = '#7f3e2a';
    ctx.fillRect(196, bannerY + 12, this.canvas.width - 392, 22);
    ctx.font = 'bold 22px Georgia';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = '#f7e8aa';
    ctx.fillText('Roaring Days', this.canvas.width / 2, bannerY + 24);

    ctx.fillStyle = '#c8925d';
    for (let x = 36; x < this.canvas.width; x += 84) {
      ctx.fillRect(x, this.canvas.height - 224, 8, 82);
      ctx.fillRect(x - 2, this.canvas.height - 206, 42, 6);
      ctx.fillRect(x - 2, this.canvas.height - 172, 42, 6);
    }

    this.drawMelon(254, this.canvas.height - 82, 1.15);
    this.drawMelon(336, this.canvas.height - 92, 0.92);
    this.drawMelon(402, this.canvas.height - 80, 0.8);
    this.drawMelon(572, this.canvas.height - 86, 1.05);
    this.drawMelon(646, this.canvas.height - 76, 0.88);
    this.drawMelon(712, this.canvas.height - 92, 1.12);
  }

  private drawMelon(x: number, y: number, scale: number): void {
    const { ctx } = this;
    const width = 28 * scale;
    const height = 18 * scale;
    ctx.fillStyle = '#325d27';
    ctx.fillRect(x + width * 0.3, y - height - 4 * scale, 4 * scale, 4 * scale);
    ctx.fillRect(x + width * 0.48, y - height - 6 * scale, 6 * scale, 3 * scale);
    ctx.fillStyle = '#8dc456';
    ctx.fillRect(x, y - height, width, height);
    ctx.fillStyle = '#bde37b';
    ctx.fillRect(x + 3 * scale, y - height + 2 * scale, 4 * scale, height - 4 * scale);
    ctx.fillRect(x + 11 * scale, y - height + 1 * scale, 4 * scale, height - 2 * scale);
    ctx.fillRect(x + 19 * scale, y - height + 2 * scale, 4 * scale, height - 4 * scale);
    ctx.fillStyle = '#5c8d34';
    ctx.fillRect(x + 7 * scale, y - height + 1 * scale, 2 * scale, height - 2 * scale);
    ctx.fillRect(x + 15 * scale, y - height + 1 * scale, 2 * scale, height - 2 * scale);
    ctx.fillRect(x + 23 * scale, y - height + 2 * scale, 2 * scale, height - 4 * scale);
  }

  private drawEnemies(): void {
    const { ctx } = this;
    for (const enemy of this.enemies) {
      const image = this.images.get(enemy.config.sprite);
      const size = enemy.radius * 2;
      ctx.save();
      if (enemy.hitFlash > 0) {
        ctx.globalAlpha = 0.6 + enemy.hitFlash * 2;
      }
      ctx.translate(enemy.x, enemy.y);
      ctx.drawImage(image ?? this.makeFallbackSprite(enemy.config.tint), -size / 2, -size / 2, size, size);
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

  private drawOuthouse(time: number): void {
    const { ctx } = this;
    const rect = this.getOuthouseRect();
    const shakeX = this.shakeTimer > 0 ? Math.sin(time * 42) * 6 : 0;
    const shakeY = this.shakeTimer > 0 ? Math.cos(time * 35) * 4 : 0;
    const image = this.images.get('assets/outhouse.svg');

    ctx.save();
    ctx.translate(shakeX, shakeY);
    ctx.drawImage(image ?? this.makeFallbackSprite('#8c5a35'), rect.x, rect.y, rect.width, rect.height);
    if (this.outhouseFlash > 0) {
      ctx.fillStyle = `rgba(255, 149, 110, ${this.outhouseFlash * 2.6})`;
      ctx.fillRect(rect.x, rect.y, rect.width, rect.height);
    }
    ctx.restore();
  }

  private drawFloatingTexts(): void {
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

  private drawComboBanner(): void {
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

  private makeFallbackSprite(color: string): HTMLCanvasElement {
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












