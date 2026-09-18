(() => {
  'use strict';

  const tg = window.Telegram && window.Telegram.WebApp;
  const $ = (id) => document.getElementById(id);
  const el = {
    gate: $('gate'), gateText: $('gate-text'),
    drop: $('drop'), file: $('file'), dropHint: $('drop-hint'),
    progress: $('progress'), jobName: $('job-name'), jobPct: $('job-pct'),
    barFill: $('bar-fill'), jobStage: $('job-stage'),
    result: $('result'), resBadge: $('res-badge'), resCov: $('res-cov'),
    resFacts: $('res-facts'), resWarn: $('res-warn'), resDownload: $('res-download'),
    resSend: $('res-send'), resTtl: $('res-ttl'), resAgain: $('res-again'),
    error: $('error'), errorText: $('error-text'), errorAgain: $('error-again'),
    history: $('history'), historyList: $('history-list'),
  };

  let initData = '';
  let cfg = null;
  let pollTimer = null;
  let currentJob = null;

  // ---------- утилиты ----------
  const show = (node) => node.classList.remove('hidden');
  const hide = (node) => node.classList.add('hidden');
  const mb = (bytes) => (bytes / 1024 / 1024).toFixed(1) + ' МБ';
  const pct = (v) => (v * 100).toFixed(2) + '%';

  function haptic(type) {
    try { tg && tg.HapticFeedback && tg.HapticFeedback.notificationOccurred(type); }
    catch (_) { /* не критично */ }
  }

  async function api(path, options = {}) {
    const res = await fetch(path, {
      ...options,
      headers: { 'X-Telegram-Init-Data': initData, ...(options.headers || {}) },
    });
    let body = null;
    try { body = await res.json(); } catch (_) { /* пустой ответ */ }
    if (!res.ok) {
      throw new Error((body && body.detail) || `Сервер ответил ${res.status}`);
    }
    return body;
  }

  // ---------- экраны ----------
  function screenIdle() {
    stopPolling();
    hide(el.progress); hide(el.result); hide(el.error);
    show(el.drop);
    el.file.value = '';
    loadHistory();
  }

  function screenProgress(name) {
    hide(el.drop); hide(el.result); hide(el.error); hide(el.history);
    show(el.progress);
    el.jobName.textContent = name;
    setProgress(0, 'загрузка на сервер');
  }

  function setProgress(p, stage) {
    const v = Math.max(0, Math.min(100, Math.round(p)));
    el.barFill.style.width = v + '%';
    el.jobPct.textContent = v + '%';
    if (stage) el.jobStage.textContent = stage;
  }

  function screenError(message) {
    stopPolling();
    hide(el.progress); hide(el.drop); hide(el.result);
    show(el.error);
    el.errorText.textContent = message;
    haptic('error');
  }

  function fact(dl, key, value) {
    const dt = document.createElement('dt');
    dt.textContent = key;
    const dd = document.createElement('dd');
    dd.textContent = value;
    dl.append(dt, dd);
  }

  function screenResult(job) {
    stopPolling();
    hide(el.progress); hide(el.drop); hide(el.error);
    show(el.result);

    const s = job.summary || {};
    const cov = s.coverage || {};
    const sq = s.squeeze || {};
    const out = s.output || {};
    const shown = s.verified_coverage != null ? s.verified_coverage : cov.after;

    el.resCov.textContent = pct(shown) + ' кадра';
    el.resBadge.textContent = 'порог ' + pct(cov.threshold != null ? cov.threshold : 0.25) + ' взят';
    el.resBadge.classList.remove('warn');

    el.resFacts.textContent = '';
    fact(el.resFacts, 'Готовый файл', `${out.width}×${out.height}, ${out.duration} с`);
    fact(el.resFacts, 'Вставка', `с ${(s.insert || {}).at} с, ${(s.insert || {}).duration} с`);
    fact(el.resFacts, 'До обработки', pct(cov.before));
    fact(el.resFacts, 'Сжатие кадра',
      sq.applied ? `${sq.px} px (${(sq.ratio * 100).toFixed(1)}%)` : 'не потребовалось');
    if (s.bars_removed) fact(el.resFacts, 'Чёрные поля', 'срезаны');
    fact(el.resFacts, 'Размер', mb(job.output_size));
    if (s.seconds != null) fact(el.resFacts, 'Обработка', s.seconds + ' с');

    const warnings = s.warnings || [];
    if (warnings.length) {
      el.resWarn.textContent = '';
      warnings.forEach((w) => {
        const p = document.createElement('p');
        p.textContent = w;
        el.resWarn.append(p);
      });
      show(el.resWarn);
      el.resBadge.classList.add('warn');
    } else {
      hide(el.resWarn);
    }

    el.resDownload.href = job.download_url;
    el.resSend.disabled = !job.can_send_to_chat;
    el.resSend.textContent = job.can_send_to_chat
      ? 'Отправить в чат'
      : 'Для чата слишком большой';
    el.resSend.dataset.jobId = job.id;

    const ttl = cfg ? cfg.link_ttl_hours : 48;
    el.resTtl.textContent = `Ссылка живёт ${ttl} ч`;
    haptic('success');
    loadHistory();
  }

  // ---------- загрузка ----------
  function upload(file) {
    if (cfg && file.size > cfg.max_upload_bytes) {
      screenError(`Файл ${mb(file.size)} — больше лимита ${mb(cfg.max_upload_bytes)}`);
      return;
    }
    screenProgress(file.name);

    const form = new FormData();
    form.append('file', file, file.name);
    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/jobs');
    xhr.setRequestHeader('X-Telegram-Init-Data', initData);

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        // загрузка занимает первые 40% полосы, остальное — обработка
        setProgress((e.loaded / e.total) * 40, 'загрузка на сервер');
      }
    };
    xhr.onload = () => {
      let body = null;
      try { body = JSON.parse(xhr.responseText); } catch (_) { /* ignore */ }
      if (xhr.status === 201 && body && body.id) {
        currentJob = body.id;
        setProgress(40, 'в очереди');
        startPolling(body.id);
      } else {
        screenError((body && body.detail) || `Сервер ответил ${xhr.status}`);
      }
    };
    xhr.onerror = () => screenError('Обрыв связи при загрузке');
    xhr.send(form);
  }

  // ---------- опрос статуса ----------
  function startPolling(jobId) {
    stopPolling();
    const tick = async () => {
      try {
        const job = await api(`/api/jobs/${jobId}`);
        if (job.status === 'done') { screenResult(job); return; }
        if (job.status === 'error') { screenError(job.error || 'Обработка не удалась'); return; }
        const stage = job.status === 'queued'
          ? (job.queue_position ? `в очереди, впереди ${job.queue_position}` : 'в очереди')
          : job.stage;
        // 40% уже отдано загрузке
        setProgress(40 + job.progress * 0.6, stage);
      } catch (e) {
        screenError(e.message);
        return;
      }
      pollTimer = setTimeout(tick, 1500);
    };
    pollTimer = setTimeout(tick, 900);
  }

  function stopPolling() {
    if (pollTimer) { clearTimeout(pollTimer); pollTimer = null; }
  }

  // ---------- история ----------
  async function loadHistory() {
    let jobs;
    try { jobs = (await api('/api/jobs')).jobs; } catch (_) { return; }
    const done = jobs.filter((j) => j.status === 'done' && j.id !== currentJob);
    if (!done.length) { hide(el.history); return; }

    el.historyList.textContent = '';
    done.slice(0, 6).forEach((j) => {
      const li = document.createElement('li');
      const name = document.createElement('span');
      name.className = 'h-name';
      name.textContent = j.input_name;
      const meta = document.createElement('span');
      meta.className = 'h-meta';
      const cov = (j.summary && j.summary.verified_coverage);
      meta.textContent = cov != null ? pct(cov) : '';
      const link = document.createElement('a');
      link.href = j.download_url;
      link.textContent = 'скачать';
      link.download = '';
      li.append(name, meta, link);
      el.historyList.append(li);
    });
    show(el.history);
  }

  // ---------- события ----------
  el.drop.addEventListener('click', () => el.file.click());
  el.file.addEventListener('change', () => {
    if (el.file.files && el.file.files[0]) upload(el.file.files[0]);
  });
  ['dragenter', 'dragover'].forEach((ev) =>
    el.drop.addEventListener(ev, (e) => { e.preventDefault(); el.drop.classList.add('over'); }));
  ['dragleave', 'drop'].forEach((ev) =>
    el.drop.addEventListener(ev, () => el.drop.classList.remove('over')));
  el.drop.addEventListener('drop', (e) => {
    e.preventDefault();
    const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
    if (f) upload(f);
  });

  el.resAgain.addEventListener('click', () => { currentJob = null; screenIdle(); });
  el.errorAgain.addEventListener('click', () => { currentJob = null; screenIdle(); });

  el.resSend.addEventListener('click', async () => {
    const id = el.resSend.dataset.jobId;
    el.resSend.disabled = true;
    const before = el.resSend.textContent;
    el.resSend.textContent = 'Отправляю…';
    try {
      await api(`/api/jobs/${id}/send`, { method: 'POST' });
      el.resSend.textContent = 'Отправлено';
      haptic('success');
      if (tg) setTimeout(() => tg.close(), 900);
    } catch (e) {
      el.resSend.textContent = before;
      el.resSend.disabled = false;
      screenError(e.message);
    }
  });

  // ---------- старт ----------
  async function boot() {
    if (tg) {
      tg.ready();
      tg.expand();
      document.documentElement.classList.add('tg-themed');
      if (tg.setHeaderColor) {
        try { tg.setHeaderColor('secondary_bg_color'); } catch (_) { /* старый клиент */ }
      }
      initData = tg.initData || '';
    }
    if (!initData) {
      hide(el.drop);
      show(el.gate);
      el.gateText.textContent =
        'Эта страница работает только внутри Telegram. Открой бота и нажми «Открыть autoedit».';
      return;
    }
    try {
      cfg = await api('/api/config');
    } catch (e) {
      hide(el.drop);
      show(el.gate);
      el.gateText.textContent = e.message;
      return;
    }
    el.dropHint.textContent =
      `или перетащи файл сюда · до ${Math.round(cfg.max_upload_bytes / 1024 / 1024 / 1024 * 10) / 10} ГБ`;
    screenIdle();
  }

  boot();
})();
