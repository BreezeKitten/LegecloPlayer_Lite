// Legeclo Interactive Visual Novel Engine
class LegecloPlayer {
  constructor() {
    this.allCharacters = [];
    this.currentChapterData = null;
    this.dialogueIndex = 0;
    this.currentPhaseIndex = -1;
    
    // Audio state
    this.audioUnlocked = false;
    this.isMuted = false;
    this.bgmVolume = 0.35;
    this.voiceVolume = 1.0;
    this.bgmAudio = document.getElementById('bgm-audio');
    this.voiceAudio = document.getElementById('voice-audio');
    this.bgmAudio.volume = this.bgmVolume;
    this.voiceAudio.volume = this.voiceVolume;

    // Playback settings
    this.isAutoPlay = false;
    this.autoTimer = null;
    this.autoDelay = 1200; // ms after voice or reading
    this.loopMode = 'story'; // 'story' or 'infinite'
    this.isUIHidden = false;

    // DOM Elements
    this.stageContainer = document.getElementById('stage-container');
    this.bgImage = document.getElementById('bg-image');
    this.stillImage = document.getElementById('still-image');
    this.stageVideo = document.getElementById('stage-video');
    this.speakerTag = document.getElementById('speaker-tag');
    this.dialogueText = document.getElementById('dialogue-text');
    this.currentTitle = document.getElementById('current-title');
    this.phaseBar = document.getElementById('phase-bar');
    this.sidebar = document.getElementById('sidebar');
    this.charList = document.getElementById('char-list');
    this.charSearch = document.getElementById('char-search');
    this.settingsModal = document.getElementById('settings-modal');
    this.logModal = document.getElementById('log-modal');
    this.logList = document.getElementById('log-list');
    this.autoBtn = document.getElementById('auto-btn');
    this.loopModeBtn = document.getElementById('loop-mode-btn');
    this.audioToggleBtn = document.getElementById('audio-toggle-btn');
    this.startOverlay = document.getElementById('start-overlay');
    this.startBtn = document.getElementById('start-btn');
    this.replayVoiceBtn = document.getElementById('replay-voice-btn');

    // Gallery Modal DOM Elements
    this.galleryModal = document.getElementById('gallery-modal');
    this.galleryGrid = document.getElementById('gallery-grid');
    this.gallerySearch = document.getElementById('gallery-search');
    this.galleryCount = document.getElementById('gallery-count');
    this.openGalleryBtn = document.getElementById('open-gallery-btn');
    this.closeGalleryBtn = document.getElementById('close-gallery-btn');

    // Mobile & Aspect Ratio Controls
    this.ratioToggleBtn = document.getElementById('ratio-toggle-btn');
    this.orientationOverlay = document.getElementById('orientation-overlay');
    this.rotateFullscreenBtn = document.getElementById('rotate-fullscreen-btn');
    this.iosGuideModal = document.getElementById('ios-guide-modal');
    this.closeIosGuideBtn = document.getElementById('close-ios-guide-btn');
    this.iosGuideOkBtn = document.getElementById('ios-guide-ok-btn');
    this.isFillMode = false;

    // Standing Illustration Spine 3.8 & Fallback
    this.standingLayer = document.getElementById('standing-layer');
    this.spineContainer = document.getElementById('spine-standing-container');
    this.staticStandingFallback = document.getElementById('static-standing-fallback');
    this.standingAnimWrap = document.getElementById('standing-anim-wrap');
    this.standingAnimSelect = document.getElementById('standing-anim-select');
    this.spinePlayer = null;
    this.currentSpineCharId = null;
    this.currentStandingAnim = null;
    this.isManualStandingAnim = false;

    // Voice / Subtitle Synchronization
    this.voiceDelayTimer = null;
    this.voiceDelay = 180; // ms natural onset delay for subtitles before speech starts

    this.initEventListeners();
    this.loadCharacterList();
  }

  initEventListeners() {
    // Standing animation dropdown change and click isolation
    if (this.standingAnimWrap) {
      this.standingAnimWrap.addEventListener('click', (e) => e.stopPropagation());
      this.standingAnimWrap.addEventListener('mousedown', (e) => e.stopPropagation());
    }
    const rebuildStandingBtn = document.getElementById('rebuild-standing-btn');
    if (rebuildStandingBtn) {
      rebuildStandingBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.rebuildCurrentStanding();
      });
      rebuildStandingBtn.addEventListener('mousedown', (e) => e.stopPropagation());
    }
    if (this.standingAnimSelect) {
      this.standingAnimSelect.addEventListener('click', (e) => e.stopPropagation());
      this.standingAnimSelect.addEventListener('mousedown', (e) => e.stopPropagation());
      this.standingAnimSelect.addEventListener('change', (e) => {
        e.stopPropagation();
        const anim = e.target.value;
        if (anim === 'auto') {
          this.isManualStandingAnim = false;
          const d = this.currentChapterData && this.currentChapterData.dialogues && this.currentChapterData.dialogues[this.dialogueIndex];
          this.updateStandingAnimationForDialogue(d);
        } else if (this.spinePlayer && anim) {
          this.isManualStandingAnim = true;
          this.setStandingAnimation(anim);
        }
      });
    }

    // Unlock Audio Overlay Click
    const handleStartClick = (e) => {
      e.stopPropagation();
      this.unlockAudio();
    };
    if (this.startOverlay) {
      this.startOverlay.addEventListener('click', handleStartClick);
    }
    if (this.startBtn) {
      this.startBtn.addEventListener('click', handleStartClick);
    }

    // Stage click to advance dialogue or unhide UI
    document.getElementById('stage-clicker').addEventListener('click', () => {
      this.unlockAudio();
      if (this.isUIHidden) {
        this.setUIHidden(false);
      } else {
        this.advanceDialogue();
      }
    });

    // Dialogue box click also advances dialogue
    document.getElementById('dialogue-box').addEventListener('click', (e) => {
      if (e.target.closest('#replay-voice-btn') || e.target.closest('#standing-anim-wrap')) return;
      this.unlockAudio();
      this.advanceDialogue();
    });

    // Audio Toggle Button
    this.audioToggleBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      this.toggleAudio();
    });

    // Replay voice
    this.replayVoiceBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      this.unlockAudio();
      clearTimeout(this.voiceDelayTimer);
      this.playCurrentVoice(true);
    });

    // Auto-play button
    this.autoBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      this.unlockAudio();
      this.toggleAutoPlay();
    });

    // Loop mode button
    this.loopModeBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      this.toggleLoopMode();
    });

    // Hide UI button
    document.getElementById('hide-ui-btn').addEventListener('click', (e) => {
      e.stopPropagation();
      this.setUIHidden(true);
    });

    // Sidebar open/close
    document.getElementById('open-sidebar-btn').addEventListener('click', (e) => {
      e.stopPropagation();
      this.sidebar.classList.add('open');
    });
    document.getElementById('close-sidebar-btn').addEventListener('click', (e) => {
      e.stopPropagation();
      this.sidebar.classList.remove('open');
    });

    // Search filter
    this.charSearch.addEventListener('input', (e) => {
      this.renderCharacterList(e.target.value.trim());
    });

    // Settings Modal
    document.getElementById('settings-btn').addEventListener('click', (e) => {
      e.stopPropagation();
      this.settingsModal.classList.remove('hidden');
    });
    document.getElementById('close-settings-btn').addEventListener('click', (e) => {
      e.stopPropagation();
      this.settingsModal.classList.add('hidden');
    });

    // Volume sliders
    document.getElementById('bgm-volume').addEventListener('input', (e) => {
      this.bgmVolume = e.target.value / 100;
      this.bgmAudio.volume = this.bgmVolume;
      document.getElementById('bgm-vol-val').textContent = `${e.target.value}%`;
    });
    document.getElementById('voice-volume').addEventListener('input', (e) => {
      this.voiceVolume = e.target.value / 100;
      this.voiceAudio.volume = this.voiceVolume;
      document.getElementById('voice-vol-val').textContent = `${e.target.value}%`;
    });
    const voiceDelayInput = document.getElementById('voice-delay');
    if (voiceDelayInput) {
      voiceDelayInput.addEventListener('input', (e) => {
        this.voiceDelay = e.target.value * 10;
        document.getElementById('voice-delay-val').textContent = `${(this.voiceDelay / 1000).toFixed(2)} 秒`;
      });
    }
    document.getElementById('auto-delay').addEventListener('input', (e) => {
      this.autoDelay = e.target.value * 100;
      document.getElementById('auto-delay-val').textContent = `${(this.autoDelay / 1000).toFixed(1)} 秒`;
    });
    document.getElementById('loop-mode-select').addEventListener('change', (e) => {
      this.setLoopMode(e.target.value);
    });

    // Cache Rebuild & Management in Settings
    const clearCharCacheBtn = document.getElementById('clear-char-cache-btn');
    if (clearCharCacheBtn) {
      clearCharCacheBtn.addEventListener('click', () => this.rebuildCurrentStanding());
    }
    const clearAllStandingBtn = document.getElementById('clear-all-standing-btn');
    if (clearAllStandingBtn) {
      clearAllStandingBtn.addEventListener('click', () => this.clearAllStandingCache());
    }

    // Log Modal
    document.getElementById('log-btn').addEventListener('click', (e) => {
      e.stopPropagation();
      this.renderLog();
      this.logModal.classList.remove('hidden');
    });
    document.getElementById('close-log-btn').addEventListener('click', (e) => {
      e.stopPropagation();
      this.logModal.classList.add('hidden');
    });

    // Gallery Modal
    if (this.openGalleryBtn) {
      this.openGalleryBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.renderAvatarGallery();
        this.galleryModal.classList.remove('hidden');
        if (this.gallerySearch) {
          this.gallerySearch.value = '';
          this.gallerySearch.focus();
        }
      });
    }
    if (this.closeGalleryBtn) {
      this.closeGalleryBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.galleryModal.classList.add('hidden');
      });
    }
    if (this.gallerySearch) {
      this.gallerySearch.addEventListener('input', (e) => {
        this.renderAvatarGallery(e.target.value.trim());
      });
    }
    if (this.galleryModal) {
      this.galleryModal.addEventListener('click', (e) => {
        if (e.target === this.galleryModal) {
          this.galleryModal.classList.add('hidden');
        }
      });
    }

    // Fullscreen & Mobile Ratio
    const fsBtn = document.getElementById('fullscreen-btn');
    if (fsBtn) {
      fsBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.toggleFullscreen();
      });
    }

    if (this.ratioToggleBtn) {
      this.ratioToggleBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.toggleRatioMode();
      });
    }

    if (this.rotateFullscreenBtn) {
      this.rotateFullscreenBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.toggleFullscreen(true);
        if (this.orientationOverlay) this.orientationOverlay.classList.add('hidden');
      });
    }

    // Mobile Orientation & Canvas Resize Watcher
    const handleResize = () => {
      const isMobile = window.innerWidth <= 1024;
      const isPortrait = window.innerHeight > window.innerWidth;
      if (this.orientationOverlay) {
        if (isMobile && isPortrait) {
          this.orientationOverlay.classList.remove('hidden');
        } else {
          this.orientationOverlay.classList.add('hidden');
        }
      }
      if (this.spinePlayer && this.spinePlayer.sceneRenderer) {
        try { this.spinePlayer.sceneRenderer.resize(spine.webgl.ResizeMode.Expand); } catch (e) {}
      }
    };
    window.addEventListener('resize', handleResize);
    window.addEventListener('orientationchange', () => setTimeout(handleResize, 200));
    handleResize();

    // iOS Guide Modal
    if (this.closeIosGuideBtn) {
      this.closeIosGuideBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.iosGuideModal.classList.add('hidden');
      });
    }
    if (this.iosGuideOkBtn) {
      this.iosGuideOkBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.iosGuideModal.classList.add('hidden');
        this.toggleRatioMode(true);
      });
    }
    if (this.iosGuideModal) {
      this.iosGuideModal.addEventListener('click', (e) => {
        if (e.target === this.iosGuideModal) {
          this.iosGuideModal.classList.add('hidden');
        }
      });
    }

    // Keyboard Hotkeys
    window.addEventListener('keydown', (e) => {
      if (e.target.tagName === 'INPUT') return;
      this.unlockAudio();
      
      if (e.code === 'Space' || e.code === 'Enter') {
        e.preventDefault();
        if (this.isUIHidden) {
          this.setUIHidden(false);
        } else {
          this.advanceDialogue();
        }
      } else if (e.code === 'KeyH') {
        this.setUIHidden(!this.isUIHidden);
      } else if (e.code === 'KeyA') {
        this.toggleAutoPlay();
      } else if (e.code === 'KeyM') {
        this.toggleAudio();
      } else if (e.code === 'KeyL') {
        this.logModal.classList.toggle('hidden');
      } else if (e.code === 'Escape') {
        this.settingsModal.classList.add('hidden');
        this.logModal.classList.add('hidden');
        if (this.galleryModal) this.galleryModal.classList.add('hidden');
        this.sidebar.classList.remove('open');
        this.setUIHidden(false);
      }
    });

    // When voice audio ends
    this.voiceAudio.addEventListener('ended', () => {
      if (this.isAutoPlay) {
        clearTimeout(this.autoTimer);
        this.autoTimer = setTimeout(() => {
          this.advanceDialogue();
        }, this.autoDelay);
      }
    });
  }

  unlockAudio() {
    if (!this.audioUnlocked) {
      this.audioUnlocked = true;
      if (this.startOverlay) {
        this.startOverlay.classList.add('hidden');
      }
      if (window.innerWidth <= 1024 && screen.orientation && screen.orientation.lock) {
        screen.orientation.lock('landscape').catch(() => {});
      }
      this.updateAudioButtonState(true);
      this.playBGM();
      this.playCurrentVoice();
    }
  }

  toggleFullscreen(forceLandscape = false) {
    const el = document.documentElement;
    const isFs = !!(document.fullscreenElement || document.webkitFullscreenElement || document.mozFullScreenElement || document.msFullscreenElement);
    const rfs = el.requestFullscreen || el.webkitRequestFullscreen || el.mozRequestFullScreen || el.msRequestFullscreen;

    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
    const isStandalone = window.navigator.standalone === true || window.matchMedia('(display-mode: standalone)').matches;

    // On iPhone Safari, Apple strictly blocks HTML5 requestFullscreen on <div>/<html> elements.
    // If not running in standalone (PWA from home screen), show the user the native iOS tutorial and toggle fill-mode.
    if (isIOS && !isStandalone) {
      this.toggleRatioMode(true);
      if (this.iosGuideModal) {
        this.iosGuideModal.classList.remove('hidden');
      }
      return;
    }

    if (!isFs || forceLandscape) {
      if (rfs) {
        rfs.call(el).then(() => {
          if (screen.orientation && screen.orientation.lock) {
            screen.orientation.lock('landscape').catch(() => {});
          }
        }).catch(err => {
          console.warn('Fullscreen request failed:', err);
          this.toggleRatioMode(true);
        });
      } else {
        this.toggleRatioMode(true);
      }
    } else {
      const efs = document.exitFullscreen || document.webkitExitFullscreen || document.mozCancelFullScreen || document.msExitFullscreen;
      if (efs) {
        efs.call(document);
      }
    }
  }

  toggleRatioMode(forceFill = null) {
    if (forceFill !== null) {
      this.isFillMode = forceFill;
    } else {
      this.isFillMode = !this.isFillMode;
    }

    if (this.isFillMode) {
      this.stageContainer.classList.add('fill-mode');
      if (this.ratioToggleBtn) {
        this.ratioToggleBtn.textContent = '🔳 16:9';
        this.ratioToggleBtn.classList.add('active');
      }
    } else {
      this.stageContainer.classList.remove('fill-mode');
      if (this.ratioToggleBtn) {
        this.ratioToggleBtn.textContent = '🔲 滿版';
        this.ratioToggleBtn.classList.remove('active');
      }
    }

    if (this.spinePlayer && this.spinePlayer.sceneRenderer) {
      setTimeout(() => {
        try { this.spinePlayer.sceneRenderer.resize(spine.webgl.ResizeMode.Expand); } catch (e) {}
      }, 50);
    }
  }

  toggleAudio() {
    if (!this.audioUnlocked) {
      this.unlockAudio();
      return;
    }

    this.isMuted = !this.isMuted;
    if (this.isMuted) {
      this.bgmAudio.pause();
      this.voiceAudio.pause();
      this.updateAudioButtonState(false, true);
    } else {
      this.updateAudioButtonState(true, false);
      this.playBGM();
      this.playCurrentVoice();
    }
  }

  updateAudioButtonState(isPlaying, manualMute = false) {
    if (manualMute || this.isMuted) {
      this.audioToggleBtn.textContent = '🔇 已靜音 (點擊開啟)';
      this.audioToggleBtn.classList.add('muted');
    } else if (!isPlaying) {
      this.audioToggleBtn.textContent = '🔇 點擊啟用聲音';
      this.audioToggleBtn.classList.add('muted');
    } else {
      this.audioToggleBtn.textContent = '🔊 聲音正常';
      this.audioToggleBtn.classList.remove('muted');
    }
  }

  playBGM() {
    if (!this.audioUnlocked || this.isMuted) return;
    if (!this.currentChapterData || !this.currentChapterData.bgm_url) return;

    this.bgmAudio.volume = this.bgmVolume;
    this.bgmAudio.play().then(() => {
      this.updateAudioButtonState(true);
    }).catch(err => {
      console.log('BGM play blocked or waiting:', err);
      this.updateAudioButtonState(false);
    });
  }

  playCurrentVoice(force = false) {
    if (!this.currentChapterData) return;
    const d = this.currentChapterData.dialogues[this.dialogueIndex];

    if (d && d.voice) {
      this.replayVoiceBtn.style.display = 'inline-flex';
      this.replayVoiceBtn.innerHTML = '🔊 重播語音';
      this.replayVoiceBtn.disabled = false;

      if (!this.audioUnlocked || this.isMuted) return;

      try {
        this.voiceAudio.pause();
        this.voiceAudio.currentTime = 0;
      } catch (e) {}

      this.voiceAudio.src = d.voice;
      this.voiceAudio.volume = this.voiceVolume;
      const playPromise = this.voiceAudio.play();
      if (playPromise !== undefined) {
        playPromise.then(() => {
          this.updateAudioButtonState(true);
        }).catch(err => {
          if (err.name !== 'AbortError') {
            console.log('Voice play note:', err);
            if (!force) this.updateAudioButtonState(false);
          }
        });
      }
    } else {
      // Narration without voice
      this.replayVoiceBtn.style.display = 'inline-flex';
      this.replayVoiceBtn.innerHTML = '💭 旁白無語音';
      this.replayVoiceBtn.disabled = true;
      try {
        this.voiceAudio.pause();
        this.voiceAudio.currentTime = 0;
      } catch (e) {}
    }
  }

  async loadCharacterList() {
    try {
      const res = await fetch('/api/characters');
      this.allCharacters = await res.json();
      this.renderCharacterList();
      this.renderAvatarGallery();
      
      // Check query parameters
      const params = new URLSearchParams(window.location.search);
      const qChar = params.get('char');
      const qEp = parseInt(params.get('ep') || '2');

      if (params.get('autostart') === '1') {
        this.unlockAudio();
      }

      if (qChar) {
        // Direct link to specific character: hide gallery and load immediately
        this.galleryModal.classList.add('hidden');
        this.loadChapter(qChar, qEp);
      } else {
        // Default startup: Show Character Avatar Gallery Lobby!
        this.galleryModal.classList.remove('hidden');
        this.currentTitle.textContent = '🌸 請選擇欲播放的角色';
        if (this.startOverlay) {
          this.startOverlay.classList.add('hidden');
        }
      }
    } catch (e) {
      console.error('Failed to load characters:', e);
      this.currentTitle.textContent = '無法連線至伺服器';
    }
  }

  renderCharacterList(filterText = '') {
    this.charList.innerHTML = '';
    const filtered = this.allCharacters.filter(c => 
      !filterText || c.name.toLowerCase().includes(filterText.toLowerCase()) || c.id.toLowerCase().includes(filterText.toLowerCase())
    );

    filtered.forEach(c => {
      const item = document.createElement('div');
      item.className = 'char-item';
      
      // Avatar thumbnail
      const avatarImg = document.createElement('img');
      avatarImg.className = 'char-avatar-mini';
      avatarImg.src = c.avatar || '/assets/default_avatar.png';
      avatarImg.alt = c.name;
      avatarImg.loading = 'lazy';
      avatarImg.onerror = () => { avatarImg.src = '/assets/default_avatar.png'; };
      item.appendChild(avatarImg);

      const infoWrap = document.createElement('div');
      infoWrap.className = 'char-info';

      const nameEl = document.createElement('div');
      nameEl.className = 'char-name';
      nameEl.textContent = c.name;
      infoWrap.appendChild(nameEl);

      const badgesEl = document.createElement('div');
      badgesEl.className = 'char-badges';
      c.chapters.forEach(ep => {
        const badge = document.createElement('span');
        badge.className = 'chapter-badge';
        badge.textContent = `第 ${ep} 章`;
        badge.addEventListener('click', (e) => {
          e.stopPropagation();
          this.sidebar.classList.remove('open');
          this.loadChapter(c.id, ep);
        });
        badgesEl.appendChild(badge);
      });
      infoWrap.appendChild(badgesEl);
      item.appendChild(infoWrap);

      // Clicking item loads first chapter
      item.addEventListener('click', () => {
        this.sidebar.classList.remove('open');
        this.loadChapter(c.id, c.chapters[0]);
      });

      this.charList.appendChild(item);
    });
  }

  renderAvatarGallery(filterText = '') {
    if (!this.galleryGrid) return;
    this.galleryGrid.innerHTML = '';

    const filtered = this.allCharacters.filter(c => 
      !filterText || c.name.toLowerCase().includes(filterText.toLowerCase()) || c.id.toLowerCase().includes(filterText.toLowerCase())
    );

    if (this.galleryCount) {
      this.galleryCount.textContent = `共 ${filtered.length} 位角色`;
    }

    if (filtered.length === 0) {
      this.galleryGrid.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; color: #8892b0; padding: 40px 0; font-size: 15px;">沒有找到符合「${filterText}」的角色</div>`;
      return;
    }

    filtered.forEach(c => {
      const card = document.createElement('div');
      card.className = 'gallery-card';
      card.title = `${c.name} (${c.chapters.map(ep => `第${ep}章`).join(', ')})`;

      const avatarWrap = document.createElement('div');
      avatarWrap.className = 'gallery-avatar-wrap';

      const img = document.createElement('img');
      img.className = 'gallery-avatar-img';
      img.src = c.avatar || '/assets/default_avatar.png';
      img.alt = c.name;
      img.loading = 'lazy';
      img.onerror = () => { img.src = '/assets/default_avatar.png'; };
      avatarWrap.appendChild(img);
      card.appendChild(avatarWrap);

      const nameEl = document.createElement('div');
      nameEl.className = 'gallery-char-name';
      nameEl.textContent = c.name;
      card.appendChild(nameEl);

      const badgesWrap = document.createElement('div');
      badgesWrap.className = 'gallery-badges';
      c.chapters.forEach(ep => {
        const badge = document.createElement('span');
        badge.className = 'gallery-chapter-badge';
        badge.textContent = `第${ep}章`;
        badge.addEventListener('click', (e) => {
          e.stopPropagation();
          this.unlockAudio();
          this.galleryModal.classList.add('hidden');
          this.loadChapter(c.id, ep);
        });
        badgesWrap.appendChild(badge);
      });
      card.appendChild(badgesWrap);

      card.addEventListener('click', () => {
        this.unlockAudio();
        this.galleryModal.classList.add('hidden');
        this.loadChapter(c.id, c.chapters[0]);
      });

      this.galleryGrid.appendChild(card);
    });
  }

  async loadChapter(cid, ep) {
    this.currentTitle.textContent = '載入劇情資料中...';
    clearTimeout(this.autoTimer);
    clearTimeout(this.voiceDelayTimer);
    try {
      this.voiceAudio.pause();
      this.voiceAudio.currentTime = 0;
    } catch (e) {}
    
    // 1. Immediately reset playback settings and clear media from previous character
    this.setLoopMode('story');
    this.stageVideo.pause();
    this.stageVideo.removeAttribute('src');
    this.stageVideo.load();
    this.stageVideo.classList.add('hidden');
    this.stillImage.classList.add('hidden');
    this.bgImage.src = '';
    this.phaseBar.innerHTML = '';
    this.speakerTag.textContent = '';
    this.dialogueText.textContent = '正在載入角色素材與章節劇情，請稍候...';
    this.currentPhaseIndex = -1;
    this.hideStanding();
    if (this.spinePlayer) {
      try { this.spinePlayer.dispose(); } catch (e) {}
      this.spinePlayer = null;
    }
    if (this.spineContainer) {
      this.spineContainer.innerHTML = '';
    }
    this.currentSpineCharId = null;

    try {
      const res = await fetch(`/api/chapter?char=${cid}&ep=${ep}`);
      this.currentChapterData = await res.json();
      this.dialogueIndex = 0;
      
      const charName = this.currentChapterData.character_name;
      this.currentTitle.textContent = `${charName} - 第 ${ep} 章`;

      // Set BGM source (only re-assign if changed to avoid audio cut/stutter)
      if (this.currentChapterData.bgm_url) {
        const targetBgm = this.currentChapterData.bgm_url;
        if (!this.bgmAudio.src || !this.bgmAudio.src.endsWith(targetBgm)) {
          this.bgmAudio.src = targetBgm;
          this.playBGM();
        } else if (this.bgmAudio.paused) {
          this.playBGM();
        }
      }

      // Set Background
      if (this.currentChapterData.bg_url) {
        this.bgImage.src = this.currentChapterData.bg_url;
      }

      // Render Phase quick jump bar
      this.renderPhaseBar();

      // Force render initial phase (force = true)
      const initialPhase = (this.currentChapterData.dialogues[0] && this.currentChapterData.dialogues[0].phase_idx !== undefined)
        ? this.currentChapterData.dialogues[0].phase_idx
        : 0;
      this.setPhase(initialPhase, false, true);

      // Render current dialogue
      this.renderCurrentDialogue();
    } catch (e) {
      console.error('Failed to load chapter data:', e);
      this.currentTitle.textContent = '載入章節失敗';
      this.dialogueText.textContent = '載入失敗，請檢查伺服器連線或重新整理頁面。';
    }
  }

  renderPhaseBar() {
    this.phaseBar.innerHTML = '';
    if (!this.currentChapterData || !this.currentChapterData.phases) return;

    this.currentChapterData.phases.forEach((p, idx) => {
      const chip = document.createElement('button');
      chip.className = `phase-chip ${idx === this.currentPhaseIndex ? 'active' : ''}`;
      chip.textContent = p.name;
      chip.addEventListener('click', (e) => {
        e.stopPropagation();
        this.unlockAudio();
        this.jumpToPhase(idx);
      });
      this.phaseBar.appendChild(chip);
    });
  }

  jumpToPhase(phaseIdx) {
    if (!this.currentChapterData || !this.currentChapterData.phases || !this.currentChapterData.phases[phaseIdx]) return;

    // 1. 切換視覺畫面 (動畫/插圖/立繪)，保持為劇情同步模式
    this.setPhase(phaseIdx, false, true);

    // 2. 自動尋找並同步至該段落的第一句對白與語音
    if (this.currentChapterData.dialogues && this.currentChapterData.dialogues.length) {
      let targetIdx = this.currentChapterData.dialogues.findIndex(d => d.phase_idx === phaseIdx);
      if (targetIdx === -1) {
        // 若該段落無專屬對白 (如純高潮過場)，跳至最接近的後續對白
        for (let i = 0; i < this.currentChapterData.dialogues.length; i++) {
          if (this.currentChapterData.dialogues[i].phase_idx >= phaseIdx) {
            targetIdx = i;
            break;
          }
        }
      }

      if (targetIdx !== -1) {
        this.dialogueIndex = targetIdx;
        this.renderCurrentDialogue();
      }
    }
  }

  setPhase(phaseIdx, lockLoop = false, force = false) {
    if (!this.currentChapterData || !this.currentChapterData.phases || !this.currentChapterData.phases[phaseIdx]) return;
    if (!force && phaseIdx === this.currentPhaseIndex && !lockLoop) return;

    this.currentPhaseIndex = phaseIdx;
    const phase = this.currentChapterData.phases[phaseIdx];

    // Update active chip
    const chips = this.phaseBar.querySelectorAll('.phase-chip');
    chips.forEach((c, i) => c.classList.toggle('active', i === phaseIdx));

    if (phase.type === 'video') {
      this.hideStanding();
      this.stillImage.classList.add('hidden');
      this.stageVideo.classList.remove('hidden');
      if (this.stageVideo.src !== phase.url && !this.stageVideo.src.endsWith(phase.url)) {
        this.stageVideo.src = phase.url;
      }
      this.stageVideo.currentTime = 0;
      this.stageVideo.play().catch(e => console.log('Video autoplay error:', e));
    } else if (phase.type === 'image') {
      this.hideStanding();
      this.stageVideo.pause();
      this.stageVideo.removeAttribute('src');
      this.stageVideo.load();
      this.stageVideo.classList.add('hidden');
      this.stillImage.classList.remove('hidden');
      this.stillImage.src = phase.url;
    } else { // 'bg' (background only - Phase 0 with Standing Illustration)
      this.stageVideo.pause();
      this.stageVideo.removeAttribute('src');
      this.stageVideo.load();
      this.stageVideo.classList.add('hidden');
      this.stillImage.classList.add('hidden');
      if (phase.url) {
        this.bgImage.src = phase.url;
      }
      this.showStanding();
    }

    if (lockLoop) {
      this.setLoopMode('infinite');
    }
  }

  updatePhaseForCurrentDialogue() {
    if (this.loopMode === 'infinite') return; // in infinite mode, do not auto-switch phase
    if (!this.currentChapterData || !this.currentChapterData.dialogues.length) return;

    const d = this.currentChapterData.dialogues[this.dialogueIndex];
    if (d && d.phase_idx !== undefined && d.phase_idx !== this.currentPhaseIndex) {
      this.setPhase(d.phase_idx, false, false);
    }
  }

  renderCurrentDialogue() {
    if (!this.currentChapterData || !this.currentChapterData.dialogues.length) {
      this.speakerTag.textContent = '';
      this.dialogueText.textContent = '此章節無對白數據';
      return;
    }

    const d = this.currentChapterData.dialogues[this.dialogueIndex];
    if (d.speaker) {
      this.speakerTag.textContent = `【${d.speaker}】`;
    } else {
      this.speakerTag.textContent = '【旁白】';
    }

    // Trigger visual dialogue update with subtitle animation refresh
    this.dialogueText.textContent = d.text;
    this.dialogueText.style.animation = 'none';
    void this.dialogueText.offsetHeight;
    this.dialogueText.style.animation = '';

    // Clear any pending voice play
    clearTimeout(this.voiceDelayTimer);
    try {
      this.voiceAudio.pause();
      this.voiceAudio.currentTime = 0;
    } catch (e) {}

    // Synchronize voice onset delay with dialogue text
    if (d.voice) {
      this.replayVoiceBtn.style.display = 'inline-flex';
      this.replayVoiceBtn.innerHTML = '🔊 重播語音';
      this.replayVoiceBtn.disabled = false;
      this.voiceDelayTimer = setTimeout(() => {
        this.playCurrentVoice();
      }, this.voiceDelay);
    } else {
      this.playCurrentVoice();
    }

    this.updateStandingAnimationForDialogue(d);

    // Auto play timing
    if (this.isAutoPlay) {
      clearTimeout(this.autoTimer);
      if (!d.voice) {
        // Line without voice: calculate reading delay based on text length
        const readingMs = Math.max(2200, d.text.length * 140) + this.autoDelay;
        this.autoTimer = setTimeout(() => {
          this.advanceDialogue();
        }, readingMs);
      }
    }
  }

  advanceDialogue() {
    if (!this.currentChapterData || !this.currentChapterData.dialogues.length) return;
    clearTimeout(this.autoTimer);
    clearTimeout(this.voiceDelayTimer);

    if (this.dialogueIndex < this.currentChapterData.dialogues.length - 1) {
      this.dialogueIndex++;
      this.updatePhaseForCurrentDialogue();
      this.renderCurrentDialogue();
    } else {
      // Reached the end of chapter
      if (this.isAutoPlay) {
        this.toggleAutoPlay(false);
      }
      this.dialogueText.textContent = '── 本章劇情結束 ──';
      this.speakerTag.textContent = '';
      this.replayVoiceBtn.style.display = 'none';
    }
  }

  toggleAutoPlay(forceState = null) {
    this.isAutoPlay = forceState !== null ? forceState : !this.isAutoPlay;
    this.autoBtn.classList.toggle('active', this.isAutoPlay);
    this.autoBtn.textContent = this.isAutoPlay ? '⏸ 自動播放中' : '▶ 自動播放';

    if (this.isAutoPlay) {
      this.advanceDialogue();
    } else {
      clearTimeout(this.autoTimer);
    }
  }

  setLoopMode(mode) {
    this.loopMode = mode;
    this.loopModeBtn.textContent = mode === 'story' ? '🔄 劇情同步' : '♾️ 動作鎖定';
    this.loopModeBtn.classList.toggle('active', mode === 'infinite');
    document.getElementById('loop-mode-select').value = mode;

    if (mode === 'story' && this.currentChapterData && this.currentChapterData.dialogues.length) {
      const d = this.currentChapterData.dialogues[this.dialogueIndex];
      if (d && d.phase_idx !== undefined) {
        this.setPhase(d.phase_idx, false, true);
      }
    }
  }

  toggleLoopMode() {
    this.setLoopMode(this.loopMode === 'story' ? 'infinite' : 'story');
  }

  setUIHidden(hidden) {
    this.isUIHidden = hidden;
    this.stageContainer.classList.toggle('ui-hidden', hidden);
  }

  renderLog() {
    this.logList.innerHTML = '';
    if (!this.currentChapterData) return;

    for (let i = 0; i <= this.dialogueIndex; i++) {
      const d = this.currentChapterData.dialogues[i];
      const entry = document.createElement('div');
      entry.className = 'log-entry';

      const spk = document.createElement('div');
      spk.className = 'log-speaker';
      spk.textContent = d.speaker ? `【${d.speaker}】` : '【旁白】';
      entry.appendChild(spk);

      const txt = document.createElement('div');
      txt.className = 'log-text';
      txt.textContent = d.text;
      entry.appendChild(txt);

      this.logList.appendChild(entry);
    }

    // Scroll to bottom
    this.logList.scrollTop = this.logList.scrollHeight;
  }

  showStanding() {
    if (!this.currentChapterData || !this.currentChapterData.standing) {
      this.hideStanding();
      return;
    }
    const standing = this.currentChapterData.standing;

    // 1. Ensure standing layer is visible and force browser layout reflow
    if (this.standingLayer) {
      this.standingLayer.classList.remove('hidden');
      void this.standingLayer.offsetWidth; // Force synchronous layout reflow so clientWidth/Height are non-zero!
    }
    if (this.standingAnimWrap) {
      this.standingAnimWrap.classList.toggle('hidden', !standing.has_standing);
    }

    // Immediate preview: show fallback image first so screen is never blank while Spine loads
    if (this.staticStandingFallback) {
      const fallbackUrl = (standing.fallback_img && !standing.fallback_img.includes('/standing/'))
        ? standing.fallback_img
        : `/cache/avatars/${standing.character_id || this.currentChapterData.char_id}.png`;
      this.staticStandingFallback.src = fallbackUrl;
      this.staticStandingFallback.classList.remove('hidden');
    }

    // 2. Static Fallback for characters without Spine 2D model
    if (!standing.has_standing) {
      if (this.spinePlayer) {
        try { this.spinePlayer.dispose(); } catch (e) {}
        this.spinePlayer = null;
      }
      if (this.spineContainer) this.spineContainer.innerHTML = '';
      return;
    }

    // If Spine player is already running for this character, unpause, resize and resume
    if (this.spinePlayer && this.currentSpineCharId === standing.character_id) {
      try {
        this.spinePlayer.paused = false;
        this.spinePlayer.play();
        if (this.spinePlayer.sceneRenderer) {
          this.spinePlayer.sceneRenderer.resize(spine.webgl.ResizeMode.Expand);
        }
      } catch (e) {}
      if (this.staticStandingFallback) {
        this.staticStandingFallback.classList.add('hidden');
      }
      return;
    }

    // Initialize Spine player for character
    if (this.spineContainer) this.spineContainer.innerHTML = '';
    this.spinePlayer = null;
    this.currentSpineCharId = standing.character_id;

    const animLabels = {
      'st_01_standard': '標準待機',
      'st_02_normal': '日常微笑',
      'st_03_smile': '開懷燦笑',
      'st_04_anger': '生氣鼓嘴',
      'st_05_sad': '難過悲傷',
      'st_06_shy': '害羞臉紅',
      'st_07_surprise': '驚訝吃驚',
      'st_08_stop': '制止緊張',
      'st_09_sp01': '特殊表情 1',
      'st_10_sp02': '特殊表情 2',
      'st_11_sp03': '特殊表情 3',
      'st_12_sp04': '特殊表情 4',
      'st_13_sp05': '特殊表情 5'
    };

    if (this.standingAnimSelect) {
      this.standingAnimSelect.innerHTML = '';
      
      // Auto emotion option
      const autoOpt = document.createElement('option');
      autoOpt.value = 'auto';
      autoOpt.textContent = '✨ 自動情緒感應';
      this.standingAnimSelect.appendChild(autoOpt);

      (standing.animations || []).forEach(anim => {
        const opt = document.createElement('option');
        opt.value = anim;
        opt.textContent = animLabels[anim] || anim.replace('st_', '');
        this.standingAnimSelect.appendChild(opt);
      });

      this.standingAnimSelect.value = 'auto';
      this.isManualStandingAnim = false;
    }

    const defaultAnim = standing.default_anim || (standing.animations && standing.animations[0]) || 'st_01_standard';
    this.currentStandingAnim = defaultAnim;

    try {
      if (typeof spine !== 'undefined' && spine.SpinePlayer) {
        // Run in requestAnimationFrame to ensure DOM layout dimensions are fully computed
        requestAnimationFrame(() => {
          if (this.currentPhaseIndex !== 0 || !this.currentChapterData) return;
          this.spinePlayer = new spine.SpinePlayer(this.spineContainer, {
            skelUrl: standing.skel,
            atlasUrl: standing.atlas,
            animation: defaultAnim,
            alpha: true,
            backgroundColor: "#00000000",
            showControls: false,
            success: (player) => {
              this.spinePlayer = player;
              player.paused = false;
              try { player.play(); } catch (e) {}
              if (player.canvas) {
                player.canvas.style.display = 'block';
                player.canvas.style.width = '100%';
                player.canvas.style.height = '100%';
              }
              if (player.sceneRenderer) {
                try { player.sceneRenderer.resize(spine.webgl.ResizeMode.Expand); } catch (e) {}
              }
              // Hide static fallback once Spine dynamic model is loaded and rendering
              if (this.staticStandingFallback) {
                this.staticStandingFallback.classList.add('hidden');
              }
              // Synchronize animation with current active dialogue
              const d = this.currentChapterData && this.currentChapterData.dialogues && this.currentChapterData.dialogues[this.dialogueIndex];
              if (d) {
                this.updateStandingAnimationForDialogue(d);
              } else {
                this.setStandingAnimation(defaultAnim);
              }
              console.log(`[Spine] Initialized and animating standing for ${standing.character_id}`);
            },
            error: (player, msg) => {
              console.error(`[Spine] Standing load error:`, msg);
              if (this.spineContainer) this.spineContainer.innerHTML = '';
              if (this.staticStandingFallback) {
                const fallbackUrl = (standing.fallback_img && !standing.fallback_img.includes('/standing/'))
                  ? standing.fallback_img
                  : `/cache/avatars/${standing.character_id || this.currentChapterData.char_id}.png`;
                this.staticStandingFallback.src = fallbackUrl;
                this.staticStandingFallback.classList.remove('hidden');
              }
            }
          });
        });
      }
    } catch (e) {
      console.error('[Spine] Exception creating SpinePlayer:', e);
      if (this.spineContainer) this.spineContainer.innerHTML = '';
      if (this.staticStandingFallback) {
        const fallbackUrl = standing.fallback_img || `/cache/avatars/${standing.character_id || this.currentChapterData.char_id}.png`;
        this.staticStandingFallback.src = fallbackUrl;
        this.staticStandingFallback.classList.remove('hidden');
      }
    }
  }

  hideStanding() {
    if (this.standingLayer) {
      this.standingLayer.classList.add('hidden');
    }
    if (this.standingAnimWrap) {
      this.standingAnimWrap.classList.add('hidden');
    }
    if (this.staticStandingFallback) {
      this.staticStandingFallback.classList.add('hidden');
    }
    if (this.spinePlayer) {
      try {
        this.spinePlayer.pause();
      } catch (e) {}
    }
  }

  setStandingAnimation(anim) {
    if (!this.spinePlayer) return;
    this.currentStandingAnim = anim;
    if (this.standingAnimSelect && this.standingAnimSelect.value !== anim && this.isManualStandingAnim) {
      this.standingAnimSelect.value = anim;
    }
    // If skeleton/animationState is not yet ready, store requested animation in config so it will be used when loaded
    if (!this.spinePlayer.animationState || !this.spinePlayer.skeleton) {
      this.spinePlayer.config.animation = anim;
      return;
    }
    try {
      if (typeof this.spinePlayer.setAnimation === 'function') {
        this.spinePlayer.setAnimation(anim, true);
      } else {
        this.spinePlayer.animationState.setAnimation(0, anim, true);
      }
      this.spinePlayer.paused = false;
      try { this.spinePlayer.play(); } catch (e) {}
    } catch (err) {
      console.warn('setStandingAnimation error:', err);
    }
  }

  updateStandingAnimationForDialogue(dialogue) {
    if (!this.spinePlayer || this.currentPhaseIndex !== 0) return;
    if (this.isManualStandingAnim) return; // Locked to manual expression
    if (!dialogue) return;

    let targetAnim = null;
    const txt = dialogue.text || '';

    if (/害羞|臉紅|討厭|心跳|可愛|唔|嗚|咬|喘|呀/.test(txt)) {
      targetAnim = 'st_06_shy';
    } else if (/笑|開心|高興|♪|呼呼|太好了|喜歡|哈|呵呵/.test(txt)) {
      targetAnim = 'st_03_smile';
    } else if (/！？|？！|咦|啊！|什麼|驚|欸/.test(txt)) {
      targetAnim = 'st_07_surprise';
    } else if (/難過|悲傷|對不起|抱歉|寂寞|哭/.test(txt)) {
      targetAnim = 'st_05_sad';
    } else if (/生氣|怒|哼|不可原諒/.test(txt)) {
      targetAnim = 'st_04_anger';
    } else {
      targetAnim = (this.currentChapterData && this.currentChapterData.standing && this.currentChapterData.standing.default_anim) || 'st_01_standard';
    }

    const available = (this.currentChapterData && this.currentChapterData.standing && this.currentChapterData.standing.animations) || [];
    if (available.length > 0 && !available.includes(targetAnim)) {
      targetAnim = available.includes('st_01_standard') ? 'st_01_standard' : available[0];
    }

    this.setStandingAnimation(targetAnim);
  }

  showToast(message, duration = 3000) {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = 'toast-bubble';
    toast.textContent = message;
    container.appendChild(toast);
    
    requestAnimationFrame(() => toast.classList.add('show'));

    setTimeout(() => {
      toast.classList.remove('show');
      setTimeout(() => {
        if (toast.parentNode) toast.parentNode.removeChild(toast);
      }, 400);
    }, duration);
  }

  async rebuildCurrentStanding(charId = null, clearType = 'standing') {
    const cid = charId || (this.currentChapterData && this.currentChapterData.char_id) || this.currentSpineCharId;
    if (!cid) {
      this.showToast('⚠️ 未載入角色，無法重建快取');
      return;
    }

    const btn1 = document.getElementById('rebuild-standing-btn');
    const btn2 = document.getElementById('clear-char-cache-btn');
    const orig1 = btn1 ? btn1.innerHTML : '';
    const orig2 = btn2 ? btn2.innerHTML : '';
    if (btn1) { btn1.innerHTML = '⏳ 重建中...'; btn1.disabled = true; }
    if (btn2) { btn2.innerHTML = '⏳ 重建中...'; btn2.disabled = true; }

    const charName = (this.currentChapterData && this.currentChapterData.char_name) || cid;
    this.showToast(`⏳ 正在重構【${charName}】的立繪快取...`, 2000);

    try {
      const resp = await fetch(`/api/clear_cache?char=${encodeURIComponent(cid)}&type=${clearType}&t=${Date.now()}`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();

      if (data.standing && this.currentChapterData) {
        // Append cache-busting timestamp so browser does not load stale binary from memory
        const bustTime = Date.now();
        data.standing.skel = data.standing.skel + '?t=' + bustTime;
        data.standing.atlas = data.standing.atlas + '?t=' + bustTime;
        this.currentChapterData.standing = data.standing;
      }

      // Dispose existing spine player to reload freshly
      if (this.spinePlayer) {
        try { this.spinePlayer.dispose(); } catch (e) {}
        this.spinePlayer = null;
      }
      this.currentSpineCharId = null;

      // Re-trigger standing initialization
      if (this.currentChapterData && this.currentChapterData.standing) {
        this.showStanding();
      }

      this.showToast(`✨ 【${charName}】立繪快取已重構完成！`);
    } catch (err) {
      console.error('[Cache] Rebuild failed:', err);
      this.showToast(`❌ 快取重構失敗: ${err.message}`);
    } finally {
      if (btn1) { btn1.innerHTML = orig1; btn1.disabled = false; }
      if (btn2) { btn2.innerHTML = orig2; btn2.disabled = false; }
    }
  }

  async clearAllStandingCache() {
    if (!confirm('確定要重建所有角色的立繪快取嗎？\n\n（遊戲原檔 resources 完整保留，各角色將於切換時自動重新解碼）')) {
      return;
    }
    const btn = document.getElementById('clear-all-standing-btn');
    const orig = btn ? btn.innerHTML : '';
    if (btn) { btn.innerHTML = '⏳ 清理中...'; btn.disabled = true; }

    try {
      const resp = await fetch(`/api/clear_cache?char=all&type=standing&t=${Date.now()}`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      this.showToast('✨ 已重置全角色立繪快取！');
      
      // Reload current character standing if active
      if (this.currentChapterData && this.currentChapterData.char_id) {
        await this.rebuildCurrentStanding(this.currentChapterData.char_id);
      }
    } catch (err) {
      console.error('[Cache] Clear all failed:', err);
      this.showToast(`❌ 清理失敗: ${err.message}`);
    } finally {
      if (btn) { btn.innerHTML = orig; btn.disabled = false; }
    }
  }
}

// Start player when page loads
window.addEventListener('DOMContentLoaded', () => {
  window.player = new LegecloPlayer();
});
