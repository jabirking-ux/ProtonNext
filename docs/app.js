// ProtonNext Interactive Client, Map Vector Controller, Flyouts & Installer Benchmark
const SERVERS = [
  {
    code: 'NL',
    country: 'Netherlands',
    city: 'Amsterdam',
    nodes: ['NL-FREE#102', 'NL-FREE#38', 'NL-FREE#19', 'NL-FREE#64'],
    ip: '185.107.56.221',
    ping: 18,
    load: 34,
    svgX: 628,
    svgY: 152,
    panX: 0,
    panY: 18,
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
    svgX: 305,
    svgY: 195,
    panX: 22,
    panY: 12,
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
    svgX: 1061,
    svgY: 210,
    panX: -26,
    panY: 10,
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
    svgX: 690,
    svgY: 176,
    panX: -4,
    panY: 15,
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
    svgX: 977,
    svgY: 353,
    panX: -20,
    panY: -6,
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
    svgX: 670,
    svgY: 153,
    panX: -3,
    panY: 18,
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
    svgX: 638,
    svgY: 172,
    panX: -1,
    panY: 16,
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
    svgX: 646,
    svgY: 112,
    panX: -1,
    panY: 24,
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
    svgX: 330,
    svgY: 148,
    panX: 20,
    panY: 18,
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
    svgX: 644,
    svgY: 156,
    panX: -1,
    panY: 18,
    bandwidth: '10 Gbps'
  }
];

const PROFILES = [
  {
    name: 'Fastest Free Server',
    sub: 'Auto-selects lowest latency node',
    icon: 'assets/flags/Fastest.svg',
    targetIdx: 0
  },
  {
    name: 'Random Country Rotation',
    sub: 'Cycles across distinct countries',
    icon: 'assets/flags/Random.svg',
    targetIdx: -1
  },
  {
    name: 'P2P / BitTorrent Optimized',
    sub: 'Netherlands • Port Forwarding Ready',
    icon: 'assets/flags/NL.svg',
    targetIdx: 0
  },
  {
    name: 'Streaming & High Bandwidth',
    sub: 'United States • 10 Gbps Cluster',
    icon: 'assets/flags/US.svg',
    targetIdx: 1
  }
];

const FEATURE_CONFIG = {
  netshield: {
    title: 'NetShield DNS Filtering',
    desc: 'Blocks advertisements, tracking scripts, and malware domains at the DNS resolver level (10.2.0.1) inside the WireGuard tunnel.',
    current: 2,
    modes: [
      { label: 'Off', chip: 'OFF', art: 'assets/illustrations/netshield-off.png', isOff: true },
      { label: 'Block malware only', chip: 'LEVEL 1', art: 'assets/illustrations/netshield-on-level-1.png', isOff: false },
      { label: 'Block ads, trackers & malware', chip: 'LEVEL 2', art: 'assets/illustrations/netshield-on-level-2.png', isOff: false }
    ]
  },
  killswitch: {
    title: 'Kill Switch (WFP Callout)',
    desc: 'Prevents unprotected packets from leaving your network interface if the VPN connection drops or is re-negotiating.',
    current: 2,
    modes: [
      { label: 'Off', chip: 'OFF', art: 'assets/illustrations/kill-switch-off.png', isOff: true },
      { label: 'Standard', chip: 'STANDARD', art: 'assets/illustrations/kill-switch-on-standard.png', isOff: false },
      { label: 'Advanced (Permanent)', chip: 'ADVANCED', art: 'assets/illustrations/kill-switch-on-advanced.png', isOff: false }
    ]
  },
  splittunnel: {
    title: 'Split Tunneling',
    desc: 'Choose which applications or IPv4 subnets bypass the VPN tunnel or exclusively use the encrypted WireGuard interface.',
    current: 1,
    modes: [
      { label: 'Off', chip: 'OFF', art: 'assets/illustrations/split-tunneling-off.png', isOff: true },
      { label: 'Exclude apps/IPs (Standard)', chip: 'STANDARD', art: 'assets/illustrations/split-tunneling-standard.png', isOff: false },
      { label: 'Include only selected (Inverse)', chip: 'INVERSE', art: 'assets/illustrations/split-tunneling-inverse.png', isOff: false }
    ]
  },
  portforward: {
    title: 'NAT-PMP Port Forwarding',
    desc: 'Maps an inbound TCP/UDP port through the VPN gateway for P2P seeding, self-hosted game servers, and direct socket peers.',
    current: 1,
    modes: [
      { label: 'Off', chip: 'OFF', art: 'assets/illustrations/port-forwarding-off.png', isOff: true },
      { label: 'Active (Port 58412)', chip: 'PORT 58412', art: 'assets/illustrations/active-port-number.png', isOff: false }
    ]
  }
};

let currentCountryIdx = 0;
let currentNodeIdx = 0;
let isConnected = true;
let activeSidebarTab = 'countries';
let activeFlyoutKey = null;
let mapZoom = 1.25;
let adsBlocked = 48;
let trackersStopped = 194;
let sessionSeconds = 862;
const downHistory = [38, 52, 64, 58, 71, 66, 84, 79, 62, 68, 74, 65];
const upHistory = [12, 15, 18, 14, 21, 19, 24, 17, 16, 19, 22, 18];

document.addEventListener('DOMContentLoaded', () => {
  renderSidebarList('');
  renderMapNodes();
  renderServersTable();
  updateClientUi();
  bindClientEvents();
  bindFlyoutEvents();
  bindCopyButtons();
  bindBenchmark();
  startLiveTelemetryLoop();
});

function renderSidebarList(filterText) {
  const listEl = document.getElementById('client-country-list');
  const countEl = document.getElementById('client-country-count');
  const rightHdrEl = document.getElementById('client-list-right-hdr');
  if (!listEl) return;

  listEl.innerHTML = '';

  if (activeSidebarTab === 'profiles') {
    if (countEl) countEl.textContent = `Unlocked Profiles (${PROFILES.length})`;
    if (rightHdrEl) rightHdrEl.textContent = 'Action';

    PROFILES.forEach((p) => {
      const row = document.createElement('div');
      row.className = 'client-country-row';
      row.innerHTML = `
        <div class="country-row-left">
          <img src="${p.icon}" alt="" class="country-row-flag">
          <div>
            <span class="country-row-name">${p.name}</span>
            <span class="country-row-sub">${p.sub}</span>
          </div>
        </div>
        <div class="country-row-right">
          <button class="connect-mini-btn" style="display:inline-block;">Connect</button>
        </div>
      `;
      row.addEventListener('click', () => {
        if (p.targetIdx === -1) {
          const others = SERVERS.map((_, i) => i).filter(i => i !== currentCountryIdx);
          currentCountryIdx = others[Math.floor(Math.random() * others.length)];
        } else {
          currentCountryIdx = p.targetIdx;
        }
        currentNodeIdx = Math.floor(Math.random() * SERVERS[currentCountryIdx].nodes.length);
        isConnected = true;
        updateClientUi();
      });
      listEl.appendChild(row);
    });
    return;
  }

  const q = (filterText || '').trim().toLowerCase();
  const filtered = SERVERS.map((s, idx) => ({ s, idx })).filter(
    item => item.s.country.toLowerCase().includes(q) || item.s.code.toLowerCase().includes(q) || item.s.city.toLowerCase().includes(q)
  );

  if (countEl) countEl.textContent = `Countries (${filtered.length})`;
  if (rightHdrEl) rightHdrEl.textContent = 'Load';

  filtered.forEach(({ s, idx }) => {
    const row = document.createElement('div');
    row.className = 'client-country-row' + (isConnected && idx === currentCountryIdx ? ' active' : '');
    row.innerHTML = `
      <div class="country-row-left">
        <img src="assets/flags/${s.code}.svg" alt="${s.code}" class="country-row-flag">
        <div>
          <span class="country-row-name">${s.country}</span>
          <span class="country-row-sub">${s.city}</span>
        </div>
      </div>
      <div class="country-row-right">
        <button class="connect-mini-btn">Connect</button>
        <span class="load-pill">${s.load}%</span>
        <span class="load-dot"></span>
      </div>
    `;
    row.addEventListener('click', () => {
      currentCountryIdx = idx;
      currentNodeIdx = Math.floor(Math.random() * s.nodes.length);
      isConnected = true;
      updateClientUi();
      renderSidebarList(document.getElementById('client-search')?.value || '');
    });
    listEl.appendChild(row);
  });
}

function renderMapNodes() {
  const svgNodesGroup = document.getElementById('map-nodes-group');
  if (!svgNodesGroup) return;

  svgNodesGroup.innerHTML = '';
  SERVERS.forEach((s, idx) => {
    const isAct = isConnected && idx === currentCountryIdx;
    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    g.setAttribute('class', 'map-node-pin');
    g.setAttribute('transform', `translate(${s.svgX}, ${s.svgY})`);

    if (isAct) {
      const pulse = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      pulse.setAttribute('r', '14');
      pulse.setAttribute('fill', 'rgba(44, 255, 204, 0.25)');
      g.appendChild(pulse);
    }

    const core = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    core.setAttribute('class', 'pin-core');
    core.setAttribute('r', isAct ? '6.5' : '4.5');
    core.setAttribute('fill', isAct ? '#2CFFCC' : '#8A6EFF');
    core.setAttribute('stroke', '#16141C');
    core.setAttribute('stroke-width', '2');
    g.appendChild(core);

    const lblBg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    const textStr = isAct ? `${s.nodes[currentNodeIdx % s.nodes.length]}` : s.code;
    const boxW = isAct ? 92 : 26;
    lblBg.setAttribute('x', String(-boxW / 2));
    lblBg.setAttribute('y', '-24');
    lblBg.setAttribute('width', String(boxW));
    lblBg.setAttribute('height', '15');
    lblBg.setAttribute('rx', '3');
    lblBg.setAttribute('fill', isAct ? '#16141C' : 'rgba(22, 20, 28, 0.85)');
    lblBg.setAttribute('stroke', isAct ? '#2CFFCC' : 'rgba(255,255,255,0.2)');
    lblBg.setAttribute('stroke-width', '1');
    g.appendChild(lblBg);

    const txt = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    txt.setAttribute('x', '0');
    txt.setAttribute('y', '-13.5');
    txt.setAttribute('text-anchor', 'middle');
    txt.setAttribute('fill', isAct ? '#2CFFCC' : '#FFFFFF');
    txt.setAttribute('font-size', '9.5');
    txt.setAttribute('font-family', 'JetBrains Mono, monospace');
    txt.setAttribute('font-weight', '700');
    txt.textContent = textStr;
    g.appendChild(txt);

    g.addEventListener('click', (e) => {
      e.stopPropagation();
      currentCountryIdx = idx;
      currentNodeIdx = Math.floor(Math.random() * s.nodes.length);
      isConnected = true;
      updateClientUi();
      renderSidebarList(document.getElementById('client-search')?.value || '');
    });

    svgNodesGroup.appendChild(g);
  });

  // Update connection arc path
  const arcPath = document.getElementById('map-connection-arc');
  if (arcPath) {
    if (!isConnected) {
      arcPath.setAttribute('d', '');
    } else {
      const s = SERVERS[currentCountryIdx];
      // Origin point (Central Europe / Neutral user origin)
      const ox = 610, oy = 185;
      const tx = s.svgX, ty = s.svgY;
      const cx = (ox + tx) / 2;
      const cy = Math.min(oy, ty) - Math.hypot(tx - ox, ty - oy) * 0.28;
      arcPath.setAttribute('d', `M ${ox} ${oy} Q ${cx} ${cy} ${tx} ${ty}`);
    }
  }
}

function updateMapTransform() {
  const inner = document.getElementById('map-vector-inner');
  if (!inner) return;
  const s = SERVERS[currentCountryIdx];
  if (isConnected && mapZoom > 1.05) {
    inner.style.transform = `scale(${mapZoom}) translate(${s.panX}%, ${s.panY}%)`;
  } else {
    inner.style.transform = `scale(${mapZoom}) translate(0%, 0%)`;
  }
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
    if (btnRotate) btnRotate.disabled = false;
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
    if (btnRotate) btnRotate.disabled = true;
    if (hudIp) hudIp.textContent = 'Exposed';
    if (hudPing) hudPing.textContent = '--';
  }

  renderMapNodes();
  updateMapTransform();
}

function bindClientEvents() {
  const btnDisconnect = document.getElementById('client-btn-disconnect');
  const btnRotate = document.getElementById('client-btn-rotate');
  const searchInput = document.getElementById('client-search');
  const tabCountries = document.getElementById('tab-btn-countries');
  const tabProfiles = document.getElementById('tab-btn-profiles');
  const btnZoomIn = document.getElementById('map-zoom-in');
  const btnZoomOut = document.getElementById('map-zoom-out');
  const btnZoomReset = document.getElementById('map-zoom-reset');

  btnDisconnect?.addEventListener('click', () => {
    isConnected = !isConnected;
    updateClientUi();
    renderSidebarList(searchInput?.value || '');
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
    renderSidebarList(searchInput?.value || '');
  });

  searchInput?.addEventListener('input', (e) => {
    activeSidebarTab = 'countries';
    tabCountries?.classList.add('active');
    tabProfiles?.classList.remove('active');
    renderSidebarList(e.target.value);
  });

  tabCountries?.addEventListener('click', () => {
    activeSidebarTab = 'countries';
    tabCountries.classList.add('active');
    tabProfiles?.classList.remove('active');
    renderSidebarList(searchInput?.value || '');
  });

  tabProfiles?.addEventListener('click', () => {
    activeSidebarTab = 'profiles';
    tabProfiles.classList.add('active');
    tabCountries?.classList.remove('active');
    renderSidebarList('');
  });

  btnZoomIn?.addEventListener('click', () => {
    mapZoom = Math.min(2.0, +(mapZoom + 0.25).toFixed(2));
    updateMapTransform();
  });

  btnZoomOut?.addEventListener('click', () => {
    mapZoom = Math.max(1.0, +(mapZoom - 0.25).toFixed(2));
    updateMapTransform();
  });

  btnZoomReset?.addEventListener('click', () => {
    mapZoom = 1.0;
    updateMapTransform();
  });
}

function bindFlyoutEvents() {
  const drawer = document.getElementById('client-flyout-drawer');
  const closeBtn = document.getElementById('flyout-close-btn');

  document.querySelectorAll('.ft-chip[data-feature]').forEach(chip => {
    chip.addEventListener('click', () => {
      const key = chip.getAttribute('data-feature');
      if (!key || !FEATURE_CONFIG[key]) return;

      if (activeFlyoutKey === key && drawer?.classList.contains('open')) {
        drawer.classList.remove('open');
        activeFlyoutKey = null;
        document.querySelectorAll('.ft-chip').forEach(c => c.classList.remove('selected'));
        return;
      }

      activeFlyoutKey = key;
      document.querySelectorAll('.ft-chip').forEach(c => c.classList.remove('selected'));
      chip.classList.add('selected');
      renderFlyoutContent(key);
      drawer?.classList.add('open');
    });
  });

  closeBtn?.addEventListener('click', () => {
    drawer?.classList.remove('open');
    activeFlyoutKey = null;
    document.querySelectorAll('.ft-chip').forEach(c => c.classList.remove('selected'));
  });
}

function renderFlyoutContent(key) {
  const cfg = FEATURE_CONFIG[key];
  if (!cfg) return;

  const artImg = document.getElementById('flyout-art-img');
  const titleEl = document.getElementById('flyout-title');
  const descEl = document.getElementById('flyout-desc');
  const btnsWrap = document.getElementById('flyout-mode-btns');

  const activeMode = cfg.modes[cfg.current];
  if (artImg) artImg.src = activeMode.art;
  if (titleEl) titleEl.textContent = cfg.title;
  if (descEl) descEl.textContent = cfg.desc;

  if (btnsWrap) {
    btnsWrap.innerHTML = '';
    cfg.modes.forEach((m, idx) => {
      const b = document.createElement('button');
      b.className = 'flyout-mode-btn' + (idx === cfg.current ? ' active' : '');
      b.textContent = m.label;
      b.addEventListener('click', () => {
        cfg.current = idx;
        renderFlyoutContent(key);
        const chipVal = document.getElementById(`chip-val-${key}`);
        if (chipVal) {
          chipVal.textContent = m.chip;
          chipVal.className = 'ft-chip-on' + (m.isOff ? ' off' : '');
        }
      });
      btnsWrap.appendChild(b);
    });
  }
}

function startLiveTelemetryLoop() {
  setInterval(() => {
    const timerEl = document.getElementById('client-session-timer');
    const downEl = document.getElementById('speed-down-val');
    const upEl = document.getElementById('speed-up-val');
    const polyDown = document.getElementById('sparkline-down');
    const polyUp = document.getElementById('sparkline-up');

    if (!isConnected) {
      if (timerEl) timerEl.textContent = '00:00:00';
      if (downEl) downEl.textContent = '0.0 Mbps';
      if (upEl) upEl.textContent = '0.0 Mbps';
      return;
    }

    sessionSeconds++;
    const hrs = String(Math.floor(sessionSeconds / 3600)).padStart(2, '0');
    const mins = String(Math.floor((sessionSeconds % 3600) / 60)).padStart(2, '0');
    const secs = String(sessionSeconds % 60).padStart(2, '0');
    if (timerEl) timerEl.textContent = `${hrs}:${mins}:${secs}`;

    const nextDown = +(48 + Math.random() * 42).toFixed(1);
    const nextUp = +(11 + Math.random() * 16).toFixed(1);
    downHistory.push(nextDown);
    downHistory.shift();
    upHistory.push(nextUp);
    upHistory.shift();

    if (downEl) downEl.textContent = `${nextDown} Mbps`;
    if (upEl) upEl.textContent = `${nextUp} Mbps`;

    if (polyDown) {
      const pts = downHistory.map((v, i) => `${i * 10.5},${30 - (v / 100) * 26}`).join(' ');
      polyDown.setAttribute('points', pts);
    }
    if (polyUp) {
      const pts = upHistory.map((v, i) => `${i * 10.5},${30 - (v / 100) * 26}`).join(' ');
      polyUp.setAttribute('points', pts);
    }
  }, 1200);
}

function bindBenchmark() {
  const btnRun = document.getElementById('btn-run-bench');
  const fillFast = document.getElementById('bench-fill-fast');
  const fillSlow = document.getElementById('bench-fill-slow');
  const timeFast = document.getElementById('bench-time-fast');
  const timeSlow = document.getElementById('bench-time-slow');
  const logBox = document.getElementById('bench-log-box');

  const sampleFiles = [
    'ProtonVPN.Client.exe',
    'ProtonVPN.Client.Logic.Connection.dll',
    'ProtonVPN.Client.Logic.Servers.dll',
    'Microsoft.UI.Xaml.dll',
    'WinRT.Runtime.dll',
    'SkiaSharp.dll',
    'ProtonVPN-Next-CLI/pvpn_cli/vpn.py',
    'ProtonVPN-Next-CLI/pvpn_cli/handshake.py',
    'ProtonVPN-Next-CLI/engine/pvpn-engine.exe',
    'ProtonVPN-Next-CLI/engine/wintun.dll',
    'Assets/Illustrations/world-map.svg',
    'Uninstall.exe'
  ];

  btnRun?.addEventListener('click', () => {
    btnRun.disabled = true;
    btnRun.textContent = 'Running Extraction Benchmark...';
    let t0 = performance.now();
    let logIdx = 0;
    if (logBox) logBox.innerHTML = 'Output folder: C:\\Program Files\\ProtonNext<br>';

    const timer = setInterval(() => {
      const elapsed = (performance.now() - t0) / 1000;
      const fastPct = Math.min(100, (elapsed / 1.45) * 100);
      const slowPct = Math.min(100, (elapsed / 45.0) * 100);

      if (fillFast) fillFast.style.width = `${fastPct}%`;
      if (fillSlow) fillSlow.style.width = `${slowPct}%`;

      if (fastPct < 100) {
        if (timeFast) timeFast.textContent = `${elapsed.toFixed(2)}s (${Math.floor((fastPct / 100) * 2313)} / 2,313 files)`;
        if (logBox && logIdx < sampleFiles.length) {
          logBox.innerHTML += `Extract (64KB stream): ${sampleFiles[logIdx++]}<br>`;
          logBox.scrollTop = logBox.scrollHeight;
        }
      } else {
        if (timeFast) timeFast.textContent = `1.45s — COMPLETED (2,313 files)`;
      }

      if (timeSlow) {
        timeSlow.textContent = `${elapsed.toFixed(1)}s / ~45.0s (${Math.floor((slowPct / 100) * 2313)} / 2,313 files)`;
      }

      if (elapsed >= 3.2) {
        clearInterval(timer);
        if (logBox) {
          logBox.innerHTML += `<strong>Completed in 1.45s (NSIS still at 7% / 164 files).</strong>`;
          logBox.scrollTop = logBox.scrollHeight;
        }
        btnRun.disabled = false;
        btnRun.textContent = 'Re-run Extraction Benchmark';
      }
    }, 80);
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
      renderSidebarList('');
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
