(() => {
  'use strict';
  const byId = (id) => document.getElementById(id);
  const titles = {inspection: 'Inspect the ventilation system', inspect_actuator_feedback: 'Check actuator travel and position feedback first', inspect_airflow_path: 'Inspect the airflow path first'};
  const activities = {scheduled:'Inspection scheduled', checked:'Inspection performed', escalated:'Specialist requested'};
  const requested = new URLSearchParams(location.search).get('order');
  let selected = requested, current = null, reviewing = null, savedAction = null, pending = false, fetching = false;
  let queueSignature = '';
  function label(id, text) {
    const element = byId(id);
    if (element.textContent !== text) element.textContent = text;
  }
  function resetForm() { byId('inspection').reset(); reviewing = null; savedAction = null; label('save-state', ''); }
  function displayNumber(value, unit) { return value == null ? 'Awaiting evidence' : Number(value).toLocaleString() + unit; }
  const missingReason = {
    awaiting_outcome: 'Waiting for the response to the ventilation action.',
    awaiting_current_command_followup: 'Waiting for measurements after the latest command.',
    awaiting_independent_sample: 'Waiting for the independent shaft measurement.',
    unknown: 'Independent shaft evidence is unavailable for this revision.'
  };
  function workItem(order) {
    const entry = (order.inspections || []).find(item => order.resource_id && item.work_order_ri === order.resource_id);
    let title = 'Inspect ventilation';
    let state = 'Awaiting evidence';
    let rank = 3;
    if (order.recovery) {
      title = 'Review operating recovery';
      state = 'Recovery verified';
      rank = 1;
    } else if (order.priority === 'inspect_actuator_feedback' || order.priority === 'inspect_airflow_path') {
      title = order.priority === 'inspect_actuator_feedback' ? 'Check actuator travel' : 'Inspect airflow path';
      state = 'Ready to inspect';
      rank = 0;
    } else if (order.evidence_status === 'awaiting_outcome') {
      state = 'Awaiting action outcome';
    } else if (order.evidence_status === 'awaiting_current_command_followup') {
      state = 'Awaiting new measurements';
    }
    if (entry) {
      state = activities[entry.action] || 'Activity recorded';
      rank = 2;
    }
    const reference = order.work_order_id.replace(/^work-incident-/, '');
    return {id: order.work_order_id, zone: order.zone_name, title, state, rank, reference};
  }
  function chooseOrder(id) {
    selected = id;
    resetForm();
    history.replaceState(null, '', '?order=' + encodeURIComponent(id));
    render(null);
    refresh();
  }
  function updateQueue(items) {
    const sig = JSON.stringify(items);
    const queue = byId('queue');
    const missing = selected && !items.some(item => item.id === selected);
    const needsMissingOption = Boolean(missing) !== Boolean(queue.querySelector('[data-missing]'));
    if (sig !== queueSignature || needsMissingOption) {
      const priorFocus = document.activeElement?.closest('.work-item')?.value;
      const buttons = [];
      const options = [];
      for (const item of items) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'work-item';
        button.value = item.id;
        button.dataset.kind = item.rank === 0 ? 'ready' : 'other';
        for (const [cls, text] of [['work-title', item.title], ['work-meta', item.zone + ' · ' + item.reference], ['work-state', item.state]]) {
          const span = document.createElement('span');
          span.className = cls;
          span.textContent = text;
          button.append(span);
        }
        buttons.push(button);
        options.push(new Option(item.title + ' · ' + item.state + ' · ' + item.zone + ' · ' + item.reference, item.id));
      }
      if (missing) {
        const option = new Option('Requested work order unavailable', selected);
        option.dataset.missing = 'true';
        options.unshift(option);
      }
      if (!options.length) options.push(new Option('No work orders yet', ''));
      queue.replaceChildren(...options);
      byId('worklist').replaceChildren(...buttons);
      if (priorFocus) buttons.find(button => button.value === priorFocus)?.focus({preventScroll:true});
      queueSignature = sig;
    }
    if (queue.value !== (selected || '')) queue.value = selected || '';
    for (const button of byId('worklist').children) button.setAttribute('aria-current', String(button.value === selected));
  }
  function plotBar(id, value, maximum, tone) {
    const el = byId(id);
    const missing = !Number.isFinite(value) || !Number.isFinite(maximum) || maximum <= 0;
    el.dataset.missing = String(missing);
    el.dataset.tone = tone;
    el.querySelector('.reading').setAttribute('width', String(missing ? 0 : Math.min(100, Math.max(0, 100 * value / maximum))));
  }
  function renderMeasurements(order) {
    const target = order.configured_target_m3_h;
    const flow = order.airflow;
    const position = order.recovery ? null : order.sample?.value;
    label('requested', displayNumber(order.requested_pct, '%'));
    label('position', order.recovery ? 'Not required' : displayNumber(position, '%'));
    label('flow', displayNumber(flow, ' m³/h'));
    byId('requested').dataset.missing = String(!Number.isFinite(order.requested_pct));
    byId('position').dataset.missing = String(!Number.isFinite(position));
    byId('flow').dataset.missing = String(!Number.isFinite(flow));
    plotBar('requested-rail', order.requested_pct, 100, 'normal');
    plotBar('position-rail', position, 100, order.priority === 'inspect_actuator_feedback' ? 'short' : 'normal');
    // Leave headroom so a target at or above the measured value is still visible.
    const largest = Math.max(Number.isFinite(target) ? target : 0, Number.isFinite(flow) ? flow : 0);
    const magnitude = largest > 0 ? 10 ** Math.floor(Math.log10(largest)) : 1;
    const maximum = largest > 0 ? Math.ceil(largest * 1.15 / magnitude) * magnitude : 1;
    plotBar('flow-rail', flow, maximum, Number.isFinite(flow) && Number.isFinite(target) && flow < target ? 'short' : 'normal');
    const marker = byId('flow-rail').querySelector('.target-mark');
    marker.setAttribute('visibility', Number.isFinite(target) ? 'visible' : 'hidden');
    if (Number.isFinite(target)) {
      const x = String(100 * target / maximum);
      marker.setAttribute('x1', x);
      marker.setAttribute('x2', x);
    }
    label('flow-scale', largest > 0 ? displayNumber(maximum, ' m³/h') : '—');
    label('flow-target', Number.isFinite(target) ? 'Target ' + displayNumber(target, ' m³/h') : 'Target unavailable');
  }
  function row(parent, name, value) {
    if (value == null) return;
    const dt = document.createElement('dt'), dd = document.createElement('dd');
    dt.textContent = name; dd.textContent = value; parent.append(dt, dd);
  }
  function render(order) {
    current = order || null;
    byId('order').hidden = !order;
    if (!order) return;
    label('order-state', 'Work order ' + order.status);
    const recovery = order.recovery;
    label('decision-kind', recovery ? 'Operating recovery' : order.priority === 'inspection' ? 'Inspection planning' : 'First inspection');
    label('priority', recovery ? 'Review verified operating recovery' : titles[order.priority] || 'Review maintenance evidence');
    label('context', [order.zone_name, order.asset_id, order.revision ? 'Revision ' + order.revision : 'Awaiting revision'].filter(Boolean).join(' · '));
    renderMeasurements(order);
    const source = order.target_source === 'work_order_cin' ? 'Target recorded with this work order' : 'Current profile target (historical target unavailable)';
    const target = Number.isFinite(order.configured_target_m3_h) ? source + ' ' + displayNumber(order.configured_target_m3_h, ' m³/h') + '.' : '';
    const evidence = order.mode === 'mec046' ? 'MEC 046 sensor sharing' : 'Local oneM2M sensor';
    const reason = recovery
      ? recovery.observations.length + ' fresh observations met the operating profile after the device ACK. The work order remains open for field review.'
      : order.sample ? 'Independent position supplied by ' + evidence + '.' : missingReason[order.evidence_status] || 'No independent measurement recorded for this revision.';
    label('reason', [target, reason].filter(Boolean).join(' '));
    const details = byId('provenance'); details.replaceChildren();
    for (const [title, value] of [
      ['Work order', order.work_order_id], ['Revision', order.revision || 'Awaiting new evidence'], ['Work-order CIN',order.resource_id], ['Profile version',order.profile_version],
      ['Incident',order.incident_id], ['Command',order.command_id], ['Follow-up airflow CIN',order.source_cin_ri],
      ['Position source',order.sample?.sensor_id], ['Position measurement time',order.sample?.observed_at], ['Service response CIN',order.response_ri],
      ['Position sample CIN',order.provider_receipt?.sample_cin_ri], ['Record read request',order.read_rqi]
    ]) row(details, title, value);
    if (recovery) {
      row(details, 'Device ACK CIN', recovery.ack.cin_ri);
      recovery.observations.forEach((obs, i) => row(details, 'Recovery observation ' + (i + 1),
        displayNumber(obs.airflow, ' m³/h') + ' · ' + obs.observed_at + ' · ' + obs.cin_ri));
    }
    byId('save').disabled = pending || !order.resource_id || !byId('action').value || reviewing !== order.resource_id;
    if (reviewing && reviewing !== order.resource_id) label('save-state', 'A new revision arrived. Change the activity selection to confirm you reviewed the latest recommendation.');
    const history = byId('history'); history.replaceChildren();
    if (order.inspections.length) {
      const h = document.createElement('h3'); h.textContent = 'Inspection history'; history.append(h);
      const list = document.createElement('ul');
      for (const activity of order.inspections) {
        const li = document.createElement('li'); li.textContent = (activities[activity.action] || activity.action) + (activity.note ? ' — ' + activity.note : '') + ' · ' + activity.recorded_at + ' · ' + activity.resource_id; list.append(li);
      }
      history.append(list);
    }
  }
  async function refresh() {
    if (fetching) return;
    fetching = true;
    try {
      const response = await fetch('/api/work-orders');
      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        if (response.status === 401 || response.status === 403 || error.rsc === 4103) {
          resetForm();
          byId('provenance').replaceChildren();
          byId('history').replaceChildren();
        }
        throw Error('Facility queue unavailable. Reload to reconnect.');
      }
      const data = await response.json();
      label('facility', data.facility.name);
      label('scope', data.facility.simulation ? 'Simulated equipment' : 'Commissioned facility profile');
      const orders = data.work_orders;
      const items = orders.map(workItem).sort((a, b) => a.rank - b.rank);
      if (!selected && items.length) selected = items[0].id;
      updateQueue(items);
      label('status', orders.length + (orders.length === 1 ? ' work order' : ' work orders'));
      const chosen = orders.find(o => o.work_order_id === selected);
      byId('empty-state').hidden = Boolean(chosen);
      if (!chosen) label('empty-state', selected ? 'This work order is unavailable in the current facility.' : 'No work orders have been opened in this facility.');
      render(chosen);
    } catch (err) {
      render(null);
      queueSignature = '';
      byId('worklist').replaceChildren();
      byId('queue').replaceChildren(new Option('Queue unavailable', ''));
      byId('save').disabled = true;
      byId('empty-state').hidden = false;
      label('empty-state', 'Waiting for the facility queue to reconnect.');
      label('status', err.message);
    }
    finally { fetching = false; }
  }
  byId('queue').addEventListener('change', event => chooseOrder(event.target.value));
  byId('worklist').addEventListener('click', event => {
    const button = event.target.closest('.work-item');
    if (button && button.value !== selected) chooseOrder(button.value);
  });
  byId('action').addEventListener('change', () => {
    reviewing = current?.resource_id || null; savedAction = null; label('save-state',''); if (current) render(current);
  });
  byId('note').addEventListener('input', () => { savedAction = null; });
  byId('inspection').addEventListener('submit', async event => {
    event.preventDefault(); if (pending || !current?.resource_id || reviewing !== current.resource_id) return;
    pending = true; byId('save').disabled = true;
    const orderId = current.work_order_id;
    const payload = {work_order_ri: reviewing, action:byId('action').value, note:byId('note').value.trim(), request_id:savedAction || crypto.randomUUID()};
    savedAction = payload.request_id;
    try {
      const response = await fetch('/api/work-orders/' + encodeURIComponent(orderId) + '/inspections', {method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(payload)});
      const result = await response.json();
      if (!response.ok) throw Error(typeof result.detail === 'string' ? result.detail : 'The inspection entry could not be saved.');
      if(selected===orderId) {resetForm(); label('save-state','Inspection entry recorded · ' + result.resource_id);}
    } catch(err) {if (selected === orderId) label('save-state',err.message);}
    finally { pending = false; await refresh(); }
  });
  refresh(); window.setInterval(refresh, 3000);
})();
