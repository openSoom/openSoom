// Capture operator interactions in the real app. No request interception or injected telemetry.
const { chromium } = require('playwright');
const fs = require('node:fs/promises');
const path = require('node:path');
const [url, out] = process.argv.slice(2);
const runs = [];
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));

async function shoot(browser, name, facility, scenario, zone) {
  const ctx = await browser.newContext({viewport:{width:1440,height:900},
    deviceScaleFactor:1,recordVideo:{dir:out,size:{width:1440,height:900}}});
  const page = await ctx.newPage();
  page.setDefaultTimeout(18000);
  const start = Date.now(), cues = {};
  const mark = name => {cues[name] = +( (Date.now()-start)/1000 ).toFixed(2);};
  const go = async id => {
    await page.locator(id).evaluate(el=>el.scrollIntoView({behavior:'smooth',block:'center'}));
    await wait(1000);
  };
  let runId, actual;
  try {
    await page.goto(url, {waitUntil:'domcontentloaded'});
    await page.waitForFunction(()=>document.querySelector('#facility-select option[value="learning-b"]'));
    await page.selectOption('#facility-select',facility);
    await page.waitForFunction(()=>!document.querySelector('#start-demo-button').disabled);
    await page.waitForFunction(()=>document.querySelector('#spatial-labels button')||document.querySelector('#facility-map [data-zone]'));
    await go('#scenario-select');
    await page.selectOption('#scenario-select',scenario);
    if(await page.locator('#autorun-toggle').isChecked()) await page.locator('label.toggle-label').click();
    const response=page.waitForResponse(r=>r.url().endsWith('/api/demo/start')&&r.request().method()==='POST');
    await page.click('#start-demo-button');
    runId=(await (await response).json()).run_id;
    await wait(2600);
    await go('#spatial-stage');
    mark('facility');
    await wait(3500);
    await page.click('[data-metric="pm25"]');await wait(2100);
    await page.click('[data-metric="airflow"]');await wait(2200);
    await page.click('#view-2d');await wait(2450);
    if(!await page.locator('#view-3d').isDisabled()) await page.click('#view-3d');
    await wait(2500);
    mark('detail');
    await go('#zone-detail');
    await page.click('[data-inspect-zone="'+zone+'"]');
    await page.waitForSelector('#evidence-dialog[open]');
    await wait(5200);
    mark('action');
    await page.click('[data-zone-action="set_damper"]');
    await page.waitForSelector('#evidence-dialog[open]',{state:'hidden'});
    await go('#zone-proof');
    await wait(9000);
    mark('result');
    await go('#spatial-stage');await wait(3800);
    await go('#zone-proof');await wait(4500);
    await go('#command-detail');await wait(4000);
    const cmdEvidence=page.locator('[data-command-evidence]').first();
    if(await cmdEvidence.count()){await cmdEvidence.click();await wait(3800);await page.click('[aria-label="Close evidence"]');}
    await go('#spatial-stage');await wait(2000);
    mark('end');
    // The dashboard itself already polls this authenticated endpoint. Reuse its
    // next response without exposing the embedded loopback credential.
    const data=await (await page.waitForResponse(r=>r.url().endsWith('/api/state')&&r.status()===200)).json();
    actual={runId, facility, scenario, commands:(data.commands||[]).filter(x=>x.run_id===runId), 
      core: data.facilities.find(x=>x.id===facility)?.zones.find(x=>x.id===zone),
      events:(data.events||[]).filter(x=>x.run_id===runId).map(({type,kind,facility_id,message,timestamp})=>({type,kind,facility_id,message,timestamp}))};
    if(!actual.commands.some(x=>x.ack && x.observed_result===(scenario==='no_recovery'?'unresolved':'recovered'))) throw Error('Failed to capture expected command result: '+JSON.stringify(actual.commands).slice(0,500));
    runs.push({name,cues,...actual}); 
  } finally {
    const v=page.video();await ctx.close();
    await v.saveAs(path.join(out,name+'.webm'));await v.delete();
  }
}

(async()=>{
  const browser=await chromium.launch({executablePath:process.env.FILM_CHROME||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-dev-shm-usage']});
  try {
    if (process.env.OPENSOOM_FILM_TAKE==='food-unresolved') {
      await shoot(browser,'food-unresolved','food-a','no_recovery','cook');
    } else {
      await shoot(browser,'food','food-a','exhaust_fault','cook');
      await shoot(browser,'learning','learning-b','no_recovery','classroom');
    }
    await fs.writeFile(path.join(out,'browser-runs.json'),JSON.stringify({kind:'actual_isolated_dashboard_screen_recording',physical_devices:'simulated',model_calls:0,runs},null,2));
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
