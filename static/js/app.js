/* Mohtavam — theme, sidebar, icons, shared UI */

(function () {
  const STORAGE_KEY = 'mohtavam-theme';

  function getPreferredTheme() {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === 'light' || saved === 'dark') return saved;
    return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(STORAGE_KEY, theme);
    const sun = document.querySelector('[data-theme-icon="sun"]');
    const moon = document.querySelector('[data-theme-icon="moon"]');
    if (sun && moon) {
      sun.style.display = theme === 'dark' ? 'none' : 'block';
      moon.style.display = theme === 'dark' ? 'block' : 'none';
    }
    if (typeof lucide !== 'undefined') lucide.createIcons();
  }

  window.refreshIcons = function () {
    if (typeof lucide !== 'undefined') lucide.createIcons();
  };

  window.toggleTheme = function () {
    const current = document.documentElement.getAttribute('data-theme') || 'dark';
    applyTheme(current === 'dark' ? 'light' : 'dark');
  };

  window.openSidebar = function () {
    document.getElementById('sidebar')?.classList.add('open');
    document.getElementById('sidebarOverlay')?.classList.add('show');
  };

  window.closeSidebar = function () {
    document.getElementById('sidebar')?.classList.remove('open');
    document.getElementById('sidebarOverlay')?.classList.remove('show');
  };

  window.togglePicker = function (id) {
    const p = document.getElementById('picker-' + id);
    if (p) p.style.display = p.style.display === 'none' ? 'block' : 'none';
  };

  window.showTab = function (btn, gridId) {
    const picker = btn.closest('.emoji-picker');
    picker.querySelectorAll('.emoji-grid').forEach((g) => (g.style.display = 'none'));
    picker.querySelectorAll('.etab').forEach((t) => t.classList.remove('active'));
    const grid = document.getElementById('grid-' + gridId);
    if (grid) grid.style.display = 'flex';
    btn.classList.add('active');
  };

  window.insertText = function (id, val) {
    const ta = document.getElementById(id);
    if (!ta) return;
    const s = ta.selectionStart;
    const e = ta.selectionEnd;
    ta.value = ta.value.substring(0, s) + val + ta.value.substring(e);
    ta.selectionStart = ta.selectionEnd = s + val.length;
    ta.focus();
    ta.dispatchEvent(new Event('input'));
  };

  window.ins = window.insertText;

  window.toggleRule = function (ruleId, type) {
    fetch(`/${type}-rule/${ruleId}/toggle`, { method: 'POST' })
      .then((r) => r.json())
      .then((data) => {
        const card = document.getElementById('rule-' + ruleId);
        if (!card) return;
        card.classList.toggle('rule-inactive', !data.active);
        const badge = card.querySelector('.rule-status-badge');
        if (badge) {
          const dot = badge.querySelector('.status-dot');
          if (dot) dot.className = 'status-dot ' + (data.active ? 'on' : 'off');
          const label = badge.querySelector('.status-label');
          if (label) label.textContent = data.active ? 'فعال' : 'غیرفعال';
          badge.className = 'badge ' + (data.active ? 'ok' : '') + ' rule-status-badge';
        }
      });
  };

  document.addEventListener('DOMContentLoaded', function () {
    applyTheme(getPreferredTheme());
    window.refreshIcons();

    document.querySelectorAll('select').forEach((sel) => {
      if (sel.closest('.select-wrap')) return;
      const wrap = document.createElement('div');
      wrap.className = 'select-wrap';
      sel.parentNode.insertBefore(wrap, sel);
      wrap.appendChild(sel);
    });

    document.querySelectorAll('textarea[id]').forEach((ta) => {
      const counter = document.getElementById('count_' + ta.id) || document.getElementById('charcount');
      if (counter) {
        const update = () => (counter.textContent = ta.value.length + ' کاراکتر');
        ta.addEventListener('input', update);
        update();
      }
    });

    setTimeout(() => {
      document.querySelectorAll('.flash').forEach((f) => {
        f.style.transition = 'opacity .35s, transform .35s';
        f.style.opacity = '0';
        f.style.transform = 'translateY(-4px)';
        setTimeout(() => f.remove(), 350);
      });
    }, 4000);
  });
})();
