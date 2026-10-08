'use strict';

const $ = (selector) => document.querySelector(selector);

function el(tag, props = {}, ...kids) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (key === 'class') node.className = value;
    else if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
    else if (value !== false && value != null) node.setAttribute(key, value === true ? '' : value);
  }
  for (const kid of kids.flat()) {
    if (kid != null) node.append(kid.nodeType ? kid : document.createTextNode(kid));
  }
  return node;
}

const SVG_NS = 'http://www.w3.org/2000/svg';

function svgEl(tag, attrs = {}, ...kids) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  node.append(...kids);
  return node;
}

// Small interface glyphs: one 2.4 stroke, round caps, drawn on a 24 grid.
const GLYPHS = {
  heart: 'M12 20.5C5 15.2 3 11.8 3 8.8 3 6.3 5 4.5 7.3 4.5c1.8 0 3.4 1 4.7 2.9 1.3-1.9 2.9-2.9 4.7-2.9C19 4.5 21 6.3 21 8.8c0 3-2 6.4-9 11.7z',
  x: 'M6 6l12 12M18 6L6 18',
  check: 'M5 12.5l4.5 4.5L19 7.5',
  arrow: 'M5 12h14M13 6l6 6-6 6',
  gear: 'M12 8.8a3.2 3.2 0 1 0 0 6.4 3.2 3.2 0 1 0 0-6.4zM12 2.8v3M12 18.2v3M2.8 12h3M18.2 12h3M5.5 5.5l2.1 2.1M16.4 16.4l2.1 2.1M18.5 5.5l-2.1 2.1M7.6 16.4l-2.1 2.1',
  list: 'M9 6h11M9 12h11M9 18h11M4 6h.01M4 12h.01M4 18h.01',
};

// Six dots, drawn solid rather than stroked.
function gripGlyph() {
  const dots = [5, 12, 19].flatMap((cy) => [5, 11].map((cx) => svgEl('circle', {cx, cy, r: 2})));
  return svgEl('svg', {viewBox: '0 0 16 24', class: 'glyph', 'aria-hidden': 'true'}, svgEl('g', {fill: 'currentColor'}, ...dots));
}

function glyph(name, filled = false) {
  return svgEl('svg', {viewBox: '0 0 24 24', class: 'glyph', 'aria-hidden': 'true'},
    svgEl('path', {
      d: GLYPHS[name], pathLength: '1', fill: filled ? 'currentColor' : 'none', stroke: 'currentColor',
      'stroke-width': '2.4', 'stroke-linecap': 'round', 'stroke-linejoin': 'round',
    }));
}

// Weather drawings on a 64 grid. By night the sun becomes a moon.
const CLOUD = 'M20 46a10 10 0 0 1-2-19.8 14 14 0 0 1 26.5-3.7A11 11 0 0 1 48 46z';

function rays(cx, cy, from, to) {
  let d = '';
  for (let i = 0; i < 8; i++) {
    const a = i * Math.PI / 4;
    d += `M${(cx + from * Math.cos(a)).toFixed(1)} ${(cy + from * Math.sin(a)).toFixed(1)}`
      + `L${(cx + to * Math.cos(a)).toFixed(1)} ${(cy + to * Math.sin(a)).toFixed(1)}`;
  }
  return svgEl('path', {d, class: 'ray'});
}

function skyBody(night, cx, cy, r) {
  if (!night) return [rays(cx, cy, r + 6, r + 12), svgEl('circle', {cx, cy, r, class: 'sun'})];
  const d = `M${cx + r * 0.3} ${cy - r}A${r} ${r} 0 1 0 ${cx + r} ${cy + r * 0.35}A${r * 0.8} ${r * 0.8} 0 0 1 ${cx + r * 0.3} ${cy - r}Z`;
  return [svgEl('path', {d, class: 'moon'}),
    svgEl('circle', {cx: cx + r * 0.9, cy: cy - r * 0.9, r: 1.8, class: 'star'})];
}

function cloudAt(extra, cls = 'cloud') {
  return svgEl('path', {d: CLOUD, class: cls, ...extra});
}

function weatherIcon(kind, night) {
  const high = {transform: 'translate(0 -6)'};
  let parts;
  if (kind === 'clear') parts = skyBody(night, 32, 32, 11);
  else if (kind === 'partly') parts = [...skyBody(night, 24, 24, 8), cloudAt({transform: 'translate(10 12) scale(.8)'})];
  else if (kind === 'cloudy') parts = [cloudAt({transform: 'translate(14 -2) scale(.8)'}, 'cloud back'), cloudAt({transform: 'translate(-2 6)'})];
  else if (kind === 'fog') parts = [cloudAt(high), svgEl('path', {d: 'M14 46h36M20 53h30M14 60h24', class: 'mist'})];
  else if (kind === 'rain') parts = [cloudAt(high), ...[24, 33, 42].map((x) => svgEl('path', {d: `M${x} 46l-3 8`, class: 'drop'}))];
  else if (kind === 'snow') parts = [cloudAt(high), ...[[23, 50], [33, 57], [43, 50]].map(([cx, cy]) => svgEl('circle', {cx, cy, r: 2.8, class: 'flake'}))];
  else if (kind === 'storm') parts = [cloudAt(high, 'cloud storm'), svgEl('path', {d: 'M34 40 26 52h6l-3 9 11-14h-6l4-7z', class: 'bolt'})];
  else parts = [];
  return svgEl('svg', {viewBox: '0 0 64 64', class: 'wx', 'aria-hidden': 'true'}, ...parts);
}

let state = null;
let weather = null;
let showHidden = false;
let justChecked = null;
let lastNight = null;
let dragging = false;
let editing = false;
let editInput = null;
let abortDrag = null;
let abortEdit = null;
let pollSkipped = false;
let pendingSaves = 0;
let saveChain = Promise.resolve();
let when = 'today';
let showUpcoming = false;
let lastUndoId = null;
let undoTimer = null;
let addedTimer = null;
let settingsOpen = false;
let settingsBusy = 0;
let settingsChain = Promise.resolve();
let settingsTab = 'appearance';
let ruleForm = null;
let lastRulesSig = '';

// A request that hangs rejects like any other failure, so every pending flag gets cleared.
async function api(method, path, body, timeout = 15000) {
  const stop = new AbortController();
  const timer = setTimeout(() => stop.abort(), timeout);
  let response;
  let payload = null;
  try {
    response = await fetch(path, {
      method,
      headers: {'Content-Type': 'application/json'},
      body: body ? JSON.stringify(body) : undefined,
      signal: stop.signal,
    });
    try { payload = await response.json(); } catch (error) { /* not JSON */ }
  } finally {
    clearTimeout(timer);
  }
  if (!response.ok) {
    const failure = new Error(response.statusText);
    // The server words its own validation errors in plain language.
    failure.detail = payload && typeof payload.error === 'string' ? payload.error : '';
    throw failure;
  }
  return payload;
}

function setError(message) {
  const box = $('#error');
  box.textContent = message;
  box.hidden = !message;
}

async function act(method, path, body) {
  try {
    state = await api(method, path, body);
    setError('');
    render();
    return true;
  } catch (error) {
    setError("That didn't work. Try again.");
    return false;
  }
}

function undoneTodayIds() {
  return state.tasks.today.filter((task) => !task.done).map((task) => task.id);
}

function focusGrip(id) {
  const grip = $(`#task-list [data-id="${id}"] .grip`);
  if (grip) grip.focus();
}

// Send the full undone order. The screen moves first; a failure puts the last good state back.
function saveOrder(ids, focusId) {
  const before = state;
  const byId = new Map(state.tasks.today.map((task) => [task.id, task]));
  const done = state.tasks.today.filter((task) => task.done);
  state = {...state, tasks: {...state.tasks, today: [...ids.map((id) => byId.get(id)), ...done]}};
  render();
  if (focusId) focusGrip(focusId);
  pendingSaves += 1;
  saveChain = saveChain.then(async () => {
    try {
      const next = await api('POST', '/api/tasks/reorder', {ids});
      if (pendingSaves === 1) { state = next; setError(''); }
    } catch (error) {
      state = before;
      setError("That didn't work. Try again.");
    }
    pendingSaves -= 1;
    if (pendingSaves === 0) {
      render();
      if (focusId) focusGrip(focusId);
    }
  });
  return saveChain;
}

function moveByKey(event, task) {
  const step = event.key === 'ArrowUp' ? -1 : event.key === 'ArrowDown' ? 1 : 0;
  if (!step) return;
  event.preventDefault();
  const ids = undoneTodayIds();
  const from = ids.indexOf(task.id);
  const to = from + step;
  if (from < 0 || to < 0 || to >= ids.length) return;
  ids.splice(to, 0, ids.splice(from, 1)[0]);
  saveOrder(ids, task.id);
}

function zoomOf(node) {
  return node.offsetWidth ? node.getBoundingClientRect().width / node.offsetWidth || 1 : 1;
}

function startDrag(event, task, row) {
  if (event.button > 0 || dragging) return;
  event.preventDefault();
  const grip = event.currentTarget;
  const scroller = $('.scroll');
  const rows = [...$('#task-list').querySelectorAll('.task:not(.done)')];
  const others = rows.filter((item) => item !== row);
  // Large text zooms the page: CSS lengths and scrollTop count in zoomed units, pointer coordinates do not.
  const zoom = zoomOf(scroller);
  const startScroll = scroller.scrollTop;
  const mids = others.map((item) => {
    const box = item.getBoundingClientRect();
    return box.top + box.height / 2;
  });
  const grab = event.clientY - row.getBoundingClientRect().top;
  const slot = el('li', {class: 'drop-slot', 'aria-hidden': 'true'});
  let target = rows.indexOf(row);
  try { grip.setPointerCapture(event.pointerId); } catch (error) { /* no active pointer */ }
  row.classList.add('dragging');

  const place = () => {
    if (target < others.length) others[target].before(slot);
    else others[others.length - 1].after(slot);
  };
  const follow = (clientY) => {
    const edge = scroller.getBoundingClientRect();
    if (clientY < edge.top + 50) scroller.scrollTop -= 14 / zoom;
    else if (clientY > edge.bottom - 50) scroller.scrollTop += 14 / zoom;
    const scrolled = (scroller.scrollTop - startScroll) * zoom;
    target = mids.filter((m) => m - scrolled < clientY).length;
    if (others.length) place();
    row.style.transform = 'none';
    row.style.transform = `translateY(${(clientY - grab - row.getBoundingClientRect().top) / zoom}px)`;
  };
  const onMove = (move) => follow(move.clientY);
  const finish = (commit, redraw = true) => {
    if (!dragging) return;
    grip.removeEventListener('pointermove', onMove);
    grip.removeEventListener('pointerup', onUp);
    grip.removeEventListener('pointercancel', onCancel);
    grip.removeEventListener('lostpointercapture', onCancel);
    clearTimeout(watchdog);
    slot.remove();
    row.style.transform = '';
    row.classList.remove('dragging');
    dragging = false;
    abortDrag = null;
    const ids = undoneTodayIds();
    const at = ids.indexOf(task.id);
    if (at === -1) { if (redraw) render(); return; }
    ids.splice(at, 1);
    ids.splice(target, 0, task.id);
    if (!commit) { if (redraw) render(); return; }
    if (ids.join() !== undoneTodayIds().join()) saveOrder(ids, task.id);
    else if (pollSkipped) refresh();
  };
  const onUp = () => finish(true);
  const onCancel = () => finish(false);
  dragging = true;
  abortDrag = () => finish(false, false);
  // A drag that never ends (lost pointer) must not freeze the refresh forever.
  const watchdog = setTimeout(() => { if (abortDrag) { abortDrag(); render(); if (pollSkipped) refresh(); } }, 60 * 1000);
  grip.addEventListener('pointermove', onMove);
  grip.addEventListener('pointerup', onUp);
  grip.addEventListener('pointercancel', onCancel);
  grip.addEventListener('lostpointercapture', onCancel);
  follow(event.clientY);
}

function startEdit(task, title) {
  if (editing) return;
  editing = true;
  const input = el('input', {class: 'title-edit', type: 'text', value: task.title, maxlength: '200', 'aria-label': 'Task name'});
  editInput = input;
  let settled = false;
  let idle = null;
  const settle = async (save) => {
    if (settled) return;
    settled = true;
    clearTimeout(idle);
    editing = false;
    editInput = null;
    abortEdit = null;
    const next = input.value.trim();
    if (!save || !next || next === task.title) { render(); if (pollSkipped) refresh(); return; }
    // On failure keep the error on screen: re-render the old title but skip the catch-up poll.
    if (!(await act('PATCH', `/api/tasks/${task.id}`, {title: next}))) render();
  };
  // A wall display must not sit in an edit box forever (midnight rollover).
  abortEdit = () => { settled = true; clearTimeout(idle); editing = false; editInput = null; abortEdit = null; };
  const rest = () => { clearTimeout(idle); idle = setTimeout(() => settle(false), 2 * 60 * 1000); };
  input.addEventListener('input', rest);
  rest();
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') { event.preventDefault(); settle(true); }
    else if (event.key === 'Escape') { event.preventDefault(); settle(false); }
  });
  input.addEventListener('blur', () => settle(true));
  title.replaceWith(input);
  input.focus();
  input.select();
}

function taskRow(task, kind) {
  const check = el('button', {
    class: 'check' + (task.done ? ' on' : ''),
    'aria-label': task.done ? 'Mark not done' : 'Mark done',
    onclick: () => { if (!task.done) justChecked = task.id; act('POST', `/api/tasks/${task.id}/done`); },
  }, task.done ? glyph('check') : null);
  const popped = task.id === justChecked && task.done;
  if (popped) justChecked = null;
  const title = el('span', {class: 'title'}, task.title,
    kind === 'carryover' && task.count > 1 ? el('span', {class: 'days'}, `(${task.count} days)`) : null);
  const row = el('li', {class: 'task' + (task.done ? ' done' : '') + (popped ? ' pop' : '') + (kind === 'carryover' ? ' carry' : ''), 'data-id': task.id});
  if (kind === 'today') {
    row.append(task.done
      ? el('span', {class: 'grip-gap'})
      : el('button', {
        class: 'grip',
        'aria-label': 'Drag to reorder',
        onpointerdown: (event) => startDrag(event, task, row),
        onkeydown: (event) => moveByKey(event, task),
      }, gripGlyph()));
  }
  row.append(check, title);
  if (!task.done) {
    title.classList.add('editable');
    title.setAttribute('tabindex', '0');
    title.setAttribute('role', 'button');
    title.addEventListener('click', () => startEdit(task, title));
    title.addEventListener('keydown', (event) => { if (event.key === 'Enter') startEdit(task, title); });
    row.append(el('button', {class: 'ghost', onclick: () => act('POST', `/api/tasks/${task.id}/move`)}, 'Move to tomorrow'));
  }
  if (kind === 'carryover') {
    row.append(el('button', {class: 'ghost', onclick: () => act('POST', `/api/tasks/${task.id}/dismiss`)}, 'Dismiss'));
  } else if (task.source === 'manual') {
    row.append(el('button', {
      class: 'icon',
      'aria-label': 'Remove task',
      onclick: () => { if (confirm('Remove this task?')) act('DELETE', `/api/tasks/${task.id}`); },
    }, glyph('x')));
  }
  return row;
}

function renderProgress() {
  const total = state.tasks.today.length;
  const done = state.tasks.today.filter((task) => task.done).length;
  $('#progress').hidden = total === 0;
  $('#progress-text').textContent = `${done} of ${total} done`;
  $('#stitches').style.setProperty('--done', `${total ? Math.round(done / total * 100) : 0}%`);
}

function renderTasks() {
  // A drag or edit whose element was just replaced can never finish; let it go.
  if (dragging && abortDrag) abortDrag();
  renderProgress();
  const carry = $('#carryover');
  carry.replaceChildren();
  if (state.tasks.carryover.length) {
    carry.append(el('div', {class: 'group-label row'}, 'From yesterday',
      el('button', {class: 'ghost', onclick: () => act('POST', '/api/tasks/dismiss-carryover')}, 'Dismiss all')),
      el('ul', {}, state.tasks.carryover.map((t) => taskRow(t, 'carryover'))));
  }
  const list = $('#task-list');
  list.replaceChildren();
  if (!state.tasks.today.length) list.append(el('li', {class: 'empty'}, 'Nothing planned. Enjoy the day.'));
  for (const task of state.tasks.today) list.append(taskRow(task, 'today'));
  if (editing && abortEdit && !(editInput && editInput.isConnected)) abortEdit();
}

// Dates come from the server's day (state.date), never the browser clock.
function addDays(iso, n) {
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d + n)).toISOString().slice(0, 10);
}

function dateLabel(iso, weekday) {
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString('en-US', {
    timeZone: 'UTC', month: 'short', day: 'numeric', ...(weekday ? {weekday: 'short'} : {}),
  });
}

function renderWhen() {
  const box = $('#when');
  // Built once so keyboard focus survives re-renders; later calls only update the pressed state.
  if (!box.children.length) {
    box.append(...[['today', 'Today'], ['tomorrow', 'Tomorrow'], ['pick', 'Pick a date']].map(([key, label]) =>
      el('button', {type: 'button', 'data-when': key, onclick: () => {
        when = key;
        renderWhen();
        if (key === 'pick') $('#add-date').focus();
      }}, label)));
  }
  for (const button of box.children) button.setAttribute('aria-pressed', String(button.dataset.when === when));
  const date = $('#add-date');
  date.hidden = when !== 'pick';
  if (state) { date.min = state.date; date.max = addDays(state.date, 365); }
}

function renderUpcoming() {
  const list = state.tasks.upcoming || [];
  if (!list.length) showUpcoming = false;
  const toggle = $('#upcoming-toggle');
  toggle.hidden = list.length === 0;
  toggle.textContent = `Coming up (${list.length})`;
  toggle.onclick = () => { showUpcoming = !showUpcoming; renderUpcoming(); };
  const panel = $('#upcoming-panel');
  panel.hidden = !showUpcoming || list.length === 0;
  panel.replaceChildren(...list.map((task) => el('div', {class: 'rule-row'},
    el('span', {class: 'when'}, dateLabel(task.date, true)),
    el('span', {class: 'what'}, task.title),
    el('button', {
      class: 'icon',
      'aria-label': task.source === 'manual' ? 'Remove task' : 'Skip this one',
      onclick: () => {
        // Chores that repeat cannot be deleted, only skipped (which can be undone).
        if (task.source === 'manual') { if (confirm('Remove this task?')) act('DELETE', `/api/tasks/${task.id}`); }
        else if (confirm('Skip this one?')) act('POST', `/api/tasks/${task.id}/dismiss`);
      },
    }, glyph('x')))));
}

function hideUndo() {
  clearTimeout(undoTimer);
  $('#undo').hidden = true;
}

function renderUndo() {
  if (!state.undo) { lastUndoId = null; hideUndo(); return; }
  if (state.undo.id === lastUndoId) return;
  lastUndoId = state.undo.id;
  $('#undo-label').textContent = state.undo.label;
  $('#undo').hidden = false;
  clearTimeout(undoTimer);
  undoTimer = setTimeout(hideUndo, 8000);
}

function showAdded(iso) {
  const note = $('#added');
  note.textContent = `Added for ${dateLabel(iso)}`;
  clearTimeout(addedTimer);
  addedTimer = setTimeout(() => { note.textContent = ''; }, 4000);
}

// The kiosk window has no tabs, so recipe links are opened by the server in the default
// browser. If that fails the link still works as a plain new window.
function recipeLink(recipe, props, ...kids) {
  return el('a', {
    ...props,
    href: recipe.url,
    target: '_blank',
    rel: 'noopener',
    onclick: (event) => {
      event.preventDefault();
      api('POST', '/api/open', {url: recipe.url}).catch(() => window.open(recipe.url, '_blank', 'noopener'));
    },
  }, ...kids);
}

function dinnerCard(key, recipe) {
  const planned = recipe.url && allPlans().find((plan) => plan.date === state.date && plan.url === recipe.url);
  const meta = [recipe.protein ? `${recipe.protein}g protein` : null, `${recipe.carbs}g carbs`, `${recipe.minutes} min`].filter(Boolean);
  const tools = el('div', {class: 'tools'}, el('button', {
    class: 'icon' + (recipe.favorite ? ' on' : ''),
    'aria-label': recipe.favorite ? 'Remove from favorites' : 'Save as favorite',
    onclick: () => act('POST', `/api/dinners/${key}/favorite`, {recipeId: recipe.id}),
  }, glyph('heart', recipe.favorite)));
  if (key === 'v') {
    tools.append(el('button', {
      class: 'icon',
      'aria-label': 'Never show this again',
      onclick: () => act('POST', '/api/dinners/v/hide', {recipeId: recipe.id}),
    }, glyph('x')));
  }
  return el('article', {class: 'dinner' + (planned ? ' planned' : '')},
    el('h4', {}, recipe.name),
    el('p', {class: 'desc'}, planned ? 'Planned for tonight' : recipe.description),
    el('p', {class: 'meta'}, meta.map((text) => el('span', {class: 'tag'}, text))),
    el('div', {class: 'links'},
      recipeLink(recipe, {}, 'Get the recipe', glyph('arrow')),
      el('button', {
        type: 'button', class: 'icon' + (planned ? ' on' : ''), 'aria-label': planned ? "Open tonight's plan" : 'Plan this dinner',
        title: planned ? "Open tonight's plan" : 'Plan this dinner',
        onclick: () => (planned ? openPlan(planned.id) : planFromRecipe(key, recipe)),
      }, glyph('list'))),
    el('div', {class: 'row'},
      el('button', {class: 'ghost', onclick: () => act('POST', `/api/dinners/${key}/swap`, {recipeId: recipe.id})}, 'Not tonight, show another'),
      tools));
}

function renderDinners() {
  for (const key of ['chris', 'v']) {
    const data = state.dinners[key];
    const cards = $(`#${key} .cards`);
    cards.replaceChildren(...data.picks.map((recipe) => dinnerCard(key, recipe)));
  }
  const favs = $('#chris .favs');
  favs.replaceChildren();
  const favorites = state.dinners.chris.favorites;
  if (!favorites.length) favs.append(el('span', {class: 'empty'}, 'Tap the heart on a dinner to save it here'));
  for (const recipe of favorites) {
    favs.append(recipeLink(recipe, {class: 'chip'}, glyph('heart', true), recipe.name));
  }
  const hidden = state.dinners.v.hidden;
  const toggle = $('#hidden-toggle');
  toggle.hidden = hidden.length === 0;
  toggle.textContent = `Hidden recipes (${hidden.length})`;
  toggle.onclick = () => { showHidden = !showHidden; renderDinners(); };
  const panel = $('#hidden-panel');
  panel.hidden = !showHidden || hidden.length === 0;
  panel.replaceChildren(...hidden.map((recipe) => el('div', {class: 'hrow'},
    el('span', {}, recipe.name),
    el('button', {class: 'ghost', onclick: () => act('POST', '/api/dinners/v/restore', {recipeId: recipe.id})}, 'Restore'))));
}

function isNight() {
  const now = new Date();
  if (weather && weather.available) return now < new Date(weather.sunrise) || now > new Date(weather.sunset);
  return now.getHours() < 7 || now.getHours() >= 19;
}

// EPA US AQI bands; only worth a word when it is not Good.
function aqiWord(aqi) {
  if (aqi <= 50) return 'Good';
  if (aqi <= 100) return 'Moderate';
  if (aqi <= 150) return 'Unhealthy for some';
  return 'Unhealthy';
}

function weatherExtras() {
  const bits = [];
  if (weather.rainSoon >= 50) bits.push(`Rain likely soon (${weather.rainSoon}%): bring laundry in`);
  if (Number.isFinite(weather.aqi)) bits.push(`Air ${aqiWord(weather.aqi)} (${weather.aqi})`);
  return bits.length ? el('div', {class: 'w-meta small'}, bits.join(' · ')) : null;
}

function renderWeather() {
  const box = $('#weather');
  const outlook = $('#outlook');
  box.replaceChildren();
  outlook.replaceChildren();
  if (!weather || !weather.available) {
    box.append(el('div', {class: 'w-meta'}, 'Weather unavailable right now'));
    return;
  }
  const night = isNight();
  const updated = weather.stale
    ? el('div', {class: 'w-meta small'}, 'Updated ' + new Date(weather.updatedAt).toLocaleTimeString([], {hour: 'numeric', minute: '2-digit'}))
    : null;
  box.append(el('div', {class: 'window', 'data-kind': weather.kind, 'data-night': night}, weatherIcon(weather.kind, night)),
    el('div', {},
      el('div', {class: 'w-temp'}, `${weather.temp}°F`),
      el('div', {class: 'w-meta'}, `${weather.label} · H ${weather.high}° L ${weather.low}° · Rain ${weather.rain}%`),
      weatherExtras(),
      updated));
  for (const day of weather.outlook) {
    outlook.append(el('div', {class: 'day'},
      el('div', {class: 'dn'}, day.day),
      el('div', {class: 'ic'}, weatherIcon(day.kind, false)),
      el('div', {class: 'hi'}, `${day.high}°`)));
  }
}

let lastDate = null;

function render() {
  if (!state) return;
  // A new day: the add form starts again from Today, not from yesterday's pick.
  if (lastDate && state.date !== lastDate) { when = 'today'; $('#add-date').value = ''; }
  lastDate = state.date;
  $('#date').textContent = state.dateLabel;
  renderTasks();
  renderNudge();
  renderUpcoming();
  renderSoon();
  renderWhen();
  renderUndo();
  renderDinners();
  renderPlans();
  renderShopping();
  applyTheme();
  renderSettings();
}

// ---- Settings: appearance and repeating tasks ----
const DEFAULT_SETTINGS = {theme: 'auto', accent: 'blue', textSize: 'normal'};
const ACCENTS = ['blue', 'green', 'purple', 'orange', 'rose'];
const DAY_KEYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];
const DAY_NAMES = {mon: 'Monday', tue: 'Tuesday', wed: 'Wednesday', thu: 'Thursday', fri: 'Friday', sat: 'Saturday', sun: 'Sunday'};
const REPEAT_CHOICES = [['daily', 'Every day'], ['weekdays', 'Weekdays'], ['weekly', 'Chosen days'], ['biweekly', 'Every other week'], ['monthly', 'Monthly']];
const GENERIC_ERROR = "That didn't work. Try again.";

// The last settings seen are kept so a restart paints the right theme before the first fetch returns.
let cachedSettings = {};
try { cachedSettings = JSON.parse(localStorage.getItem('dashSettings')) || {}; } catch (error) { /* no storage */ }
let storedSig = JSON.stringify(cachedSettings);

function currentSettings() {
  return {...DEFAULT_SETTINGS, ...(state ? state.settings : cachedSettings)};
}

// Auto follows sunrise and sunset; Light and Dark force it. The weather drawings keep following
// real daylight, so a forced Light screen at night still shows the moon.
function applyTheme() {
  const settings = currentSettings();
  const night = isNight();
  const root = document.documentElement;
  const theme = settings.theme === 'light' || settings.theme === 'dark' ? settings.theme : night ? 'dark' : 'light';
  if (root.dataset.theme !== theme) root.dataset.theme = theme;
  if (root.dataset.accent !== settings.accent) root.dataset.accent = settings.accent;
  if (root.dataset.size !== settings.textSize) root.dataset.size = settings.textSize;
  if (lastNight !== null && night !== lastNight) renderWeather();
  lastNight = night;
  if (state) {
    const sig = JSON.stringify(settings);
    if (sig !== storedSig) {
      storedSig = sig;
      try { localStorage.setItem('dashSettings', sig); } catch (error) { /* no storage */ }
    }
  }
}

function joinNames(names) {
  return names.length < 2 ? names.join('') : `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`;
}

function ordinal(n) {
  const tail = n % 100;
  if (tail >= 11 && tail <= 13) return `${n}th`;
  return `${n}${{1: 'st', 2: 'nd', 3: 'rd'}[n % 10] || 'th'}`;
}

function ruleSummary(rule) {
  const days = DAY_KEYS.filter((key) => (rule.days || []).includes(key)).map((key) => DAY_NAMES[key]);
  if (rule.repeat === 'daily') return 'Every day';
  if (rule.repeat === 'weekdays') return 'Weekdays';
  if (rule.repeat === 'weekly') return days.length ? `Every ${joinNames(days)}` : 'Pick at least one day';
  if (rule.repeat === 'biweekly') return days.length ? `Every other ${joinNames(days)}` : 'Pick at least one day';
  if (rule.repeat === 'monthly') {
    const day = Number(rule.dayOfMonth);
    return Number.isInteger(day) && day >= 1 && day <= 31 ? `Monthly on the ${ordinal(day)}` : 'Pick a day from 1 to 31';
  }
  return '';
}

function pressedGroup(label, options, current, onPick) {
  const group = el('div', {class: 'seg', role: 'group', 'aria-label': label});
  for (const [value, text] of options) {
    group.append(el('button', {type: 'button', 'data-value': value, 'aria-pressed': String(value === current), onclick: () => onPick(value)}, text));
  }
  return group;
}

function buildAppearance() {
  const panel = $('#panel-appearance');
  const settings = currentSettings();
  const swatches = el('div', {class: 'swatches', role: 'group', 'aria-label': 'Colour'});
  for (const name of ACCENTS) {
    swatches.append(el('button', {type: 'button', class: 'swatch', 'data-value': name, 'data-name': name, 'aria-pressed': String(name === settings.accent), onclick: () => saveSetting('accent', name)},
      el('i', {}, glyph('check')), name[0].toUpperCase() + name.slice(1)));
  }
  panel.replaceChildren(
    el('div', {class: 'field'}, el('label', {}, 'Mode'),
      pressedGroup('Mode', [['auto', 'Auto'], ['light', 'Light'], ['dark', 'Dark']], settings.theme, (value) => saveSetting('theme', value)),
      el('p', {class: 'note'}, 'Auto follows sunrise and sunset.')),
    el('div', {class: 'field'}, el('label', {}, 'Colour'), swatches),
    el('div', {class: 'field'}, el('label', {}, 'Text size'),
      pressedGroup('Text size', [['normal', 'Normal'], ['large', 'Large']], settings.textSize, (value) => saveSetting('textSize', value))));
}

function syncAppearance() {
  const settings = currentSettings();
  const groups = {'Mode': settings.theme, 'Text size': settings.textSize, 'Colour': settings.accent};
  for (const group of $('#panel-appearance').querySelectorAll('[aria-label]')) {
    for (const button of group.children) button.setAttribute('aria-pressed', String(button.dataset.value === groups[group.getAttribute('aria-label')]));
  }
}

function saveSetting(key, value) {
  const previous = currentSettings()[key];
  if (previous === value) return;
  state = {...state, settings: {...currentSettings(), [key]: value}};
  applyTheme();
  syncAppearance();
  settingsBusy += 1;
  settingsChain = settingsChain.then(async () => {
    try {
      const next = await api('PUT', '/api/settings', {[key]: value});
      if (settingsBusy === 1) { state = next; setError(''); }
    } catch (error) {
      state = {...state, settings: {...state.settings, [key]: previous}};
      setError(GENERIC_ERROR);
    }
    settingsBusy -= 1;
    if (!settingsBusy) {
      render();
      if (pollSkipped) refresh();
    }
  });
}

function ruleBody(rule, changes = {}) {
  const {id, ...rest} = rule;
  return {...rest, ...changes};
}

function focusRuleButton(id, cls) {
  const button = $(`#rules-list [data-rule="${id}"] .${cls}`);
  if (button) button.focus();
}

// List actions report the server's own words when it gives any.
async function ruleAction(method, path, body) {
  try {
    state = await api(method, path, body);
    setError('');
    render();
    return true;
  } catch (failure) {
    setError(failure.detail || GENERIC_ERROR);
    return false;
  }
}

function ruleRow(rule) {
  return el('div', {class: 'rule-row' + (rule.paused ? ' paused' : ''), 'data-rule': rule.id},
    el('div', {class: 'what'}, rule.title, el('div', {class: 'when'}, ruleSummary(rule))),
    rule.paused ? el('span', {class: 'badge'}, 'Paused') : null,
    el('button', {type: 'button', class: 'ghost pause', onclick: async () => {
      if (await ruleAction('PUT', `/api/rules/${rule.id}`, ruleBody(rule, {paused: !rule.paused}))) focusRuleButton(rule.id, 'pause');
    }}, rule.paused ? 'Resume' : 'Pause'),
    el('button', {type: 'button', class: 'ghost edit', onclick: () => openRuleForm(rule)}, 'Edit'),
    el('button', {type: 'button', class: 'ghost remove', onclick: async () => {
      if (!confirm(`Delete "${rule.title}"? Tasks already on the list stay.`)) return;
      if (await ruleAction('DELETE', `/api/rules/${rule.id}`)) $('#add-rule').focus();
    }}, 'Delete'));
}

function renderRules() {
  const sig = JSON.stringify(state.rules || []);
  if (sig === lastRulesSig) return;
  lastRulesSig = sig;
  const rules = state.rules || [];
  $('#rules-list').replaceChildren(...(rules.length
    ? rules.map(ruleRow)
    : [el('p', {class: 'empty'}, 'Nothing repeats yet. Add one and it will show up on the right days.')]));
}

// Birthdays and countdowns: the next few show as one line under "Today's tasks"; they are managed in Settings > Dates.
function renderSoon() {
  const box = $('#soon');
  const dates = state.dates || {soon: [], moreSoon: 0};
  box.hidden = !dates.soon.length;
  box.replaceChildren(...dates.soon.map((item) =>
    el('span', {class: 'soon-item' + (item.days === 0 ? ' today' : '')}, `${item.label}: ${item.when.toLowerCase()}`)),
  ...(dates.moreSoon ? [el('span', {class: 'soon-item'}, `+${dates.moreSoon} more`)] : []));
}

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

function datesText(item) {
  return `${MONTHS[item.month - 1]} ${item.day}${item.year ? `, ${item.year}` : ''}`;
}

function buildDates() {
  const label = el('input', {id: 'date-label', type: 'text', maxlength: '100', autocomplete: 'off', placeholder: "Mom's birthday"});
  const month = el('select', {id: 'date-month', 'aria-label': 'Month'}, MONTHS.map((name, at) => el('option', {value: String(at + 1)}, name)));
  const day = el('input', {id: 'date-day', type: 'number', min: '1', max: '31', step: '1', inputmode: 'numeric', 'aria-label': 'Day', placeholder: 'Day'});
  const year = el('input', {id: 'date-year', type: 'number', min: '1900', max: '2200', step: '1', inputmode: 'numeric', 'aria-label': 'Year (leave empty to repeat every year)', placeholder: 'Year'});
  const error = el('p', {class: 'form-error', role: 'alert', hidden: true});
  const add = async (event) => {
    event.preventDefault();
    const body = {label: label.value, month: Number(month.value), day: day.value === '' ? null : Number(day.value), year: year.value === '' ? null : Number(year.value)};
    try {
      state = await api('POST', '/api/dates', body);
      label.value = day.value = year.value = '';
      error.hidden = true;
      render();
      label.focus();
    } catch (failure) {
      error.textContent = failure && failure.detail ? failure.detail : "That didn't work. Try again.";
      error.hidden = false;
    }
  };
  $('#panel-dates').replaceChildren(
    el('p', {class: 'note'}, "Birthdays and countdowns show under Today's tasks in the 30 days before. Leave the year empty to repeat every year."),
    el('form', {class: 'dates-form', onsubmit: add}, label, month, day, year, el('button', {type: 'submit', class: 'primary'}, 'Add')),
    error,
    el('div', {id: 'dates-list', class: 'rules-list'}));
}

function renderDatesList() {
  const list = $('#dates-list');
  if (!list || !state || !state.dates) return;
  list.replaceChildren(...(state.dates.items.length ? state.dates.items.map((item) => el('div', {class: 'rule-row'},
    el('div', {class: 'what'}, item.label, el('div', {class: 'when'}, `${datesText(item)} · ${item.when.toLowerCase()}${item.year ? '' : ', every year'}`)),
    el('button', {
      type: 'button', class: 'ghost', 'aria-label': `Remove ${item.label}`,
      onclick: () => act('DELETE', `/api/dates/${item.id}`),
    }, 'Remove'))) : [el('p', {class: 'note'}, 'Nothing here yet.')]));
}

function buildRules() {
  $('#panel-rules').replaceChildren(
    el('div', {id: 'rules-head', class: 'rules-head'},
      el('p', {class: 'note'}, 'These add themselves to the task list on the days you choose.'),
      el('button', {type: 'button', class: 'primary', id: 'add-rule', onclick: () => openRuleForm(null)}, 'Add a repeating task')),
    el('div', {id: 'rules-list', class: 'rules-list'}),
    el('div', {id: 'rule-form-box', class: 'rule-form-box', hidden: true}));
  lastRulesSig = '';
}

function openRuleForm(rule) {
  const draft = {
    title: rule ? rule.title : '',
    repeat: rule ? rule.repeat : 'daily',
    days: new Set(rule && rule.days ? rule.days : []),
    dayOfMonth: rule && rule.dayOfMonth ? String(rule.dayOfMonth) : '1',
  };
  ruleForm = {rule};
  const title = el('input', {id: 'rule-title', type: 'text', value: draft.title, maxlength: '200', autocomplete: 'off', placeholder: 'What needs doing?'});
  const summary = el('p', {class: 'summary', role: 'status'});
  const error = el('p', {class: 'form-error', role: 'alert', hidden: true});
  const dayField = el('fieldset', {class: 'field'}, el('legend', {}, 'On these days'),
    el('div', {class: 'daypick'}, DAY_KEYS.map((key) => el('button', {
      type: 'button', 'data-day': key, 'aria-label': DAY_NAMES[key], 'aria-pressed': String(draft.days.has(key)),
      onclick: (event) => {
        if (draft.days.has(key)) draft.days.delete(key); else draft.days.add(key);
        event.currentTarget.setAttribute('aria-pressed', String(draft.days.has(key)));
        update();
      },
    }, key[0].toUpperCase() + key.slice(1)))));
  const dayNumber = el('input', {id: 'rule-dom', type: 'number', min: '1', max: '31', step: '1', value: draft.dayOfMonth, inputmode: 'numeric'});
  const monthField = el('div', {class: 'field'}, el('label', {for: 'rule-dom'}, 'Day of the month'), dayNumber,
    el('p', {class: 'note'}, 'On the 29th to 31st, short months use their last day.'));
  const body = () => {
    const out = {title: draft.title.trim(), repeat: draft.repeat, paused: rule ? Boolean(rule.paused) : false};
    if (draft.repeat === 'weekly' || draft.repeat === 'biweekly') out.days = DAY_KEYS.filter((key) => draft.days.has(key));
    if (draft.repeat === 'biweekly' && rule && rule.repeat === 'biweekly' && rule.anchor) out.anchor = rule.anchor;
    if (draft.repeat === 'monthly') out.dayOfMonth = draft.dayOfMonth === '' ? null : Number(draft.dayOfMonth);
    return out;
  };
  const update = () => {
    dayField.hidden = !(draft.repeat === 'weekly' || draft.repeat === 'biweekly');
    monthField.hidden = draft.repeat !== 'monthly';
    summary.textContent = `Repeats: ${ruleSummary(body())}`;
  };
  const radios = el('fieldset', {class: 'field'}, el('legend', {}, 'Repeats'),
    el('div', {class: 'radios'}, REPEAT_CHOICES.map(([value, text]) => el('label', {class: 'radio'},
      el('input', {type: 'radio', name: 'rule-repeat', value, checked: value === draft.repeat, onchange: () => { draft.repeat = value; update(); }}), text))));
  title.addEventListener('input', () => { draft.title = title.value; });
  dayNumber.addEventListener('input', () => { draft.dayOfMonth = dayNumber.value; update(); });
  let saving = false;
  const form = el('form', {class: 'rule-form', novalidate: true, onsubmit: async (event) => {
    event.preventDefault();
    if (saving) return;
    saving = true;
    error.hidden = true;
    try {
      state = rule
        ? await api('PUT', `/api/rules/${rule.id}`, body())
        : await api('POST', '/api/rules', body());
      setError('');
      closeRuleForm();
      render();
      if (rule) focusRuleButton(rule.id, 'edit'); else $('#add-rule').focus();
    } catch (failure) {
      error.textContent = failure.detail || GENERIC_ERROR;
      error.hidden = false;
    } finally {
      saving = false;
    }
  }},
    el('h3', {class: 'form-title'}, rule ? 'Edit repeating task' : 'Add a repeating task'),
    el('div', {class: 'field'}, el('label', {for: 'rule-title'}, 'What needs doing?'), title),
    radios, dayField, monthField,
    el('div', {class: 'form-foot'}, el('div', {class: 'form-msgs'}, summary, error),
      el('div', {class: 'form-actions'},
        el('button', {type: 'button', class: 'ghost', onclick: () => { closeRuleForm(); renderSettings(); $('#add-rule').focus(); }}, 'Cancel'),
        el('button', {type: 'submit', class: 'primary'}, 'Save'))));
  update();
  $('#rules-head').hidden = true;
  $('#rules-list').hidden = true;
  const box = $('#rule-form-box');
  box.replaceChildren(form);
  box.hidden = false;
  title.focus();
}

function closeRuleForm() {
  ruleForm = null;
  const box = $('#rule-form-box');
  if (!box) return;
  box.replaceChildren();
  box.hidden = true;
  $('#rules-head').hidden = false;
  $('#rules-list').hidden = false;
  lastRulesSig = '';
}

function selectTab(name, focus) {
  settingsTab = name;
  for (const tab of $('#settings-tabs').children) {
    const on = tab.dataset.tab === name;
    tab.setAttribute('aria-selected', String(on));
    tab.tabIndex = on ? 0 : -1;
    if (on && focus) tab.focus();
  }
  $('#panel-appearance').hidden = name !== 'appearance';
  $('#panel-rules').hidden = name !== 'rules';
  $('#panel-dates').hidden = name !== 'dates';
  renderSettings();
}

function renderSettings() {
  if (!settingsOpen || !state) return;
  syncAppearance();
  if (!ruleForm) renderRules();
  renderDatesList();
}

function focusables() {
  return [...$('#settings .sheet').querySelectorAll('button, input, a[href]')]
    .filter((node) => !node.disabled && node.tabIndex >= 0 && !node.closest('[hidden]'));
}

let settingsIdle = null;

// A wall display left in Settings goes back to the dashboard on its own.
function restSettings() {
  clearTimeout(settingsIdle);
  settingsIdle = settingsOpen ? setTimeout(closeSettings, 4 * 60 * 1000) : null;
}

function openSettings() {
  if (settingsOpen || !state) return;
  settingsOpen = true;
  if (!$('#panel-appearance').children.length) buildAppearance();
  if (!$('#rules-list')) buildRules();
  if (!$('#dates-list')) buildDates();
  document.documentElement.classList.add('locked');
  $('.top').inert = true;
  $('main').inert = true;
  $('#plans-view').inert = true;
  $('#shopping-view').inert = true;
  $('#timers-view').inert = true;
  $('#settings').hidden = false;
  selectTab(settingsTab, false);
  (focusables()[0] || $('#settings-done')).focus();
  restSettings();
}

// Esc, the X and a tap outside back out one step: an open repeating-task form closes first (Done closes everything).
function backOutOfSettings() {
  if (ruleForm) { closeRuleForm(); renderSettings(); $('#add-rule').focus(); } else closeSettings();
}

function closeSettings() {
  if (!settingsOpen) return;
  settingsOpen = false;
  clearTimeout(settingsIdle);
  closeRuleForm();
  $('#settings').hidden = true;
  $('.top').inert = false;
  $('main').inert = false;
  $('#plans-view').inert = false;
  $('#shopping-view').inert = false;
  $('#timers-view').inert = false;
  document.documentElement.classList.remove('locked');
  $('#gear').focus();
  if (pollSkipped) refresh();
}

function initSettings() {
  $('#gear').append(glyph('gear'));
  $('#gear').addEventListener('click', openSettings);
  $('#settings-done').addEventListener('click', closeSettings);
  $('#settings-close').append(glyph('x'));
  $('#settings-close').addEventListener('click', backOutOfSettings);
  // The dark area outside the sheet closes it, but only when the press began there too (a text-select drag that ends outside must not).
  let pressedOutside = false;
  $('#settings').addEventListener('pointerdown', (event) => { pressedOutside = event.target === event.currentTarget; });
  $('#settings').addEventListener('click', (event) => { if (pressedOutside && event.target === event.currentTarget) backOutOfSettings(); pressedOutside = false; });
  const tabs = [['appearance', 'Appearance'], ['rules', 'Repeating tasks'], ['dates', 'Dates']];
  $('#settings-tabs').append(...tabs.map(([key, label], at) =>
    el('button', {type: 'button', class: 'tab', role: 'tab', 'data-tab': key, onclick: () => selectTab(key, false),
      onkeydown: (event) => {
        if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
          event.preventDefault();
          selectTab(tabs[(at + (event.key === 'ArrowLeft' ? -1 : 1) + tabs.length) % tabs.length][0], true);
        }
      }}, label)));
  for (const type of ['pointerdown', 'keydown', 'input']) $('#settings').addEventListener(type, restSettings);
  document.addEventListener('keydown', (event) => {
    if (!settingsOpen) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      backOutOfSettings();
      return;
    }
    if (event.key !== 'Tab') return;
    const nodes = focusables();
    if (!nodes.length) return;
    const first = nodes[0];
    const last = nodes[nodes.length - 1];
    if (!$('#settings .sheet').contains(document.activeElement)) { event.preventDefault(); first.focus(); }
    else if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });
}

// Screen care: at night, after 10 quiet minutes the screen dims. It never dims while a weather alert or a finished
// timer needs reading. The first touch only wakes it (swallowed, so a tap on a dim screen never acts by accident).
const IDLE_DIM_MS = 10 * 60 * 1000;
let lastInput = Date.now();
let wokeByTap = false;

function applyDim() {
  const quiet = isNight() && Date.now() - lastInput >= IDLE_DIM_MS
    && !document.body.classList.contains('has-alert') && !document.querySelector('.timer-chip.done');
  document.documentElement.toggleAttribute('data-dim', quiet);
}

function wake() {
  lastInput = Date.now();
  applyDim();
}

document.addEventListener('pointerdown', (event) => {
  if (document.documentElement.hasAttribute('data-dim')) { wokeByTap = true; event.stopPropagation(); event.preventDefault(); }
  wake();
}, true);
document.addEventListener('click', (event) => {
  if (wokeByTap) { wokeByTap = false; event.stopPropagation(); event.preventDefault(); }
}, true);
for (const type of ['pointermove', 'keydown']) document.addEventListener(type, wake, {passive: true});

function tick() {
  $('#time').textContent = new Date().toLocaleTimeString([], {hour: 'numeric', minute: '2-digit'});
  renderNudge();
  applyTheme();
  applyDim();
}

async function refresh() {
  if (dragging || editing || pendingSaves || settingsBusy || planFormOpen()) { pollSkipped = true; return; }
  pollSkipped = false;
  try {
    const next = await api('GET', '/api/state');
    if (dragging || editing || pendingSaves || settingsBusy || planFormOpen()) { pollSkipped = true; return; }
    state = next;
    setError('');
    render();
  } catch (error) { /* keep showing the last good state */ }
}

async function refreshWeather() {
  try {
    weather = await api('GET', '/api/weather', undefined, 30000);
  } catch (error) { /* keep the last weather */ }
  renderWeather();
  applyTheme();
}

$('#add-form').addEventListener('submit', (event) => {
  event.preventDefault();
  const input = $('#add-input');
  const title = input.value.trim();
  if (!title || !state) return;
  const body = {title};
  if (when === 'tomorrow') body.date = addDays(state.date, 1);
  else if (when === 'pick') {
    const picked = $('#add-date').value;
    if (!picked || picked < state.date || picked > addDays(state.date, 365)) {
      setError('Pick a day from today up to a year ahead.');
      $('#add-date').focus();
      return;
    }
    if (picked > state.date) body.date = picked;
  }
  act('POST', '/api/tasks', body).then((ok) => {
    if (ok) input.value = '';
    if (ok && body.date) showAdded(body.date);
    if (ok) { when = 'today'; $('#add-date').value = ''; renderWhen(); }
    input.focus();
  });
});

$('#undo-btn').addEventListener('click', () => { act('POST', '/api/undo', state.undo ? {id: state.undo.id} : undefined).then((ok) => { if (ok) hideUndo(); }); });

initSettings();
initViews();
initShopping();

document.addEventListener('visibilitychange', () => { if (!document.hidden) { refresh(); refreshWeather(); pollAlerts(); } });
setInterval(tick, 1000);
setInterval(refresh, 60 * 1000);
setInterval(refreshWeather, 10 * 60 * 1000);
setInterval(pollAlerts, 2 * 60 * 1000);
tick();
refresh();
refreshWeather();
pollAlerts();
