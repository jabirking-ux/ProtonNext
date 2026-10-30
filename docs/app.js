// ProtonNext Interactive Client & Server Directory Controller
const SERVERS = [
  {
    code: 'NL',
    country: 'Netherlands',
    city: 'Amsterdam',
    nodes: ['NL-FREE#102', 'NL-FREE#38', 'NL-FREE#19', 'NL-FREE#64'],
    ip: '185.107.56.221',
    ping: 18,
    load: 34,
    pinLeft: '50.2%',
    pinTop: '28.0%',
    bandwidth: '10 Gbps'
  },
  {
    code: 'US',
    country: 'United States',
    city: 'New York / Miami',
    nodes: ['US-FREE#45', 'US-FREE#18', 'US-FREE#82', 'US-FREE#11'],
    ip: '198.54.135.14',
    ping: 68,
    load: 41,
    pinLeft: '24.5%',
    pinTop: '34.0%',
    bandwidth: '10 Gbps'
  },
  {
    code: 'JP',
    country: 'Japan',
    city: 'Tokyo',
    nodes: ['JP-FREE#12', 'JP-FREE#07', 'JP-FREE#23', 'JP-FREE#31'],
    ip: '103.125.234.8',
    ping: 138,
    load: 29,
    pinLeft: '82.5%',
    pinTop: '36.5%',
    bandwidth: '10 Gbps'
  },
  {
    code: 'RO',
    country: 'Romania',
    city: 'Bucharest',
    nodes: ['RO-FREE#04', 'RO-FREE#09', 'RO-FREE#14', 'RO-FREE#02'],
    ip: '185.225.17.65',
    ping: 32,
    load: 22,
    pinLeft: '55.1%',
    pinTop: '32.0%',
    bandwidth: '10 Gbps'
  },
  {
    code: 'SG',
    country: 'Singapore',
    city: 'Singapore',
    nodes: ['SG-FREE#08', 'SG-FREE#15', 'SG-FREE#03', 'SG-FREE#21'],
    ip: '103.111.140.2',
    ping: 112,
    load: 31,
    pinLeft: '76.5%',
    pinTop: '56.0%',
    bandwidth: '10 Gbps'
  },
  {
    code: 'PL',
    country: 'Poland',
    city: 'Warsaw',
    nodes: ['PL-FREE#06', 'PL-FREE#11', 'PL-FREE#03'],
    ip: '185.244.214.91',
    ping: 27,
    load: 26,
    pinLeft: '53.5%',
    pinTop: '28.5%',
    bandwidth: '10 Gbps'
  },
  {
    code: 'CH',
    country: 'Switzerland',
    city: 'Zurich',
    nodes: ['CH-FREE#02', 'CH-FREE#05', 'CH-FREE#08'],
    ip: '185.159.157.44',
    ping: 21,
    load: 19,
    pinLeft: '50.9%',
    pinTop: '31.5%',
    bandwidth: '10 Gbps'
  },
  {
    code: 'NO',
    country: 'Norway',
    city: 'Oslo',
    nodes: ['NO-FREE#03', 'NO-FREE#07'],
    ip: '176.10.99.200',
    ping: 29,
    load: 17,
    pinLeft: '52.0%',
    pinTop: '19.5%',
    bandwidth: '10 Gbps'
  },
  {
    code: 'CA',
    country: 'Canada',
    city: 'Toronto / Montreal',
    nodes: ['CA-FREE#14', 'CA-FREE#06', 'CA-FREE#22'],
    ip: '149.56.102.77',
    ping: 72,
    load: 35,
    pinLeft: '28.0%',
    pinTop: '24.0%',
    bandwidth: '10 Gbps'
  },
  {
    code: 'DE',
    country: 'Germany',
    city: 'Frankfurt',
    nodes: ['DE-FREE#19', 'DE-FREE#04', 'DE-FREE#12'],
    ip: '185.216.34.109',
    ping: 19,
    load: 37,
    pinLeft: '51.5%',
    pinTop: '29.0%',
    bandwidth: '10 Gbps'
  }
];

let currentCountryIdx = 0;
let currentNodeIdx = 0;
let isConnected = true;
let adsBlocked = 48;
let trackersStopped = 194;

document.addEventListener('DOMContentLoaded', () => {
  renderSidebarCountries('');
  renderServersTable();
  updateClientUi();
  bindClientEvents();
  bindCopyButtons();
});

function renderSidebarCountries(filterText) {
  const listEl = document.getElementById('client-country-list');
  const countEl = document.getElementById('client-country-count');
  if (!listEl) return;

  const q = (filterText || '').trim().toLowerCase();
  const filtered = SERVERS.map((s, idx) => ({ s, idx })).filter(
    item => item.s.country.toLowerCase().includes(q) || item.s.code.toLowerCase().includes(q) || item.s.city.toLowerCase().includes(q)
  );

  if (countEl) {
    countEl.textContent = `Countries (${filtered.length})`;
  }

  listEl.innerHTML = '';
  filtered.forEach(({ s, idx }) => {
    const row = document.createElement('div');
    row.className = 'client-country-row' + (isConnected && idx === currentCountryIdx ? ' active' : '');
    row.innerHTML = `
      <div class="country-row-left">
        <img src="assets/flags/${s.code}.svg" alt="${s.code}" class="country-row-flag">
        <span class="country-row-name">${s.country}</span>
      </div>
      <div class="country-row-right">
        <span class="load-pill">${s.load}%</span>
        <span class="load-dot"></span>
      </div>
    `;
    row.addEventListener('click', () => {
      currentCountryIdx = idx;
      // Pick random node from top nodes (never stuck on #1)
      currentNodeIdx = Math.floor(Math.random() * s.nodes.length);
      isConnected = true;
      updateClientUi();
      renderSidebarCountries(document.getElementById('client-search')?.value || '');
    });
    listEl.appendChild(row);
  });
}

function updateClientUi() {
  const s = SERVERS[currentCountryIdx];
  const nodeName = s.nodes[currentNodeIdx % s.nodes.length];

  const connCard = document.getElementById('client-conn-card');
  const shieldStatus = document.getElementById('client-shield-status');
  const activeFlag = document.getElementById('client-active-flag');
  const activeName = document.getElementById('client-active-name');
  const activeSub = document.getElementById('client-active-sub');
  const btnDisconnect = document.getElementById('client-btn-disconnect');
  const btnRotate = document.getElementById('client-btn-rotate');

  const pinOverlay = document.getElementById('map-pin-overlay');
  const pinPulse = document.getElementById('map-pin-pulse');
  const pinLabel = document.getElementById('map-pin-label');
  const hudIp = document.getElementById('hud-ip-val');
  const hudPing = document.getElementById('hud-ping-val');

  if (isConnected) {
    connCard?.classList.remove('unprotected');
    if (shieldStatus) shieldStatus.textContent = 'PROTECTED';
    if (activeFlag) {
      activeFlag.src = `assets/flags/${s.code}.svg`;
      activeFlag.style.display = 'block';
    }
    if (activeName) activeName.textContent = s.country;
    if (activeSub) activeSub.textContent = `${nodeName} • WireGuard`;
    if (btnDisconnect) {
      btnDisconnect.textContent = 'Disconnect';
      btnDisconnect.className = 'client-btn client-btn-danger';
    }
    if (btnRotate) {
      btnRotate.disabled = false;
    }
    if (pinOverlay) {
      pinOverlay.style.left = s.pinLeft;
      pinOverlay.style.top = s.pinTop;
    }
    pinPulse?.classList.remove('disconnected');
    if (pinLabel) pinLabel.textContent = `${nodeName} (${s.ip})`;
    if (hudIp) hudIp.textContent = s.ip;
    if (hudPing) hudPing.textContent = `${s.ping} ms • awg0`;
  } else {
    connCard?.classList.add('unprotected');
    if (shieldStatus) shieldStatus.textContent = 'UNPROTECTED';
    if (activeFlag) activeFlag.style.display = 'none';
    if (activeName) activeName.textContent = 'Not connected';
    if (activeSub) activeSub.textContent = 'Traffic is unencrypted';
    if (btnDisconnect) {
      btnDisconnect.textContent = 'Quick connect';
      btnDisconnect.className = 'client-btn client-btn-primary';
    }
    if (btnRotate) {
      btnRotate.disabled = true;
    }
    pinPulse?.classList.add('disconnected');
    if (pinLabel) pinLabel.textContent = 'Disconnected';
    if (hudIp) hudIp.textContent = 'Exposed';
    if (hudPing) hudPing.textContent = '--';
  }
}

function bindClientEvents() {
  const btnDisconnect = document.getElementById('client-btn-disconnect');
  const btnRotate = document.getElementById('client-btn-rotate');
  const searchInput = document.getElementById('client-search');

  btnDisconnect?.addEventListener('click', () => {
    isConnected = !isConnected;
    updateClientUi();
    renderSidebarCountries(searchInput?.value || '');
  });

  btnRotate?.addEventListener('click', () => {
    if (!isConnected) return;
    // Strictly exclude current country on Change Server (matching our vpn.py fix)
    const otherIndices = SERVERS.map((_, i) => i).filter(i => i !== currentCountryIdx);
    currentCountryIdx = otherIndices[Math.floor(Math.random() * otherIndices.length)];
    const targetCountry = SERVERS[currentCountryIdx];
    currentNodeIdx = Math.floor(Math.random() * targetCountry.nodes.length);

    adsBlocked += Math.floor(Math.random() * 4) + 1;
    trackersStopped += Math.floor(Math.random() * 9) + 2;
    const elAds = document.getElementById('ns-ads-val');
    const elTrackers = document.getElementById('ns-trackers-val');
    if (elAds) elAds.textContent = String(adsBlocked);
    if (elTrackers) elTrackers.textContent = String(trackersStopped);

    updateClientUi();
    renderSidebarCountries(searchInput?.value || '');
  });

  searchInput?.addEventListener('input', (e) => {
    renderSidebarCountries(e.target.value);
  });
}

function renderServersTable() {
  const tbody = document.getElementById('servers-table-body');
  if (!tbody) return;

  tbody.innerHTML = '';
  SERVERS.forEach((s, idx) => {
    const tr = document.createElement('tr');
    tr.style.cursor = 'pointer';
    tr.innerHTML = `
      <td>
        <div class="srv-country-cell">
          <img src="assets/flags/${s.code}.svg" alt="${s.code}">
          <span>${s.country} (${s.city})</span>
        </div>
      </td>
      <td class="mono-cell">${s.nodes.join(', ')}</td>
      <td class="mono-cell">WireGuard / OpenVPN</td>
      <td class="mono-cell">${s.bandwidth}</td>
      <td class="mono-cell">${s.load}%</td>
      <td><span class="status-online">● Active</span></td>
    `;
    tr.addEventListener('click', () => {
      currentCountryIdx = idx;
      currentNodeIdx = Math.floor(Math.random() * s.nodes.length);
      isConnected = true;
      updateClientUi();
      renderSidebarCountries('');
      document.getElementById('client-window')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
    tbody.appendChild(tr);
  });
}

function bindCopyButtons() {
  document.querySelectorAll('[data-copy]').forEach(btn => {
    btn.addEventListener('click', () => {
      const text = btn.getAttribute('data-copy') || '';
      navigator.clipboard.writeText(text).then(() => {
        const prev = btn.textContent;
        btn.textContent = 'Copied';
        setTimeout(() => {
          btn.textContent = prev;
        }, 1600);
      });
    });
  });
}
