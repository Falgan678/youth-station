// 主页：地图 + 列表 + 筛选
let map, cluster, markers = [];
let allStations = [], filtered = [];
let citiesData = [];

const selCity = document.getElementById('sel-city');
const selDistrict = document.getElementById('sel-district');
const inpKw = document.getElementById('kw');
const listEl = document.getElementById('station-list');
const cntEl = document.getElementById('list-count');

function initMap() {
  map = new AMap.Map('map', {
    zoom: 10,
    center: [113.264, 23.13],   // 默认广州
    resizeEnable: true
  });
  AMap.plugin('AMap.ToolBar', () => {
    map.addControl(new AMap.ToolBar({
      position: { right: '20px', bottom: '40px' }
    }));
  });
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
  // 清空
  markers.forEach(m => map.remove(m));
  markers = [];
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
    marker.on('click', () => openInfoWindow(s));
    marker._sid = s.id;
    map.add(marker);
    markers.push(marker);
    points.push([s.lng, s.lat]);
  });
  if (points.length) map.setFitView(markers, false, [60, 60, 60, 60]);
}

let infoWin;
function openInfoWindow(s) {
  if (!infoWin) infoWin = new AMap.InfoWindow({ offset: new AMap.Pixel(0, -32) });
  infoWin.setContent(`
    <div class="iw">
      <h4>${escapeHtml(s.name)}</h4>
      <div class="iw-addr">${escapeHtml(s.address || '')}</div>
      <a href="/station/${s.id}" target="_blank">查看详情 / 申请入住 →</a>
    </div>`);
  infoWin.open(map, [s.lng, s.lat]);
}

function focusStation(id) {
  const s = filtered.find(x => x.id === id);
  if (!s) return;
  document.querySelectorAll('#station-list li').forEach(li => li.classList.toggle('active', parseInt(li.dataset.id) === id));
  if (s.lng && s.lat) {
    map.setZoomAndCenter(15, [s.lng, s.lat]);
    openInfoWindow(s);
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
document.getElementById('btn-fit').onclick = () => { if (markers.length) map.setFitView(markers, false, [60,60,60,60]); };

(async function () {
  initMap();
  await loadCities();
  await loadStations();
})();
