const buttons = [...document.querySelectorAll('[data-decision]')];
const byId = id => document.getElementById(id);

async function loadRecord() {
  const response = await fetch('assets/maintenance-run.json');
  if (!response.ok) throw new Error('Run record unavailable');
  const run = await response.json();
  const command = run.command;
  const sample = run.after.sample;
  const flow = run.airflow;
  const stages = [
    ['Requested damper opening', command.value + '%', 'The controller received the command.',
      'The virtual actuator acknowledged the setting. The site operator waits for a fresh airflow measurement.'],
    ['Airflow after acknowledgement', flow.observed + ' ' + flow.unit, 'Keep the incident open.',
      'The target for this simulated zone is ' + flow.target + ' ' + flow.unit + '. The technician starts with a general inspection.'],
    ['Independent shaft position', sample.value + sample.unit, 'Check actuator travel and position feedback first.',
      'The technician compares the shaft position with the requested opening. The same work order now names the first inspection. The airflow incident remains open.']
  ];
  function show(index) {
    const [label, value, title, note] = stages[index];
    for (const [id, content] of Object.entries({'decision-label':label, 'decision-value':value,
      'decision-title':title, 'decision-note':note})) byId(id).textContent = content;
    buttons.forEach((button, position) => button.setAttribute('aria-pressed', String(index === position)));
    byId('decision-id').textContent = index === 0 ? command.id : run.after.work_order_id;
  }
  buttons.forEach((button, index) => button.addEventListener('click', () => show(index)));
  show(0);
}
loadRecord().catch(() => {
  byId('decision-id').textContent = 'Read the linked CSE record for this example.';
  buttons.forEach(button => button.disabled = true);
});

const routes = {
  missing: {
    title: 'Keep the general inspection open.',
    detail: 'The site has an ACK and low airflow. Without a fresh independent position, the technician cannot yet choose between the actuator and the airflow path.',
    evidence: 'Open work order before the independent reading · demo-271a6c3a23',
    file: 'maintenance-release-local.json',
    steps: [
      ['Operations AE', 'Records the ACK and low airflow in the MN-CSE.'],
      ['Facility bridge', 'Finds no valid independent reading for the asset.'],
      ['Maintenance AE', 'Keeps the general inspection open.']
    ]
  },
  local: {
    title: 'The position sensor publishes locally.',
    detail: 'The bridge reads a separate sensor AE’s content instance. The maintenance app receives a measurement with its sensor ID, unit and observation time.',
    evidence: 'Local MN-CSE · demo-271a6c3a23',
    file: 'maintenance-release-local.json',
    steps: [
      ['Independent sensor AE', 'Publishes a shaft reading to the local MN-CSE.'],
      ['Facility bridge', 'Checks the asset, unit and observation time.'],
      ['Maintenance AE', 'Reads the response and revises its work order.']
    ]
  },
  cloud: {
    title: 'The bridge asks the external sensor provider.',
    detail: 'The site administrator commissions an approved provider through MEC 033. The bridge uses the MEC registry and MEC 046 Sensor Sharing, then returns the shaft reading to the MN-CSE. The maintenance app updates the pending work order.',
    evidence: 'Private cloud · actual MEC 033 and 046 · demo-a8c5ef7ada',
    file: 'option-c/commissioned-sensor-roundtrip.json',
    steps: [
      ['MN-CSE · selected MEC edge', 'Holds the approved provider request and the open work order.'],
      ['Facility bridge · MEC services', 'Uses 033 to connect the provider and 046 to configure a subscription and query the sensor.'],
      ['Maintenance AE · same edge', 'Reads the checked response from the MN-CSE and revises the existing order.']
    ]
  }
};
const routeButtons = [...document.querySelectorAll('[data-route]')];
for (const button of routeButtons) {
  button.addEventListener('click', () => {
    const route = routes[button.dataset.route];
    byId('route-title').textContent = route.title;
    byId('route-description').textContent = route.detail;
    const items = byId('route-steps').children;
    route.steps.forEach(([actor, operation], index) => {
      items[index].querySelector('strong').textContent = actor;
      items[index].querySelector('span').textContent = operation;
    });
    byId('route-proof').textContent = route.evidence;
    byId('route-source').href = 'https://github.com/openSoom/openSoom/blob/main/evidence/runtime/' + route.file;
    routeButtons.forEach(item => item.setAttribute('aria-pressed', String(item === button)));
  });
}
