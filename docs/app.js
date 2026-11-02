// ==========================================================================
// Proton VPN Next - High-Fidelity Scrollytelling & Interactive Engine
// ==========================================================================

(function () {
  'use strict';

  // 1. Elements
  const header = document.getElementById('siteHeader');
  const stickyBar = document.getElementById('stickyDownloadBar');
  const scrollProgressBar = document.getElementById('scrollProgressBar');
  const introTrack = document.getElementById('introTrack');
  const introStagePrimary = document.getElementById('introStagePrimary');
  const introStageRedesign = document.getElementById('introStageRedesign');
  const introScrollCue = document.getElementById('introScrollCue');
  const introBeatsIndicator = document.getElementById('introBeatsIndicator');
  const beatButtons = document.querySelectorAll('.beat-dot-btn');
  const navLinks = document.querySelectorAll('.nav-links a[href^="#"]');
  const sections = document.querySelectorAll('main section[id]');
  const mobileToggle = document.getElementById('mobileMenuToggle');
  const mobileDrawer = document.getElementById('mobileNavDrawer');
  const mobileLinks = document.querySelectorAll('.mobile-nav-link');
  const copyHashBtn = document.getElementById('copyHashBtn');
  const checksumValue = document.getElementById('checksumValue');
  const backToTopBtn = document.getElementById('backToTopBtn');

  function clamp(val, min, max) {
    return Math.max(min, Math.min(max, val));
  }

  // 2. High-Performance Scrollytelling & Scroll Engine
  let isTicking = false;

  function onScroll() {
    if (!isTicking) {
      window.requestAnimationFrame(() => {
        updateScrollState();
        isTicking = false;
      });
      isTicking = true;
    }
  }

  function updateScrollState() {
    const scrollY = window.scrollY || window.pageYOffset;
    const vh = window.innerHeight || 900;
    const docHeight = document.documentElement.scrollHeight - vh;

    // Top Global Progress Bar
    if (scrollProgressBar && docHeight > 0) {
      const scrollPercent = clamp((scrollY / docHeight) * 100, 0, 100);
      scrollProgressBar.style.width = scrollPercent.toFixed(2) + '%';
    }

    // Multi-beat Scrollytelling Track (0.00 -> 1.00)
    if (introTrack && introStagePrimary) {
      const trackHeight = introTrack.offsetHeight - vh;
      const progress = trackHeight > 0 ? clamp(scrollY / trackHeight, 0, 1) : 1;

      // Beat 1: welcome-unlimited.png + "Redesigned." (0.00 -> 0.44)
      const beat1Progress = clamp(progress / 0.44, 0, 1);
      const stageScale = 1 + beat1Progress * 0.12;
      const stageTranslateY = -beat1Progress * 85;
      const stageOpacity = clamp(1 - Math.pow(beat1Progress, 1.35), 0, 1);
      const stageBlur = beat1Progress * 10;

      introStagePrimary.style.transform = `translate3d(0, ${stageTranslateY.toFixed(1)}px, 0) scale(${stageScale.toFixed(3)})`;
      introStagePrimary.style.opacity = stageOpacity.toFixed(3);
      introStagePrimary.style.filter = stageBlur > 0.25 ? `blur(${stageBlur.toFixed(1)}px)` : 'none';
      introStagePrimary.style.pointerEvents = stageOpacity < 0.15 ? 'none' : 'auto';

      // Beat 2: Rising redesign.png + What's New Trio (0.22 -> 0.82)
      if (introStageRedesign) {
        let redesignOpacity = 0;
        let redesignTranslateY = 90;
        let redesignScale = 0.9;

        if (progress >= 0.22) {
          const enterP = clamp((progress - 0.22) / 0.34, 0, 1);
          const exitP = clamp((progress - 0.82) / 0.18, 0, 1);
          redesignOpacity = enterP * (1 - exitP * 0.65);
          redesignTranslateY = (1 - enterP) * 95 - exitP * 35;
          redesignScale = 0.9 + enterP * 0.1;
        }

        introStageRedesign.style.opacity = redesignOpacity.toFixed(3);
        introStageRedesign.style.transform = `translate3d(0, ${redesignTranslateY.toFixed(1)}px, 0) scale(${redesignScale.toFixed(3)})`;
      }

      // Update Side Beat Indicator Dots
      let currentBeat = 0;
      if (progress > 0.65) currentBeat = 2;
      else if (progress > 0.25) currentBeat = 1;

      beatButtons.forEach((btn, idx) => {
        if (idx === currentBeat) {
          btn.classList.add('active');
        } else {
          btn.classList.remove('active');
        }
      });

      // Fade out "Scroll to explore" cue
      if (introScrollCue) {
        const cueOpacity = clamp(1 - progress * 5.0, 0, 1);
        introScrollCue.style.opacity = cueOpacity.toFixed(3);
        introScrollCue.style.pointerEvents = cueOpacity < 0.1 ? 'none' : 'auto';
      }
    }

    // Header Background Solidification
    const mainThreshold = vh * 0.55;
    if (header) {
      if (scrollY > mainThreshold) {
        header.classList.add('scrolled');
      } else {
        header.classList.remove('scrolled');
      }
    }

    // Floating Bottom Download Bar
    if (stickyBar) {
      if (scrollY > vh * 1.8) {
        stickyBar.classList.add('visible');
        stickyBar.setAttribute('aria-hidden', 'false');
      } else {
        stickyBar.classList.remove('visible');
        stickyBar.setAttribute('aria-hidden', 'true');
      }
    }

    // Active Navigation Link Tracking
    let currentId = 'overview';
    sections.forEach((sec) => {
      const rect = sec.getBoundingClientRect();
      if (rect.top <= 160) {
        currentId = sec.getAttribute('id');
      }
    });

    navLinks.forEach((link) => {
      const href = link.getAttribute('href').replace('#', '');
      if (href === currentId) {
        link.classList.add('active');
      } else {
        link.classList.remove('active');
      }
    });
  }

  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', onScroll, { passive: true });
  updateScrollState();

  // Beat Dots Click to Jump
  beatButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      const beat = parseInt(btn.getAttribute('data-beat'), 10);
      const vh = window.innerHeight || 900;
      if (!introTrack) return;
      const trackHeight = introTrack.offsetHeight - vh;
      let targetScroll = 0;
      if (beat === 1) targetScroll = trackHeight * 0.5;
      else if (beat === 2) targetScroll = trackHeight + 50;
      window.scrollTo({ top: targetScroll, behavior: 'smooth' });
    });
  });

  // Mobile Navigation Drawer Toggle
  if (mobileToggle && mobileDrawer) {
    mobileToggle.addEventListener('click', () => {
      const isOpen = mobileDrawer.classList.contains('open');
      if (isOpen) {
        mobileDrawer.classList.remove('open');
      } else {
        mobileDrawer.classList.add('open');
      }
    });

    mobileLinks.forEach((link) => {
      link.addEventListener('click', () => {
        mobileDrawer.classList.remove('open');
      });
    });
  }

  // Back to Top Button
  if (backToTopBtn) {
    backToTopBtn.addEventListener('click', () => {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  }

  // 3. Interactive NetShield Level Selector
  const netshieldButtons = document.querySelectorAll('.netshield-btn');
  const statAdsBlocked = document.getElementById('statAdsBlocked');
  const statTrackersStopped = document.getElementById('statTrackersStopped');
  const statDataSaved = document.getElementById('statDataSaved');

  const netshieldData = {
    0: { ads: '0', trackers: '0', data: '0 MB' },
    1: { ads: '4,120', trackers: '0', data: '32 MB' },
    2: { ads: '14,892', trackers: '3,410', data: '412 MB' }
  };

  function animateMetricNumber(el, targetText) {
    if (!el) return;
    el.style.transform = 'scale(1.15)';
    el.style.transition = 'transform 0.15s ease';
    setTimeout(() => {
      el.textContent = targetText;
      el.style.transform = 'scale(1)';
    }, 120);
  }

  netshieldButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      const level = btn.getAttribute('data-level');
      netshieldButtons.forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');

      const data = netshieldData[level] || netshieldData[2];
      animateMetricNumber(statAdsBlocked, data.ads);
      animateMetricNumber(statTrackersStopped, data.trackers);
      animateMetricNumber(statDataSaved, data.data);
    });
  });

  // 4. Interactive VPN Accelerator Speed Gauge
  const speedChips = document.querySelectorAll('.speed-mode-chip');
  const speedGaugeFill = document.getElementById('speedGaugeFill');
  const speedGaugeNumber = document.getElementById('speedGaugeNumber');
  const speedLatency = document.getElementById('speedLatency');
  const speedPacketLoss = document.getElementById('speedPacketLoss');
  const speedBoostLabel = document.getElementById('speedBoostLabel');

  speedChips.forEach((chip) => {
    chip.addEventListener('click', () => {
      const mode = chip.getAttribute('data-mode');
      speedChips.forEach((c) => c.classList.remove('active'));
      chip.classList.add('active');

      if (mode === 'off') {
        if (speedGaugeFill) speedGaugeFill.style.width = '24%';
        if (speedGaugeNumber) {
          speedGaugeNumber.textContent = '145 Mbps';
          speedGaugeNumber.style.color = '#FFFFFF';
        }
        if (speedLatency) speedLatency.textContent = '89 ms';
        if (speedPacketLoss) {
          speedPacketLoss.textContent = '1.8%';
          speedPacketLoss.style.color = 'var(--signal-warning)';
        }
        if (speedBoostLabel) {
          speedBoostLabel.textContent = 'Baseline';
          speedBoostLabel.style.color = 'var(--text-weak)';
        }
      } else {
        if (speedGaugeFill) speedGaugeFill.style.width = '92%';
        if (speedGaugeNumber) {
          speedGaugeNumber.textContent = '842 Mbps';
          speedGaugeNumber.style.color = 'var(--vpn-green)';
        }
        if (speedLatency) speedLatency.textContent = '24 ms';
        if (speedPacketLoss) {
          speedPacketLoss.textContent = '0.0%';
          speedPacketLoss.style.color = 'var(--vpn-green)';
        }
        if (speedBoostLabel) {
          speedBoostLabel.textContent = '+480%';
          speedBoostLabel.style.color = 'var(--primary)';
        }
      }
    });
  });

  // 5. Interactive Global Server Explorer & Search
  const regionTabButtons = document.querySelectorAll('.region-tab-btn');
  const serverSearchInput = document.getElementById('serverSearchInput');
  const countryCards = document.querySelectorAll('#countryCardsGrid .country-card');

  function filterServerCards() {
    const activeTab = document.querySelector('.region-tab-btn.active');
    const region = activeTab ? activeTab.getAttribute('data-region') : 'all';
    const query = serverSearchInput ? serverSearchInput.value.trim().toLowerCase() : '';

    countryCards.forEach((card) => {
      const cardRegion = card.getAttribute('data-region') || '';
      const cardCountry = card.getAttribute('data-country') || '';

      const matchesRegion = region === 'all' || cardRegion === region;
      const matchesQuery = query === '' || cardCountry.includes(query);

      if (matchesRegion && matchesQuery) {
        card.style.display = 'flex';
      } else {
        card.style.display = 'none';
      }
    });
  }

  regionTabButtons.forEach((tabBtn) => {
    tabBtn.addEventListener('click', () => {
      regionTabButtons.forEach((b) => b.classList.remove('active'));
      tabBtn.classList.add('active');
      filterServerCards();
    });
  });

  if (serverSearchInput) {
    serverSearchInput.addEventListener('input', filterServerCards);
  }

  // Server Card Click to simulate fast server hop
  countryCards.forEach((card) => {
    card.addEventListener('click', () => {
      const pingPill = card.querySelector('.country-ping-pill');
      if (pingPill) {
        const origText = pingPill.textContent;
        pingPill.textContent = 'Connecting...';
        pingPill.style.color = '#FFFFFF';
        setTimeout(() => {
          pingPill.textContent = origText;
          pingPill.style.color = 'var(--vpn-green)';
        }, 350);
      }
    });
  });

  // 6. SHA-256 Checksum One-Click Copy
  if (copyHashBtn && checksumValue) {
    copyHashBtn.addEventListener('click', () => {
      const hash = checksumValue.textContent.trim();
      navigator.clipboard.writeText(hash).then(() => {
        copyHashBtn.classList.add('copied');
        copyHashBtn.querySelector('span').textContent = 'Copied!';
        setTimeout(() => {
          copyHashBtn.classList.remove('copied');
          copyHashBtn.querySelector('span').textContent = 'Copy Hash';
        }, 2400);
      }).catch(() => {
        // Fallback for older browsers
        const textarea = document.createElement('textarea');
        textarea.value = hash;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
        copyHashBtn.classList.add('copied');
        copyHashBtn.querySelector('span').textContent = 'Copied!';
        setTimeout(() => {
          copyHashBtn.classList.remove('copied');
          copyHashBtn.querySelector('span').textContent = 'Copy Hash';
        }, 2400);
      });
    });
  }

  // 7. Reveal-On-Scroll Observer
  const revealEls = document.querySelectorAll('.reveal-on-scroll');
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('in-view');
          }
        });
      },
      { threshold: 0.12, rootMargin: '0px 0px -40px 0px' }
    );
    revealEls.forEach((el) => observer.observe(el));
  } else {
    revealEls.forEach((el) => el.classList.add('in-view'));
  }

  // 8. FAQ Accordion
  const faqItems = document.querySelectorAll('.faq-item');
  faqItems.forEach((item) => {
    const btn = item.querySelector('.faq-question');
    const answer = item.querySelector('.faq-answer');
    if (!btn || !answer) return;

    btn.addEventListener('click', () => {
      const isOpen = item.classList.contains('open');

      faqItems.forEach((other) => {
        other.classList.remove('open');
        const otherAns = other.querySelector('.faq-answer');
        if (otherAns) otherAns.style.maxHeight = null;
      });

      if (!isOpen) {
        item.classList.add('open');
        answer.style.maxHeight = answer.scrollHeight + 'px';
      }
    });
  });
})();
