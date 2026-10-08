'use strict';

// Severe weather banner: the first thing on every screen while a warning or watch is active.
// Loaded after shopping.js and before app.js, so it only uses app.js's helpers ($, el, api,
// GENERIC_ERROR) when a function runs, never at load time. The server already hides dismissed alerts.

let alertList = [];
let alertsExpanded = false;
let alertsError = '';
let alertsBusy = false;
let alertsSig = null;

function alertUntil(alert) {
  const when = alert.ends ? new Date(alert.ends) : null;
  if (!when || Number.isNaN(when.getTime())) return alert.event;
  const hh = String(when.getHours()).padStart(2, '0');
  const mm = String(when.getMinutes()).padStart(2, '0');
  const now = new Date();
  const sameDay = when.getFullYear() === now.getFullYear() && when.getMonth() === now.getMonth() && when.getDate() === now.getDate();
  const day = sameDay ? '' : `${when.toLocaleDateString(undefined, {weekday: 'short'})} `;
  return `${alert.event} until ${day}${clock12(`${hh}:${mm}`)}`;
}

function alertDismissButton(alert) {
  return el('button', {
    type: 'button', class: 'alert-dismiss', 'data-key': `alert-dismiss-${alert.id}`,
    'aria-label': `Dismiss ${alert.event}`, onclick: () => dismissAlert(alert.id),
  }, 'Dismiss');
}

function alertRow(alert, withDismiss) {
  return el('div', {class: 'alert-row' + (withDismiss ? ' extra' : '')},
    el('div', {class: 'alert-text'},
      el('div', {class: 'alert-title'}, alertUntil(alert)),
      alert.area ? el('div', {class: 'alert-area', title: alert.area}, alert.area) : null),
    withDismiss ? alertDismissButton(alert) : null);
}

// Pass the server's list to update; call with no argument to repaint after a local change.
function renderAlerts(list) {
  if (Array.isArray(list)) alertList = list.filter((item) => item && typeof item.id === 'string');
  const sig = JSON.stringify([alertList, alertsExpanded, alertsError]);
  if (sig === alertsSig) return; // nothing changed; leave the banner (and any tap in progress) alone
  alertsSig = sig;
  const bar = $('#alert-bar');
  document.body.classList.toggle('has-alert', alertList.length > 0);
  bar.hidden = !alertList.length;
  if (!alertList.length) {
    alertsExpanded = false;
    alertsError = '';
    alertsSig = null;
    bar.className = 'alert-bar';
    bar.replaceChildren();
    return;
  }
  const [top, ...rest] = alertList;
  if (!rest.length) alertsExpanded = false;
  const active = document.activeElement;
  const key = active && active.dataset ? active.dataset.key : null;
  bar.className = 'alert-bar ' + top.level;
  const more = rest.length ? el('button', {
    type: 'button', class: 'alert-more', 'data-key': 'alert-more', 'aria-expanded': String(alertsExpanded),
    onclick: () => { alertsExpanded = !alertsExpanded; renderAlerts(); },
  }, alertsExpanded ? 'Show fewer' : `+${rest.length} more`) : null;
  bar.replaceChildren(...[
    el('div', {class: 'alert-main'}, alertRow(top, false), more, alertDismissButton(top)),
    alertsError ? el('div', {class: 'alert-error'}, alertsError) : null,
    rest.length && alertsExpanded ? el('div', {class: 'alert-rest'}, ...rest.map((item) => alertRow(item, true))) : null,
  ].filter(Boolean)); // replaceChildren would turn a null into the text "null"
  if (key) {
    const again = document.querySelector(`[data-key="${CSS.escape(key)}"]`);
    if (again) again.focus();
  }
}

async function dismissAlert(id) {
  if (alertsBusy) return;
  alertsBusy = true;
  let failed = false;
  try {
    const payload = await api('POST', '/api/alerts/dismiss', {id});
    alertsError = '';
    renderAlerts(payload.alerts);
  } catch (error) {
    failed = true;
    alertsError = GENERIC_ERROR;
    renderAlerts();
  } finally {
    alertsBusy = false;
  }
  if (failed) pollAlerts(id); // the alert may have expired (404): refresh so it disappears
}

async function pollAlerts(keepErrorFor) {
  if (alertsBusy) return;
  try {
    const payload = await api('GET', '/api/alerts', undefined, 30000);
    const still = keepErrorFor && Array.isArray(payload.alerts) && payload.alerts.some((item) => item && item.id === keepErrorFor);
    if (!still) alertsError = '';
    renderAlerts(payload.alerts);
  } catch (error) { /* keep the banner we have */ }
}
