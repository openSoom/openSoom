// Explanatory animation only. No service requests or fabricated measured values.
const root = document.querySelector('#journey');
const stages = [
  {label:'Observation',resource:'CIN · timestamps',title:'Start with an observation, not an assumption.',en:'The adapter preserves the reported value, unit and observation time. A running fan and insufficient exhaust can coexist.',ko:'센서 값·단위·측정 시각을 함께 보관합니다. 팬이 켜져 있다는 값만으로 환기가 충분하다고 판단하지 않습니다.'},
  {label:'Shared CSE',resource:'SUB · GRP · ACP',title:'The common service layer shares the evidence.',en:'A native subscription notifies the service. Group reads retrieve zone observations, subject to access policies. The service reads the CSE again before diagnosis.',ko:'oneM2M이 알림·그룹 조회·접근 권한을 제공합니다. 알림 자체를 진실로 쓰지 않고 CSE의 자원을 다시 읽습니다.'},
  {label:'Policy check',resource:'Scope · freshness',title:'Check whether the proposed action is allowed.',en:'The service validates role, facility, profile, data freshness and allowed action. The AI can request an action; it cannot grant itself permission.',ko:'AI는 조치를 요청할 수 있지만 자기 권한을 늘릴 수 없습니다. 서비스가 역할·시설·프로필·최신 데이터·허용 조치를 확인합니다.'},
  {label:'Command',resource:'Command CIN',title:'A stored command is the beginning of execution.',en:'An authorized command is written to a CSE resource with an identity and expiry. CSE acceptance alone does not establish that equipment acted.',ko:'허용된 명령에 ID와 만료 시각을 붙여 CSE에 저장합니다. 저장 성공은 장비 실행 성공이 아닙니다.'},
  {label:'Device ACK',resource:'Separate ACK CIN',title:'The device reports what it applied.',en:'The virtual adapter reads the command and writes a separate acknowledgement. That confirms the reported action, not the ventilation outcome.',ko:'가상 장치가 명령을 읽고 별도 ACK를 보냅니다. ACK는 조치 응답이며, 공기 상태가 좋아졌다는 증거는 아닙니다.'},
  {label:'Verify outcome',resource:'2 fresh samples',title:'Close the incident only with later evidence.',en:'Two distinct, fresh healthy observations after ACK verify the simulated recovery. The command and samples remain linked to the current run.',ko:'ACK 이후 서로 다른 최신 정상 관측 두 개를 확인해야 회복으로 처리합니다. 현재 실행의 명령과 관측이어야 합니다.'}
];
const cases = {
  recovery:{last:5,status:'VERIFIED RECOVERY',terminal:stages[5]},
  missing_ack:{last:4,status:'UNRESOLVED · ACK TIMEOUT',terminal:{title:'The command was stored. The device never answered.',en:'No matching device ACK arrived before expiry. Keep the incident unresolved; do not jump to the observation-verification stage.',ko:'명령은 저장됐지만 만료 전 장비 ACK가 없습니다. 사건을 미해결로 남기며 회복 검증을 통과한 것처럼 처리하지 않습니다.'}},
  no_recovery:{last:5,status:'UNRESOLVED · NO RECOVERY',terminal:{title:'Acknowledgement is not recovery.',en:'The virtual device acknowledged the action, but later observations remain deficient. Preserve the unresolved outcome for diagnosis and maintenance.',ko:'장비는 응답했지만 이후 관측도 여전히 기준에 못 미칩니다. 미해결 상태와 증거를 유지해 추가 진단·유지보수로 이어갑니다.'}},
  stale:{last:2,status:'BLOCKED · STALE EVIDENCE',terminal:{title:'Stop before writing an unsafe command.',en:'The server freshness guard rejects the action before a command is written. Refresh the evidence; do not infer the present from an old observation.',ko:'서버가 오래된 증거를 확인해 명령 저장 전에 거절합니다. 과거의 값을 현재처럼 쓰지 않고 최신 관측을 다시 확보해야 합니다.'}}
};
let selected='recovery', step=0, playing=false, timer=null;
let redraw=()=>{};
const reduced=matchMedia('(prefers-reduced-motion: reduce)');
function renderText(){
  const choice=cases[selected],end=step===choice.last;
  const content=end?choice.terminal:stages[step];
  root.dataset.case=selected;root.dataset.step=String(step);root.dataset.outcome=end?choice.status:'IN PROGRESS';
  root.querySelector('#journey-title').textContent=content.title;
  root.querySelector('#journey-description').textContent=content.en;
  root.querySelector('#journey-korean').textContent=content.ko;
  root.querySelector('#journey-status').textContent=end?choice.status:`STEP ${step+1} / ${choice.last+1}`;
  root.querySelector('#journey-status').classList.toggle('warning',end&&selected!=='recovery');
  root.querySelectorAll('[data-journey-step]').forEach((button,i)=>{button.disabled=i>choice.last;button.setAttribute('aria-pressed',String(i===step));button.classList.toggle('reached',i<step);});
  root.querySelectorAll('[data-journey-case]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.journeyCase===selected)));
  root.querySelector('#journey-play').textContent=playing?'Pause explanation':'Play explanation';
  root.querySelector('#journey-play').setAttribute('aria-pressed',String(playing));
  redraw();
}
function stop(){playing=false;clearInterval(timer);timer=null;}
root.querySelectorAll('[data-journey-step]').forEach(button=>button.addEventListener('click',()=>{stop();step=Number(button.dataset.journeyStep);renderText();}));
root.querySelectorAll('[data-journey-case]').forEach(button=>button.addEventListener('click',()=>{stop();selected=button.dataset.journeyCase;step=cases[selected].last;renderText();}));
root.querySelector('#journey-play').addEventListener('click',()=>{
  if(playing){stop();renderText();return;}
  playing=true;step=0;renderText();timer=setInterval(()=>{if(document.hidden)return;step++;if(step>=cases[selected].last){step=cases[selected].last;stop();}renderText();},2800);
});
document.addEventListener('visibilitychange',()=>{if(document.hidden){stop();renderText();}});
renderText();

async function scene(){
  const THREE=await import('./vendor/three.module.js');
  const host=root.querySelector('#journey-scene');
  const renderer=new THREE.WebGLRenderer({alpha:true,antialias:true,powerPreference:'low-power'});
  renderer.setPixelRatio(Math.min(devicePixelRatio,1.7));renderer.outputColorSpace=THREE.SRGBColorSpace;
  host.append(renderer.domElement);host.dataset.renderer='three.js-0.187.0';
  const world=new THREE.Scene(),camera=new THREE.PerspectiveCamera(35,1,.1,100);
  world.add(new THREE.HemisphereLight(0xfff8dc,0x466b60,3));const key=new THREE.DirectionalLight(0xffffff,3);key.position.set(-4,8,5);world.add(key);
  const stageGroup=new THREE.Group();world.add(stageGroup);
  const tileGeo=new THREE.BoxGeometry(1.65,.22,1.15),blockGeo=new THREE.BoxGeometry(1,.45,.55);
  const positions=[[-3,0,-1.4],[0,0,-1.4],[3,0,-1.4],[3,0,1.4],[0,0,1.4],[-3,0,1.4]];
  const nodes=positions.map((p,i)=>{
    const group=new THREE.Group();group.position.set(...p);stageGroup.add(group);
    const mat=new THREE.MeshStandardMaterial({color:0xd6dfca,roughness:.7});
    const tile=new THREE.Mesh(tileGeo,mat);group.add(tile);
    const block=new THREE.Mesh(blockGeo,new THREE.MeshStandardMaterial({color:0x668577,metalness:.2,roughness:.6}));block.position.y=.32;group.add(block);
    if(i===0){const stem=new THREE.Mesh(new THREE.CylinderGeometry(.04,.04,.45,8),mat);stem.position.y=.7;group.add(stem);}
    if(i===1){for(let j=0;j<3;j++){const slot=new THREE.Mesh(new THREE.BoxGeometry(.72,.04,.03),new THREE.MeshBasicMaterial({color:0xc6e6bb}));slot.position.set(0,.2+j*.12,.29);group.add(slot);}}
    if(i===2){const check=new THREE.Mesh(new THREE.OctahedronGeometry(.24),new THREE.MeshStandardMaterial({color:0xc5a45f,metalness:.4,roughness:.5}));check.position.y=.85;group.add(check);}
    if(i===3){const card=new THREE.Mesh(new THREE.BoxGeometry(.45,.55,.04),new THREE.MeshStandardMaterial({color:0xf3f3de}));card.position.set(.12,.8,0);card.rotation.z=-.16;group.add(card);}
    if(i===5){for(let j=0;j<2;j++){const sample=new THREE.Mesh(new THREE.CylinderGeometry(.1,.1,.32,12),new THREE.MeshStandardMaterial({color:0xb6d1a8}));sample.position.set(-.2+j*.4,.76,0);group.add(sample);}}
    if(i===4){const ring=new THREE.Mesh(new THREE.TorusGeometry(.24,.05,8,24),mat);ring.position.set(0,.75,0);group.add(ring);}
    const label=document.createElement('span');label.className='journey-node-label';label.innerHTML=`<b>${String(i+1).padStart(2,'0')} ${stages[i].label}</b><small>${stages[i].resource}</small>`;host.append(label);
    return {group,tile,block,label};
  });
  const links=positions.slice(0,-1).map((p,i)=>{
    const a=new THREE.Vector3(...p).add(new THREE.Vector3(0,.04,0)),b=new THREE.Vector3(...positions[i+1]).add(new THREE.Vector3(0,.04,0));
    const curve=new THREE.LineCurve3(a,b);const mesh=new THREE.Mesh(new THREE.TubeGeometry(curve,1,.035,6,false),new THREE.MeshStandardMaterial({color:0xb8c6b4}));stageGroup.add(mesh);const arrow=new THREE.Mesh(new THREE.ConeGeometry(.1,.23,8),mesh.material);arrow.position.copy(a).lerp(b,.6);arrow.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),b.clone().sub(a).normalize());stageGroup.add(arrow);return {curve,mesh,arrow};
  });
  const packet=new THREE.Mesh(new THREE.SphereGeometry(.105,12,12),new THREE.MeshBasicMaterial({color:0xe1a660}));stageGroup.add(packet);
  let visible=false,time=0,last=performance.now();
  new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;if(visible)redraw();},{threshold:.05}).observe(host);
  const resize=()=>{const w=host.clientWidth,h=host.clientHeight;renderer.setSize(w,h,false);camera.aspect=w/h;const distance=Math.max(7.7,4.8/(Math.tan(35*Math.PI/360)*camera.aspect));camera.position.set(0,distance*.78,distance*.625);camera.lookAt(0,0,0);camera.updateProjectionMatrix();camera.updateMatrixWorld();redraw();};new ResizeObserver(resize).observe(host);resize();
  redraw=()=>{
    const cap=cases[selected].last,terminal=step===cap,warning=terminal&&selected!=='recovery';
    nodes.forEach((n,i)=>{n.tile.material.color.setHex(i>cap?0xe1e4db:i===step?(warning?0xd58e59:0x7eaa8d):i<step?0xa9c4ac:0xd6dfca);n.block.material.color.setHex(i>cap?0xc3c9bf:i===step?0x254e40:0x668577);n.group.position.y=i===step?.08:0;n.label.classList.toggle('active',i===step);n.label.classList.toggle('unreached',i>cap);const point=n.group.position.clone().add(new THREE.Vector3(0,-.2,.8)).project(camera);n.label.style.left=`${(point.x*.5+.5)*host.clientWidth}px`;n.label.style.top=`${(-point.y*.5+.5)*host.clientHeight}px`;});
    links.forEach(({mesh,arrow},i)=>{mesh.material.color.setHex(i<step?0x69977a:0xc6cebf);mesh.visible=i<cap;arrow.visible=i<cap;});
    packet.visible=step>0&&!warning;if(packet.visible)packet.position.copy(links[Math.min(step-1,4)].curve.getPoint((time*.5)%1)).add(new THREE.Vector3(0,.22,0));
    renderer.render(world,camera);
  };
  function frame(now){requestAnimationFrame(frame);const dt=Math.max(0,Math.min(.05,(now-last)/1000));last=now;if(!visible||document.hidden)return;if(!reduced.matches&&root.dataset.motion!=='paused')time+=dt;redraw();}
  redraw();requestAnimationFrame(frame);
}
root.querySelector('#journey-motion').addEventListener('click',event=>{const off=root.dataset.motion!=='paused';root.dataset.motion=off?'paused':'playing';event.currentTarget.textContent=off?'Resume particles':'Pause particles';event.currentTarget.setAttribute('aria-pressed',String(off));});
root.dataset.motion=reduced.matches?'paused':'playing';root.querySelector('#journey-motion').textContent=reduced.matches?'Resume particles':'Pause particles';root.querySelector('#journey-motion').setAttribute('aria-pressed',String(reduced.matches));
scene().catch(()=>{root.querySelector('#journey-scene').dataset.renderer='fallback';root.querySelector('#journey-scene').textContent='The 3D view is unavailable. Use the six steps below to follow the same explanation.';});
