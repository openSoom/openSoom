const controls = [...document.querySelectorAll('[data-inspection]')];
const decisions = {
  inspect_actuator_feedback: ['Actuator travel and position feedback', 'The independent position fell well short of the accepted setting.'],
  inspect_airflow_path: ['The airflow path', 'The shaft followed its setting within the site tolerance. The technician checks the airflow path while the operator keeps the incident open.']
};

async function loadInspections() {
  const response = await fetch('./assets/workshop-inspections.json');
  if (!response.ok) throw Error('Workshop record unavailable');
  const record = await response.json();
  const show = index => {
    const reading = record.decisions[index];
    const [action, reason] = decisions[reading.priority];
    for (const [id, value] of Object.entries({
      'comparison-air': reading.airflow,
      'comparison-request': reading.requested_pct + '%',
      'comparison-shaft': reading.shaft_pct + '%',
      'comparison-action': action,
      'comparison-reason': reason,
    })) document.getElementById(id).textContent = value;
    document.getElementById('comparison-source').href = record.source;
    controls.forEach((button, position) => button.setAttribute('aria-pressed', String(index === position)));
  };
  controls.forEach((button, index) => button.addEventListener('click', () => show(index)));
  show(0);
}
loadInspections().catch(() => controls.forEach(button => { button.disabled = true; }));
