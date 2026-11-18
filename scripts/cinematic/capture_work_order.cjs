// Record the actual local dashboard and the landing page backed by its retained CSE run.
const {chromium} = require('playwright');
const fs = require('node:fs/promises');
const {createHash} = require('node:crypto');
const path = require('node:path');
const [dashboardURL, landingURL, recordFile, output] = process.argv.slice(2);
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));

async function center(locator) {
  await locator.evaluate(node => node.scrollIntoView({block:'center', behavior:'instant'}));
}

async function main() {
  const record = JSON.parse(await fs.readFile(recordFile, 'utf8'));
  const orderId = record.after.work_order_id;
  await fs.mkdir(output, {recursive:true});
  const browser = await chromium.launch({executablePath:process.env.FILM_CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args:['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader']});
  try {
    const context = await browser.newContext({viewport:{width:1280,height:720}, reducedMotion:'reduce',
      recordVideo:{dir:output,size:{width:1280,height:720}}});
    const page = await context.newPage();
    const cues = {};
    const frames = {};
    await fs.mkdir(path.join(output, 'frames'), {recursive:true});
    const sha = bytes => createHash('sha256').update(bytes).digest('hex');
    async function freeze(scene, proof) {
      await proof.waitFor({state:'visible'});
      const bytes = await page.screenshot({animations:'disabled'});
      if (!await proof.isVisible()) return false;
      const file = 'frames/' + scene + '.png';
      await fs.writeFile(path.join(output, file), bytes);
      frames[scene] = {file, sha256:sha(bytes)};
      return true;
    }
    async function capture(scene, proof) {
      if (!await freeze(scene, proof)) throw Error('View changed during ' + scene + ' screenshot');
      mark(scene);
    }
    const started = Date.now();
    function mark(key) { cues[key] = (Date.now() - started)/1000; }
    // Sample the recorded disclosure as well as the selected decision in each view.
    await page.goto(landingURL, {waitUntil:'domcontentloaded'});
    await page.locator('#decision-id').getByText(record.command.id, {exact:true}).waitFor();
    mark('landing'); await pause(2400);
    const card = page.locator('.incident-card');
    await center(card);
    await capture('ack', card.getByText('The controller received the command.', {exact:true}));
    await pause(1700);
    await page.getByRole('button',{name:'Airflow check',exact:true}).focus();
    await page.keyboard.press('Enter');
    await page.getByText('Keep the incident open.', {exact:true}).waitFor();
    await capture('flow', card.getByText('Keep the incident open.', {exact:true}));
    await pause(2300);
    await page.getByRole('button',{name:'Shaft measurement',exact:true}).click();
    await page.getByText(orderId, {exact:true}).waitFor();
    await center(card);
    await page.screenshot({path:path.join(output,'landing-decision.png')});
    await capture('shaft', card.getByText(orderId, {exact:true}));
    await pause(2600);
    await page.goto(dashboardURL, {waitUntil:'domcontentloaded'});
    await page.locator('#facility-select option[value="food-a"]').waitFor({state:'attached'});
    await page.selectOption('#facility-select', 'food-a');
    const current = page.locator('#maintenance-detail article').filter({hasText:orderId});
    await current.waitFor();
    await center(page.locator('#spatial-stage'));
    await capture('facility', page.locator('#spatial-stage'));
    await pause(3500);
    await page.screenshot({path:path.join(output,'dashboard-facility.png')});
    await center(page.locator('#maintenance-panel'));
    await current.getByText('Check actuator travel and position feedback first', {exact:true}).waitFor();
    await current.getByText('35%', {exact:true}).waitFor();
    await current.getByText('360 m³/h', {exact:true}).waitFor();
    await page.screenshot({path:path.join(output,'dashboard-order.png')});
    await capture('order', current.getByText('35%', {exact:true}));
    await pause(4000);
    // A live dashboard refresh may close a disclosure between two browser paints.
    const openReceipt = current.locator('details[open] pre').filter({hasText:orderId});
    for (let attempt = 0; attempt < 5 && !frames.receipt; attempt++) {
      if (!await openReceipt.isVisible()) await current.locator('summary').click();
      await center(current.locator('summary'));
      if (await openReceipt.isVisible()) await freeze('receipt', openReceipt);
    }
    if (!frames.receipt) throw Error('Work-order receipt did not remain open during capture');
    mark('receipt'); await pause(3000);
    const desktopVideo = page.video();
    await context.close();
    await desktopVideo.saveAs(path.join(output,'work-order.webm'));
    await desktopVideo.delete();
    const mobile = await browser.newContext({viewport:{width:390,height:844}, reducedMotion:'reduce'});
    const mobilePage = await mobile.newPage();
    const checks = [];
    for (const [url, focus] of [[landingURL,'.incident-card'],[dashboardURL,'#maintenance-panel']]) {
      await mobilePage.goto(url,{waitUntil:'domcontentloaded'});
      if (url === dashboardURL) await mobilePage.locator('#maintenance-detail article').filter({hasText:orderId}).waitFor();
      else await mobilePage.getByRole('button',{name:'Shaft measurement',exact:true}).click();
      await center(mobilePage.locator(focus));
      const clip = await mobilePage.evaluate(() => ({width:innerWidth, contentWidth:document.documentElement.scrollWidth}));
      if (clip.contentWidth > clip.width + 1) throw Error('Horizontal overflow on '+focus+': '+JSON.stringify(clip));
      checks.push({surface:focus,...clip});
      await mobilePage.screenshot({path:path.join(output,focus.includes('incident')?'landing-mobile.png':'dashboard-mobile.png')});
    }
    await mobile.close();
    await fs.writeFile(path.join(output,'capture.json'),JSON.stringify({run_id:record.run_id,work_order_id:orderId,
      dimensions:[1280,720],media:'browser screen recording',sensor_path:record.sensor_path,
      recording_sha256:sha(await fs.readFile(path.join(output,'work-order.webm'))),
      frames,cues,mobile:checks},null,2)+'\n');
  } finally { await browser.close(); }
}
main().catch(error=>{console.error(error.message);process.exitCode=1;});
