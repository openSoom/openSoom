(() => {
  'use strict';
  const byId = (id) => document.getElementById(id);
  const titles = {inspection: 'Inspect the ventilation system', inspect_actuator_feedback: 'Check actuator travel and position feedback first', inspect_airflow_path: 'Inspect the airflow path first'};
  const activities = {scheduled:'Inspection scheduled', checked:'Inspection performed', escalated:'Specialist requested'};
  const requested = new URLSearchParams(location.search).get('order');
  let selected = requested, current = null, reviewing = null, savedAction = null, pending = false, fetching = false;
  function label(id, text) { byId(id).textContent = text; }
  function resetForm() { byId('inspection').reset(); reviewing = null; savedAction = null; label('save-state', ''); }
  function displayNumber(value, unit) { return value == null ? 'Awaiting evidence' : Number(value).toLocaleString() + unit; }
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
    label('priority', titles[order.priority] || 'Review maintenance evidence');
    label('context', order.zone_name + ' · ' + order.asset_id);
    label('requested', displayNumber(order.requested_pct, '%'));
    label('position', displayNumber(order.sample?.value, '%'));
    label('flow', displayNumber(order.airflow, ' m³/h'));
    const evid = order.sample && (order.mode === 'mec046' ? 'MEC 046 sensor sharing' : 'Local oneM2M sensor');
    const source = order.target_source === 'work_order_cin' ? 'Target recorded with this work order' : 'Current profile target (historical target unavailable)';
    const target = source + ' ' + displayNumber(order.configured_target_m3_h, ' m³/h') + '. ';
    label('reason', target + (evid ? 'Independent position supplied by ' + evid + '.' : 'The maintenance app is awaiting current independent evidence.'));
    const details = byId('provenance'); details.replaceChildren();
    for (const [title, value] of [
      ['Work order', order.work_order_id], ['Revision', order.revision || 'Awaiting new evidence'], ['Work-order CIN',order.resource_id], ['Profile version',order.profile_version],
      ['Incident',order.incident_id], ['Command',order.command_id], ['Follow-up airflow CIN',order.source_cin_ri],
      ['Position source',order.sample?.sensor_id], ['Position measurement time',order.sample?.observed_at], ['Service response CIN',order.response_ri],
      ['Position sample CIN',order.provider_receipt?.sample_cin_ri], ['Record read request',order.read_rqi]
    ]) row(details, title, value);
    byId('save').disabled = pending || !order.resource_id || (reviewing !== null && reviewing !== order.resource_id);
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
      if (!response.ok) throw Error('Facility queue unavailable. Reload to reconnect.');
      const data = await response.json(), queue = byId('queue');
      label('facility', data.facility.name);
      label('scope', data.facility.simulation ? 'Local demonstration with simulated equipment.' : 'Commissioned facility profile.');
      const orders = data.work_orders;
      const choices = orders.map(o => new Option(o.zone_name + ' · ' + o.work_order_id, o.work_order_id));
      if (selected && !orders.some(o => o.work_order_id === selected)) choices.unshift(new Option('Requested work order unavailable', selected));
      if (!selected && orders.length) selected = orders[0].work_order_id;
      if (!choices.length) choices.push(new Option('No work orders yet', ''));
      const prior = Array.from(queue.options);
      if (prior.length !== choices.length || choices.some((option, i) => option.value !== prior[i]?.value || option.text !== prior[i]?.text)) queue.replaceChildren(...choices);
      if (queue.value !== (selected || '')) queue.value = selected || '';
      label('status', orders.length + (orders.length === 1 ? ' work order' : ' work orders') + ' in this facility');
      render(orders.find(o => o.work_order_id === selected));
    } catch (err) {label('status', err.message); current = null; byId('save').disabled = true;}
    finally { fetching = false; }
  }
  byId('queue').addEventListener('change', event => {
    selected = event.target.value; resetForm(); render(null);
    history.replaceState(null,'','?order=' + encodeURIComponent(selected)); refresh();
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
    } catch(err) {label('save-state',err.message);}
    finally { pending = false; await refresh(); }
  });
  refresh(); window.setInterval(refresh, 3000);
})();
