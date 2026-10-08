'use strict';

// Kitchen timers: a fourth screen with three presets and a visible countdown, no sound. Client side only;
// end times are kept in localStorage so a reload on the kiosk does not lose a running timer. The Timers tab
// shows the soonest countdown (or "Time's up") so it can be read from any screen. Uses el() and $() from
// app.js, so this file loads after it.
const TIMER_PRESETS = [[10, '10 min'], [30, '30 min'], [60, '1 hour']];
const TIMER_MAX = 4;
const TIMER_KEY = 'timers';
let timers = [];

function loadTimers() {
  try {
    const saved = JSON.parse(localStorage.getItem(TIMER_KEY));
    if (Array.isArray(saved)) timers = saved.filter((t) => t && Number.isFinite(t.end) && Number.isFinite(t.minutes)).slice(0, TIMER_MAX);
  } catch (error) { /* storage blocked or garbled: start with none */ }
}

function saveTimers() {
  try { localStorage.setItem(TIMER_KEY, JSON.stringify(timers)); } catch (error) { /* timers still run this session */ }
}

function timerText(ms) {
  const total = Math.max(0, Math.ceil(ms / 1000));
  const h = Math.floor(total / 3600);
  const m = String(Math.floor((total % 3600) / 60)).padStart(h ? 2 : 1, '0');
  const s = String(total % 60).padStart(2, '0');
  return h ? `${h}:${m}:${s}` : `${m}:${s}`;
}

function timerLabel(minutes) {
  return minutes === 60 ? '1 hour' : `${minutes} min`;
}

function startTimer(minutes) {
  if (timers.length >= TIMER_MAX) return;
  timers.push({end: Date.now() + minutes * 60000, minutes});
  saveTimers();
  renderTimers();
}

function clearTimer(timer) {
  timers = timers.filter((t) => t !== timer);
  saveTimers();
  renderTimers();
}

function timerChip(timer) {
  const left = timer.end - Date.now();
  const done = left <= 0;
  return el('div', {class: 'timer-chip' + (done ? ' done' : ''), role: done ? 'alert' : null},
    el('span', {class: 'timer-time', 'data-end': timer.end}, done ? "Time's up" : timerText(left)),
    el('span', {class: 'timer-of'}, timerLabel(timer.minutes)),
    el('button', {
      type: 'button', class: 'timer-x', 'aria-label': done ? `Dismiss ${timerLabel(timer.minutes)} timer` : `Cancel ${timerLabel(timer.minutes)} timer`,
      onclick: () => clearTimer(timer),
    }, done ? 'OK' : 'Cancel'));
}

// The tab reads "Timers", "Timers 9:58" (soonest running) or "Time's up" (any finished).
function updateTimersTab() {
  const tab = $('#tab-timers');
  const now = Date.now();
  const done = timers.some((t) => t.end <= now);
  const soonest = Math.min(...timers.filter((t) => t.end > now).map((t) => t.end));
  tab.textContent = done ? "Time's up" : Number.isFinite(soonest) ? `Timers ${timerText(soonest - now)}` : 'Timers';
  tab.classList.toggle('timer-done', done);
}

function renderTimers() {
  const full = timers.length >= TIMER_MAX;
  $('#timer-presets').replaceChildren(...TIMER_PRESETS.map(([minutes, text]) =>
    el('button', {type: 'button', class: 'ghost timer-preset', disabled: full, onclick: () => startTimer(minutes)}, text)));
  $('#timer-list').replaceChildren(...(timers.length ? timers.map(timerChip) : [el('p', {class: 'timer-empty'}, 'No timers running.')]));
  updateTimersTab();
}

function tickTimers() {
  const finished = timers.some((t) => t.end <= Date.now() && !document.querySelector(`.timer-chip.done [data-end="${t.end}"]`));
  if (finished) {
    renderTimers(); // a timer just finished: repaint into its "Time's up" state
    return;
  }
  for (const node of document.querySelectorAll('.timer-time[data-end]')) {
    const left = Number(node.dataset.end) - Date.now();
    if (left > 0) node.textContent = timerText(left);
  }
  updateTimersTab();
}

loadTimers();
renderTimers();
setInterval(tickTimers, 1000);
