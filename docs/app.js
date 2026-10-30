// ProtonNext Interactive Web Engine
document.addEventListener('DOMContentLoaded', () => {
  initLiveVpnCard();
  initFaqAccordion();
  initCliCopy();
  initServerGrid();
});

// Real Free Server Database for Interactive Simulation
const FREE_SERVERS = [
  { name: 'NL-FREE#102', country: 'Netherlands', flag: '🇳🇱', ip: '185.107.56.221', ping: 18, load: 38, region: 'eu' },
  { name: 'US-FREE#45', country: 'United States', flag: '🇺🇸', ip: '198.54.135.14', ping: 74, load: 42, region: 'na' },
  { name: 'JP-FREE#12', country: 'Japan', flag: '🇯🇵', ip: '103.125.234.8', ping: 142, load: 29, region: 'ap' },
  { name: 'RO-FREE#04', country: 'Romania', flag: '🇷🇴', ip: '185.225.17.65', ping: 35, load: 24, region: 'eu' },
  { name: 'SG-FREE#08', country: 'Singapore', flag: '🇸🇬', ip: '103.111.140.2', ping: 115, load: 31, region: 'ap' }
];

let currentIndex = 0;
let isConnected = true;

function initLiveVpnCard() {
  const btnToggle = document.getElementById('demo-toggle-btn');
  const btnRotate = document.getElementById('demo-rotate-btn');
  const badgeStatus = document.getElementById('demo-status-badge');
  const valServer = document.getElementById('demo-val-server');
  const valIp = document.getElementById('demo-val-ip');
  const valPing = document.getElementById('demo-val-ping');
  const valProtocol = document.getElementById('demo-val-protocol');

  function updateUi() {
    const s = FREE_SERVERS[currentIndex];
    if (isConnected) {
      badgeStatus.className = 'conn-status-badge status-connected';
      badgeStatus.innerHTML = '<span class="dot" style="width:7px;height:7px;background:#10b981;border-radius:50%"></span> Connected • WireGuard';
      valServer.textContent = `${s.flag} ${s.name}`;
      valIp.textContent = s.ip;
      valPing.textContent = `${s.ping} ms`;
      valProtocol.textContent = 'WireGuard (awg0)';
      btnToggle.textContent = 'Disconnect';
      btnToggle.className = 'btn btn-secondary btn-sm';
      btnRotate.disabled = false;
      btnRotate.style.opacity = '1';
    } else {
      badgeStatus.className = 'conn-status-badge status-disconnected';
      badgeStatus.innerHTML = '<span class="dot" style="width:7px;height:7px;background:#ef4444;border-radius:50%"></span> Disconnected';
      valServer.textContent = 'None';
      valIp.textContent = 'Your Real IP (Exposed)';
      valPing.textContent = '--';
      valProtocol.textContent = 'Inactive';
      btnToggle.textContent = 'Quick Connect';
      btnToggle.className = 'btn btn-primary btn-sm';
      btnRotate.disabled = true;
      btnRotate.style.opacity = '0.5';
    }

    // Highlight active in sidebar
    document.querySelectorAll('.server-item').forEach((item, idx) => {
      if (idx === currentIndex && isConnected) {
        item.classList.add('active');
      } else {
        item.classList.remove('active');
      }
    });
  }

  if (btnToggle) {
    btnToggle.addEventListener('click', () => {
      isConnected = !isConnected;
      updateUi();
    });
  }

  if (btnRotate) {
    btnRotate.addEventListener('click', () => {
      if (!isConnected) return;
      btnRotate.textContent = 'Rotating...';
      btnRotate.disabled = true;
      setTimeout(() => {
        currentIndex = (currentIndex + 1) % FREE_SERVERS.length;
        updateUi();
        btnRotate.textContent = 'Change Server';
        btnRotate.disabled = false;
      }, 350);
    });
  }

  // Sidebar item clicks
  document.querySelectorAll('.server-item').forEach((item) => {
    item.addEventListener('click', () => {
      const idx = parseInt(item.getAttribute('data-index') || '0', 10);
      currentIndex = idx;
      isConnected = true;
      updateUi();
    });
  });

  updateUi();
}

function initFaqAccordion() {
  const items = document.querySelectorAll('.faq-item');
  items.forEach(item => {
    const question = item.querySelector('.faq-question');
    question?.addEventListener('click', () => {
      const isActive = item.classList.contains('active');
      items.forEach(other => other.classList.remove('active'));
      if (!isActive) {
        item.classList.add('active');
      }
    });
  });
}

function initCliCopy() {
  document.querySelectorAll('.copy-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const cmd = btn.getAttribute('data-cmd') || '';
      navigator.clipboard.writeText(cmd).then(() => {
        const originalText = btn.textContent;
        btn.textContent = 'Copied!';
        btn.style.borderColor = '#10b981';
        btn.style.color = '#10b981';
        setTimeout(() => {
          btn.textContent = originalText;
          btn.style.borderColor = '';
          btn.style.color = '';
        }, 2000);
      });
    });
  });
}

function initServerGrid() {
  const grid = document.getElementById('server-network-grid');
  if (!grid) return;

  grid.innerHTML = '';
  FREE_SERVERS.forEach((s, idx) => {
    const box = document.createElement('div');
    box.className = 'server-box';
    box.innerHTML = `
      <div class="server-box-header">
        <span class="server-box-title">${s.flag} ${s.country}</span>
        <span class="server-status-dot"></span>
      </div>
      <div class="server-box-meta">
        <span>${s.name}</span>
        <span>Load: ${s.load}%</span>
      </div>
      <div class="server-box-meta" style="margin-top:0.4rem;">
        <span style="color:#06b6d4;">WireGuard</span>
        <span>${s.ping} ms</span>
      </div>
    `;
    box.addEventListener('click', () => {
      currentIndex = idx;
      isConnected = true;
      const preview = document.getElementById('preview-section');
      if (preview) {
        preview.scrollIntoView({ behavior: 'smooth' });
      }
      initLiveVpnCard();
    });
    grid.appendChild(box);
  });
}
