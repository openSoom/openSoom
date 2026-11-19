// Capture ordinary browser controls on an already-running, local openSoom lab.
const { chromium } = require('playwright');
const fs = require('node:fs/promises');
const path = require('node:path');
const assert = require('node:assert/strict');
const [url, output] = process.argv.slice(2);
if (!url || !output || !['127.0.0.1', 'localhost'].includes(new URL(url).hostname)) {
  throw Error('Usage: node capture_air_quality.cjs http://127.0.0.1:19490 PATH');
}
const trials = [
  ['air_quality_recovery', 'Both targets met'],
  ['air_quality_persistent', 'Outside air-quality targets'],
  ['air_quality_rebound', 'Above target again']
];
async function main() {
  await fs.mkdir(output, { recursive: true });
  const browser = await chromium.launch({
    executablePath:process.env.FILM_CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']
  });
  try {
    const page = await browser.newPage({viewport:{width:1280,height:720}, reducedMotion:'reduce'});
    const errors=[]; page.on('pageerror', error => errors.push(error.message));
    await page.goto(url, {waitUntil:'domcontentloaded'});
    await page.locator('#facility-select option[value="food-a"]').waitFor({state:'attached'});
    await page.selectOption('#facility-select','food-a');
    const panel=page.locator('#air-outcome');
    const cases={};
    for (const [scenario, label] of trials) {
      await page.selectOption('#scenario-select', scenario);
      const started=page.waitForResponse(r=>r.url().endsWith('/api/demo/start') && r.request().method()==='POST');
      await page.locator('#start-demo-button').click();
      const {run_id}=await (await started).json();
      await page.waitForFunction(id=>document.getElementById('air-outcome').dataset.runId===id,run_id);
      await panel.evaluate(el=>el.scrollIntoView({block:'center',behavior:'instant'}));
      const frames=[];
      const begin=Date.now();
      let matchedAt=null, last=null;
      while (Date.now()-begin < 66000) {
        const file=scenario + '-' + String(frames.length).padStart(3,'0') + '.png';
        await page.screenshot({path:path.join(output,file),animations:'disabled'});
        frames.push({file,seconds:(Date.now()-begin)/1000});
        last=await panel.evaluate(el=>({
          status:el.querySelector('#air-outcome-status')?.textContent,
          hold:el.querySelector('#air-outcome-hold')?.textContent,
          first:el.querySelector('#air-outcome-first')?.textContent,
          pm25:el.querySelector('#air-outcome-pm25 [data-reading=latest]')?.textContent,
          co2:el.querySelector('#air-outcome-co2 [data-reading=latest]')?.textContent,
          command:el.dataset.commandId
        }));
        const final=last.status?.includes(label) && last.pm25===(scenario==='air_quality_recovery'?'15':'60') && last.co2==='720';
        if(final && (scenario!=='air_quality_recovery' || parseFloat(last.hold)>2)){
          matchedAt ??= Date.now();
          if(Date.now()-matchedAt > 1600) break;
        } else matchedAt=null;
        await new Promise(resolve=>setTimeout(resolve,320));
      }
      assert(matchedAt,'Missing final state '+scenario+' '+JSON.stringify(last));
      await panel.screenshot({path:path.join(output,scenario+'-panel.png')});
      cases[scenario]={run_id, ...last, frames};
      console.log(scenario,last.status,last.first,last.hold);
    }
    assert.deepEqual(errors,[]);
    await fs.writeFile(path.join(output,'capture.json'),JSON.stringify({cases,errors},null,2));
  } finally {await browser.close();}
}
main().catch(error=>{console.error(error); process.exitCode=1;});
