import { writeFile } from 'node:fs/promises'
import puppeteer from '../tests/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js'
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const UA = 'IranRobotImporter/1.0 (+contact)'
const OUTDIR = '/Users/pouyanshams/Desktop/hooshafarin/iran-robota/tmp'
const CATS = [
  { key: 'ugvs', url: 'https://www.robotsasia.com/Unmanned-Ground-Vehicles.htm' },
  { key: 'acc-hands', url: 'https://www.robotsasia.com/Robot-Hands.htm' },
  { key: 'acc-batteries', url: 'https://www.robotsasia.com/Robot-Batteries.htm' },
  { key: 'acc-chargers', url: 'https://www.robotsasia.com/Robot-Chargers.htm' },
  { key: 'acc-sensors', url: 'https://www.robotsasia.com/Robot-Sensors.htm' },
]
const b = await puppeteer.launch({ executablePath: CHROME, headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] })
try {
  const page = await b.newPage(); await page.setUserAgent(UA)
  for (const { key, url } of CATS) {
    const byUrl = new Map(); let title = '', total = null
    for (let p = 1; p <= 5; p++) {
      try { await page.goto(`${url}?p=${p}`, { waitUntil: 'networkidle2', timeout: 60000 }) } catch { break }
      await page.evaluate(async () => { for (let y = 0; y < document.body.scrollHeight; y += 800) { window.scrollTo(0, y); await new Promise(r => setTimeout(r, 90)) } })
      await new Promise(r => setTimeout(r, 1000))
      title = await page.title()
      const r = await page.evaluate(() => {
        const out = []
        document.querySelectorAll('a.product-item-link').forEach(a => {
          const it = a.closest('.product-item,.product-item-info,li'); let price = null
          if (it) { const pe = it.querySelector('.price'); price = pe ? pe.textContent.trim().replace(/\s+/g, ' ') : null }
          out.push({ name: a.textContent.trim().replace(/\s+/g, ' '), url: a.href, price })
        })
        const tn = [...document.querySelectorAll('.toolbar-number')].map(e => e.textContent.trim())
        return { out, tn }
      })
      const before = byUrl.size
      for (const f of r.out) if (f.url && !byUrl.has(f.url)) byUrl.set(f.url, f)
      if (r.tn.length >= 3) total = r.tn[2]
      if (byUrl.size === before) break
    }
    const products = [...byUrl.values()]
    await writeFile(`${OUTDIR}/ra-${key}-listing.json`, JSON.stringify({ key, url, title, total, count: products.length, products }, null, 2))
    console.log(`\n=== ${key} (${title}) total=${total} collected=${products.length} ===`)
    for (const p of products) console.log('  ', (p.price || '—').padEnd(14), p.name.slice(0, 66), '||', p.url.split('/').pop())
  }
} finally { await b.close() }
