'use strict';

// Dinner plans: the second screen. Loaded before app.js, so it only uses app.js's helpers
// ($, el, glyph, api, act, state, render ...) when a function runs, never at load time.

const SCREENS = [['today', 'Today'], ['plans', 'Dinner plans'], ['shopping', 'Shopping list'], ['timers', 'Timers']];
const PANELS = {today: 'today-view', plans: 'plans-view', shopping: 'shopping-view', timers: 'timers-view'};
let activeScreen = 'today';
let openPlanId = null;
let planForm = null;
let planFormIdle = null;

function planFormOpen() {
  return planForm !== null;
}

function selectView(name, focus) {
  activeScreen = name;
  for (const tab of $('#views').children) {
    const on = tab.dataset.view === name;
    tab.setAttribute('aria-selected', String(on));
    tab.tabIndex = on ? 0 : -1;
    if (on && focus) tab.focus();
  }
  $('main').hidden = name !== 'today';
  $('#plans-view').hidden = name !== 'plans';
  $('#shopping-view').hidden = name !== 'shopping';
  $('#timers-view').hidden = name !== 'timers';
}

function initViews() {
  $('#views').append(...SCREENS.map(([key, label]) =>
    el('button', {type: 'button', class: 'view-tab', id: 'tab-' + key, role: 'tab', 'aria-controls': PANELS[key], 'data-view': key, onclick: () => selectView(key, false),
      onkeydown: (event) => {
        if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(event.key)) {
          event.preventDefault();
          const step = ['ArrowUp', 'ArrowLeft'].includes(event.key) ? -1 : 1;
          const at = SCREENS.findIndex(([name]) => name === key);
          selectView(SCREENS[(at + step + SCREENS.length) % SCREENS.length][0], true);
        }
      }}, label)));
  $('#plan-new').addEventListener('click', () => { selectView('plans', false); openForm(null); });
  selectView('today', false);
}

// ---- Times: plan times are "HH:MM" on a 24-hour clock ----
function clock12(hhmm) {
  const [h, m] = hhmm.split(':').map(Number);
  return `${h % 12 || 12}:${String(m).padStart(2, '0')} ${h < 12 ? 'AM' : 'PM'}`;
}

function addMinutes(hhmm, minutes) {
  const [h, m] = hhmm.split(':').map(Number);
  const total = (((h * 60 + m + minutes) % 1440) + 1440) % 1440;
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
}

function readyLine(plan) {
  return plan.startTime && plan.prepMinutes ? `Ready around ${clock12(addMinutes(plan.startTime, plan.prepMinutes))}` : '';
}

function prepLabel(minutes) {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return [hours ? `${hours} hr` : '', rest || !hours ? `${rest} min` : ''].filter(Boolean).join(' ');
}

function doneCount(items) {
  return items.filter((item) => item.done).length;
}

// ---- Data helpers ----
function allPlans() {
  return state && state.plans ? state.plans.items : [];
}

function findPlan(id) {
  return allPlans().find((plan) => plan.id === id) || null;
}

function currentPlan() {
  let plan = findPlan(openPlanId);
  if (!plan) {
    plan = allPlans()[0] || null;
    openPlanId = plan ? plan.id : null;
  }
  return plan;
}

// Like act(), but hands back the response (for planId) or a plain-language error instead of the global banner.
async function planCall(method, path, body) {
  try {
    const payload = await api(method, path, body);
    state = payload;
    setError('');
    return {payload};
  } catch (error) {
    return {error: error.detail || GENERIC_ERROR};
  }
}

// ---- The list ----
function planGroups(items, today) {
  return [
    ['Today', items.filter((plan) => plan.date === today)],
    ['Coming up', items.filter((plan) => plan.date > today)],
    ['Earlier', items.filter((plan) => plan.date < today)],
  ].filter(([, list]) => list.length);
}

function planRow(plan) {
  const bits = [];
  if (plan.date !== state.date) bits.push(dateLabel(plan.date, true));
  if (plan.startTime) bits.push(clock12(plan.startTime));
  if (plan.steps.length) bits.push(`${doneCount(plan.steps)} of ${plan.steps.length} steps`);
  return el('button', {
    type: 'button', class: 'plan-row', 'data-key': `plan-${plan.id}`, 'aria-current': String(plan.id === openPlanId),
    onclick: () => { if (planFormOpen()) return; openPlanId = plan.id; renderPlans(); },
  }, el('span', {class: 'name', title: plan.title}, plan.title), el('span', {class: 'sub'}, bits.join(' · ') || 'Tap to open'));
}

function renderPlanList() {
  const groups = planGroups(allPlans(), state.date);
  $('#plan-list').replaceChildren(...(groups.length
    ? groups.flatMap(([label, list]) => [el('div', {class: 'group-label'}, label), ...list.map(planRow)])
    : [el('p', {class: 'empty'}, 'No dinner plans yet. Tap New dinner plan to start.')]));
}

// ---- The open plan ----
function stepRow(plan, kind, item) {
  return el('button', {
    type: 'button', class: 'step-row' + (item.done ? ' done' : ''), role: 'checkbox', 'aria-checked': String(item.done),
    'data-key': `${kind}-${item.id}`,
    onclick: () => act('POST', `/api/plans/${plan.id}/check`, {kind, itemId: item.id}),
  }, el('span', {class: 'check' + (item.done ? ' on' : '')}, item.done ? glyph('check') : null), el('span', {class: 'text'}, item.text));
}

function itemColumn(plan, kind, title, noun, empty) {
  const items = plan[kind];
  return el('div', {class: 'plan-col'},
    el('div', {class: 'col-head'}, el('h3', {}, title),
      items.length ? el('span', {class: 'count'}, `${doneCount(items)} of ${items.length} ${noun}`) : null),
    items.length
      ? el('ul', {class: 'items'}, ...items.map((item) => el('li', {}, stepRow(plan, kind, item))))
      : el('p', {class: 'empty'}, empty));
}

function planMeta(plan) {
  const tags = [];
  if (plan.prepMinutes) tags.push(`Prep ${prepLabel(plan.prepMinutes)}`);
  if (plan.startTime) tags.push(`Start ${clock12(plan.startTime)}`);
  if (readyLine(plan)) tags.push(readyLine(plan));
  if (plan.date !== state.date) tags.push(dateLabel(plan.date, true));
  return el('p', {class: 'plan-meta'}, ...tags.map((text) => el('span', {class: 'tag'}, text)),
    plan.url ? recipeLink(plan, {class: 'plan-link'}, 'Get the recipe', glyph('arrow')) : null);
}

async function cookAgain(plan) {
  const result = await planCall('POST', `/api/plans/${plan.id}/copy`);
  if (result.error) { setError(result.error); return; }
  openPlanId = result.payload.planId;
  render();
}

// The "Added N items" line shown next to the button for a few seconds; kept here so a re-render does not lose it.
let planShopNote = null;
let planShopTimer = null;

function paintShopNote() {
  const box = document.getElementById('plan-shop-status');
  if (!box) return;
  const text = planShopNote && planShopNote.planId === openPlanId ? planShopNote.text : '';
  box.textContent = text;
  box.hidden = !text;
}

async function addPlanToShopping(plan) {
  const result = await planCall('POST', `/api/plans/${plan.id}/shopping`);
  let text;
  if (result.error) text = result.error;
  else {
    const added = result.payload.added || 0;
    text = added ? (added === 1 ? 'Added 1 item' : `Added ${added} items`) : 'Already on the list';
  }
  planShopNote = {planId: plan.id, text};
  clearTimeout(planShopTimer);
  planShopTimer = setTimeout(() => { planShopNote = null; paintShopNote(); }, 4000);
  if (result.error) paintShopNote(); else render();
}

function renderPlanDetail() {
  const plan = currentPlan();
  if (!plan) {
    $('#plan-detail').replaceChildren(el('p', {class: 'empty'}, 'Pick a dinner plan, or tap New dinner plan.'));
    return;
  }
  $('#plan-detail').replaceChildren(
    el('div', {class: 'plan-top'},
      el('h2', {title: plan.title}, plan.title),
      el('div', {class: 'plan-actions'},
        el('button', {type: 'button', class: 'ghost', onclick: () => openForm(plan)}, 'Edit'),
        el('button', {type: 'button', class: 'ghost', onclick: () => cookAgain(plan)}, 'Cook again'),
        plan.ingredients.some((item) => !item.done)
          ? el('button', {type: 'button', class: 'ghost', 'data-key': 'plan-shop', onclick: () => addPlanToShopping(plan)}, 'Add to shopping list')
          : null,
        el('button', {type: 'button', class: 'ghost', onclick: () => { if (confirm('Delete this plan?')) act('DELETE', `/api/plans/${plan.id}`); }}, 'Delete'))),
    planMeta(plan),
    el('p', {class: 'plan-shop-status', id: 'plan-shop-status', role: 'status', hidden: true}),
    el('div', {class: 'plan-cols'},
      itemColumn(plan, 'ingredients', 'Ingredients', 'gathered', 'No ingredients yet. Tap Edit to add them.'),
      itemColumn(plan, 'steps', 'Steps', 'steps done', 'No steps yet. Tap Edit to add them.')));
  paintShopNote();
}

// A re-render replaces the buttons, so put focus and each column's scroll position back afterwards.
function keepFocus(build) {
  const active = document.activeElement;
  const key = active && active.dataset ? active.dataset.key : null;
  const scrolls = [...document.querySelectorAll('#plan-detail .items')].map((box) => box.scrollTop);
  build();
  document.querySelectorAll('#plan-detail .items').forEach((box, i) => { box.scrollTop = scrolls[i] || 0; });
  if (key) {
    const again = document.querySelector(`[data-key="${CSS.escape(key)}"]`);
    if (again) again.focus();
  }
}

function renderPlans() {
  if (!state) return;
  if (planForm) return; // never rebuild a form being typed in
  keepFocus(() => { renderPlanList(); renderPlanDetail(); });
}

// ---- Create / edit form ----
function lineList(text) {
  return text.split('\n').map((line) => line.trim()).filter(Boolean);
}

function closeForm(openId) {
  clearTimeout(planFormIdle);
  planForm = null;
  if (openId) openPlanId = openId;
  render();
  if (pollSkipped) refresh();
}

// A wall display left on a half-filled form goes back to the list on its own, so the day can still roll over.
function restForm() {
  clearTimeout(planFormIdle);
  planFormIdle = planForm ? setTimeout(() => closeForm(null), 10 * 60 * 1000) : null;
}

function formField(label, ...kids) {
  return el('div', {class: 'field'}, el('label', {}, label), ...kids);
}

function openForm(plan) {
  planForm = {id: plan ? plan.id : null, when: 'today'};
  const today = state.date;
  if (plan && plan.date !== today) planForm.when = plan.date === addDays(today, 1) ? 'tomorrow' : 'pick';

  const title = el('input', {id: 'plan-title', type: 'text', maxlength: '200', autocomplete: 'off', placeholder: 'What are you making?', value: plan ? plan.title : ''});
  const date = el('input', {id: 'plan-date', type: 'date', min: addDays(today, -60), max: addDays(today, 365), value: plan ? plan.date : today, 'aria-label': 'Pick a date'});
  const prep = el('input', {id: 'plan-prep', type: 'number', min: '1', max: '600', inputmode: 'numeric', value: plan && plan.prepMinutes ? String(plan.prepMinutes) : ''});
  const start = el('input', {id: 'plan-start', type: 'time', value: plan ? plan.startTime : ''});
  const dinner = el('input', {id: 'plan-dinner', type: 'time'});
  const ingredients = el('textarea', {id: 'plan-ingredients', placeholder: 'One ingredient per line'}, plan ? plan.ingredients.map((item) => item.text).join('\n') : '');
  const steps = el('textarea', {id: 'plan-steps', placeholder: 'One step per line'}, plan ? plan.steps.map((item) => item.text).join('\n') : '');
  const ready = el('p', {class: 'summary', role: 'status'});
  const error = el('p', {class: 'form-error', role: 'alert', hidden: true});
  const save = el('button', {type: 'submit', class: 'primary'}, 'Save');

  const showError = (message) => { error.textContent = message; error.hidden = !message; };
  const paintReady = () => {
    const minutes = Number(prep.value);
    ready.textContent = start.value && minutes ? `Ready around ${clock12(addMinutes(start.value, minutes))}` : '';
  };
  const whenBox = el('div', {class: 'seg', role: 'group', 'aria-label': 'When'},
    ...[['today', 'Today'], ['tomorrow', 'Tomorrow'], ['pick', 'Pick a date']].map(([key, label]) =>
      el('button', {type: 'button', 'data-when': key, onclick: () => { planForm.when = key; paintWhen(); if (key === 'pick') date.focus(); }}, label)));
  const paintWhen = () => {
    for (const button of whenBox.children) button.setAttribute('aria-pressed', String(button.dataset.when === planForm.when));
    date.hidden = planForm.when !== 'pick';
  };
  const chosenDate = () => (planForm.when === 'today' ? today : planForm.when === 'tomorrow' ? addDays(today, 1) : date.value);

  dinner.addEventListener('change', () => {
    if (!dinner.value) return;
    const minutes = Number(prep.value);
    if (!Number.isInteger(minutes) || minutes < 1) { showError('Enter the prep time first, then Dinner at can set the start time.'); return; }
    start.value = addMinutes(dinner.value, -minutes);
    showError('');
    paintReady();
  });
  prep.addEventListener('input', paintReady);
  start.addEventListener('input', paintReady);

  const submit = async (event) => {
    event.preventDefault();
    const thisForm = planForm;
    const body = {
      title: title.value,
      date: chosenDate(),
      prepMinutes: prep.value.trim() === '' ? null : Number(prep.value),
      startTime: start.value,
      ingredients: lineList(ingredients.value),
      steps: lineList(steps.value),
    };
    save.disabled = true;
    const result = plan ? await planCall('PUT', `/api/plans/${plan.id}`, body) : await planCall('POST', '/api/plans', body);
    save.disabled = false;
    if (result.error) { showError(result.error); return; }
    if (planForm === thisForm) closeForm(plan ? plan.id : result.payload.planId);
  };

  const form = el('form', {class: 'plan-form', novalidate: true, onsubmit: submit,
    onkeydown: (event) => { if (event.key === 'Escape') { event.preventDefault(); if (!save.disabled) closeForm(null); } }},
    el('h2', {}, plan ? 'Edit dinner plan' : 'New dinner plan'),
    formField('Dinner', title),
    el('div', {class: 'form-row'},
      formField('Day', whenBox, date),
      formField('Prep time (minutes)', prep),
      formField('Start time', start),
      formField('Dinner at (optional)', dinner)),
    ready,
    el('div', {class: 'form-row lists'},
      formField('Ingredients', ingredients),
      formField('Steps', steps)),
    el('div', {class: 'form-foot'},
      el('div', {class: 'form-msgs'}, error),
      el('div', {class: 'form-actions'},
        el('button', {type: 'button', class: 'ghost', onclick: () => { if (!save.disabled) closeForm(null); }}, 'Cancel'),
        save)));
  $('#plan-detail').replaceChildren(form);
  for (const type of ['pointerdown', 'keydown', 'input']) form.addEventListener(type, restForm);
  paintWhen();
  paintReady();
  restForm();
  (plan && plan.title ? ingredients : title).focus();
}

// ---- Today screen hooks ----
function openPlan(id) {
  if (planFormOpen()) return;
  openPlanId = id;
  selectView('plans', false);
  renderPlans();
}

function nowHHMM() {
  const now = new Date();
  return `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
}

// Runs every second from tick(); only touches the page when the wording changes.
function renderNudge() {
  const pill = $('#nudge');
  const nudge = state && state.plans ? state.plans.nudge : null;
  if (!nudge) { pill.hidden = true; return; }
  const late = nowHHMM() >= nudge.startTime;
  const text = late ? 'Time to start dinner' : `Start dinner at ${clock12(nudge.startTime)}`;
  if (pill.textContent !== text) pill.textContent = text;
  if (pill.title !== nudge.title) pill.title = nudge.title;
  pill.classList.toggle('now', late);
  pill.hidden = false;
  pill.onclick = () => openPlan(nudge.id);
}

async function planFromRecipe(key, recipe) {
  if (planFormOpen()) return;
  const result = await planCall('POST', `/api/dinners/${key}/plan`, {recipeId: recipe.id});
  if (result.error) { setError(result.error); return; }
  openPlanId = result.payload.planId;
  const plan = findPlan(openPlanId);
  render();
  selectView('plans', false);
  if (plan && !plan.ingredients.length && !plan.steps.length) openForm(plan);
}
