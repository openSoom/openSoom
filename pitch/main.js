const $ = selector => document.querySelector(selector);
const $$ = selector => [...document.querySelectorAll(selector)];
const layers = {
 adapter: {kicker:'ADAPT ONCE', title:'Different formats.\nCommon meaning.', body:'One vendor reports dust in mg/m³ and flow in litres per second. Another uses µg/m³ and m³/h. Adapters preserve meaning and timestamps before the same diagnostic code sees the data.', proof:'vendor B: 0.012 mg/m³\ncanonical: 12 µg/m³\nSDT PM2.5: 12 µg/m³', limit:'The original observation retains precision. The standard PM2.5 projection is an integer. CO₂ ppm is not assigned to the incompatible SDT mass-concentration field.'},
 cse: {kicker:'STANDARD SHARED SERVICES',title:'Discover once.\nShare with purpose.',body:'Actual oneM2M resources connect independent application identities. Native subscriptions notify diagnosis. A group reads zone resources. Explicit access policies distinguish readers, operators and adapters.',proof:'AE  application identity\nCNT / CIN  observations, commands, ACK\nSUB / GRP / ACP / FCNT  common services',limit:'A successful group request is a CSE result. It does not establish device execution. The application preserves native errors, including a denied group member.'},
 operations: {kicker:'KEEP THE OPERATING CONTEXT',title:'The service owns\nthe outcome.',body:'Profiles define site-specific targets. The service checks scope and freshness, persists incidents, correlates the command and ACK, and verifies later observations. An old successful command cannot close a new run.',proof:'run ID → tool call → CSE request ID\ncurrent command → distinct ACK\n2 unique later healthy samples → recovery',limit:'These thresholds and equipment responses are simulation inputs. No universal ventilation target, capture efficiency or clinical outcome is asserted.'},
 agent: {kicker:'GUIDANCE WITH BOUNDED AUTHORITY',title:'An agent that acts\nand checks.',body:'The Codex plugin guides setup and diagnosis. A separate actual model API runner chooses structured tools through the same MCP server. Server-side permissions remain fixed, and state survives the chat.',proof:'discover → read_evidence\nrequest_action → verify_result\nreport recovered / unresolved / denied',limit:'Actual Codex CLI host calls and hosted LLM inference are separately captured. A standalone MCP test, fixture or API connection alone cannot establish a live model pass.'}
};
$$('[data-layer]').forEach(button => button.addEventListener('click', () => {
 $$('[data-layer]').forEach(item => item.classList.toggle('active',item===button));
 const data=layers[button.dataset.layer];
 $('#layer-kicker').textContent=data.kicker;$('#layer-title').textContent=data.title;$('#layer-title').style.whiteSpace='pre-line';
 $('#layer-body').textContent=data.body;$('#layer-proof').textContent=data.proof;$('#layer-proof').style.whiteSpace='pre-line';$('#layer-limit').textContent=data.limit;
}));
const guide = [
 {title:'공기질 경보를 해제해도 될까요?',body:'첫 사건은 CO₂가 720 ppm까지 내려갔지만 초미세먼지가 60 µg/m³로 남아 구역 기준 45를 넘습니다. 운영자는 경보를 유지합니다.',action:'영상을 재생하고 운영자의 경보 유지부터 보세요. 두 번째 장면은 별도 클라우드 사건입니다.',target:'#top'},
 {title:'별도의 저풍량 사건에서 첫 점검 부위를 정합니다.',body:'풍량이 900 m³/h 목표에서 360에 머문 사건입니다. 100% 개방 명령에 독립 MEC 센서가 35%를 보고했습니다. 정비 앱이 같은 작업지시서를 3판에서 4판으로 갱신해 구동부와 위치 피드백을 먼저 점검하도록 했습니다.',action:'클라우드 기록에서 센서와 작업지시서 ID를 펼쳐 보세요. 정비사가 점검 일정을 저장한 뒤에도 운영 사건은 열려 있었습니다.',target:'#human-apps'},
 {title:'AI는 도구를 고르고, 서비스가 권한과 결과를 검증합니다.',body:'LLM은 시설의 최신 증거를 읽고 허용된 조치를 요청합니다. 역할·시설·프로필·데이터 신선도는 서버가 검사합니다. 모델이 “성공”이라고 말해도 그것만으로 회복이 되지 않습니다.',action:'Observe, Authorize, Acknowledge, Verify 순서로 설명합니다. ACK 뒤의 서로 다른 정상 관측 2개가 필요합니다. 미회복 테스트도 함께 말하세요.',target:'#workflow'},
 {title:'중앙 연결이 끊겨도 현장에 필요한 판단은 남아 있습니다.',body:'두 시설의 MN-CSE와 중앙 IN-CSE를 실제로 실행했습니다. 중앙을 중단한 동안 현장 관측·명령·ACK·회복이 이어졌습니다. 재연결 후 만료된 중앙 명령은 거절됩니다.',action:'Across facilities와 Central offline을 선택하세요. 이는 중앙 장애 중 현장 연속성 시험이며 CSE handover나 MEC 배포는 아니라고 구분합니다.',target:'#explore',view:'network',condition:'offline'},
 {title:'구현된 것, 가상인 것, 아직 확인하지 않은 것을 구분합니다.',body:'CSE·프로토콜·MCP·실제 모델 호출은 실행했습니다. 센서와 액추에이터는 가상입니다. Codex는 CLI 호스트 호출을 검증했고 별도 데스크톱 UI나 실제 장비 검증은 하지 않았습니다.',action:'증거 링크를 열어 run ID와 명령·ACK·이후 관측의 연결을 보여줍니다. 테스트 PASS가 건강 효과나 미회복 시설의 정상화를 의미하지 않습니다.',target:'#proof'},
 {title:'오픈소스의 가치는 다음 시설이 덜 다시 만드는 데 있습니다.',body:'새 시설은 프로필과 어댑터를 선택하는 설정으로 추가합니다. 새 제조사를 연결할 때도 진단과 도구 코드는 유지하는 것이 목표입니다. 현재 실제 하드웨어 어댑터는 추가 작업이 필요합니다.',action:'설치 명령과 저장소 구조를 보여주세요. “지금 바로 가상 환경으로 재현할 수 있고, 다음 기여자는 프로필·어댑터를 확장할 수 있다”로 마무리합니다.',target:'#start'}
];
function guideState(open){$('#guide').hidden=!open;$('#guide-toggle').setAttribute('aria-expanded',String(open));if(!open)$('#guide-toggle').focus();}
$('#guide-toggle').addEventListener('click',()=>guideState($('#guide').hidden));$('#guide-close').addEventListener('click',()=>guideState(false));
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!$('#guide').hidden)guideState(false);});
$$('[data-guide]').forEach(button=>button.addEventListener('click',()=>{
 const data=guide[Number(button.dataset.guide)];$('#guide-title').textContent=data.title;$('#guide-body').textContent=data.body;$('#guide-action').textContent=data.action;
 $$('[data-guide]').forEach(item=>item.classList.toggle('selected',item===button));
 if(data.view)document.querySelector(`[data-view="${data.view}"]`).click();
 if(data.condition)document.querySelector(`[data-condition="${data.condition}"]`).click();
 $(data.target).scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'start'});
}));
$('#copy-command').addEventListener('click',async()=>{
 try{await navigator.clipboard.writeText($('#commands').textContent);$('#copy-command').textContent='Copied';}
 catch{const range=document.createRange();range.selectNodeContents($('#commands'));const selection=window.getSelection();selection.removeAllRanges();selection.addRange(range);$('#copy-command').textContent='Selected — copy text';}
});

const viewText={
 facility:{number:'01',counter:'FACILITY',title:'Look beyond the fan status.',description:'A running exhaust fan and deficient airflow can coexist. Read both, check freshness, then decide what to do.'},
 architecture:{number:'02',counter:'SHARED LAYER',title:'A common path for every application.',description:'Adapters write standard resources. The CSE shares them. Operations, agents and the dashboard use one evidence trail.'},
 network:{number:'03',counter:'DISTRIBUTED',title:'Local work continues through the gap.',description:'Two facility CSEs share selected resources with a central CSE. Local control stays at the facility during a central outage.'}
};
let selectedView='facility',condition='fault',paused=matchMedia('(prefers-reduced-motion: reduce)').matches;
function updateCopy(){const data=viewText[selectedView];$('#scene-number').textContent=data.number;$('#scene-counter').textContent=`${data.number} / ${data.counter}`;$('#scene-title').textContent=data.title;$('#scene-description').textContent=data.description;
 if(condition==='recovered'&&selectedView==='facility'){$('#scene-title').textContent='Recovery needs later evidence.';$('#scene-description').textContent='An ACK is followed by two fresh healthy observations in the actual workflow. This illustrative view shows the verified condition.';}
 if(condition==='offline'){$('#scene-title').textContent='The central connection can pause.';$('#scene-description').textContent='The tested local observation and control loop remains available. On reconnection, expired intents are rejected. No serving-CSE handover is claimed.';}
}
$$('[data-view]').forEach(button=>button.addEventListener('click',()=>{selectedView=button.dataset.view;$$('[data-view]').forEach(item=>item.setAttribute('aria-selected',String(item===button)));updateCopy();}));
$$('[data-condition]').forEach(button=>button.addEventListener('click',()=>{condition=button.dataset.condition;$$('[data-condition]').forEach(item=>item.setAttribute('aria-pressed',String(item===button)));updateCopy();}));
$$('[role=tab]').forEach((tab,index,tabs)=>tab.addEventListener('keydown',event=>{let next;if(event.key==='ArrowRight')next=(index+1)%tabs.length;if(event.key==='ArrowLeft')next=(index+tabs.length-1)%tabs.length;if(event.key==='Home')next=0;if(event.key==='End')next=tabs.length-1;if(next!==undefined){event.preventDefault();tabs[next].focus();tabs[next].click();}}));
function motionLabel(){$('#motion-toggle').textContent=paused?'Resume motion':'Pause motion';$('#motion-toggle').setAttribute('aria-pressed',String(paused));}motionLabel();
$('#motion-toggle').addEventListener('click',()=>{paused=!paused;motionLabel();});

async function initializeScene(){
 const THREE=await import('./vendor/three.module.js');
 const host=$('#scene'),labels=$('#scene-labels');
 const renderer=new THREE.WebGLRenderer({antialias:true,alpha:true,powerPreference:'low-power'});
 renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.setClearColor(0xe9ede1,0);renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFShadowMap;
 renderer.outputColorSpace=THREE.SRGBColorSpace;host.insertBefore(renderer.domElement,labels);$('#scene-fallback').classList.add('hidden');host.dataset.renderer='three.js-0.187.0';
 const scene=new THREE.Scene(),camera=new THREE.OrthographicCamera(-6,6,4,-4,.1,100);camera.position.set(10,10,12);camera.lookAt(0,.65,0);
 scene.add(new THREE.HemisphereLight(0xfff9e9,0x61816c,2.7));const sun=new THREE.DirectionalLight(0xfffcf3,3.4);sun.position.set(-4,10,5);sun.castShadow=true;sun.shadow.mapSize.set(1024,1024);sun.shadow.camera.left=-9;sun.shadow.camera.right=9;sun.shadow.camera.top=9;sun.shadow.camera.bottom=-9;sun.shadow.normalBias=.05;scene.add(sun);
 const root=new THREE.Group();scene.add(root);root.rotation.y=-.2;
 const materials={floor:new THREE.MeshStandardMaterial({color:0xdbe0cf,roughness:.93}),wall:new THREE.MeshStandardMaterial({color:0xf7f5e9,roughness:.8}),steel:new THREE.MeshStandardMaterial({color:0x7e9b88,metalness:.3,roughness:.55}),dark:new THREE.MeshStandardMaterial({color:0x244c40,roughness:.7}),mint:new THREE.MeshStandardMaterial({color:0xa5c9a8,roughness:.8}),fault:new THREE.MeshStandardMaterial({color:0xd9864d,roughness:.6}),glass:new THREE.MeshStandardMaterial({color:0x65a38b,transparent:true,opacity:.17,roughness:.6})};
 function box(parent,w,h,d,x,y,z,material){const mesh=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),material);mesh.position.set(x,y,z);mesh.castShadow=true;mesh.receiveShadow=true;parent.add(mesh);return mesh;}
 function cylinder(parent,r,h,x,y,z,material){const mesh=new THREE.Mesh(new THREE.CylinderGeometry(r,r,h,28),material);mesh.position.set(x,y,z);mesh.castShadow=true;mesh.receiveShadow=true;parent.add(mesh);return mesh;}
 function pipe(parent,points,color=0x6e9c82,radius=.035){const curve=new THREE.CatmullRomCurve3(points.map(p=>new THREE.Vector3(...p)));const mesh=new THREE.Mesh(new THREE.TubeGeometry(curve,40,radius,7,false),new THREE.MeshStandardMaterial({color,roughness:.7}));parent.add(mesh);return {curve,mesh};}
 const labelRecords=[];
 function label(group,text,position,kind=''){const element=document.createElement('div');element.className=`model-label ${kind}`;element.textContent=text;labels.appendChild(element);labelRecords.push({group,element,position:new THREE.Vector3(...position)});return element;}
 const facility=new THREE.Group(),architecture=new THREE.Group(),network=new THREE.Group();root.add(facility,architecture,network);
 box(facility,8,.22,5.1,0,-.25,0,materials.floor);box(facility,8,.7,.12,0,.15,-2.5,materials.wall);box(facility,.12,.7,5.1,-4,.15,0,materials.wall);
 [-1.3,1.35].forEach(x=>box(facility,.06,.12,4.8,x,-.07,0,materials.wall));
 const zoneCenters=[-2.63,0,2.65],zoneTiles=[];
 zoneCenters.forEach((x,i)=>{zoneTiles.push(box(facility,2.4,.035,4.55,x,-.11,0,materials.mint.clone()));box(facility,1.75,.5,1.15,x,.2,.3,materials.wall);box(facility,1.9,.09,1.3,x,.5,.3,materials.steel);box(facility,.18,.75,.18,x-.72,.08,.75,materials.dark);box(facility,.18,.75,.18,x+.72,.08,.75,materials.dark);});
 for(let i=0;i<4;i++){const x=-3.1+(i%2)*.75,z=.05+Math.floor(i/2)*.55;cylinder(facility,.24,.17,x,.64,z,materials.dark);cylinder(facility,.17,.025,x,.74,z,materials.steel);}
 box(facility,1.2,.03,.65,0,.56,.3,materials.dark);box(facility,.8,.1,.4,0,.58,.3,materials.steel);
 for(let i=0;i<3;i++)box(facility,.4,.22,.6,2.1+i*.52,.65,.3,materials.mint);
 box(facility,1.95,.18,1.25,-2.63,2.05,.15,materials.steel);box(facility,.45,1,.45,-2.63,2.55,.15,materials.wall);
 pipe(facility,[[-2.63,3,.15],[-2.63,3,-1.8],[0,3,-1.8],[2.65,3,-1.8]],0x94aa91,.13);
 [0,2.65].forEach(x=>pipe(facility,[[x,1.2,-1.9],[x,3,-1.9]],0x94aa91,.12));
 const fan=new THREE.Group();fan.position.set(2.7,3,-1.8);facility.add(fan);const ring=new THREE.Mesh(new THREE.TorusGeometry(.4,.07,10,36),materials.dark);ring.rotation.x=Math.PI/2;fan.add(ring);const rotor=new THREE.Group();fan.add(rotor);for(let i=0;i<3;i++){const blade=box(rotor,.18,.04,.6,0,0,.13,materials.steel);blade.rotation.y=i*Math.PI*2/3;}
 label(facility,'COOKING LINE',[-2.63,.04,2.05]);label(facility,'WASH',[0,.04,2.05]);label(facility,'PACK',[2.65,.04,2.05]);const fanLabel=label(facility,'FAN RUNNING',[2.7,3.55,-1.8]);const airLabel=label(facility,'AIRFLOW BELOW TARGET',[-2.63,1.25,1.15],'fault');
 const particles=[];const particleGeometry=new THREE.SphereGeometry(.035,6,6);for(let i=0;i<80;i++){const mesh=new THREE.Mesh(particleGeometry,new THREE.MeshBasicMaterial({color:i<44?0xc77a44:0x5f967a,transparent:true,opacity:.65}));facility.add(mesh);particles.push({mesh,phase:i*.178,zone:i<44?0:i<62?1:2});}
 const archNodes=[{id:'adapter',x:-3.4,y:.4,z:1,label:'DEVICE ADAPTERS',mat:'mint'},{id:'cse',x:0,y:.65,z:1,label:'oneM2M CSE',mat:'dark'},{id:'service',x:3.2,y:.4,z:1,label:'OPERATIONS',mat:'mint'},{id:'mcp',x:.2,y:.6,z:-2.2,label:'MCP / CODEX / LLM',mat:'wall'},{id:'ui',x:3.3,y:.4,z:-2.2,label:'DASHBOARD',mat:'wall'}];
 archNodes.forEach(n=>{box(architecture,1.9,n.y+.5,1.3,n.x,n.y/2,n.z,materials[n.mat]);label(architecture,n.label,[n.x,n.y+1,n.z]);});
 const archPaths=[pipe(architecture,[[-2.5,.5,1],[-1.7,.5,1],[-.95,.5,1]],0x6f9c7e,.045),pipe(architecture,[[.95,.6,1],[1.6,.6,1],[2.25,.6,1]],0x6f9c7e,.045),pipe(architecture,[[.2,.7,-1.55],[.2,.8,-.4],[2.5,.7,.3]],0xb99a60,.04),pipe(architecture,[[3.3,.6,-1.55],[3.3,.7,-.4],[3.3,.6,.35]],0x6f9c7e,.04)];
 box(architecture,9,.12,6,0,-.25,-.3,materials.floor);label(architecture,'NATIVE MQTT / TLS',[-1.65,.1,2.55]);label(architecture,'HTTPS',[1.65,.1,2.55]);
 const localGroups=[];
 [-2.65,2.65].forEach((x,i)=>{const group=new THREE.Group();group.position.set(x,0,1.2);network.add(group);box(group,3.2,.16,2.9,0,-.2,0,materials.floor);box(group,2.7,.3,.14,0,0,-1.3,materials.wall);for(let j=0;j<3;j++)box(group,.55,.45,.7,-.9+j*.9,.1,.1,materials.mint);box(group,1.1,.7,.65,0,.2,-.8,materials.dark);label(network,i?'LEARNING / MN-CSE':'FOOD / MN-CSE',[x,1.3,.5]);localGroups.push(group);});
 const central=box(network,2.1,.85,1.2,0,.35,-2.1,materials.dark.clone());label(network,'CENTRAL / IN-CSE',[0,1.6,-2.1]);const centralLines=[pipe(network,[[-2.65,.6,.4],[-2.65,.8,-1.8],[-1,.8,-2.1]],0x648a71,.04),pipe(network,[[2.65,.6,.4],[2.65,.8,-1.8],[1,.8,-2.1]],0x648a71,.04)];const centralLabel=label(network,'SELECTIVE RESOURCE SHARING',[0,.45,.45]);
 const movingDots=[];for(let i=0;i<12;i++){const dot=new THREE.Mesh(new THREE.SphereGeometry(.055,8,8),new THREE.MeshBasicMaterial({color:0xc7954b}));architecture.add(dot);movingDots.push(dot);}
 const localDots=[];localGroups.forEach(group=>{for(let i=0;i<6;i++){const dot=new THREE.Mesh(new THREE.SphereGeometry(.045,7,7),new THREE.MeshBasicMaterial({color:0x3f8466}));group.add(dot);localDots.push({dot,i});}});
 let targetRotation=-.2,dragStart=null,visible=true,time=0,last=performance.now();
 renderer.domElement.addEventListener('pointerdown',event=>{dragStart={x:event.clientX,rotation:targetRotation};renderer.domElement.setPointerCapture(event.pointerId);});
 renderer.domElement.addEventListener('pointermove',event=>{if(dragStart)targetRotation=dragStart.rotation+(event.clientX-dragStart.x)*.008;});
 renderer.domElement.addEventListener('pointerup',()=>dragStart=null);renderer.domElement.addEventListener('pointercancel',()=>dragStart=null);
 $('#reset-view').addEventListener('click',()=>targetRotation=-.2);
 const resize=()=>{const w=host.clientWidth,h=host.clientHeight;renderer.setSize(w,h,false);const aspect=w/h;const span=Math.max(3.2,5.8/aspect);camera.left=-span*aspect;camera.right=span*aspect;camera.top=span;camera.bottom=-span;camera.updateProjectionMatrix();};new ResizeObserver(resize).observe(host);resize();
 new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;}).observe(host);
 function frame(now){requestAnimationFrame(frame);const dt=Math.max(0,Math.min((now-last)/1000,.06));last=now;if(!visible||document.hidden)return;if(!paused)time+=dt;root.rotation.y+=(targetRotation-root.rotation.y)*.12;
  facility.visible=selectedView==='facility';architecture.visible=selectedView==='architecture';network.visible=selectedView==='network';
  const healthy=condition==='recovered';zoneTiles[0].material.color.setHex(healthy?0xa5c9a8:0xe1b38d);airLabel.textContent=healthy?'2 LATER SAMPLES VERIFIED':'AIRFLOW BELOW TARGET';airLabel.classList.toggle('fault',!healthy);fanLabel.textContent='FAN RUNNING';rotor.rotation.y=time*2;
  particles.forEach(({mesh,phase,zone})=>{const t=(time*(healthy?.45:.22)+phase)%1;const x=zoneCenters[zone];mesh.position.set(x+Math.sin(phase*13+t*4)*.48,.7+t*(healthy?2.4:1.1),.2+Math.cos(phase*7+t*3)*.42);mesh.material.opacity=(1-t)*(healthy?.38:.68);mesh.material.color.setHex(zone===0&&!healthy?0xc77a44:0x5f967a);});
  movingDots.forEach((dot,i)=>{const curve=archPaths[i%archPaths.length].curve;dot.position.copy(curve.getPoint((time*.25+i*.13)%1));});
  const offline=condition==='offline';central.material.color.setHex(offline?0xa98a67:0x244c40);centralLines.forEach(({mesh})=>mesh.visible=!offline);centralLabel.textContent=offline?'CENTRAL OFFLINE / LOCAL LOOP ACTIVE':'SELECTIVE RESOURCE SHARING';centralLabel.classList.toggle('fault',offline);
  localDots.forEach(({dot,i})=>{const angle=time*1.2+i*Math.PI/3;dot.position.set(Math.cos(angle),.65,Math.sin(angle)*.65);});
  root.updateMatrixWorld();labelRecords.forEach(record=>{record.element.hidden=!record.group.visible;if(!record.group.visible)return;const point=record.position.clone();record.group.localToWorld(point);point.project(camera);record.element.style.left=`${(point.x*.5+.5)*host.clientWidth}px`;record.element.style.top=`${(-point.y*.5+.5)*host.clientHeight}px`;});renderer.render(scene,camera);
 }
 requestAnimationFrame(frame);
}
initializeScene().catch(error=>{$('#scene-fallback').dataset.reason=error.name;$('#scene').dataset.renderer='fallback';$('#scene-fallback p').textContent='The 3D view is unavailable in this browser. Every architectural component and the same explanation are available below.';});
