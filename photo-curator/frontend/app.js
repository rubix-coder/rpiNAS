/* Photo Curator — Vanilla JS SPA */
'use strict';

// ── API thin wrapper ──────────────────────────────────────────────────────────
const API = {
  async get(path) {
    const r = await fetch(path);
    if (!r.ok) throw new Error(`API ${path}: ${r.status}`);
    return r.json();
  },
  async post(path, body = {}) {
    const r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    if (!r.ok) throw new Error(`API ${path}: ${r.status}`);
    return r.json();
  },
  async patch(path, body = {}) {
    const r = await fetch(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    if (!r.ok) throw new Error(`API ${path}: ${r.status}`);
    return r.json();
  },
  async del(path) {
    const r = await fetch(path, { method: 'DELETE' });
    if (!r.ok) throw new Error(`API ${path}: ${r.status}`);
    return r.json();
  },
};

// ── Utility ───────────────────────────────────────────────────────────────────
function starsHtml(n) {
  return '★'.repeat(n) + '☆'.repeat(5 - n);
}
function scoreTip(val, thresholds, labels) {
  for (let i = 0; i < thresholds.length; i++) {
    if (val <= thresholds[i]) return labels[i];
  }
  return labels[labels.length - 1];
}
function el(id) { return document.getElementById(id); }

// ── App state ─────────────────────────────────────────────────────────────────
const State = {
  currentStep: 1,
  scanJobId: null,
  scanPollTimer: null,
  galleryPage: 1,
  galleryFilter: '',
  galleryMinScore: 0,
  galleryTotal: 0,
  galleryPages: 0,
  galleryImages: [],
  lightboxIdx: 0,
  currentAlbumId: null,
  albums: [],
};

// ── App controller ────────────────────────────────────────────────────────────
const App = {
  goToStep(n) {
    if (n < 1 || n > 4) return;
    document.querySelectorAll('.wizard-panel').forEach(p => p.classList.add('hidden'));
    el(`step-${n}`).classList.remove('hidden');
    document.querySelectorAll('.wizard-step-btn').forEach(b => {
      const s = parseInt(b.dataset.step);
      b.classList.remove('active', 'completed');
      if (s < n) b.classList.add('completed');
      if (s === n) b.classList.add('active');
    });
    for (let i = 1; i <= 3; i++) {
      const conn = el(`conn-${i}-${i + 1}`);
      if (conn) conn.classList.toggle('done', i < n);
    }
    State.currentStep = n;
    if (n === 3) Gallery.init();
    if (n === 4) AlbumBuilder.init();
  },
};

// ── Step 1: Choose Folder ─────────────────────────────────────────────────────
const Step1 = {
  async init() {
    try {
      const s = await API.get('/api/settings');
      if (s.last_image_dir) el('path-input').value = s.last_image_dir;
      const radio = document.querySelector(`input[name="path-type"][value="${s.path_type || 'local'}"]`);
      if (radio) { radio.checked = true; Step1.onPathTypeChange(); }
    } catch (_) {}
  },

  onPathTypeChange() {
    const val = document.querySelector('input[name="path-type"]:checked')?.value;
    if (val === 'network') {
      el('path-hint').textContent = '(e.g. /mnt/nas/photos or a mounted share path)';
      el('path-input').placeholder = '/mnt/nas/photos';
    } else {
      el('path-hint').textContent = '(e.g. /home/user/Pictures)';
      el('path-input').placeholder = '/home/user/Pictures';
    }
  },

  async testPath() {
    const path = el('path-input').value.trim();
    if (!path) return;
    const resultEl = el('path-test-result');
    resultEl.className = 'mt-2 text-sm text-gray-500';
    resultEl.textContent = 'Checking…';
    resultEl.classList.remove('hidden');
    el('start-scan-btn').disabled = true;

    try {
      const res = await API.post('/api/settings/test-path', { path });
      if (res.accessible) {
        resultEl.className = 'mt-2 text-sm text-green-600';
        resultEl.textContent = `✓ ${res.message}`;
        el('start-scan-btn').disabled = false;
        await API.patch('/api/settings', { last_image_dir: path });
      } else {
        resultEl.className = 'mt-2 text-sm text-red-600';
        resultEl.textContent = `✗ ${res.message}`;
      }
    } catch (e) {
      resultEl.className = 'mt-2 text-sm text-red-600';
      resultEl.textContent = 'Could not connect to the server. Is the app running?';
    }
  },

  async startScan() {
    const path = el('path-input').value.trim();
    if (!path) return;
    const pathType = document.querySelector('input[name="path-type"]:checked')?.value;
    await API.patch('/api/settings', { last_image_dir: path, path_type: pathType });

    try {
      const res = await API.post('/api/images/scan', { directory: path });
      State.scanJobId = res.job_id;
      App.goToStep(2);
      Step2.startPolling(res.job_id);
    } catch (e) {
      alert('Failed to start scan: ' + e.message);
    }
  },
};

// ── Step 2: Scan & Score ──────────────────────────────────────────────────────
const Step2 = {
  startPolling(jobId) {
    el('gpu-pill').classList.remove('hidden');
    const messages = [
      { pct: 0,  emoji: '🔍', text: 'Finding your photos…', sub: 'Scanning folder for images…' },
      { pct: 15, emoji: '📸', text: 'Photos found!',         sub: 'Starting AI quality check…' },
      { pct: 40, emoji: '🤖', text: 'Analysing quality…',    sub: 'Running AI beauty and sharpness scoring on your photos.' },
      { pct: 80, emoji: '✨', text: 'Almost there!',         sub: 'Final quality checks in progress…' },
      { pct: 98, emoji: '🎉', text: 'Done!',                 sub: 'Your best photos are ready to review.' },
    ];

    State.scanPollTimer = setInterval(async () => {
      try {
        const job = await API.get(`/api/images/scan/${jobId}`);
        const pct = job.progress_pct;
        el('scan-progress-bar').style.width = pct + '%';
        el('scan-progress-pct').textContent = Math.round(pct) + '%';
        el('scan-count-text').textContent = `${job.scored_files.toLocaleString()} / ${job.total_files.toLocaleString()} photos analysed`;
        el('scan-progress-label').textContent = job.status === 'running' ? 'Analysing…' : 'Complete!';

        const phase = messages.slice().reverse().find(m => pct >= m.pct) || messages[0];
        el('scan-emoji').textContent = phase.emoji;
        el('scan-status-text').textContent = phase.text;
        el('scan-sub-text').textContent = phase.sub;
        if (job.total_files > 0) {
          el('scan-sub-text').textContent = `${job.scored_files.toLocaleString()} of ${job.total_files.toLocaleString()} photos checked`;
        }

        if (job.status === 'complete' || job.status === 'failed') {
          clearInterval(State.scanPollTimer);
          el('scan-progress-bar').style.width = '100%';
          if (job.status === 'complete') {
            setTimeout(() => App.goToStep(3), 800);
          } else {
            el('scan-status-text').textContent = 'Something went wrong';
            el('scan-sub-text').textContent = 'Check that the folder path is correct and try again.';
          }
        }
      } catch (_) {}
    }, 1500);
  },

  cancel() {
    clearInterval(State.scanPollTimer);
    App.goToStep(1);
  },
};

// ── Step 3: Gallery ───────────────────────────────────────────────────────────
const Gallery = {
  _loading: false,
  _observer: null,

  async init() {
    State.galleryPage = 1;
    State.galleryImages = [];
    el('gallery-grid').innerHTML = '';
    await this.load();
    this._setupObserver();
  },

  setFilter(f) {
    State.galleryFilter = f;
    document.querySelectorAll('.filter-tab').forEach(t => {
      t.classList.toggle('active', t.dataset.filter === f);
    });
    this.init();
  },

  setMinStars(v) {
    const labels = ['Any', '★ 1+', '★★ 2+', '★★★ 3+', '★★★★ 4+'];
    el('min-stars-label').textContent = labels[v] || 'Any';
    State.galleryMinScore = [0, 0.2, 0.4, 0.6, 0.8][parseInt(v)];
    this.init();
  },

  async load() {
    if (this._loading) return;
    this._loading = true;
    el('gallery-loading').classList.remove('hidden');

    try {
      const params = new URLSearchParams({
        page: State.galleryPage,
        limit: 50,
        sort: 'composite_score',
        order: 'desc',
        exclude_duplicates: 'true',
      });
      if (State.galleryFilter) params.set('decision', State.galleryFilter);
      if (State.galleryMinScore > 0) params.set('min_score', State.galleryMinScore);

      const res = await API.get('/api/images?' + params);
      State.galleryTotal = res.total;
      State.galleryPages = res.pages;

      if (State.galleryPage === 1) {
        State.galleryImages = res.items;
        this._updateBanner(res.total);
      } else {
        State.galleryImages = [...State.galleryImages, ...res.items];
      }

      this._render(res.items, State.galleryPage > 1);

      if (res.page >= res.pages) {
        el('gallery-end').classList.remove('hidden');
        el('gallery-loading').classList.add('hidden');
      } else {
        el('gallery-end').classList.add('hidden');
      }

      if (res.total === 0) {
        el('gallery-empty').classList.remove('hidden');
        el('gallery-grid').innerHTML = '';
      } else {
        el('gallery-empty').classList.add('hidden');
      }
    } finally {
      this._loading = false;
      el('gallery-loading').classList.add('hidden');
    }
  },

  _updateBanner(total) {
    const top = Math.round(total * 0.1);
    el('gallery-title').textContent = total > 0
      ? `We found your top ${total.toLocaleString()} photos${State.galleryFilter ? ' (filtered)' : ''}`
      : 'No photos found';
    el('gallery-subtitle').textContent = '';
  },

  _render(items, append) {
    const grid = el('gallery-grid');
    if (!append) grid.innerHTML = '';

    items.forEach((img, offset) => {
      const idx = append ? State.galleryImages.length - items.length + offset : offset;
      const card = document.createElement('div');
      card.className = `photo-card decision-${img.decision}`;
      card.dataset.idx = idx;

      const decisionBadge = img.decision === 'approved' ? '<span class="decision-badge approved">✓ Kept</span>'
        : img.decision === 'rejected' ? '<span class="decision-badge rejected">✗</span>' : '';

      card.innerHTML = `
        <img src="${img.thumbnail_url}" alt="${img.filename}" loading="lazy" onclick="Gallery.openLightbox(${idx})" />
        <div class="card-overlay">${decisionBadge}</div>
        <div class="card-footer">
          <span class="card-stars" title="${img.stars} stars">${starsHtml(img.stars || 0)}</span>
          <div class="card-actions">
            <button class="card-action-btn keep"   aria-label="Keep"   onclick="Gallery.quickDecide(event,${img.id},'approved',${idx})">✓</button>
            <button class="card-action-btn skip"   aria-label="Skip"   onclick="Gallery.quickDecide(event,${img.id},'skipped',${idx})">–</button>
            <button class="card-action-btn remove" aria-label="Remove" onclick="Gallery.quickDecide(event,${img.id},'rejected',${idx})">✗</button>
          </div>
        </div>
      `;
      grid.appendChild(card);
    });
  },

  async quickDecide(e, imageId, decision, idx) {
    e.stopPropagation();
    await API.post(`/api/images/${imageId}/${decision}`);
    State.galleryImages[idx].decision = decision;
    const cards = document.querySelectorAll('.photo-card');
    const card = cards[idx];
    if (card) {
      card.className = `photo-card decision-${decision}`;
      const overlay = card.querySelector('.card-overlay');
      if (overlay) {
        overlay.innerHTML = decision === 'approved' ? '<span class="decision-badge approved">✓ Kept</span>'
          : decision === 'rejected' ? '<span class="decision-badge rejected">✗</span>' : '';
      }
    }
  },

  openLightbox(idx) {
    State.lightboxIdx = idx;
    Lightbox.show(State.galleryImages[idx]);
  },

  _setupObserver() {
    if (this._observer) this._observer.disconnect();
    const sentinel = document.createElement('div');
    sentinel.id = 'gallery-sentinel';
    el('gallery-grid').after(sentinel);
    this._observer = new IntersectionObserver(entries => {
      if (entries[0].isIntersecting && State.galleryPage < State.galleryPages) {
        State.galleryPage++;
        this.load();
      }
    }, { rootMargin: '200px' });
    this._observer.observe(sentinel);
  },

  async addAllApprovedToAlbum() {
    if (!State.currentAlbumId) {
      alert('Please create or select an album first in Step 4.');
      App.goToStep(4);
      return;
    }
    const approved = State.galleryImages.filter(i => i.decision === 'approved');
    if (approved.length === 0) {
      alert('No photos are marked as Kept yet. Use the ✓ button or press K to keep photos.');
      return;
    }
    let added = 0;
    for (let i = 0; i < approved.length; i++) {
      try {
        await API.post(`/api/albums/${State.currentAlbumId}/images`, {
          image_id: approved[i].id, print_size: '4x6', sort_order: i,
        });
        added++;
      } catch (_) {} // already added — skip
    }
    alert(`Added ${added} photos to your album!`);
    App.goToStep(4);
  },
};

// ── Lightbox ──────────────────────────────────────────────────────────────────
const Lightbox = {
  show(img) {
    el('lightbox-img').src = img.original_url || img.thumbnail_url;
    el('lb-filename').textContent = img.filename;
    el('lb-filename-full').textContent = img.filename;

    const stars = img.stars || 0;
    el('lb-stars').textContent = starsHtml(stars);
    el('lb-composite-label').textContent = `Quality: ${stars}/5 stars`;

    const aes = img.aesthetic_score;
    el('lb-aesthetic-val').textContent = aes != null ? `${aes.toFixed(1)}/10` : '–';
    el('lb-aesthetic-bar').style.width = aes != null ? `${aes * 10}%` : '0%';
    el('lb-aesthetic-tip').textContent = aes != null
      ? scoreTip(aes, [4, 6, 8], ['Average', 'Good', 'Great', 'Excellent'])
      : '';

    const sharp = img.sharpness_score;
    el('lb-sharpness-val').textContent = sharp != null ? Math.round(sharp * 100) + '%' : '–';
    el('lb-sharpness-bar').style.width = sharp != null ? `${sharp * 100}%` : '0%';
    el('lb-sharpness-tip').textContent = sharp != null
      ? scoreTip(sharp, [0.3, 0.6, 0.85], ['Blurry', 'Slightly soft', 'Sharp', 'Very sharp'])
      : '';

    const exp = img.exposure_score;
    el('lb-exposure-val').textContent = exp != null ? Math.round(exp * 100) + '%' : '–';
    el('lb-exposure-bar').style.width = exp != null ? `${exp * 100}%` : '0%';
    el('lb-exposure-tip').textContent = exp != null
      ? scoreTip(exp, [0.3, 0.6, 0.85], ['Very dark/bright', 'A bit off', 'Well-lit', 'Perfect lighting'])
      : '';

    el('lb-faces').textContent = img.face_count > 0
      ? `${img.face_count} face${img.face_count > 1 ? 's' : ''} detected`
      : 'No faces detected';

    if (img.captured_at) {
      el('lb-date').textContent = '📅 ' + new Date(img.captured_at).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' });
    } else {
      el('lb-date').textContent = '';
    }
    if (img.width && img.height) {
      el('lb-dims').textContent = `📐 ${img.width} × ${img.height} px`;
    }

    // Populate album dropdown
    const sel = el('lb-album-select');
    sel.innerHTML = State.albums.map(a => `<option value="${a.id}">${a.name}</option>`).join('');
    if (!sel.innerHTML) sel.innerHTML = '<option value="">— create an album first —</option>';

    // Highlight current decision
    el('lb-approve-btn').style.background = img.decision === 'approved' ? '#6ee7b7' : '';

    el('lightbox').classList.remove('hidden');
    el('lightbox').classList.add('flex');
  },

  close(e) {
    if (e && e.target !== el('lightbox') && !e.target.closest('.absolute.inset-0')) return;
    el('lightbox').classList.add('hidden');
    el('lightbox').classList.remove('flex');
  },

  async decide(decision) {
    const img = State.galleryImages[State.lightboxIdx];
    if (!img) return;
    await API.post(`/api/images/${img.id}/${decision}`);
    img.decision = decision;
    Gallery._render(State.galleryImages, false);
    this.next();
  },

  prev() {
    if (State.lightboxIdx > 0) {
      State.lightboxIdx--;
      this.show(State.galleryImages[State.lightboxIdx]);
    }
  },

  next() {
    if (State.lightboxIdx < State.galleryImages.length - 1) {
      State.lightboxIdx++;
      this.show(State.galleryImages[State.lightboxIdx]);
    } else {
      this.close({});
    }
  },

  async addToAlbum() {
    const albumId = parseInt(el('lb-album-select').value);
    const img = State.galleryImages[State.lightboxIdx];
    if (!albumId || !img) return;
    try {
      await API.post(`/api/albums/${albumId}/images`, { image_id: img.id, print_size: '4x6' });
      State.currentAlbumId = albumId;
      alert('Added to album!');
    } catch (e) {
      alert('Could not add to album (it may already be there).');
    }
  },
};

// ── Step 4: Album Builder ─────────────────────────────────────────────────────
const AlbumBuilder = {
  async init() {
    await this.loadAlbums();
    if (State.currentAlbumId) {
      this.selectAlbum(State.currentAlbumId);
    }
    // Pre-fill export path
    try {
      const s = await API.get('/api/settings');
      if (s.last_export_dir) el('export-dir-input').value = s.last_export_dir;
    } catch (_) {}
  },

  async loadAlbums() {
    try {
      State.albums = await API.get('/api/albums');
      this._renderAlbumList();
    } catch (_) {}
  },

  _renderAlbumList() {
    const list = el('album-list');
    list.innerHTML = '';
    if (!State.albums.length) {
      list.innerHTML = '<p class="text-sm text-gray-400 text-center py-4">No albums yet.</p>';
      return;
    }
    State.albums.forEach(a => {
      const btn = document.createElement('button');
      btn.className = `w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${a.id === State.currentAlbumId ? 'bg-blue-50 text-blue-700 font-semibold' : 'hover:bg-gray-50'}`;
      btn.innerHTML = `<div class="font-medium">${a.name}</div><div class="text-xs text-gray-400">${a.image_count} photo${a.image_count !== 1 ? 's' : ''}</div>`;
      btn.onclick = () => this.selectAlbum(a.id);
      list.appendChild(btn);
    });
  },

  async createAlbum() {
    const name = prompt('Album name:', `My Album ${new Date().getFullYear()}`);
    if (!name) return;
    const album = await API.post('/api/albums', { name });
    State.currentAlbumId = album.id;
    await this.loadAlbums();
    this.selectAlbum(album.id);
  },

  async selectAlbum(id) {
    State.currentAlbumId = id;
    this._renderAlbumList();

    try {
      const album = await API.get(`/api/albums/${id}`);
      el('album-name-display').textContent = album.name;
      el('album-image-count').textContent = `${album.image_count} photo${album.image_count !== 1 ? 's' : ''}`;
      el('album-placeholder').classList.add('hidden');
      el('album-detail').classList.remove('hidden');
      this._renderAlbumImages(album.images);
    } catch (_) {}
  },

  _renderAlbumImages(images) {
    const list = el('album-images-list');
    list.innerHTML = '';
    if (!images.length) {
      el('album-empty-msg').classList.remove('hidden');
      return;
    }
    el('album-empty-msg').classList.add('hidden');
    el('album-image-count').textContent = `${images.length} photo${images.length !== 1 ? 's' : ''}`;

    images.forEach((ai, idx) => {
      const row = document.createElement('div');
      row.className = 'album-image-row';
      row.draggable = true;
      row.dataset.imageId = ai.image_id;
      row.dataset.idx = idx;

      row.innerHTML = `
        <img src="${ai.thumbnail_url}" class="album-thumb" alt="${ai.filename}" />
        <span class="album-image-name">${ai.filename}</span>
        <select class="print-size-select" onchange="AlbumBuilder.updateSize(${ai.image_id}, this.value)" aria-label="Print size">
          <option value="4x6"      ${ai.print_size==='4x6'?'selected':''}>4×6"</option>
          <option value="5x7"      ${ai.print_size==='5x7'?'selected':''}>5×7"</option>
          <option value="8x10"     ${ai.print_size==='8x10'?'selected':''}>8×10"</option>
          <option value="a4_multi" ${ai.print_size==='a4_multi'?'selected':''}>A4 grid</option>
        </select>
        <button onclick="AlbumBuilder.removeImage(${ai.image_id})" class="text-red-400 hover:text-red-600 text-lg leading-none px-1" aria-label="Remove">&times;</button>
      `;

      // Drag-to-reorder
      row.addEventListener('dragstart', e => {
        e.dataTransfer.setData('text/plain', idx);
        row.style.opacity = '0.4';
      });
      row.addEventListener('dragend', () => { row.style.opacity = ''; });
      row.addEventListener('dragover', e => { e.preventDefault(); row.classList.add('drag-over'); });
      row.addEventListener('dragleave', () => row.classList.remove('drag-over'));
      row.addEventListener('drop', async e => {
        e.preventDefault();
        row.classList.remove('drag-over');
        const fromIdx = parseInt(e.dataTransfer.getData('text/plain'));
        const toIdx = idx;
        if (fromIdx === toIdx) return;
        const moved = images.splice(fromIdx, 1)[0];
        images.splice(toIdx, 0, moved);
        await AlbumBuilder.updateSortOrder(images);
        AlbumBuilder._renderAlbumImages(images);
      });

      list.appendChild(row);
    });
  },

  async updateSize(imageId, printSize) {
    await API.patch(`/api/albums/${State.currentAlbumId}/images/${imageId}`, { print_size: printSize });
  },

  async removeImage(imageId) {
    await API.del(`/api/albums/${State.currentAlbumId}/images/${imageId}`);
    await this.selectAlbum(State.currentAlbumId);
  },

  async updateSortOrder(images) {
    for (let i = 0; i < images.length; i++) {
      try {
        await API.patch(`/api/albums/${State.currentAlbumId}/images/${images[i].image_id}`, { sort_order: i });
      } catch (_) {}
    }
  },

  async exportAlbum() {
    if (!State.currentAlbumId) { alert('Select an album first.'); return; }
    const outputDir = el('export-dir-input').value.trim() || null;
    if (outputDir) await API.patch('/api/settings', { last_export_dir: outputDir });

    const btn = el('export-btn');
    btn.disabled = true;
    btn.textContent = 'Exporting…';
    el('export-progress').classList.remove('hidden');
    el('export-progress').textContent = 'Preparing photos for printing…';

    try {
      const job = await API.post(`/api/albums/${State.currentAlbumId}/export`, { output_dir: outputDir });
      const pollTimer = setInterval(async () => {
        try {
          const status = await API.get(`/api/albums/${State.currentAlbumId}/export/status`);
          el('export-progress').textContent = status.status === 'running'
            ? 'Exporting photos… please wait.' : '';

          if (status.status === 'complete') {
            clearInterval(pollTimer);
            btn.disabled = false;
            btn.textContent = 'Export for Printing →';
            el('export-progress').classList.add('hidden');
            // Show success modal
            el('export-success-count').textContent = `${status.file_count} photo${status.file_count !== 1 ? 's' : ''} exported, all at 300 DPI — print-ready!`;
            el('export-success-path').textContent = status.output_dir;
            el('export-success-modal').classList.remove('hidden');
            el('export-success-modal').classList.add('flex');
          } else if (status.status === 'failed') {
            clearInterval(pollTimer);
            btn.disabled = false;
            btn.textContent = 'Export for Printing →';
            el('export-progress').textContent = 'Export failed: ' + (status.error || 'unknown error');
          }
        } catch (_) {}
      }, 2000);
    } catch (e) {
      btn.disabled = false;
      btn.textContent = 'Export for Printing →';
      el('export-progress').textContent = 'Export failed: ' + e.message;
    }
  },
};

// ── Keyboard shortcuts ────────────────────────────────────────────────────────
document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;
  const lightboxVisible = !el('lightbox').classList.contains('hidden');
  if (lightboxVisible) {
    if (e.key === 'Escape') Lightbox.close({});
    if (e.key === 'ArrowRight' || e.key === 'k' || e.key === 'K') Lightbox.next();
    if (e.key === 'ArrowLeft') Lightbox.prev();
    if (e.key === 'k' || e.key === 'K') Lightbox.decide('approved');
    if (e.key === 's' || e.key === 'S') Lightbox.decide('skipped');
    if (e.key === 'r' || e.key === 'R') Lightbox.decide('rejected');
  }
});

// ── Health check ──────────────────────────────────────────────────────────────
async function checkHealth() {
  try {
    const h = await API.get('/api/health');
    const badge = el('health-badge');
    if (h.status === 'ok') {
      badge.className = 'text-xs px-2 py-1 rounded-full bg-green-50 text-green-600';
      badge.textContent = h.model_loaded
        ? `GPU ready (${h.device})`
        : h.device === 'cpu' ? 'CPU mode' : 'Model loading…';
    }
  } catch (_) {
    el('health-badge').textContent = 'Server offline';
    el('health-badge').className = 'text-xs px-2 py-1 rounded-full bg-red-50 text-red-500';
  }
}

// ── Init ──────────────────────────────────────────────────────────────────────
(async () => {
  checkHealth();
  setInterval(checkHealth, 30000);
  await Step1.init();
  App.goToStep(1);
})();
