// ==========================================================================
// Proton VPN Next — Official Marketing Site UI Behavior
// Scroll header state, floating download bar, and FAQ accordion
// ==========================================================================

(function () {
  'use strict';

  const header = document.getElementById('siteHeader');
  const stickyBar = document.getElementById('stickyDownloadBar');
  const navLinks = document.querySelectorAll('.nav-links a[href^="#"]');
  const sections = document.querySelectorAll('main section[id]');

  function handleScroll() {
    const scrollY = window.scrollY || window.pageYOffset;

    if (header) {
      if (scrollY > 24) {
        header.classList.add('scrolled');
      } else {
        header.classList.remove('scrolled');
      }
    }

    if (stickyBar) {
      if (scrollY > 520) {
        stickyBar.classList.add('visible');
        stickyBar.setAttribute('aria-hidden', 'false');
      } else {
        stickyBar.classList.remove('visible');
        stickyBar.setAttribute('aria-hidden', 'true');
      }
    }

    // Active section highlight in top navigation
    let currentId = 'overview';
    sections.forEach((sec) => {
      const top = sec.offsetTop - 130;
      if (scrollY >= top) {
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

  window.addEventListener('scroll', handleScroll, { passive: true });
  handleScroll();

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
