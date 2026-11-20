/* openSoom dashboard. All operating values come from the service; no demo data is generated here. */
(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const icon = (name, extra = '') => `<svg ${extra} aria-hidden="true"><use href="#i-${name}"/></svg>`;
  const human = (value) => String(value ?? '').replace(/[_-]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  const tokenValue = document.querySelector('meta[name="opensoom-token"]')?.content || '';
  const token = tokenValue.startsWith('__') ? '' : tokenValue;
  const workbench = document.querySelector('meta[name="technician-workbench"]');
  const localShaftFacility = document.querySelector('meta[name="local-shaft-replay"]')?.content;
  const state = { data: null, facilityId: '', zoneId: '', metric: 'pm25', outcomeCommandId: '', connected: false, polling: false, busy: false, lastReceived: null, latestRunId: null, history: new Map() };
  try { state.facilityId = localStorage.getItem('opensoom.facility') || ''; } catch (_) { /* Local storage is optional. */ }
  let toastTimer;
  let facilityVisual = null;
  let visualMode = '2d';

  const units = { airflow: 'm³/h', pm25: 'µg/m³', co2: 'ppm', damper_pct: '%' };
  const labels = { airflow: 'Exhaust airflow', pm25: 'PM2.5', co2: 'CO₂', damper_pct: 'Damper opening' };
  const closedStates = new Set(['resolved', 'recovered', 'verified', 'closed']);
  const failedStates = new Set(['failed', 'denied', 'expired', 'timeout', 'timed_out', 'unresolved', 'missing_ack', 'no_recovery']);

  function setHTML(id, html) {
    const element = $(id);
    if (!element || element.innerHTML === html) return;
    const active = document.activeElement;
    const focusedZone = element.contains(active) ? active?.dataset?.zone : null;
    element.innerHTML = html;
    if (focusedZone) [...element.querySelectorAll('[data-zone]')].find((item) => item.dataset.zone === focusedZone)?.focus({ preventScroll: true });
  }

  function number(value, metric = '') {
    if (value === null || value === undefined || value === '' || typeof value === 'boolean') return '—';
    const n = Number(value);
    if (!Number.isFinite(n)) return '—';
    return new Intl.NumberFormat('en-US', { maximumFractionDigits: metric === 'pm25' ? 1 : 0 }).format(n);
  }

  function observation(zone, metric) {
    const source = zone?.observations?.[metric];
    if (source && typeof source === 'object') return { ...source, unit: source.unit ?? units[metric] ?? '' };
    return { value: source ?? null, unit: units[metric] ?? '', observed_at: zone?.observed_at, quality: source == null ? 'missing' : null };
  }

  function dateValue(value) {
    if (value === null || value === undefined || value === '') return null;
    const date = new Date(typeof value === 'number' && value < 1e12 ? value * 1000 : value);
    return Number.isFinite(date.getTime()) ? date : null;
  }

  function age(value) {
    const date = dateValue(value);
    if (!date) return 'Time not reported';
    const seconds = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000));
    if (seconds < 5) return 'Just now';
    if (seconds < 60) return `${seconds}s ago`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
  }

  function clock(value) {
    return dateValue(value)?.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) ?? '—';
  }

  function freshness(zone) {
    const qualities = Object.values(zone?.observations || {}).map((o) => o?.quality).filter(Boolean);
    const f = zone?.freshness;
    if (typeof f === 'string') return human(f);
    if (f?.status) return human(f.status);
    if (f?.fresh === false || qualities.includes('stale')) return 'Stale observations';
    if (qualities.includes('missing') || !qualities.length && !Object.keys(zone?.observations || {}).length) return 'Missing observations';
    if (f?.fresh === true || qualities.every((q) => q === 'good') && qualities.length) return 'Current observations';
    return 'Freshness not reported';
  }

  function status(zone) {
    const raw = String(zone?.status || 'unknown').toLowerCase();
    if (['nominal', 'normal', 'healthy', 'within_profile', 'ok'].includes(raw)) return 'nominal';
    if (['critical', 'fault', 'alarm', 'unsafe'].includes(raw)) return 'critical';
    if (['warning', 'attention', 'anomaly'].includes(raw)) return 'warning';
    if (['stale', 'missing', 'recovering'].includes(raw)) return raw;
    return 'unknown';
  }

  function statusLabel(zone) {
    return { nominal: 'WITHIN PROFILE', warning: 'ATTENTION', critical: 'ATTENTION', stale: 'STALE DATA', missing: 'MISSING DATA', recovering: 'VERIFYING', unknown: 'AWAITING DATA' }[status(zone)];
  }

  function facility() { return state.data?.facilities?.find((f) => f.id === state.facilityId) || null; }
  function zone() { return facility()?.zones?.find((z) => z.id === state.zoneId) || facility()?.zones?.[0] || null; }
  function scoped(items) { return (Array.isArray(items) ? items : []).filter((item) => !item.facility_id || item.facility_id === state.facilityId); }
  function ordered(items) { return [...items].sort((a, b) => (dateValue(b.timestamp || b.created_at || b.started_at)?.getTime() || 0) - (dateValue(a.timestamp || a.created_at || a.started_at)?.getTime() || 0)); }
  function commands() { return ordered(scoped(state.data?.commands)); }
  function incidents() { return ordered(scoped(state.data?.incidents)); }
  function latestRun() {
    const runs = ordered(scoped(state.data?.runs));
    const activeId = facility()?.active_run;
    return runs.find((run) => (run.id || run.run_id) === activeId) || runs[0] || null;
  }
  function incidentRecovered(incident) { return incident?.verified === true || ['recovered', 'verified'].includes(String(incident?.status).toLowerCase()) || incident?.status === 'resolved' && !!incident.resolved_at; }
  function canAct() { return !!token && state.connected && state.data?.runtime?.simulation === true && !!facility(); }

  async function api(path, body) {
    const headers = { Accept: 'application/json' };
    if (token) headers.Authorization = `Bearer ${token}`;
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(path, { method: body === undefined ? 'GET' : 'POST', headers, body: body === undefined ? undefined : JSON.stringify(body), signal: controller.signal, cache: 'no-store', credentials: 'same-origin' });
      let result;
      try { result = await response.json(); } catch (_) { throw new Error('The service returned an unreadable response.'); }
      if (!response.ok) {
        const detail = result?.detail;
        throw new Error(typeof detail === 'string' ? detail : detail?.message || result?.message || `The service returned HTTP ${response.status}.`);
      }
      return result;
    } catch (error) {
      if (error.name === 'AbortError') throw new Error('The service took too long to respond. The action outcome is not yet confirmed.');
      throw error;
    } finally { clearTimeout(timeout); }
  }

  function toast(message, error = false) {
    clearTimeout(toastTimer);
    const dialogContent = document.querySelector('dialog[open] .dialog-content');
    if (dialogContent) {
      let notice = dialogContent.querySelector('.dialog-notice');
      if (!notice) {
        notice = document.createElement('p');
        notice.className = 'dialog-notice';
        notice.setAttribute('role', 'alert');
        notice.tabIndex = -1;
        dialogContent.prepend(notice);
      }
      notice.textContent = message;
      notice.classList.toggle('error', error);
      notice.focus();
      return;
    }
    const el = $('toast');
    el.textContent = message;
    el.classList.toggle('error', error);
    el.hidden = false;
    toastTimer = setTimeout(() => { el.hidden = true; }, error ? 7000 : 4500);
  }

  function collectHistory() {
    for (const f of state.data?.facilities || []) for (const z of f.zones || []) for (const metric of ['airflow', 'pm25', 'co2']) {
      const o = observation(z, metric);
      if (o.value == null || !Number.isFinite(Number(o.value)) || !o.observed_at) continue;
      const key = `${f.id}/${z.id}/${metric}`;
      const series = state.history.get(key) || [];
      if (series.at(-1)?.timestamp !== o.observed_at) series.push({ value: Number(o.value), timestamp: o.observed_at });
      state.history.set(key, series.slice(-40));
    }
  }

  async function poll(manual = false) {
    if (state.polling || document.hidden && !manual) return;
    state.polling = true;
    $('refresh-button').classList.add('loading');
    try {
      const data = await api('/api/state');
      if (!data || !Array.isArray(data.facilities)) throw new Error('The facility response does not contain the expected state.');
      state.data = data;
      state.connected = true;
      state.lastReceived = new Date();
      if (!data.facilities.some((f) => f.id === state.facilityId)) state.facilityId = data.selected_facility || data.facilities[0]?.id || '';
      if (!facility()?.zones?.some((z) => z.id === state.zoneId)) state.zoneId = facility()?.zones?.[0]?.id || '';
      collectHistory();
      render();
    } catch (error) {
      state.connected = false;
      renderConnection(error.message);
      $('start-demo-button').disabled = true;
      renderOutcomes();
    } finally {
      state.polling = false;
      $('refresh-button').classList.remove('loading');
    }
  }

  function renderConnection(error = null) {
    const connection = $('connection-state');
    const cse = state.data?.runtime?.cse_connected === true;
    document.body.classList.toggle('offline', !state.connected || !cse);
    connection.className = `connection-state ${state.connected && cse ? 'connected' : 'offline'}`;
    connection.innerHTML = `<span class="pulse-dot"></span>${state.connected ? cse ? 'oneM2M connected' : 'CSE unavailable' : 'Service unavailable'}`;
    const banner = $('connection-banner');
    if (!state.connected) {
      banner.hidden = false;
      banner.textContent = `${error || 'The service is unavailable.'} ${state.data ? 'Last received values remain visible; they are not live.' : 'Start the openSoom service, then refresh this view.'}`;
    } else if (!cse) {
      banner.hidden = false;
      banner.textContent = 'The dashboard service is reachable, but the oneM2M CSE is not connected. New equipment operations cannot be confirmed.';
    } else if (!token) {
      banner.hidden = false;
      banner.textContent = 'Read-only view. Open the dashboard from the configured service to enable authorized demo operations.';
    } else banner.hidden = true;
    $('mode-badge').textContent = state.data?.runtime?.simulation === false ? 'Observation mode' : 'Virtual facility';
    $('map-updated').classList.toggle('live', state.connected && cse);
    $('map-updated').innerHTML = `<span class="tiny-dot"></span>${state.lastReceived ? `Updated ${clock(state.lastReceived)}` : 'No observations yet'}`;
    $('footer-updated').textContent = state.lastReceived ? `${state.connected ? 'Last sync' : 'Last received'} ${clock(state.lastReceived)} · ${state.data?.runtime?.cse_name || 'oneM2M'}` : 'Waiting for the service';
    if (!state.connected || !cse) renderVisual();
  }

  function render() {
    renderConnection();
    const facilities = state.data.facilities || [];
    const options = facilities.length ? facilities.map((f) => `<option value="${esc(f.id)}">${esc(f.name || f.id)}</option>`).join('') : '<option value="">No facility configured</option>';
    setHTML('facility-select', options);
    $('facility-select').value = state.facilityId;
    $('facility-select').disabled = !facilities.length;
    const f = facility();
    const zones = f?.zones || [];
    const open = incidents().filter((i) => !closedStates.has(String(i.status).toLowerCase()));
    const recovered = incidents().filter(incidentRecovered);
    const pending = commands().filter((c) => !closedStates.has(String(c.status).toLowerCase()) && !failedStates.has(String(c.status).toLowerCase()) && !['completed', 'maintenance_recorded'].includes(String(c.status).toLowerCase()));
    const fresh = zones.filter((z) => freshness(z) === 'Current observations').length;
    setHTML('summary-zones', `${zones.length}<small>zones</small>`);
    setHTML('summary-incidents', `${open.length}<small>incident${open.length === 1 ? '' : 's'}</small>`);
    setHTML('summary-actions', `${pending.length}<small>action${pending.length === 1 ? '' : 's'}</small>`);
    setHTML('summary-recovered', `${recovered.length}<small>outcome${recovered.length === 1 ? '' : 's'}</small>`);
    $('summary-incidents').closest('.summary-card').classList.toggle('attention', open.length > 0);
    $('summary-zones-note').textContent = zones.length ? `${fresh} of ${zones.length} reporting current observations` : 'No facility zones are configured';
    $('summary-incidents-note').textContent = open.length ? `${open.length === 1 ? 'One issue needs' : 'Issues need'} a closer look` : 'No open incidents reported';
    $('summary-actions-note').textContent = pending.length ? 'Waiting for acknowledgement or outcome' : 'No pending actions reported';
    $('facility-profile').textContent = human(typeof f?.profile === 'object' ? f.profile.name || f.profile.id : f?.profile || 'No profile loaded');
    $('overview-subtitle').textContent = f ? `${f.name || f.id} · Compare air quality before and after a ventilation action.` : 'Connect a facility to see its air-quality readings.';
    renderOutcomes();
    renderMap();
    renderZoneDetail();
    renderWorkflow();
    renderActivity();
    renderCommand();
    renderMaintenance();
    $('start-demo-button').disabled = state.busy || !canAct() || !state.data.runtime?.cse_connected;
  }

  function observedDuration(seconds) {
    if (!Number.isFinite(seconds) || seconds < 0) return '—';
    if (seconds === 0) return '0 s';
    if (seconds < 1) return seconds < 0.001 ? '<1 ms' : `${Math.round(seconds * 1000)} ms`;
    if (seconds < 60) return `${Number(seconds.toFixed(1))} s`;
    const whole = Math.floor(seconds);
    if (whole < 3600) return `${Math.floor(whole / 60)} min ${whole % 60} s`;
    return `${Math.floor(whole / 3600)} h ${Math.floor(whole % 3600 / 60)} min`;
  }

  const outcomeNumber = new Intl.NumberFormat('en-US', {maximumFractionDigits: 2});
  function outcomeMetric(outcome, key, retained) {
    const before = outcome.baseline?.[key];
    const latest = outcome.latest?.[key];
    const target = outcome.targets?.[key];
    const delta = outcome.change?.[key];
    const reading = value => Number.isFinite(value) ? outcomeNumber.format(value) : '—';
    const comparable = Number.isFinite(latest) && Number.isFinite(target);
    const above = comparable && latest > target;
    const condition = comparable ? (above ? 'Above target' : 'Within target') : 'Awaiting data';
    const tone = retained || !comparable ? 'neutral' : above ? 'exceeds' : 'within';
    let change = 'Awaiting a pair';
    if (Number.isFinite(delta?.decrease)) {
      const percent = Number.isFinite(delta.percent) ? ` (${reading(Math.abs(delta.percent))}%)` : '';
      change = delta.decrease === 0 ? 'No change' : `${reading(Math.abs(delta.decrease))} ${delta.decrease > 0 ? 'lower' : 'higher'}${percent}`;
    }

    // Each pollutant has a separate zero-based scale, shared by its three measurements.
    const values = [before, latest, target].filter(value => Number.isFinite(value) && value >= 0);
    const largest = Math.max(1, ...values);
    const step = 10 ** Math.floor(Math.log10(largest));
    const maximum = Math.ceil(largest / step) * step;
    const percent = value => 100 * (value / maximum);
    const marker = (value, name) => Number.isFinite(value) && value >= 0
      ? `<i class="metric-marker ${name}" style="left:${percent(value)}%"></i>` : '';
    const fill = Number.isFinite(latest) && latest >= 0
      ? `<i class="metric-fill" style="width:${percent(latest)}%"></i>` : '';
    return `<article class="outcome-metric ${tone}" id="air-outcome-${key}" aria-label="${labels[key]} after ventilation">
      <div class="metric-heading"><h3>${labels[key]}</h3><span class="metric-condition${above ? ' outcome-limit-warning' : ''}">${condition}</span></div>
      <div class="metric-reading"><strong data-reading="latest">${reading(latest)}</strong><span>${units[key]}</span><small data-reading="change">${esc(change)}</small></div>
      <div class="metric-plot" aria-hidden="true"><div class="metric-rail">${fill}${marker(target, 'target')}${marker(before, 'before')}</div></div>
      <div class="metric-key"><span><i class="key-latest" aria-hidden="true"></i>Latest</span><span><i class="key-before" aria-hidden="true"></i>Before <b data-reading="before">${reading(before)}</b></span><span><i class="key-target" aria-hidden="true"></i>Target <b data-reading="target">${Number.isFinite(target) ? '≤ ' + reading(target) : '—'}</b></span></div>
    </article>`;
  }

  function outcomeHeading(command, outcome, context) {
    if (context.offline) return ['Last received measurements', 'The service is offline. Current room conditions need a new reading.'];
    if (context.historical) return ['Recorded ventilation result', 'These measurements belong to the selected action.'];
    if (outcome.status === 'evidence_gap') return ['Fresh observations needed', endReasons[outcome.last_event?.issue || outcome.last_hold?.ended_by] || 'A fresh pair of pollutant readings is needed to assess this zone.'];
    if (outcome.status === 'awaiting_ack') return ['Waiting for the device', 'The ventilation action is waiting for acknowledgement.'];
    if (outcome.status === 'awaiting_sample') return ['Waiting for a follow-up reading', 'The device acknowledged the action. The next paired reading will show how the air changed.'];
    if (outcome.status === 'timed_out') return ['Check the device response', 'The ventilation action reached its deadline without an acknowledgement.'];
    if (outcome.status === 'in_target') return ['Both pollutants reached target', 'The latest paired reading meets this zone’s PM2.5 and CO₂ limits.'];
    if (outcome.status !== 'outside_target') return ['Review the latest readings', 'Use the zone’s targets to interpret the measurements.'];
    const exceeded = ['pm25', 'co2'].filter(key => Number.isFinite(outcome.latest?.[key]) && Number.isFinite(outcome.targets?.[key]) && outcome.latest[key] > outcome.targets[key]);
    const reason = exceeded.map(key => `${labels[key]} is ${outcomeNumber.format(outcome.latest[key])} ${units[key]}, above the zone limit of ${outcomeNumber.format(outcome.targets[key])} ${units[key]}.`).join(' ');
    const incident = incidents().find(item => item.id === command.incident_id && item.zone_id === command.zone_id);
    const heading = incident?.status === 'open' ? 'Keep the alert open' : 'Review the above-target reading';
    return [heading, reason || 'The latest paired reading exceeded a configured zone target.'];
  }

  const outcomeStatuses = {
    awaiting_ack: ['Awaiting device ACK', 'pending'],
    awaiting_sample: ['Awaiting first follow-up', 'pending'],
    in_target: ['Both targets met', 'within'],
    outside_target: ['Outside air-quality targets', 'outside'],
    evidence_gap: ['Measurement gap', 'outside'],
    superseded: ['Replaced by a later action', 'archived'],
    run_ended: ['Run ended', 'archived'],
    timed_out: ['Device ACK timed out', 'outside']
  };
  const endReasons = {
    above_target: 'Ended when a later reading exceeded a target.',
    sample_gap: 'The next reading arrived outside the freshness window.',
    unobserved_interval: 'A gap in the observation sequence ended this interval.',
    incomplete_air_quality: 'A required pollutant reading was missing.',
    sample_not_fresh: 'The next reading failed the freshness check.',
    conflicting_measurements: 'Conflicting readings ended this interval.',
    evidence_gap: 'A gap ended this observation window.',
    stale_silence: 'Further readings did not arrive within the freshness window.',
    superseded: 'A newer action ended this window.',
    run_ended: 'This run ended.'
  };

  function outcomeEvidence(command, outcome) {
    const rows = [
      ['Action', command.id], ['Run', command.run_id], ['Incident', command.incident_id],
      ['Action requested', command.created_at], ['Device acknowledged', outcome.ack_at], ['ACK observation ID', outcome.ack_cin_ri],
      ['Before reading', outcome.baseline?.observed_at], ['Before observation ID', outcome.baseline?.cin_ri],
      ['Latest paired reading', outcome.latest?.observed_at], ['Latest paired observation ID', outcome.latest?.cin_ri],
      ['First combined target reading', outcome.first_target_at], ['First target observation ID', outcome.first_target_sample?.cin_ri],
      ['Accepted follow-up count', outcome.sample_count], ['Freshness window', observedDuration(outcome.freshness_seconds)]
    ];
    if (outcome.hold_start_sample) rows.push(['Current interval start ID', outcome.hold_start_sample.cin_ri]);
    if (outcome.last_hold) rows.push(['Previous interval start', outcome.last_hold.start?.observed_at], ['Previous interval end', outcome.last_hold.end?.observed_at], ['Previous interval end ID', outcome.last_hold.end?.cin_ri]);
    if (outcome.last_event?.issue) rows.push(['Latest evidence issue', human(outcome.last_event.issue)], ['Evidence issue observation ID', outcome.last_event.cin_ri]);
    return `<dl class="outcome-evidence-list">${rows.filter(([, value]) => value != null && value !== '').map(([label, value]) =>
      `<div><dt>${esc(label)}</dt><dd>${esc(value)}</dd></div>`).join('')}</dl>`;
  }

  function renderOutcomes() {
    const f = facility();
    const z = zone();
    const actions = commands().filter(c => c.action === 'set_damper' && c.zone_id === z?.id);
    const current = f?.active_run ? actions.find(c => c.run_id === f.active_run) : actions.find(c => !c.run_id);
    if (!actions.some(c => c.id === state.outcomeCommandId)) state.outcomeCommandId = '';
    const command = actions.find(c => c.id === state.outcomeCommandId) || current;
    const outcome = command?.air_quality_outcome;
    setHTML('air-outcome-zone', f?.zones?.length ? f.zones.map(item => `<option value="${esc(item.id)}">${esc(item.name || item.id)}</option>`).join('') : '<option value="">No zones</option>');
    $('air-outcome-zone').value = z?.id || '';
    $('air-outcome-zone').disabled = !f?.zones?.length;
    const choices = ['<option value="">Current run · latest action</option>'];
    for (const c of actions) {
      const when = dateValue(c.created_at)?.toLocaleString('en-GB', {day:'numeric',month:'short',hour:'2-digit',minute:'2-digit',second:'2-digit'}) || 'Time unavailable';
      choices.push(`<option value="${esc(c.id)}">${esc(`${when} · ${actionName(c)} · ${c.id}`)}</option>`);
    }
    setHTML('air-outcome-command', choices.join(''));
    $('air-outcome-command').value = state.outcomeCommandId;
    $('air-outcome-command').disabled = !actions.length;
    const panel = $('air-outcome');
    panel.dataset.commandId = command?.id || '';
    panel.dataset.runId = command?.run_id || f?.active_run || '';
    panel.dataset.status = outcome?.status || 'no_outcome';
    const offline = !state.connected || !state.data?.runtime?.cse_connected;
    const finalStatus = ['superseded', 'run_ended'].includes(outcome?.status);
    const historical = finalStatus || Boolean(command && command.id !== current?.id);
    const scope = historical ? 'Recorded action' : offline ? 'Last received action' : 'Current action';
    $('air-outcome-scope').textContent = z ? `${scope} · ${z.name || z.id}` : 'Air quality after ventilation';
    $('air-outcome-context').textContent = command ? `${actionName(command)} · ${clock(command.created_at)}` : '';
    $('air-outcome-evidence').hidden = !outcome;
    if (!outcome) {
      $('air-outcome-heading').textContent = 'No air-quality result yet';
      $('air-outcome-summary').textContent = '';
      panel.dataset.tone = 'neutral';
      const message = command ? 'This action has no retained air-quality comparison.' :
        f?.active_run ? 'No ventilation action has been recorded for this zone in the current run.' :
        'Run a ventilation scenario to see the change in this zone.';
      setHTML('air-outcome-body', `<p class="outcome-empty" id="air-outcome-status">${esc(message)}</p>`);
      setHTML('air-outcome-records', '');
      return;
    }

    const hasFirst = Number.isFinite(outcome.time_to_target_seconds);
    const hasHold = Number.isFinite(outcome.hold_seconds);
    const previousHold = Number.isFinite(outcome.last_hold_seconds);
    let [statusLabel, tone] = outcomeStatuses[outcome.status] || ['Observation pending', 'pending'];
    if (outcome.status === 'outside_target' && hasFirst) statusLabel = 'Above target again';
    if (finalStatus && outcome.last_sample_status) {
      const last = outcomeStatuses[outcome.last_sample_status];
      if (last) statusLabel += ` · ${last[0].toLowerCase()} at last reading`;
    }
    const retained = offline || historical || outcome.status === 'evidence_gap';
    const [heading, reason] = outcomeHeading(command, outcome, {offline, historical});
    $('air-outcome-heading').textContent = heading;
    $('air-outcome-summary').textContent = reason;
    panel.dataset.tone = retained ? 'neutral' : tone;
    let timingNote = hasFirst ? `After ACK · first observed at ${clock(outcome.first_target_at)}` : 'Waiting for both pollutants to meet their targets.';
    if (!outcome.ack_at) timingNote = 'Timing starts at the device acknowledgement.';
    else if (!hasFirst && finalStatus) timingNote = 'No qualifying pair was observed for this action.';
    const timeValue = hasFirst ? observedDuration(outcome.time_to_target_seconds) : (outcome.sample_count > 0 ? 'Not reached' : '—');
    const holdValue = hasHold ? observedDuration(outcome.hold_seconds) : previousHold ? observedDuration(outcome.last_hold_seconds) : '—';
    let holdNote = 'Needs two qualifying observations to measure a span.';
    if (hasHold) {
      holdNote = outcome.hold_seconds === 0 ? 'One qualifying reading. Awaiting the next.' : `Observed ${clock(outcome.hold_started_at)} – ${clock(outcome.latest?.observed_at)}`;
    } else if (previousHold) {
      holdNote = endReasons[outcome.last_hold?.ended_by] || 'Last completed observation window.';
    } else if (outcome.status === 'evidence_gap') {
      holdNote = 'A continuous span cannot be verified across this gap.';
    } else if (outcome.sample_count > 0) {
      holdNote = 'No observed interval with both pollutants in target.';
    }

    setHTML('air-outcome-body', `<div class="outcome-result">
      <div class="outcome-result-head"><span class="outcome-status ${retained ? 'archived' : tone}" id="air-outcome-status">${esc(statusLabel)}</span><span class="outcome-source">${esc([outcome.source === 'simulated' ? 'Virtual measurements' : '', retained ? 'Retained measurements' : '', outcome.latest?.observed_at ? 'Paired reading ' + clock(outcome.latest.observed_at) : ''].filter(Boolean).join(' · '))}</span></div>
      <div class="outcome-metrics">${outcomeMetric(outcome, 'pm25', retained)}${outcomeMetric(outcome, 'co2', retained)}</div>
      <dl class="outcome-times">
        <div><dt>Time to both targets</dt><dd id="air-outcome-first">${esc(timeValue)}</dd><dd class="outcome-caption">${esc(timingNote)}</dd></div>
        <div><dt>${hasHold ? 'Observed time in target' : previousHold ? 'Last observed time in target' : 'Observed time in target'}</dt><dd id="air-outcome-hold">${esc(holdValue)}</dd><dd class="outcome-caption">${esc(holdNote)}</dd></div>
      </dl></div>`);
    setHTML('air-outcome-records', outcomeEvidence(command, outcome));
  }

  function project(x, y) { return [322 + (x - y) * .72, 37 + (x + y) * .39]; }
  function polygon(x, y, w, h, offset = 0) { return [[x, y], [x + w, y], [x + w, y + h], [x, y + h]].map(([a, b]) => { const [px, py] = project(a, b); return `${px.toFixed(1)},${(py + offset).toFixed(1)}`; }).join(' '); }

  function renderMap() {
    const zones = facility()?.zones || [];
    renderVisual();
    setHTML('mobile-zones', zones.map((z) => {
      const o = observation(z, state.metric);
      return `<button class="mobile-zone ${status(z)}" type="button" data-zone="${esc(z.id)}" aria-pressed="${z.id === state.zoneId}"><span>${esc(z.name || z.id)}</span><strong>${esc(number(o.value, state.metric))}<small>${esc(o.unit)}</small></strong><em>${esc(statusLabel(z).toLowerCase())}</em></button>`;
    }).join(''));
    if (!zones.length) {
      setHTML('facility-map', `<div class="map-empty">${icon('building')}<strong>Your facility will appear here</strong><span>Connect the service to see current zones and observations.</span></div>`);
      return;
    }
    const visible = zones.slice(0, 6);
    let roomShapes = '';
    visible.forEach((z, index) => {
      const count = visible.length;
      let x, y, w, h;
      if (count <= 3) {
        const rooms = count === 1 ? [[0, 0, 390, 260]] : count === 2 ? [[0, 0, 195, 260], [195, 0, 195, 260]] : [[0, 0, 200, 150], [200, 0, 200, 150], [0, 150, 400, 150]];
        [x, y, w, h] = rooms[index];
      } else { w = 135; h = 145; x = (index % 3) * w; y = Math.floor(index / 3) * h; }
      const [cx, cy] = project(x + w / 2, y + h / 2);
      const [fx, fy] = project(x + w - 29, y + 25);
      const [leftX, leftY] = project(x, y + h);
      const [rightX, rightY] = project(x + w, y + h);
      const [backX, backY] = project(x + w, y);
      const observed = observation(z, state.metric);
      const fanRunning = observation(z, 'fan_running').value === true;
      const zStatus = status(z);
      const currentFan = state.connected && state.data?.runtime?.cse_connected === true && fanRunning && observation(z, 'fan_running').quality === 'good' && !['stale', 'missing'].includes(zStatus);
      const flow = state.metric === 'airflow' && currentFan && typeof observed.value === 'number' && Number.isFinite(observed.value) && observed.value > 0 && observed.quality === 'good';
      const name = String(z.name || z.id);
      const readableName = name.length > 22 ? `${name.slice(0, 20)}…` : name;
      roomShapes += `<g class="zone-shape ${zStatus} ${z.id === state.zoneId ? 'selected' : ''}" data-zone="${esc(z.id)}" tabindex="0" role="button" aria-label="${esc(`${name}, ${labels[state.metric]} ${number(observed.value, state.metric)} ${observed.unit}, ${statusLabel(z).toLowerCase()}`)}">
        <polygon class="zone-edge" points="${leftX},${leftY} ${rightX},${rightY} ${rightX},${rightY + 9} ${leftX},${leftY + 9}"/>
        <polygon class="zone-edge" points="${rightX},${rightY} ${backX},${backY} ${backX},${backY + 9} ${rightX},${rightY + 9}"/>
        <polygon class="zone-floor" fill="${zStatus === 'recovering' ? '#e5efe3' : '#edf2e3'}" points="${polygon(x + 3, y + 3, w - 6, h - 6)}"/>
        <polygon fill="none" stroke="#d1ddc5" stroke-width=".7" points="${polygon(x + 12, y + 12, w - 24, h - 24)}"/>
        ${flow ? `<path class="air-line ${['warning', 'critical'].includes(zStatus) ? 'warning' : ''}" d="M${cx - 45} ${cy + 37}Q${cx - 12} ${cy + 20} ${cx + 46} ${cy + 18}"/><path class="air-line ${['warning', 'critical'].includes(zStatus) ? 'warning' : ''}" d="M${cx - 40} ${cy + 43}Q${cx + 8} ${cy + 31} ${cx + 52} ${cy + 27}"/>` : ''}
        <g transform="translate(${fx.toFixed(1)},${fy.toFixed(1)})"><ellipse fill="#f8faf2" stroke="#b8cba9" stroke-width="1" rx="12" ry="7"/><g class="fan-blades ${currentFan ? 'spinning' : ''}"><path class="fan-blade" d="M0 0C-9-9-11 3 0 0ZM0 0C9-8 12 4 0 0ZM0 0C2 12-9 8 0 0Z"/></g></g>
        <text class="zone-status-label" x="${cx}" y="${cy - 18}" text-anchor="middle">${statusLabel(z)}</text>
        <text class="zone-name" x="${cx}" y="${cy - 4}" text-anchor="middle">${esc(readableName)}</text>
        <text class="zone-reading" x="${cx}" y="${cy + 23}" text-anchor="middle">${esc(number(observed.value, state.metric))}</text>
        <text class="zone-unit" x="${cx}" y="${cy + 36}" text-anchor="middle">${esc(observed.value == null ? 'No observation' : observed.unit)}</text>
        <circle class="zone-signal-ring" cx="${cx - 55}" cy="${cy - 9}" r="5"/><circle class="zone-signal-dot" cx="${cx - 55}" cy="${cy - 9}" r="2"/>
      </g>`;
    });
    setHTML('facility-map', `<svg class="facility-svg" viewBox="0 0 680 320" role="group" aria-label="Illustrative facility layout. Select a zone for its reported observations."><defs><filter id="floor-shadow" x="-30%" y="-30%" width="180%" height="180%"><feGaussianBlur stdDeviation="7"/></filter></defs><ellipse cx="354" cy="244" rx="219" ry="37" fill="#cdd8be" opacity=".17" filter="url(#floor-shadow)"/>${roomShapes}<path d="M50 264v24h24" stroke="#b9c9ac" stroke-width="1" fill="none"/><text x="50" y="304" font-size="6" fill="#a1b08f" letter-spacing="1.2">ZONE SCHEMATIC</text><text x="620" y="289" text-anchor="end" font-size="7" fill="#a0af8d">${visible.length} ${visible.length === 1 ? 'ZONE' : 'ZONES'}${zones.length > 6 ? ` / ${zones.length} TOTAL` : ''}</text></svg>`);
  }

  function renderZoneDetail() {
    const z = zone();
    if (!z) return setHTML('zone-detail', '<div class="empty-inline">Select a zone to inspect its observations.</div>');
    const values = ['airflow', 'pm25', 'co2'].map((metric) => { const o = observation(z, metric); return `<div class="zone-measure"><span>${esc(labels[metric])}</span>${esc(number(o.value, metric))}<small>${esc(o.unit)}</small></div>`; }).join('');
    const quality = freshness(z);
    setHTML('zone-detail', `<div class="zone-identity"><strong>${esc(z.name || z.id)}</strong><small><i class="legend-dot ${status(z)}"></i>${esc(quality)}</small></div><div class="zone-measures">${values}<button type="button" class="zone-action-button" data-inspect-zone="${esc(z.id)}" aria-label="Inspect ${esc(z.name || z.id)}" title="Inspect zone">${icon('arrow')}</button></div>`);
  }

  function isVerified(command) {
    if (!command) return false;
    const result = command.observed_result;
    return result === 'recovered' || result === 'verified' || result?.recovered === true || result?.verified === true || ['verified', 'recovered'].includes(String(command.status).toLowerCase());
  }

  function afterRecoveryNotice(command) {
    if (!isVerified(command)) return '';
    const state = command.air_quality_outcome?.status;
    if (state === 'outside_target') return 'A pollutant is back above target after the earlier recovery.';
    if (state === 'evidence_gap') return 'A measurement gap followed the earlier recovery.';
    return '';
  }

  function hasAck(command) {
    if (!command) return false;
    return command.ack === true || !!command.ack_at || command.ack?.received === true || ['acknowledged', 'acked', 'verified', 'recovered'].includes(String(command.status).toLowerCase());
  }

  function renderVisual() {
    const f = facility();
    const z = zone();
    const run = latestRun();
    const runId = f?.active_run || run?.id || run?.run_id || '';
    const connected = state.connected && state.data?.runtime?.cse_connected === true;
    facilityVisual?.update({
      facilityId: f?.id || '', selectedZoneId: z?.id || '', runId, connected,
      metric: state.metric, metricLabel: labels[state.metric],
      zones: (f?.zones || []).map((item) => {
        const o = observation(item, state.metric);
        return { id: item.id, name: item.name || item.id, status: status(item), statusLabel: statusLabel(item), reading: `${number(o.value, state.metric)} ${o.value == null ? '' : o.unit}`.trim(), fan: observation(item, 'fan_running'), airflow: observation(item, 'airflow') };
      })
    });
    $('spatial-condition').textContent = !f ? 'Waiting for facility observations' : !connected ? 'Connection unavailable · motion stopped · last received values' : 'Select a zone · equipment reports and airflow are separate evidence';
    if (!z) { setHTML('zone-proof', '<div class="empty-inline">Select a zone to follow its command and observed result.</div>'); return; }
    // A prior successful run must never color the current zone's evidence as recovered.
    const command = runId ? commands().find((item) => item.run_id === runId && item.zone_id === z.id) : null;
    const issue = command?.incident_id ? incidents().find((item) => item.id === command.incident_id) : null;
    const ack = hasAck(command);
    const verified = isVerified(command);
    const failed = !!command && failedStates.has(String(command.status).toLowerCase());
    const laterNotice = afterRecoveryNotice(command);
    const maintenance = command?.action === 'request_maintenance';
    const stale = ['stale', 'missing', 'unknown'].includes(status(z));
    const observedCount = Number.isInteger(issue?.recovery_count) ? issue.recovery_count : null;
    const steps = [
      { title: 'Command', text: command ? actionName(command) : stale ? 'Fresh data required' : 'None in this run', kind: command ? 'complete' : stale ? 'attention' : '' },
      { title: 'Device ACK', text: maintenance ? 'Not an equipment command' : ack ? `Received ${clock(command.ack_at)}` : command ? failed ? 'Not received' : 'Waiting for device' : 'No command to acknowledge', kind: ack ? 'complete' : failed ? 'attention' : '' },
      { title: 'Observed result', text: laterNotice || (verified ? observedCount !== null ? `Recovery verified · ${observedCount} fresh samples` : 'Recovery verified' : maintenance ? 'Follow-up recorded · no recovery claim' : command?.observed_result === 'unresolved' ? 'Not recovered · follow up' : command ? ack ? 'Recovery not yet verified' : 'Not verified' : 'No recovery claim'), kind: laterNotice ? 'attention' : verified ? 'complete' : failed ? 'attention' : '' }
    ];
    const fan = observation(z, 'fan_running');
    const airflow = observation(z, 'airflow');
    const fanText = fan.value === true ? 'Running' : fan.value === false ? 'Stopped' : 'Not reported';
    const currentData = connected && !stale && fan.quality === 'good' && airflow.quality === 'good';
    const target = typeof z.target_airflow === 'number' ? ` · profile target ${number(z.target_airflow)} ${esc(airflow.unit)}` : '';
    setHTML('zone-proof', `<div class="proof-title"><span>${esc(z.name || z.id)} · follow the result</span><small>${command ? esc(human(command.status)) : 'Current run · no equipment action'}</small></div><div class="proof-steps">${steps.map((step) => `<div class="proof-step ${step.kind}"><strong>${esc(step.title)}</strong><span>${esc(step.text)}</span></div>`).join('')}</div><p class="proof-context"><b>Fan reported: ${esc(fanText)}.</b> ${currentData ? 'Airflow observed' : 'Last reported airflow'}: ${esc(number(airflow.value))} ${esc(airflow.unit)}${target}. ${currentData ? 'A running fan alone does not confirm adequate exhaust.' : 'Current observations are needed before control or a new recovery claim.'}</p>`);
    $('zone-proof').dataset.runId = runId;
    $('zone-proof').dataset.commandId = command?.id || '';
  }

  function setVisualMode(mode) {
    visualMode = mode === '3d' && facilityVisual ? '3d' : '2d';
    $('spatial-stage').hidden = visualMode !== '3d';
    $('facility-map').hidden = visualMode === '3d';
    $('motion-toggle').hidden = visualMode !== '3d';
    $('view-3d').setAttribute('aria-pressed', String(visualMode === '3d'));
    $('view-2d').setAttribute('aria-pressed', String(visualMode === '2d'));
    facilityVisual?.setActive(visualMode === '3d');
  }

  function renderMotion() {
    const paused = facilityVisual?.paused ?? true;
    $('motion-toggle').setAttribute('aria-pressed', String(paused));
    $('motion-toggle').textContent = paused ? 'Resume motion' : 'Pause motion';
  }

  function visualUnavailable() {
    setVisualMode('2d');
    $('view-3d').disabled = true;
    $('spatial-notice').hidden = false;
    $('spatial-notice').textContent = '3D is unavailable in this browser. The 2D map and all observations remain available.';
  }

  function runMode(run) {
    const mode = String(run?.mode || run?.execution_mode || '').toLowerCase();
    if (['fixture', 'deterministic', 'scripted', 'demo'].includes(mode)) return 'Deterministic run';
    if (['hosted_llm', 'live_llm', 'live', 'llm', 'api'].includes(mode)) return 'Live model run';
    if (mode === 'local_llm') return 'Local model run';
    return mode ? human(mode) : run ? 'Recorded run' : 'No active run';
  }

  function renderWorkflow() {
    const run = latestRun();
    const runId = run?.id || run?.run_id;
    const cmd = commands().find((item) => !runId || item.run_id === runId);
    const issue = incidents().find((item) => item.id === cmd?.incident_id) || incidents().find((item) => !closedStates.has(String(item.status).toLowerCase())) || incidents().find((item) => !run || (dateValue(item.resolved_at)?.getTime() || 0) >= (dateValue(run.started_at)?.getTime() || Infinity));
    const hasObservations = facility()?.zones?.some((z) => Object.values(z.observations || {}).some((o) => o?.value != null)) || false;
    const needsFreshData = facility()?.zones?.some((z) => ['stale', 'missing'].includes(status(z))) || false;
    const verified = isVerified(cmd) || incidentRecovered(issue);
    const laterNotice = afterRecoveryNotice(cmd);
    const failed = cmd && failedStates.has(String(cmd.status).toLowerCase());
    const steps = [
      { title: 'Observe the facility', sub: needsFreshData ? 'Fresh observations are needed' : hasObservations ? 'Equipment observations received' : 'Waiting for current observations', done: hasObservations && !needsFreshData, warning: needsFreshData },
      { title: 'Understand the issue', sub: issue ? issue.title || human(issue.type || issue.reason || 'Incident recorded') : run ? 'Checking the facility profile' : 'Rules belong to each facility', done: !!issue || verified },
      { title: 'Take a permitted action', sub: cmd ? hasAck(cmd) ? 'Device acknowledgement received' : failed ? human(cmd.status) : 'Command sent · awaiting device' : needsFreshData ? 'Equipment control awaits fresh data' : 'Bounded by the active profile', done: hasAck(cmd), warning: !!failed || needsFreshData },
      { title: 'Verify the outcome', sub: laterNotice || (verified ? 'Later observations confirm recovery' : cmd ? 'Recovery is not yet verified' : 'Check what changed after the action'), done: !!verified && !laterNotice, warning: !!failed || !!laterNotice }
    ];
    let currentAssigned = false;
    setHTML('workflow-steps', steps.map((step, index) => {
      let cls = step.done ? 'complete' : step.warning ? 'warning' : '';
      if (!cls && run && !currentAssigned) { cls = 'current'; currentAssigned = true; }
      return `<div class="workflow-step ${cls}"><span class="step-number">${step.done ? icon('check') : index + 1}</span><span class="step-copy"><strong>${esc(step.title)}</strong><small>${esc(step.sub)}</small></span></div>`;
    }).join(''));
    $('run-mode').textContent = runMode(run);
    const runStatus = run ? `${human(run.status || 'in progress')}${run.scenario ? ` · ${human(run.scenario)}` : ''}` : 'Ready when your facility is connected.';
    setHTML('run-summary', `<span class="tiny-dot"></span><span>${esc(runStatus)}</span>`);
  }

  function renderActivity() {
    const events = ordered(scoped(state.data?.events));
    $('nav-event-count').textContent = String(events.length);
    $('event-count').textContent = `${events.length} ${events.length === 1 ? 'event' : 'events'}`;
    if (!events.length) return setHTML('activity-list', `<div class="empty-state">${icon('activity')}<strong>A clear record of what happened</strong><p>Observations, decisions and results will appear here.</p></div>`);
    setHTML('activity-list', events.slice(0, 12).map((event) => {
      const type = String(event.type || '').toLowerCase();
      const error = /denied|failed|expired|error|timeout/.test(type);
      const warning = /anomaly|incident|stale|missing|warning/.test(type);
      const glyph = error || warning ? 'alert' : /ack|recover|verif/.test(type) ? 'check' : /command|action/.test(type) ? 'bolt' : /model|tool/.test(type) ? 'document' : 'activity';
      const zoneName = facility()?.zones?.find((z) => z.id === event.zone_id)?.name || event.zone_id;
      return `<div class="activity-row"><span class="activity-icon ${error ? 'error' : warning ? 'warning' : ''}">${icon(glyph)}</span><div><div class="activity-message">${esc(event.message || human(type) || 'Recorded event')}</div><div class="activity-meta">${esc([zoneName, event.actor || human(type)].filter(Boolean).join(' · '))}</div></div><time class="activity-time" datetime="${esc(dateValue(event.timestamp || event.created_at)?.toISOString() || '')}" title="${esc(clock(event.timestamp || event.created_at))}">${esc(age(event.timestamp || event.created_at))}</time></div>`;
    }).join(''));
  }

  function actionName(command) {
    if (command.action === 'set_damper') return `Set damper to ${number(command.value)}%`;
    if (command.action === 'request_maintenance') return 'Request maintenance';
    return human(command.action || command.name || 'Equipment action');
  }

  function renderMaintenance() {
    const f = facility();
    const scenarios = $('scenario-select');
    const matching = scenarios.querySelector('option[value="no_recovery_matching_shaft"]');
    if (localShaftFacility && f?.id === localShaftFacility && !matching) {
      scenarios.add(new Option('Low airflow, shaft follows command', 'no_recovery_matching_shaft'));
    } else if (f?.id !== localShaftFacility && matching) {
      matching.remove();
    }
    const panel = $('maintenance-panel');
    panel.hidden = !f?.maintenance_enabled;
    if (panel.hidden) return;
    const orders = (state.data?.work_orders || []).filter(order =>
      order.facility_id === f.id && (!f.active_run || order.run_id === f.active_run));
    if (!orders.length) {
      setHTML('maintenance-detail', '<p class="maintenance-note">Waiting for a maintenance decision on this run.</p>');
      return;
    }
    const actions = {
      inspection: 'Inspect the ventilation system',
      inspect_actuator_feedback: 'Check actuator travel and position feedback first',
      inspect_airflow_path: 'Inspect the airflow path'
    };
    setHTML('maintenance-detail', orders.map(order => {
      const cmd = commands().find(item => item.id === order.command_id);
      const zone = f.zones.find(item => item.id === order.zone_id);
      const requested = order.requested_pct ?? cmd?.value;
      const sample = order.sample;
      const recovery = order.recovery;
      const laterNotice = afterRecoveryNotice(cmd);
      const activity = order.latest_technician_activity;
      const activityNames = {scheduled: 'Inspection scheduled', checked: 'Inspection performed', escalated: 'Specialist requested'};
      const fieldStatus = activity && activity.work_order_ri === order.resource_id && activityNames[activity.action]
        ? `<p class="field-activity"><strong>Technician activity</strong> ${esc(activityNames[activity.action])} <small>· ${esc(activity.resource_id)}</small></p>`
        : '';
      let handoff = '';
      if (workbench?.dataset.facility === f.id) {
        const address = new URL(workbench.content);
        address.searchParams.set('order', order.work_order_id);
        handoff = `<a class="button secondary" href="${esc(address.href)}" target="_blank" rel="noopener noreferrer">Open this order in the technician workbench ${icon('arrow')}</a>`;
      }
      return `<article class="maintenance-order">
      <div><span class="status-pill warning">${esc(human(order.status))}</span>
      <strong>${esc(recovery ? 'Operating recovery verified · field review remains open' : actions[order.priority] || human(order.priority))}</strong></div>
      <dl class="maintenance-measures"><div><dt>Requested opening</dt><dd>${requested == null ? 'Pending' : esc(number(requested)) + '%'}</dd></div>
      <div><dt>Independent shaft position</dt><dd>${sample ? esc(number(sample.value)) + '%' : recovery ? 'Not needed for recovery' : 'Awaiting evidence'}</dd></div>
      <div><dt>Follow-up airflow</dt><dd>${order.airflow == null ? 'See source observation' : esc(number(order.airflow)) + ' m³/h'}</dd></div></dl>
      <p>${esc(zone?.name || order.zone_id)} · ${esc(order.asset_id)} · ${esc(order.work_order_id)}</p>
      <p>${recovery ? esc(recovery.observations.length + ' qualifying post-ACK measurements · ' + recovery.observations.map(row => number(row.airflow) + ' m³/h').join(' and ')) : sample ? esc(order.mode === 'mec046' ? 'ETSI MEC 046 sensor sharing' : 'Local oneM2M sensor') + ' · ' + esc(sample.sensor_id) : esc(human(order.evidence_status))}</p>
      ${laterNotice && recovery ? `<p>${esc(laterNotice)}</p>` : ''}${fieldStatus}${handoff}<details><summary>Work order evidence</summary><pre>${esc(JSON.stringify(sanitize(order), null, 2))}</pre></details>
    </article>`;
    }).join(''));
  }

  function renderCommand() {
    const run = latestRun();
    const runId = run?.id || run?.run_id;
    const cmd = commands().find((item) => !runId || item.run_id === runId);
    if (!cmd) return setHTML('command-detail', `<div class="empty-state">${icon('check')}<strong>${run ? 'No action requested in this run.' : 'Acknowledged is a step.<br>Verified is the outcome.'}</strong><p>${facility()?.zones?.some((z) => ['stale', 'missing'].includes(status(z))) ? 'Equipment control needs current observations. Diagnose the data source before requesting a change.' : 'When an action runs, its device response and later observations stay connected here.'}</p></div>`);
    const ack = hasAck(cmd);
    const verified = isVerified(cmd);
    const failed = failedStates.has(String(cmd.status).toLowerCase());
    const zoneName = facility()?.zones?.find((z) => z.id === cmd.zone_id)?.name || cmd.zone_id || 'Facility';
    const result = typeof cmd.observed_result === 'object' ? cmd.observed_result?.message || cmd.observed_result?.reason : cmd.observed_result;
    const resultLabels = { pending: 'Later observations have not established recovery yet.', awaiting_observations: 'Waiting for later observations to check the configured recovery condition.', unresolved: 'Later observations have not met the configured recovery condition.' };
    const laterNotice = afterRecoveryNotice(cmd);
    const outcome = laterNotice || (verified ? 'Subsequent observations confirm the configured recovery condition.' : result ? resultLabels[result] || human(result) : failed ? 'This action did not establish recovery. The incident needs follow-up.' : ack ? 'The device responded. Recovery still needs to be checked against later observations.' : 'The command was recorded. A device acknowledgement has not been confirmed yet.');
    setHTML('command-detail', `<div class="command-content"><div class="command-name"><div>${esc(actionName(cmd))}<small>${esc(zoneName)} · ${esc(clock(cmd.created_at || cmd.timestamp))}</small></div><span class="status-pill ${failed ? 'error' : verified ? '' : 'warning'}">${esc(human(cmd.status || 'pending'))}</span></div><div class="command-stages"><span class="command-stage done">01 · Requested</span><span class="command-stage ${ack ? 'done' : failed ? 'failed' : 'pending'}">02 · Device ACK</span><span class="command-stage ${verified ? 'done' : failed ? 'failed' : 'pending'}">03 · Verified result</span></div><div class="command-outcome"><strong>${laterNotice ? 'Review the latest air measurements.' : verified ? 'Recovery verified.' : 'Keep the loop open.'}</strong> ${esc(outcome)}</div><div class="command-tools"><button class="button secondary" type="button" data-verify-command="${esc(cmd.id || cmd.command_id)}" ${!token || !state.connected ? 'disabled' : ''}>${icon('refresh')}Check result</button><button class="button secondary" type="button" data-command-evidence="${esc(cmd.id || cmd.command_id)}">${icon('document')}View evidence</button></div></div>`);
  }

  function sanitize(value) {
    if (Array.isArray(value)) return value.map(sanitize);
    if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([key, child]) => [key, /password|secret|api.?key|authorization|cookie|access.?token|refresh.?token|credential/i.test(key) ? '[redacted]' : sanitize(child)]));
    return value;
  }

  function openDialog(id) {
    const dialog = $(id);
    dialog.querySelectorAll('.dialog-notice').forEach((notice) => notice.remove());
    if (!dialog.open) dialog.showModal();
  }

  function evidenceSummary(run, command = null) {
    const f = facility();
    return `<div class="evidence-summary"><div><small>Facility</small>${esc(f?.name || 'No facility')}</div><div><small>Execution</small>${esc(runMode(run))}</div><div><small>Run ID</small>${esc(run?.id || run?.run_id || command?.run_id || 'No run recorded')}</div><div><small>Command ID</small>${esc(command?.id || command?.command_id || 'No command selected')}</div></div><p class="evidence-note">Physical observations and device behavior are simulated. Service responses, CSE request IDs and run records describe actual software execution only where present. A diagram or a command acknowledgement does not prove physical ventilation performance.</p>`;
  }

  async function showEvidence(commandId = null) {
    let run = latestRun();
    const cmd = commandId ? commands().find((c) => (c.id || c.command_id) === commandId) : commands().find((c) => c.run_id === (run?.id || run?.run_id));
    if (commandId && cmd?.run_id) run = scoped(state.data?.runs).find((r) => (r.id || r.run_id) === cmd.run_id) || {id:cmd.run_id};
    $('evidence-title').textContent = 'Execution evidence';
    setHTML('evidence-content', `${evidenceSummary(run, cmd)}<p>Loading the recorded evidence…</p>`);
    openDialog('evidence-dialog');
    try {
      let evidence;
      if (run?.id || run?.run_id) {
        const id = run.id || run.run_id;
        evidence = { run: await api(`/api/runs/${encodeURIComponent(id)}`), commands: commands().filter((c) => c.run_id === id), events: scoped(state.data?.events).filter((e) => e.run_id === id) };
      }
      else if (facility() && token) evidence = await api('/api/tools/read_evidence', { arguments: { facility_id: state.facilityId } });
      else evidence = { runtime: state.data?.runtime || null, facility: facility(), incidents: incidents(), commands: commands(), note: 'No run-specific evidence is available yet.' };
      setHTML('evidence-content', `${evidenceSummary(run, cmd)}<h3>Recorded service response</h3><details open><summary>Inspect the trace and outcome</summary><pre>${esc(JSON.stringify(sanitize(evidence), null, 2))}</pre></details>`);
    } catch (error) {
      setHTML('evidence-content', `${evidenceSummary(run, cmd)}<p>${esc(error.message)}</p><p>The evidence could not be retrieved. No success is inferred from this failure.</p>`);
    }
  }

  function trendSVG(z, metric) {
    const series = state.history.get(`${state.facilityId}/${z.id}/${metric}`) || [];
    if (!series.length) return '<div class="empty-inline">No timestamped observations are available for this view.</div>';
    const values = series.map((p) => p.value);
    const low = Math.min(...values), high = Math.max(...values);
    const spread = Math.max(high - low, Math.abs(high) * .1, 1);
    const points = series.map((p, i) => [20 + i * 520 / Math.max(series.length - 1, 1), 85 - (p.value - low + spread * .15) / (spread * 1.3) * 65]);
    const path = points.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
    return `<svg class="mini-trend" viewBox="0 0 560 110" role="img" aria-label="${esc(labels[metric])} observations collected since this view opened"><path d="M20 85H540M20 50H540M20 15H540" stroke="#e3ead9" stroke-width="1"/><path d="${path}" fill="none" stroke="#7c9e65" stroke-width="2"/>${points.map(([x, y]) => `<circle cx="${x}" cy="${y}" r="2.8" fill="#7c9e65"/>`).join('')}<text x="20" y="103" font-size="7" fill="#a0ae8e">${esc(clock(series[0].timestamp))}</text><text x="540" y="103" text-anchor="end" font-size="7" fill="#a0ae8e">${esc(clock(series.at(-1).timestamp))}</text></svg><div class="trend-caption">${series.length} reported observation${series.length === 1 ? '' : 's'} · collected since this view opened · ${esc(observation(z, metric).unit)}</div>`;
  }

  function inspectZone(zoneId) {
    const z = facility()?.zones?.find((item) => item.id === zoneId);
    if (!z) return;
    state.zoneId = z.id;
    renderMap();
    renderZoneDetail();
    $('evidence-title').textContent = z.name || z.id;
    const metrics = ['airflow', 'pm25', 'co2'].map((metric) => { const o = observation(z, metric); return `<div><small>${esc(labels[metric])}</small>${esc(number(o.value, metric))}<em>${esc(o.unit)}</em></div>`; }).join('');
    const fan = observation(z, 'fan_running');
    const damper = observation(z, 'damper_pct');
    setHTML('evidence-content', `<p>${esc(facility().name || state.facilityId)} · ${esc(freshness(z))}</p><div class="zone-inspect-metrics">${metrics}</div>${trendSVG(z, state.metric)}<p><strong>Fan reported:</strong> ${fan.value === true ? 'Running' : fan.value === false ? 'Stopped' : 'Not reported'} · <strong>Damper:</strong> ${esc(number(damper.value))}${damper.value != null ? '%' : ''}</p><p class="evidence-note">A running fan and an acknowledged command are equipment reports. The facility profile determines which later observations establish recovery.</p><div class="zone-action-row"><button class="button primary" type="button" data-zone-action="set_damper" data-action-zone="${esc(z.id)}" ${canAct() ? '' : 'disabled'}>${icon('wind')}Open damper in demo</button><button class="button secondary" type="button" data-zone-action="request_maintenance" data-action-zone="${esc(z.id)}" ${canAct() ? '' : 'disabled'}>${icon('tool')}Request maintenance</button></div><h3>Observation provenance</h3><details><summary>Inspect timestamps, units and quality</summary><pre>${esc(JSON.stringify(sanitize(z.observations || {}), null, 2))}</pre></details>`);
    openDialog('evidence-dialog');
  }

  async function tool(name, args) {
    if (!token) return toast('This is a read-only view. Open the configured service to perform an action.', true);
    try {
      const result = await api(`/api/tools/${encodeURIComponent(name)}`, { arguments: args });
      await poll(true);
      return result;
    } catch (error) { toast(error.message, true); return null; }
  }

  $('facility-select').addEventListener('change', (event) => {
    state.facilityId = event.target.value;
    state.outcomeCommandId = '';
    state.zoneId = facility()?.zones?.[0]?.id || '';
    try { localStorage.setItem('opensoom.facility', state.facilityId); } catch (_) { /* Optional persistence. */ }
    render();
  });
  function selectZone(id) {
    state.zoneId = id;
    state.outcomeCommandId = '';
    renderOutcomes();
    renderMap();
    renderZoneDetail();
  }

  $('air-outcome-zone').addEventListener('change', (event) => selectZone(event.target.value));
  $('air-outcome-command').addEventListener('change', (event) => {
    state.outcomeCommandId = event.target.value;
    renderOutcomes();
  });
  $('refresh-button').addEventListener('click', () => poll(true));
  document.querySelectorAll('[data-metric]').forEach((button) => button.addEventListener('click', () => {
    state.metric = button.dataset.metric;
    document.querySelectorAll('[data-metric]').forEach((item) => { const selected = item === button; item.classList.toggle('selected', selected); item.setAttribute('aria-pressed', String(selected)); });
    renderMap();
  }));
  $('facility-map').addEventListener('click', (event) => { const target = event.target.closest('[data-zone]'); if (target) selectZone(target.dataset.zone); });
  $('mobile-zones').addEventListener('click', (event) => { const target = event.target.closest('[data-zone]'); if (target) selectZone(target.dataset.zone); });
  $('facility-map').addEventListener('keydown', (event) => { if (['Enter', ' '].includes(event.key)) { const target = event.target.closest('[data-zone]'); if (target) { event.preventDefault(); selectZone(target.dataset.zone); } } });
  $('zone-detail').addEventListener('click', (event) => { const target = event.target.closest('[data-inspect-zone]'); if (target) inspectZone(target.dataset.inspectZone); });
  $('evidence-nav').addEventListener('click', () => showEvidence());
  $('view-run-button').addEventListener('click', () => showEvidence());
  $('help-open').addEventListener('click', () => openDialog('help-dialog'));
  $('help-topbar')?.addEventListener('click', () => openDialog('help-dialog'));
  document.querySelectorAll('[data-close-dialog]').forEach((button) => button.addEventListener('click', () => $(button.dataset.closeDialog).close()));
  document.querySelectorAll('dialog').forEach((dialog) => dialog.addEventListener('click', (event) => { if (event.target === dialog) { const r = dialog.getBoundingClientRect(); if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) dialog.close(); } }));

  $('start-demo-button').addEventListener('click', async () => {
    if (state.busy || !canAct()) return;
    state.busy = true;
    $('start-demo-button').disabled = true;
    $('start-demo-button').innerHTML = `${icon('refresh')}Starting…`;
    try {
      const result = await api('/api/demo/start', { facility_id: state.facilityId, scenario: $('scenario-select').value, autorun: $('autorun-toggle').checked });
      state.latestRunId = result.run_id || result.id;
      state.outcomeCommandId = '';
      state.zoneId = facility()?.zones?.[0]?.id || '';
      toast('Scenario started. Follow its recorded observations and outcomes.');
      await poll(true);
    } catch (error) { toast(error.message, true); }
    finally { state.busy = false; $('start-demo-button').innerHTML = `${icon('play')}Run scenario`; $('start-demo-button').disabled = !canAct() || !state.data?.runtime?.cse_connected; }
  });

  $('command-detail').addEventListener('click', async (event) => {
    const verify = event.target.closest('[data-verify-command]');
    const evidence = event.target.closest('[data-command-evidence]');
    if (verify) { verify.disabled = true; const result = await tool('verify_result', { facility_id: state.facilityId, command_id: verify.dataset.verifyCommand }); if (result) { toast('Result checked. The recorded outcome is shown below.'); renderCommand(); } else verify.disabled = false; }
    if (evidence) showEvidence(evidence.dataset.commandEvidence);
  });

  $('evidence-content').addEventListener('click', async (event) => {
    const button = event.target.closest('[data-zone-action]');
    if (!button || !canAct()) return;
    button.disabled = true;
    const action = button.dataset.zoneAction;
    const result = await tool('request_action', { facility_id: state.facilityId, zone_id: button.dataset.actionZone, action, value: action === 'set_damper' ? 100 : null, reason: 'Facility manager requested a profile-scoped virtual demonstration action.', request_id: `ui-${crypto.randomUUID()}` });
    if (result) { $('evidence-dialog').close(); toast('Request recorded. Check the device acknowledgement and outcome separately.'); }
    else button.disabled = false;
  });
  document.addEventListener('visibilitychange', () => { if (!document.hidden) poll(true); });
  $('view-3d').addEventListener('click', () => setVisualMode('3d'));
  $('view-2d').addEventListener('click', () => setVisualMode('2d'));
  $('motion-toggle').addEventListener('click', () => { facilityVisual?.setPaused(!facilityVisual.paused); renderMotion(); });
  $('facility-3d').addEventListener('motion-paused', renderMotion);
  $('facility-3d').addEventListener('visual-unavailable', visualUnavailable);
  import('/assets/facility-3d.js').then(({ createFacilityVisual }) => {
    facilityVisual = createFacilityVisual({ host: $('facility-3d'), labelHost: $('spatial-labels'), onSelect: selectZone });
    $('view-3d').disabled = false;
    setVisualMode('3d');
    facilityVisual.setPaused(facilityVisual.paused);
    renderMotion();
    renderVisual();
  }).catch(visualUnavailable);
  renderWorkflow();
  poll();
  setInterval(() => poll(), 2000);
})();
