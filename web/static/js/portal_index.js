// 主页：地图 + 列表 + 筛选 + 详情卡
let map, cluster, markers = [];
let allStations = [], filtered = [];
let citiesData = [];
let activeMarker = null;

const selCity = document.getElementById('sel-city');
const selDistrict = document.getElementById('sel-district');
const inpKw = document.getElementById('kw');
const listEl = document.getElementById('station-list');
const cntEl = document.getElementById('list-count');

function initMap() {
  map = new AMap.Map('map', {
    zoom: 10,
    center: [113.264, 23.13],
    resizeEnable: true,
  });
  AMap.plugin('AMap.ToolBar', () => {
    map.addControl(new AMap.ToolBar({
      position: { right: '20px', bottom: '40px' }
    }));
  });
  // 点地图空白处自动关详情卡
  map.on('click', () => closeDetailCard());
}

async function loadCities() {
  const r = await fetch('/api/cities');
  const j = await r.json();
  citiesData = j.cities || [];
  selCity.innerHTML = '<option value="">全部城市</option>' +
    citiesData.map(c => `<option value="${c.city}">${c.city}</option>`).join('');
}

function refreshDistricts() {
  const c = selCity.value;
  const found = citiesData.find(x => x.city === c);
  selDistrict.innerHTML = '<option value="">全部区域</option>' +
    (found ? found.districts.map(d => `<option value="${d}">${d}</option>`).join('') : '');
}

async function loadStations() {
  const params = new URLSearchParams();
  if (selCity.value) params.set('city', selCity.value);
  if (selDistrict.value) params.set('district', selDistrict.value);
  if (inpKw.value.trim()) params.set('kw', inpKw.value.trim());
  const r = await fetch('/api/stations?' + params.toString());
  const j = await r.json();
  allStations = j.items || [];
  filtered = allStations;
  renderList();
  renderMarkers();
  closeDetailCard();
}

function renderList() {
  cntEl.textContent = filtered.length;
  if (!filtered.length) {
    listEl.innerHTML = '<li style="color:#8aa8d6;text-align:center;padding:40px 16px;">暂无匹配的驿站</li>';
    return;
  }
  listEl.innerHTML = filtered.map(s => `
    <li data-id="${s.id}">
      <div class="s-name">${escapeHtml(s.name)}</div>
      <div class="s-addr">${escapeHtml(s.address || '—')}</div>
      <div class="s-tags">
        ${s.city ? `<span class="tag">${escapeHtml(s.city)}</span>` : ''}
        ${s.district ? `<span class="tag tag-2">${escapeHtml(s.district)}</span>` : ''}
      </div>
    </li>`).join('');
  listEl.querySelectorAll('li').forEach(li => {
    li.addEventListener('click', () => focusStation(parseInt(li.dataset.id)));
    li.addEventListener('dblclick', () => location.href = '/station/' + li.dataset.id);
  });
}

function renderMarkers() {
  // 清空旧 marker
  markers.forEach(m => map.remove(m));
  markers = [];
  activeMarker = null;
  const points = [];
  filtered.forEach(s => {
    if (!s.lng || !s.lat) return;
    const marker = new AMap.Marker({
      position: [s.lng, s.lat],
      title: s.name,
      offset: new AMap.Pixel(-13, -30),
      icon: new AMap.Icon({
        size: new AMap.Size(26, 32),
        image: 'https://webapi.amap.com/theme/v1.3/markers/n/mark_b.png',
        imageSize: new AMap.Size(26, 32),
      })
    });
    marker.on('click', e => {
      // 阻止冒泡，避免触发地图 click 关闭卡片
      try { e && AMap.Event && AMap.Event.preventDefault && AMap.Event.preventDefault(e); } catch(_) {}
      showDetailCard(s);
      highlightMarker(marker);
    });
    marker._sid = s.id;
    map.add(marker);
    markers.push(marker);
    points.push([s.lng, s.lat]);
  });
  if (points.length) map.setFitView(markers, false, [60, 60, 60, 60]);
}

function highlightMarker(marker) {
  // 还原所有
  markers.forEach(m => {
    m.setIcon(new AMap.Icon({
      size: new AMap.Size(26, 32),
      image: 'https://webapi.amap.com/theme/v1.3/markers/n/mark_b.png',
      imageSize: new AMap.Size(26, 32),
    }));
    m.setzIndex && m.setzIndex(100);
  });
  if (marker) {
    // 选中的换红色 marker
    marker.setIcon(new AMap.Icon({
      size: new AMap.Size(26, 32),
      image: 'https://webapi.amap.com/theme/v1.3/markers/n/mark_r.png',
      imageSize: new AMap.Size(26, 32),
    }));
    marker.setzIndex && marker.setzIndex(200);
  }
  activeMarker = marker;
}

/* ============ 详情卡（替代 InfoWindow，避免重叠） ============ */
function showDetailCard(s) {
  const card = document.getElementById('station-detail-card');
  const body = document.getElementById('dc-body');
  if (!card || !body) return;

  const reqs = Array.isArray(s.requirements) ? s.requirements : [];
  const mats = Array.isArray(s.materials) ? s.materials : [];

  let infoRows = '';
  if (s.contact_phone) {
    infoRows += `<div class="dc-info-row"><span class="ir-label">📞 电话</span><span class="ir-value"><a href="tel:${escapeHtml(s.contact_phone)}">${escapeHtml(s.contact_phone)}</a>${s.contact_name ? ' · ' + escapeHtml(s.contact_name) : ''}</span></div>`;
  }
  if (s.free_days) {
    infoRows += `<div class="dc-info-row"><span class="ir-label">⏱️ 免费</span><span class="ir-value">${s.free_days} 天</span></div>`;
  }
  if (s.apply_url) {
    infoRows += `<div class="dc-info-row"><span class="ir-label">🔗 申请</span><span class="ir-value"><a href="${escapeHtml(s.apply_url)}" target="_blank">${escapeHtml(s.apply_url)}</a></span></div>`;
  }

  let reqHtml = '';
  if (reqs.length) {
    reqHtml = `<div class="dc-section">📋 申请条件</div><ul class="dc-list">${reqs.map(r => '<li>' + escapeHtml(r) + '</li>').join('')}</ul>`;
  }
  let matHtml = '';
  if (mats.length) {
    matHtml = `<div class="dc-section">📎 所需材料</div><ul class="dc-list">${mats.map(m => '<li>' + escapeHtml(m) + '</li>').join('')}</ul>`;
  }

  body.innerHTML = `
    <div class="dc-name">${escapeHtml(s.name)}</div>
    <div class="dc-meta">
      ${s.city ? `<span class="tag">${escapeHtml(s.city)}</span>` : ''}
      ${s.district ? `<span class="tag tag-2">${escapeHtml(s.district)}</span>` : ''}
    </div>
    ${s.address ? `<div class="dc-addr">📍 ${escapeHtml(s.address)}</div>` : ''}
    ${infoRows ? `<div class="dc-section">📌 关键信息</div>${infoRows}` : ''}
    ${reqHtml}
    ${matHtml}
    <div class="dc-actions">
      <a href="/station/${s.id}" class="dc-btn primary" target="_blank">查看完整详情</a>
      ${s.apply_url ? `<a href="${escapeHtml(s.apply_url)}" class="dc-btn ghost" target="_blank">一键申请</a>` : ''}
    </div>
  `;
  card.style.display = '';
}

function closeDetailCard() {
  const card = document.getElementById('station-detail-card');
  if (card) card.style.display = 'none';
  // 还原 marker 高亮
  if (activeMarker) {
    try {
      activeMarker.setIcon(new AMap.Icon({
        size: new AMap.Size(26, 32),
        image: 'https://webapi.amap.com/theme/v1.3/markers/n/mark_b.png',
        imageSize: new AMap.Size(26, 32),
      }));
    } catch(_) {}
    activeMarker = null;
  }
}
window.closeDetailCard = closeDetailCard;

function focusStation(id) {
  const s = filtered.find(x => x.id === id);
  if (!s) return;
  document.querySelectorAll('#station-list li').forEach(li => li.classList.toggle('active', parseInt(li.dataset.id) === id));
  if (s.lng && s.lat) {
    map.setZoomAndCenter(15, [s.lng, s.lat]);
    showDetailCard(s);
    // 高亮对应 marker
    const m = markers.find(x => x._sid === id);
    if (m) highlightMarker(m);
  } else {
    showDetailCard(s);
  }
}

function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
}

document.getElementById('btn-search').onclick = loadStations;
document.getElementById('btn-reset').onclick = () => {
  selCity.value = ''; selDistrict.innerHTML = '<option value="">全部区域</option>';
  inpKw.value = ''; loadStations();
};
selCity.onchange = () => { refreshDistricts(); loadStations(); };
selDistrict.onchange = loadStations;
inpKw.addEventListener('keydown', e => { if (e.key === 'Enter') loadStations(); });
document.getElementById('btn-fit').onclick = () => {
  closeDetailCard();
  if (markers.length) map.setFitView(markers, false, [60,60,60,60]);
};

(async function () {
  initMap();
  await loadCities();
  await loadStations();
})();
