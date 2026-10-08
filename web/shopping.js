'use strict';

// Shopping list: the third screen. Loaded after plans.js and before app.js, so it only uses app.js's
// helpers ($, el, glyph, api, setError, state, render ...) when a function runs, never at load time.

let shoppingBusy = false;
let shoppingSig = null;

// Like planCall(): keeps the new snapshot and hands back the response or a plain-language error.
// Unlike act(), the caller decides where a failure is shown (the add field has its own line).
async function shoppingCall(method, path, body) {
  try {
    const payload = await api(method, path, body);
    state = payload;
    setError('');
    showShoppingError('');
    render();
    return {payload};
  } catch (error) {
    return {error: error.detail || GENERIC_ERROR};
  }
}

function showShoppingError(message) {
  const box = $('#shopping-error');
  box.textContent = message;
  box.hidden = !message;
}

async function addShoppingItem(event) {
  event.preventDefault();
  if (shoppingBusy) return;
  const input = $('#shopping-input');
  const sent = input.value;
  shoppingBusy = true;
  const result = await shoppingCall('POST', '/api/shopping', {text: input.value});
  shoppingBusy = false;
  if (result.error) { showShoppingError(result.error); return; }
  showShoppingError('');
  if (input.value === sent) input.value = '';
  input.focus();
}

async function shoppingAction(method, path) {
  const result = await shoppingCall(method, path);
  if (result.error) setError(result.error);
}

function shoppingRow(item) {
  return el('li', {class: 'shopping-row' + (item.done ? ' done' : '')},
    el('button', {
      type: 'button', class: 'check shopping-tick' + (item.done ? ' on' : ''), 'aria-pressed': String(item.done),
      'aria-label': `Mark ${item.text} ${item.done ? 'not bought' : 'bought'}`, 'data-key': `shop-tick-${item.id}`,
      onclick: () => shoppingAction('POST', `/api/shopping/${item.id}/check`),
    }, item.done ? glyph('check') : null),
    el('span', {class: 'text', title: item.text}, item.text),
    el('button', {
      type: 'button', class: 'icon shopping-remove', 'aria-label': `Remove ${item.text}`, 'data-key': `shop-remove-${item.id}`,
      onclick: () => shoppingAction('DELETE', `/api/shopping/${item.id}`),
    }, glyph('x')));
}

// A re-render replaces the buttons, so put focus and the list's scroll position back afterwards.
function keepFocusShopping(build) {
  const active = document.activeElement;
  const key = active && active.dataset ? active.dataset.key : null;
  const box = $('#shopping-list');
  const scroll = box.scrollTop;
  build();
  box.scrollTop = scroll;
  if (key) {
    const again = document.querySelector(`[data-key="${CSS.escape(key)}"]`);
    if (again) again.focus();
  }
}

function renderShopping() {
  if (!state) return;
  const items = Array.isArray(state.shopping) ? state.shopping : [];
  const sig = JSON.stringify(items);
  if (sig === shoppingSig) return; // nothing changed; leave the page (and any tap in progress) alone
  shoppingSig = sig;
  const bought = items.filter((item) => item.done).length;
  $('#shopping-count').textContent = items.length ? `${bought} of ${items.length} bought` : '';
  $('#shopping-count').hidden = !items.length;
  $('#shopping-clear').hidden = !bought;
  keepFocusShopping(() => {
    $('#shopping-list').replaceChildren(items.length
      ? el('ul', {class: 'shopping-items'}, ...items.map(shoppingRow))
      : el('p', {class: 'empty'}, 'Nothing on the list. Type what you need above.'));
  });
}

function initShopping() {
  $('#shopping-add').addEventListener('submit', addShoppingItem);
  $('#shopping-input').addEventListener('input', () => showShoppingError(''));
  $('#shopping-clear').addEventListener('click', () => shoppingAction('POST', '/api/shopping/clear'));
}
