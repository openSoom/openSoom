/* Original openSoom schematic. State comes from app.js; this renderer never generates telemetry. */
import * as THREE from './vendor/three.module.js';

const palette = {
  nominal: { floor: 0xc5ddcf, accent: 0x287a6c },
  warning: { floor: 0xf0d29b, accent: 0xb47929 },
  critical: { floor: 0xf0d29b, accent: 0xb47929 },
  recovering: { floor: 0xdce8dd, accent: 0x51896b },
  stale: { floor: 0xe0e4e2, accent: 0x89958f },
  missing: { floor: 0xe0e4e2, accent: 0x89958f },
  unknown: { floor: 0xe0e4e2, accent: 0x89958f }
};

// Animation is a presentation of current reports, never evidence that an action succeeded.
export function telemetryMotion(zone, connected, metric) {
  const current = connected && !['stale', 'missing', 'unknown'].includes(zone.status);
  const spin = current && zone.fan.quality === 'good' && zone.fan.value === true;
  const flow = spin && zone.airflow.quality === 'good' && typeof zone.airflow.value === 'number' && Number.isFinite(zone.airflow.value) && zone.airflow.value > 0 && metric === 'airflow';
  return { spin, flow };
}

export function animationStep(time, previous) {
  // A first RAF timestamp may be slightly earlier than performance.now() used to schedule it.
  return Math.max(0, Math.min((time - previous) / 1000 || 0, .05));
}

export function createFacilityVisual({ host, labelHost, onSelect }) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'low-power' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFShadowMap;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = .92;
  renderer.setClearColor(0xf6f8f2, 0);
  renderer.domElement.setAttribute('aria-hidden', 'true');
  host.appendChild(renderer.domElement);
  host.dataset.renderer = `three-${THREE.REVISION}`;
  const scene = new THREE.Scene();
  const camera = new THREE.OrthographicCamera(-8, 8, 6, -6, .1, 80);
  camera.position.set(13, 15, 18);
  camera.lookAt(0, .3, 0);
  scene.add(new THREE.HemisphereLight(0xffffff, 0x708d78, 2.4));
  const sun = new THREE.DirectionalLight(0xffffff, 3.1);
  sun.position.set(-5, 13, 8);
  sun.castShadow = true;
  sun.shadow.mapSize.set(1024, 1024);
  Object.assign(sun.shadow.camera, { left: -10, right: 10, top: 10, bottom: -10, near: .5, far: 35 });
  sun.shadow.normalBias = .04;
  scene.add(sun);
  const assembly = new THREE.Group();
  scene.add(assembly);
  const projected = new THREE.Vector3();
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  let paused = reduced.matches;
  let active = false;
  let inViewport = true;
  let raf = 0;
  let lastTime = 0;
  let frame = 0;
  let layoutKey = '';
  let zones = [];
  let disposed = false;

  function material(color, extra = {}) { return new THREE.MeshStandardMaterial({ color, roughness: .83, metalness: .04, ...extra }); }
  function box(w, h, d, color, x, y, z, parent = assembly) {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), material(color));
    mesh.position.set(x, y, z); mesh.castShadow = true; mesh.receiveShadow = true; parent.add(mesh); return mesh;
  }
  function pipe(points, radius, color, parent = assembly, extra = {}) {
    const curve = new THREE.CatmullRomCurve3(points.map((p) => new THREE.Vector3(...p)));
    const mesh = new THREE.Mesh(new THREE.TubeGeometry(curve, 24, radius, 8, false), material(color, extra));
    parent.add(mesh); return { curve, mesh };
  }
  function clear() {
    assembly.traverse((object) => { object.geometry?.dispose(); if (Array.isArray(object.material)) object.material.forEach((m) => m.dispose()); else object.material?.dispose(); });
    assembly.clear(); labelHost.replaceChildren(); zones = [];
  }
  function rebuild(data) {
    clear();
    const count = data.zones.length;
    if (!count) return;
    const columns = count === 1 ? 1 : count <= 3 ? 2 : 3;
    const rows = count === 3 ? 2 : Math.ceil(count / columns);
    const width = 10.6, depth = Math.max(7.4, rows * 3.7);
    box(width + .7, .26, depth + .7, 0xdfe6db, 0, -.24, 0);
    box(width + .3, .08, depth + .3, 0xfafbf6, 0, -.065, 0);
    data.zones.forEach((zone, index) => {
      const wide = count === 3 && index === 2;
      const w = wide ? width : width / columns;
      const d = depth / rows;
      const x = wide ? 0 : -width / 2 + w / 2 + index % columns * w;
      const z = -depth / 2 + d / 2 + Math.floor(index / columns) * d;
      const room = new THREE.Group(); assembly.add(room);
      const floor = box(w - .16, .08, d - .16, palette.unknown.floor, x, .02, z, room);
      // Cutaway walls deliberately omit the camera-facing sides.
      box(w - .1, .85, .12, 0xf1f3e9, x, .47, z - d / 2, room);
      box(.12, .85, d - .1, 0xf1f3e9, x - w / 2, .47, z, room);
      box(w - .1, .045, .15, 0xb9cbbd, x, .91, z - d / 2, room);
      const outline = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(w - .18, .08, d - .18)), new THREE.LineBasicMaterial({ color: palette.unknown.accent, transparent: true, opacity: .5 }));
      outline.position.set(x, .075, z); room.add(outline);
      // An illustrative exhaust module, duct and reported-running rotor.
      const fx = x + w / 2 - .85, fz = z - d / 2 + .75;
      box(1.12, .72, 1.06, 0xe7ece5, fx, .45, fz, room);
      const housing = new THREE.Mesh(new THREE.CylinderGeometry(.39, .39, .12, 32), material(0x344c45));
      housing.position.set(fx, .9, fz); room.add(housing);
      const rotor = new THREE.Group(); rotor.position.set(fx, .99, fz); room.add(rotor);
      for (let blade = 0; blade < 4; blade += 1) {
        const shape = new THREE.Mesh(new THREE.BoxGeometry(.11, .04, .59), material(0xe3eee6));
        shape.rotation.y = blade * Math.PI / 2 + .22; rotor.add(shape);
      }
      const hub = new THREE.Mesh(new THREE.SphereGeometry(.085, 12, 8), material(0xb8d1c0)); rotor.add(hub);
      pipe([[fx, .65, fz - .45], [fx, 1.45, fz - .62], [fx, 1.7, z - d / 2 - .16]], .13, 0xb5c7bd, room);
      const sensor = box(.24, .34, .14, 0xffffff, x - w / 2 + .48, 1.13, z - d / 2 + .1, room);
      const light = box(.08, .08, .02, palette.unknown.accent, sensor.position.x, 1.15, sensor.position.z + .08, room);
      // Thin paths and beads indicate a relationship, never a CFD field or velocity scale.
      const flowGroup = new THREE.Group(); room.add(flowGroup);
      const paths = [];
      for (let lane = 0; lane < 3; lane += 1) {
        const startX = x - w * .3 + lane * .3;
        const startZ = z + d * .28 - lane * .13;
        const path = pipe([[startX, .17, startZ], [x + lane * .17, .36, z + .1], [fx - .45, .6, fz + .3], [fx, .93, fz]], .014, palette.unknown.accent, flowGroup, { transparent: true, opacity: .36 });
        const bead = new THREE.Mesh(new THREE.SphereGeometry(.065, 8, 6), material(palette.unknown.accent)); flowGroup.add(bead);
        paths.push({ ...path, bead, phase: lane / 3 });
      }
      const button = document.createElement('button');
      button.type = 'button'; button.className = 'spatial-zone';
      const title = document.createElement('span'), value = document.createElement('strong'), quality = document.createElement('small');
      button.append(title, value, quality); button.addEventListener('click', () => onSelect(zone.id)); labelHost.append(button);
      zones.push({ id: zone.id, floor, outline, rotor, light, paths, flowGroup, button, title, value, quality, labelPoint: new THREE.Vector3(x - w * .08, .1, z + d * .28), spin: false, flow: false });
    });
    host.dataset.zoneCount = String(count);
    resize();
  }
  function positionLabels() {
    zones.forEach((zone) => {
      projected.copy(zone.labelPoint).project(camera);
      zone.button.style.left = `${(projected.x * .5 + .5) * 100}%`;
      zone.button.style.top = `${(-projected.y * .5 + .5) * 100}%`;
    });
  }
  function draw() {
    if (!disposed && active && host.clientWidth && host.clientHeight) { renderer.render(scene, camera); positionLabels(); }
  }
  function tick(time) {
    raf = 0;
    if (disposed || !active || !inViewport || document.hidden || paused) return;
    const delta = animationStep(time, lastTime); lastTime = time;
    frame += delta;
    zones.forEach((zone) => {
      if (zone.spin) zone.rotor.rotation.y += delta * 2;
      if (zone.flow) zone.paths.forEach((path) => path.bead.position.copy(path.curve.getPoint((frame * .17 + path.phase) % 1)));
    });
    draw();
    if (zones.some((zone) => zone.spin || zone.flow)) raf = requestAnimationFrame(tick);
  }
  function schedule() {
    draw();
    if (!raf && active && inViewport && !paused && !document.hidden && zones.some((zone) => zone.spin || zone.flow)) { lastTime = performance.now(); raf = requestAnimationFrame(tick); }
  }
  function resize() {
    const width = host.clientWidth, height = host.clientHeight;
    if (!width || !height) return;
    renderer.setSize(width, height, false);
    const aspect = width / height;
    // Fit real mesh bounds, so a larger canvas does not leave a tiny building in its center.
    camera.updateMatrixWorld();
    const bounds = new THREE.Box3().setFromObject(assembly);
    const viewBounds = new THREE.Box3();
    if (!bounds.isEmpty()) {
      for (const x of [bounds.min.x, bounds.max.x]) for (const y of [bounds.min.y, bounds.max.y]) for (const z of [bounds.min.z, bounds.max.z]) viewBounds.expandByPoint(new THREE.Vector3(x, y, z).applyMatrix4(camera.matrixWorldInverse));
    }
    const size = viewBounds.isEmpty() ? new THREE.Vector3(12, 8, 1) : viewBounds.getSize(new THREE.Vector3());
    const center = viewBounds.isEmpty() ? new THREE.Vector3() : viewBounds.getCenter(new THREE.Vector3());
    const halfHeight = Math.max(size.y / .79, size.x / aspect / .84) / 2;
    camera.left = center.x - halfHeight * aspect; camera.right = center.x + halfHeight * aspect;
    camera.top = center.y + halfHeight; camera.bottom = center.y - halfHeight;
    host.dataset.meshWidthRatio = (size.x / (2 * halfHeight * aspect)).toFixed(3);
    host.dataset.meshHeightRatio = (size.y / (2 * halfHeight)).toFixed(3);
    camera.updateProjectionMatrix(); draw();
  }
  function update(data) {
    const key = `${data.facilityId}/${data.zones.map((zone) => zone.id).join('/')}`;
    if (key !== layoutKey) { layoutKey = key; rebuild(data); }
    host.dataset.runId = data.runId || '';
    host.dataset.connection = data.connected ? 'connected' : 'unavailable';
    zones.forEach((object) => {
      const zone = data.zones.find((item) => item.id === object.id);
      const color = palette[zone.status] || palette.unknown;
      const motion = telemetryMotion(zone, data.connected, data.metric);
      object.spin = motion.spin; object.flow = motion.flow;
      const selected = data.selectedZoneId === zone.id;
      object.floor.material.color.setHex(color.floor);
      object.outline.material.color.setHex(color.accent); object.outline.material.opacity = selected ? 1 : .35;
      object.light.material.color.setHex(color.accent);
      object.flowGroup.visible = object.flow;
      object.paths.forEach((path) => { path.mesh.material.color.setHex(color.accent); path.bead.material.color.setHex(color.accent); path.bead.position.copy(path.curve.getPoint(path.phase + .1)); });
      object.button.className = `spatial-zone ${zone.status}${selected ? ' selected' : ''}`;
      object.button.setAttribute('aria-pressed', String(selected));
      object.button.setAttribute('aria-label', `${zone.name}, ${data.metricLabel} ${zone.reading}, ${zone.statusLabel.toLowerCase()}`);
      object.button.dataset.zone = zone.id;
      object.button.dataset.flow = object.flow ? 'illustrative' : 'hidden';
      object.title.textContent = zone.name; object.value.textContent = zone.reading; object.quality.textContent = zone.statusLabel;
    });
    schedule();
  }
  const resizeObserver = new ResizeObserver(resize); resizeObserver.observe(host);
  const intersectionObserver = new IntersectionObserver(([entry]) => { inViewport = entry.isIntersecting; schedule(); }, { rootMargin: '100px' }); intersectionObserver.observe(host);
  const visibility = () => schedule(); document.addEventListener('visibilitychange', visibility);
  const onReducedChange = (event) => { if (event.matches) { paused = true; host.dispatchEvent(new CustomEvent('motion-paused')); schedule(); } };
  reduced.addEventListener('change', onReducedChange);
  renderer.domElement.addEventListener('webglcontextlost', (event) => { event.preventDefault(); active = false; host.dispatchEvent(new CustomEvent('visual-unavailable')); });
  return {
    update,
    setActive(value) { active = value; host.dataset.active = String(value); resize(); schedule(); },
    setPaused(value) { paused = value; host.dataset.motion = paused ? 'paused' : 'playing'; schedule(); },
    get paused() { return paused; },
    destroy() { disposed = true; cancelAnimationFrame(raf); resizeObserver.disconnect(); intersectionObserver.disconnect(); document.removeEventListener('visibilitychange', visibility); reduced.removeEventListener('change', onReducedChange); clear(); renderer.dispose(); renderer.domElement.remove(); }
  };
}
