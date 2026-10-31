// ==========================================================================
// Proton VPN Next — Scrollytelling Splash Intro + Official Site UI
// Stage 1 (0px): Full-viewport welcome-unlimited.png + "Redesigned."
// Stage 2 (Scroll): Smooth zoom/crossfade reveal into the main website
// ==========================================================================

(function () {
  'use strict';

  const header = document.getElementById('siteHeader');
  const stickyBar = document.getElementById('stickyDownloadBar');
  const introTrack = document.getElementById('introTrack');
  const introStagePrimary = document.getElementById('introStagePrimary');
  const introRisingPreview = document.getElementById('introRisingPreview');
  const introScrollCue = document.getElementById('introScrollCue');
  const navLinks = document.querySelectorAll('.nav-links a[href^="#"]');
  const sections = document.querySelectorAll('main section[id]');

  function clamp(val, min, max) {
    return Math.max(min, Math.min(max, val));
  }

  function updateScrollytelling() {
    const scrollY = window.scrollY || window.pageYOffset;
    const vh = window.innerHeight || 900;

    // 1. Scrollytelling Intro Track Progress (0.0 -> 1.0 across the pinned distance)
    if (introTrack && introStagePrimary) {
      const trackHeight = introTrack.offsetHeight - vh;
      const progress = trackHeight > 0 ? clamp(scrollY / trackHeight, 0, 1) : 1;

      // Primary stage (welcome-unlimited.png + "Redesigned.") scales and fades as you scroll down
      const stageScale = 1 + progress * 0.14;
      const stageTranslateY = -progress * 90;
      const stageOpacity = clamp(1 - progress * 1.45, 0, 1);
      const stageBlur = progress * 8;

      introStagePrimary.style.transform = `translate3d(0, ${stageTranslateY.toFixed(1)}px, 0) scale(${stageScale.toFixed(3)})`;
      introStagePrimary.style.opacity = stageOpacity.toFixed(3);
      introStagePrimary.style.filter = stageBlur > 0.2 ? `blur(${stageBlur.toFixed(1)}px)` : 'none';

      // Rising preview of redesign.png glides up during the middle of the scroll
      if (introRisingPreview) {
        const previewProgress = clamp((progress - 0.18) / 0.75, 0, 1);
        const previewOpacity = clamp(Math.sin(previewProgress * Math.PI) * 1.15, 0, 0.95);
        const previewTranslateY = (1 - previewProgress) * 140;
        const previewScale = 0.88 + previewProgress * 0.12;

        introRisingPreview.style.opacity = previewOpacity.toFixed(3);
        introRisingPreview.style.transform = `translate3d(-50%, ${previewTranslateY.toFixed(1)}px, 0) scale(${previewScale.toFixed(3)})`;
      }

      // Fade out the "Scroll to explore" cue right as the user starts scrolling
      if (introScrollCue) {
        const cueOpacity = clamp(1 - progress * 4.5, 0, 1);
        introScrollCue.style.opacity = cueOpacity.toFixed(3);
        introScrollCue.style.pointerEvents = cueOpacity < 0.1 ? 'none' : 'auto';
      }
    }

    // 2. Header solidifies once scrolling past the initial splash stage
    const mainThreshold = vh * 0.75;
    if (header) {
      if (scrollY > mainThreshold) {
        header.classList.add('scrolled');
      } else {
        header.classList.remove('scrolled');
      }
    }

    // 3. Floating bottom download bar appears once inside the main site
    if (stickyBar) {
      if (scrollY > vh * 1.65) {
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
