// Render the shipped technician frontend with recorded, public cloud responses.
// This is an offline replay for the film, not a new network or cloud execution.
const {chromium} = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../..');
const source = path.join(root, 'src/opensoom/technician_web');
const data = JSON.parse(fs.readFileSync(path.join(root, 'evidence/runtime/option-c/technician-handoff.json')));
const out = process.argv[2];
if (!out) throw Error('Pass an output directory');
fs.mkdirSync(out, {recursive:true});
const earlier = data.before_service_admission.orders[0];
const next = data.technician_http.reviewed_order;
const completed = data.technician_http.entry;
const command = data.before_service_admission.commands[0];
const profile = JSON.parse(fs.readFileSync(path.join(root, 'profiles/food-production.json')));
const zone = profile.zones.find(z=>z.id===earlier.zone_id);
assert.equal(next.work_order_id, earlier.work_order_id);
assert.equal(next.resource_id, completed.work_order_ri);
async function main() {
  const browser = await chromium.launch({executablePath:process.env.FILM_CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--disable-gpu']});
  try {
    const page=await browser.newPage({viewport:{width:1160,height:900},deviceScaleFactor:1.5, reducedMotion:'reduce'});
    let record=earlier, showEntry=false;
    await page.route('http://film.invalid/**',route=>{
      const pathname=new URL(route.request().url()).pathname;
      if (pathname==='/api/work-orders') {
        const row={...record, zone_name:zone.name, target_source:'work_order_cin', configured_target_m3_h:record.target_airflow_m3_h,
                   requested_pct:command.value, inspections:showEntry?[completed]:[]};
        return route.fulfill({json:{facility:data.technician_http.facility, work_orders:[row]}});
      }
      const file={'/':'index.html','/assets/workbench.css':'workbench.css','/assets/workbench.js':'workbench.js'}[pathname];
      if (!file) return route.abort();
      return route.fulfill({path:path.join(source,file),contentType:{'index.html':'text/html','workbench.css':'text/css','workbench.js':'text/javascript'}[file]});
    });
    const load=()=>page.goto('http://film.invalid/?order='+earlier.work_order_id);
    await load();
    await page.getByRole('heading',{name:'Inspect the ventilation system',exact:true}).waitFor();
    await page.locator('.sheet').first().screenshot({path:path.join(out,'revision-3.png')});
    record=next;
    await load();
    await page.getByRole('heading',{name:'Check actuator travel and position feedback first'}).waitFor();
    assert.match(await page.locator('#reason').innerText(),/MEC 046 sensor sharing/);
    await page.locator('.sheet').first().screenshot({path:path.join(out,'revision-4.png')});
    showEntry=true;
    await load();
    await page.locator('#history li').waitFor();
    assert.match(await page.locator('#history').innerText(),/Inspection scheduled/);
    await page.locator('#history').screenshot({path:path.join(out,'scheduled.png')});
  }finally{await browser.close();}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
