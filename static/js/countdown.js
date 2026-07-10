// ==========================================
// GOMACL — Countdown intelligent
// ==========================================

(function () {

  // Fenêtre de jeu : commence à 12h00, dure 25h (jusqu'à 12h59 du lendemain)
  const WINDOW_START_HOUR = 12;   // 12h00
  const WINDOW_DURATION_MS = 25 * 60 * 60 * 1000; // 25 heures

  function getMatchWindow(dateStr) {
    // dateStr = "2026-05-20" (YYYY-MM-DD)
    const matchDay = new Date(dateStr + "T00:00:00");
    const windowStart = new Date(matchDay);
    windowStart.setHours(WINDOW_START_HOUR, 0, 0, 0);
    const windowEnd = new Date(windowStart.getTime() + WINDOW_DURATION_MS);
    return { windowStart, windowEnd };
  }

  function pad(n) {
    return String(n).padStart(2, '0');
  }

  function formatCountdown(ms) {
    if (ms <= 0) return null;
    const totalSec = Math.floor(ms / 1000);
    const days    = Math.floor(totalSec / 86400);
    const hours   = Math.floor((totalSec % 86400) / 3600);
    const minutes = Math.floor((totalSec % 3600) / 60);
    const seconds = totalSec % 60;
    return { days, hours, minutes, seconds };
  }

  function renderCountdown(el, ms, type) {
    // type: 'far' | 'soon' | 'live'
    el.className = 'fx-countdown is-' + type;

    if (type === 'live') {
      el.innerHTML = `
        <span style="width:8px;height:8px;border-radius:50%;background:#47d18c;display:inline-block;animation:pulse-green 1.5s infinite;"></span>
        <span>🟢 EN COURS — Jouable maintenant</span>
      `;
      return;
    }

    const t = formatCountdown(ms);
    if (!t) return;

    let html = `<i class="fas fa-clock me-1" style="font-size:.8rem;"></i>`;

    if (t.days > 0) {
      html += `
        <span class="cd-block"><span class="cd-num">${t.days}</span><span class="cd-label">j</span></span>
        <span class="cd-sep">:</span>
      `;
    }
    html += `
      <span class="cd-block"><span class="cd-num">${pad(t.hours)}</span><span class="cd-label">h</span></span>
      <span class="cd-sep">:</span>
      <span class="cd-block"><span class="cd-num">${pad(t.minutes)}</span><span class="cd-label">min</span></span>
      <span class="cd-sep">:</span>
      <span class="cd-block"><span class="cd-num">${pad(t.seconds)}</span><span class="cd-label">sec</span></span>
    `;

    el.innerHTML = html;
  }

  function renderBracketCountdown(el, ms, type) {
    el.className = 'bk-tie__cd is-' + type;

    if (type === 'live') {
      el.innerHTML = `🟢 EN COURS`;
      return;
    }

    const t = formatCountdown(ms);
    if (!t) {
      el.innerHTML = `⏳ Bientôt`;
      return;
    }

    let txt = '';
    if (t.days > 0) txt += `${t.days}j `;
    txt += `${pad(t.hours)}:${pad(t.minutes)}:${pad(t.seconds)}`;
    el.innerHTML = `⏱ ${txt}`;
  }

  function tick() {
    const now = Date.now();

    // ---- FIXTURES PAGE ----
    document.querySelectorAll('[data-match-date][data-match-id]').forEach(function (item) {
      const isPlayed = item.getAttribute('data-is-played') === 'true';
      if (isPlayed) return;

      const dateStr  = item.getAttribute('data-match-date');
      const matchId  = item.getAttribute('data-match-id');

      // Countdown fixture
      const cdEl = document.getElementById('cd-' + matchId);
      // Countdown bracket
      const cdBkEl = document.getElementById('cd-bk-' + matchId);

      if (!cdEl && !cdBkEl) return;

      const { windowStart, windowEnd } = getMatchWindow(dateStr);
      const msToStart = windowStart.getTime() - now;
      const msToEnd   = windowEnd.getTime() - now;

      if (msToEnd <= 0) {
        // Fenêtre passée et match non joué
        if (cdEl)   { cdEl.className = 'fx-countdown'; cdEl.innerHTML = `<i class="fas fa-exclamation-triangle me-1" style="color:#ff6b6b;"></i>Fenêtre expirée`; }
        if (cdBkEl) { cdBkEl.className = 'bk-tie__cd'; cdBkEl.innerHTML = `⚠️ Expiré`; }
        return;
      }

      if (msToStart <= 0) {
        // Fenêtre ouverte = EN COURS
        if (cdEl)   renderCountdown(cdEl, 0, 'live');
        if (cdBkEl) renderBracketCountdown(cdBkEl, 0, 'live');
        return;
      }

      // Avant la fenêtre
      const hoursLeft = msToStart / (1000 * 60 * 60);
      const type = hoursLeft <= 24 ? 'soon' : 'far';

      if (cdEl)   renderCountdown(cdEl, msToStart, type);
      if (cdBkEl) renderBracketCountdown(cdBkEl, msToStart, type);
    });
  }

  // Démarrer le countdown
  document.addEventListener('DOMContentLoaded', function () {
    tick();
    setInterval(tick, 1000);
  });

})();