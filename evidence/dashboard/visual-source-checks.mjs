// Presentation regression checks. No runtime/device mutation and no browser mocks.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { telemetryMotion, animationStep } from '../../web/facility-3d.js';

const checks = [];
assert.equal(animationStep(99,100),0);checks.push('Earlier first RAF timestamp cannot produce a negative curve position');
assert.equal(animationStep(10000,100),.05);checks.push('Resuming after a background pause caps visual time advancement');
const good = { status: 'nominal', fan: {value: true, quality: 'good'}, airflow: {value: 900, quality: 'good'} };
function motion(name, zone, connected, metric, expected) {
  assert.deepEqual(telemetryMotion(zone, connected, metric), expected, name); checks.push(name);
}
motion('Current positive airflow can be illustrated', good, true, 'airflow', {spin:true, flow:true});
for (const status of ['stale', 'missing', 'unknown']) motion(`${status} values do not animate`, {...good, status}, true, 'airflow', {spin:false, flow:false});
motion('Disconnected data do not animate', good, false, 'airflow', {spin:false, flow:false});
for (const value of [0, -1, NaN, null]) motion(`${String(value)} airflow has no invented flow`, {...good, airflow:{value,quality:'good'}}, true, 'airflow', {spin:true,flow:false});
motion('Stale airflow has no invented flow', {...good,airflow:{value:900,quality:'stale'}}, true, 'airflow', {spin:true,flow:false});
motion('Stopped fan has no flow', {...good,fan:{value:false,quality:'good'}}, true, 'airflow', {spin:false,flow:false});
motion('Stale fan does not rotate', {...good,fan:{value:true,quality:'stale'}}, true, 'airflow', {spin:false,flow:false});
motion('PM mode does not imply airflow visualization', good, true, 'pm25', {spin:true,flow:false});
motion('Critical flow is a measured report, not recovery evidence', {...good,status:'critical'}, true, 'airflow', {spin:true,flow:true});

// Run the exact production proof renderer against bounded contract fixtures.
// These are synthetic presentation checks, not CSE executions or live-model evidence.
const source = fs.readFileSync(new URL('../../web/app.js', import.meta.url), 'utf8');
function part(start, end) { return source.slice(source.indexOf(start), source.indexOf(end,source.indexOf(start))); }
const renderer = part('  function renderVisual() {', '  function setVisualMode(');
const helpers = part('  function isVerified(command)', '  function renderVisual()');
function proof({command=null,active='current-run',status='critical',prior=[]}={}) {
  const elements = new Map();
  const selected = { id:'selected-zone',name:'Selected zone',status,target_airflow:900,observations:{fan_running:{value:true,quality:status==='stale'?'stale':'good'},airflow:{value:360,unit:'m³/h',quality:status==='stale'?'stale':'good'}} };
  const context = {
    state:{connected:true,data:{runtime:{cse_connected:true}},metric:'airflow'},
    facilityVisual:null, facility:()=>({id:'test-facility',active_run:active,zones:[selected]}), zone:()=>selected,
    latestRun:()=>({id:active}), commands:()=>[...(command?[command]:[]),...prior], incidents:()=>[],
    status:(z)=>z.status,statusLabel:(z)=>z.status,number:(v)=>String(v??'—'),esc:(v)=>String(v??''),human:(v)=>String(v??''),clock:(v)=>String(v??'—'),
    observation:(z,metric)=>z.observations[metric]||{value:null,quality:'missing'}, labels:{airflow:'Airflow'},
    failedStates:new Set(['timed_out','unresolved','failed']),actionName:()=> 'Set damper to 100%',
    $:(id)=>{ if(!elements.has(id))elements.set(id,{dataset:{},textContent:''});return elements.get(id);},
    setHTML:(id,html)=>{context.$(id).html=html;}
  };
  vm.runInNewContext(`${helpers}\n${renderer}\nrenderVisual();`,context);
  return context.$('zone-proof');
}
const base = {id:'test-command',run_id:'current-run',zone_id:'selected-zone',action:'set_damper',status:'requested',ack:false};
let rendered = proof({command:{...base,status:'timed_out',observed_result:'unresolved'}});
assert.match(rendered.html,/Not received/);assert.match(rendered.html,/Not recovered/);assert.doesNotMatch(rendered.html,/Recovery verified/);checks.push('Missing ACK never displays acknowledged or recovered');
rendered = proof({command:{...base,status:'unresolved',ack:true,ack_at:'recorded-ack-time',observed_result:'unresolved'}});
assert.match(rendered.html,/Received recorded-ack-time/);assert.match(rendered.html,/Not recovered/);assert.doesNotMatch(rendered.html,/Recovery verified/);checks.push('ACK with failed later observations remains unresolved');
rendered = proof({status:'stale',prior:[{...base,run_id:'old-run',status:'verified',ack:true,observed_result:'recovered'}]});
assert.match(rendered.html,/Fresh data required/);assert.match(rendered.html,/No recovery claim/);assert.equal(rendered.dataset.commandId,'');checks.push('Prior-run recovery cannot leak into current stale run');
rendered = proof({command:{...base,zone_id:'different-zone',status:'verified',ack:true,observed_result:'recovered'}});
assert.match(rendered.html,/No recovery claim/);assert.equal(rendered.dataset.commandId,'');checks.push('Another zone cannot supply selected-zone recovery');
rendered = proof({command:{...base,status:'verified',ack:true,ack_at:'recorded-ack-time',observed_result:'recovered'}});
assert.match(rendered.html,/Recovery verified/);assert.doesNotMatch(rendered.html,/2 fresh samples/);checks.push('Verified result displays without fabricating absent sample count');
rendered = proof({command:{...base,action:'request_maintenance',status:'maintenance_recorded',observed_result:'maintenance_recorded'}});
assert.match(rendered.html,/Not an equipment command/);assert.match(rendered.html,/no recovery claim/);checks.push('Maintenance record is not represented as actuator ACK or recovery');
console.log(JSON.stringify({result:'PASS', checks:checks.length, scope:'Synthetic presentation regression checks only; no CSE/device/model execution', details:checks},null,2));
