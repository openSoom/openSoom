const film = document.querySelector('#role-film video');
const loopback = ['localhost', '127.0.0.1', '[::1]'].includes(location.hostname);
let seekableCopy;

function prepareFilm() {
  if (!loopback) return Promise.resolve();
  // Python's static server serves the full MP4 without HTTP byte ranges.
  // Load a seekable local copy on first play so both chapters also work offline.
  seekableCopy ??= fetch(film.querySelector('source').src)
    .then(response => {
      if (!response.ok) throw new Error('Local film unavailable');
      return response.blob();
    })
    .then(blob => new Promise((resolve, reject) => {
      film.addEventListener('loadedmetadata', resolve, {once: true});
      film.addEventListener('error', reject, {once: true});
      film.src = URL.createObjectURL(blob);
    }))
    .catch(() => {
      film.removeAttribute('src');
      film.load();
    });
  return seekableCopy;
}

async function playFilm(start) {
  await prepareFilm();
  if (start !== undefined) film.currentTime = start;
  film.play().catch(() => { film.controls = true; });
}

film.addEventListener('play', () => {
  if (loopback && !seekableCopy) playFilm(film.currentTime);
}, {once: true});
document.getElementById('play-role-film').addEventListener('click', () => {
  film.focus();
  playFilm();
});
for (const button of document.querySelectorAll('[data-film-start]')) {
  button.addEventListener('click', () => playFilm(Number(button.dataset.filmStart)));
}

const buttons = [...document.querySelectorAll('[data-outcome]')];
const put = (id, value) => { document.getElementById(id).textContent = value; };
const decimal = new Intl.NumberFormat('en', { maximumFractionDigits: 1 });
const fmt = value => Number.isFinite(value) ? decimal.format(value) : '—';
const seconds = value => Number.isFinite(value) ? fmt(value) + ' s' : 'Not observed';

function drawOutcome(study, id) {
  const outcome = study[id];
  const {baseline, latest, targets} = outcome;
  for (const [metric, prefix] of [['pm25', 'pm'], ['co2', 'co']]) {
    const before = baseline?.[metric];
    const after = latest?.[metric];
    put(prefix + '-before', fmt(before));
    put(prefix + '-after', fmt(after));
    const diff = Number.isFinite(before) && Number.isFinite(after) ? after - before : null;
    put(prefix + '-delta', diff === null ? '—' : (diff > 0 ? '+' : diff < 0 ? '−' : '') + fmt(Math.abs(diff)));
  }
  const first = outcome.time_to_target_seconds;
  const current = outcome.hold_seconds;
  const previous = outcome.last_hold_seconds;
  const prior = current == null && Number.isFinite(previous);
  put('air-first', seconds(first));
  put('air-hold-label', prior ? 'Last observed spell in range' : 'Observed time in range');
  put('air-hold', seconds(prior ? previous : current));
  put('air-verdict', current != null ? 'Both readings reached the zone targets.' :
    (prior ? 'Particles exceeded the target again. Keep the air alert open.' : 'Keep the alert open. Particles exceeded the zone target.'));
  put('air-rule', 'Zone targets are PM2.5 ≤ ' + fmt(targets.pm25) + ' µg/m³ and CO₂ ≤ ' + fmt(targets.co2) +
    ' ppm. Airflow was 1,035 m³/h after the command in each recorded trial.');
  for (const button of buttons) button.setAttribute('aria-pressed', String(button.dataset.outcome === id));
}

try {
  const response = await fetch(new URL('./assets/air-quality-trials.json', import.meta.url));
  if (!response.ok) throw new Error('Recorded trials unavailable');
  const study = await response.json();
  for (const button of buttons) {
    button.addEventListener('click', () => drawOutcome(study, button.dataset.outcome));
  }
  drawOutcome(study, buttons[0].dataset.outcome);
} catch {
  put('air-verdict', 'Recorded measurements could not be loaded. Open the timestamped records below.');
  for (const button of buttons) button.disabled = true;
}
