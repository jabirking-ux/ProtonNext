// ==========================================================================
// Proton VPN Next — 3-Beat Scrollytelling Splash Intro + Official Site UI
// Beat 1 (0.00 -> 0.42): welcome-unlimited.png + "Redesigned."
// Beat 2 (0.32 -> 0.85): Rising redesign.png + What's New Trio
// Beat 3 (0.85 -> 1.00): Seamless transition into Main Download Hub
// ==========================================================================

(function () {
  'use strict';

  const header = document.getElementById('siteHeader');
  const stickyBar = document.getElementById('stickyDownloadBar');
  const introTrack = document.getElementById('introTrack');
  const introStagePrimary = document.getElementById('introStagePrimary');
  const introStageRedesign = document.getElementById('introStageRedesign');
  const introScrollCue = document.getElementById('introScrollCue');
  const navLinks = document.querySelectorAll('.nav-links a[href^="#"]');
  const sections = document.querySelectorAll('main section[id]');

  function clamp(val, min, max) {
    return Math.max(min, Math.min(max, val));
  }

  function updateScrollytelling() {
    const scrollY = window.scrollY || window.pageYOffset;
    const vh = window.innerHeight || 900;

    // 1. Multi-beat Scrollytelling Intro Track (0.0 -> 1.0 across pinned distance)
    if (introTrack && introStagePrimary) {
      const trackHeight = introTrack.offsetHeight - vh;
      const progress = trackHeight > 0 ? clamp(scrollY / trackHeight, 0, 1) : 1;

      // Beat 1: welcome-unlimited.png + "Redesigned." (Visible 0.0 -> 0.45)
      const beat1Progress = clamp(progress / 0.44, 0, 1);
      const stageScale = 1 + beat1Progress * 0.12;
      const stageTranslateY = -beat1Progress * 85;
      const stageOpacity = clamp(1 - Math.pow(beat1Progress, 1.35), 0, 1);
      const stageBlur = beat1Progress * 10;

      introStagePrimary.style.transform = `translate3d(0, ${stageTranslateY.toFixed(1)}px, 0) scale(${stageScale.toFixed(3)})`;
      introStagePrimary.style.opacity = stageOpacity.toFixed(3);
      introStagePrimary.style.filter = stageBlur > 0.25 ? `blur(${stageBlur.toFixed(1)}px)` : 'none';
      introStagePrimary.style.pointerEvents = stageOpacity < 0.15 ? 'none' : 'auto';

      // Beat 2: Rising redesign.png + What's New Trio (Rises 0.25 -> 0.55, Holds 0.55 -> 0.85, Fades into Main Site)
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

      // Fade out "Scroll to explore" cue right as scrolling begins
      if (introScrollCue) {
        const cueOpacity = clamp(1 - progress * 5.0, 0, 1);
        introScrollCue.style.opacity = cueOpacity.toFixed(3);
        introScrollCue.style.pointerEvents = cueOpacity < 0.1 ? 'none' : 'auto';
      }
    }

    // 2. Header solidifies once scrolling into the showcase
    const mainThreshold = vh * 0.55;
    if (header) {
      if (scrollY > mainThreshold) {
        header.classList.add('scrolled');
      } else {
        header.classList.remove('scrolled');
      }
    }

    // 3. Floating bottom download bar appears once inside the main site
    if (stickyBar) {
      if (scrollY > vh * 2.1) {
        stickyBar.classList.add('visible');
        stickyBar.setAttribute('aria-hidden', 'false');
      } else {
        stickyBar.classList.remove('visible');
        stickyBar.setAttribute('aria-hidden', 'true');
      }
    }

    // 4. Active navigation link tracking
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

  window.addEventListener('scroll', updateScrollytelling, { passive: true });
  window.addEventListener('resize', updateScrollytelling, { passive: true });
  updateScrollytelling();

  // Smooth reveal-on-scroll observer for main website sections
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

  // FAQ Accordion
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
