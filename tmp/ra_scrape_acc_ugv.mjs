import { writeFile } from 'node:fs/promises'
import puppeteer from '../tests/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js'
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const UA = 'IranRobotImporter/1.0 (+contact)'
const OUT = '/Users/pouyanshams/Desktop/hooshafarin/iran-robota/tmp/robotsasia-acc-ugv-raw.json'
const B = 'https://www.robotsasia.com/'
const TARGETS = [
  // ---- UGVs (category ugvs, no subcategory) -- all distinct from the 3 seed ugvs ----
  { product_id: 'robotsasia-ugv-husarion-panther', category: 'ugvs', subcategory: null, url: B + 'Husarion-Panther-PTH12.htm' },
  { product_id: 'robotsasia-ugv-husarion-rosbot3', category: 'ugvs', subcategory: null, url: B + 'Husarion-ROSbot-3.htm' },
  { product_id: 'robotsasia-ugv-husarion-rosbot3-pro', category: 'ugvs', subcategory: null, url: B + 'Husarion-ROSbot-3-PRO.htm' },
  { product_id: 'robotsasia-ugv-guoxing-rxr-m40d-880t', category: 'ugvs', subcategory: null, url: B + 'Guo-Xing-RXR-M40D-880T-Firefighting-Robot.htm' },
  { product_id: 'robotsasia-ugv-guoxing-rxr-mc80bd', category: 'ugvs', subcategory: null, url: B + 'Guo-Xing-RXR-MC80BD-Firefighting-Robot.htm' },
  { product_id: 'robotsasia-ugv-guoxing-eod-gxbox510', category: 'ugvs', subcategory: null, url: B + 'Guo-Xing-GXBOX510-EOD-Robot-GX-BOX510.htm' },
  { product_id: 'robotsasia-ugv-guoxing-rxr-c6bd', category: 'ugvs', subcategory: null, url: B + 'Guo-Xing-RXR-C6BD-Explosion-Proof-Inspection-Patrol-Rescue-Robot.htm' },
  { product_id: 'robotsasia-ugv-guoxing-mower-kt500', category: 'ugvs', subcategory: null, url: B + 'Guo-Xing-KT500-Guoxing-RC-Forest-Terrain-Slope-Mower.htm' },
  { product_id: 'robotsasia-ugv-topsky-rxr-c10d', category: 'ugvs', subcategory: null, url: B + 'Topsky-Small-Fire-Reconnaissance-Robot-RXR-C10D.htm' },
  { product_id: 'robotsasia-ugv-topsky-ugv', category: 'ugvs', subcategory: null, url: B + 'Topsky-UGV-UGV.htm' },
  // ---- Accessories (category accessories) -- all distinct from the 25 seed accessories ----
  { product_id: 'robotsasia-accessory-inspire-rh56f1-e2r', category: 'accessories', subcategory: 'robot-hands', url: B + 'Inspire-Robots-Dexterous-Right-Hand-RH56F1-E2R.htm' },
  { product_id: 'robotsasia-accessory-linkerbot-l10', category: 'accessories', subcategory: 'robot-hands', url: B + 'Linkerbot-Linker-Hand-L10-Standard-Version.htm' },
  { product_id: 'robotsasia-accessory-robotera-xhand1', category: 'accessories', subcategory: 'robot-hands', url: B + 'Robotera-XHAND1-Dexterous-Hand.htm' },
  { product_id: 'robotsasia-accessory-unitree-dex3-1', category: 'accessories', subcategory: 'robot-hands', url: B + 'Unitree-G1-Dex3-1-Force-Control-Three-Finger-Dexterity-Hand.htm' },
  { product_id: 'robotsasia-accessory-unitree-h1-2-hand', category: 'accessories', subcategory: 'robot-hands', url: B + 'Unitree-H1-2-Dexterous-Hand.htm' },
  { product_id: 'robotsasia-accessory-shadow-dh', category: 'accessories', subcategory: 'robot-hands', url: B + 'Shadow-DH-Dexterous-Hand.htm' },
  { product_id: 'robotsasia-accessory-agibot-omnipicker', category: 'accessories', subcategory: 'robot-hands', url: B + 'Agibot-OmniPicker.htm' },
  { product_id: 'robotsasia-accessory-agibot-x2-battery', category: 'accessories', subcategory: 'robot-batteries', url: B + 'AgiBot-X2-Spare-Battery.htm' },
  { product_id: 'robotsasia-accessory-unitree-r1-charger', category: 'accessories', subcategory: 'robot-chargers', url: B + 'Unitree-R1-Battery-Charger.htm' },
  { product_id: 'robotsasia-accessory-bwsensing-bws2700', category: 'accessories', subcategory: 'sensors', url: B + 'BWSENSING-BWS2700-High-Precision-Modbus-Dual-Axis-Inclinometer.htm' },
]
const browser = await puppeteer.launch({ executablePath: CHROME, headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] })
const results = []
try {
  const page = await browser.newPage(); await page.setUserAgent(UA)
  for (const [i, t] of TARGETS.entries()) {
    process.stderr.write(`[${i + 1}/${TARGETS.length}] ${t.product_id}\n`)
    try {
      await page.goto(t.url, { waitUntil: 'networkidle2', timeout: 60000 })
      await page.evaluate(async () => { for (let y = 0; y < document.body.scrollHeight; y += 700) { window.scrollTo(0, y); await new Promise(r => setTimeout(r, 70)) } })
      await new Promise(r => setTimeout(r, 1100))
      const d = await page.evaluate(() => {
        const clean = s => (s || '').replace(/\s+/g, ' ').trim()
        const h1 = clean(document.querySelector('h1')?.textContent)
        const priceRaw = clean(document.querySelector('.price,[data-price-type="finalPrice"] .price')?.textContent)
        const specs = []
        document.querySelectorAll('table tr').forEach(tr => { const c = [...tr.querySelectorAll('th,td')].map(x => (x.textContent || '').replace(/\s+/g, ' ').trim()); if (c.length >= 2 && c[0] && c[1] && c[0] !== c[1]) specs.push({ label: c[0], value: c.slice(1).join(' ') }) })
        return { h1, priceRaw, specs, description: clean(document.querySelector('#description')?.textContent), metaDesc: document.querySelector('meta[name="description"]')?.content || null, ogImage: document.querySelector('meta[property="og:image"]')?.content || null }
      })
      results.push({ ...t, ...d })
      process.stderr.write(`    ok "${d.h1}" specs=${d.specs.length} desc=${(d.description || '').length}c img=${d.ogImage ? 'Y' : 'n'}\n`)
    } catch (e) { results.push({ ...t, error: String(e).slice(0, 150) }); process.stderr.write(`    FAIL ${e}\n`) }
    await new Promise(r => setTimeout(r, 1800))
  }
  await writeFile(OUT, JSON.stringify({ count: results.length, products: results }, null, 2))
  process.stderr.write(`\nwrote ${OUT}\n`)
} finally { await browser.close() }
