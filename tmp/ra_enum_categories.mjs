#!/usr/bin/env node
/** Enumerate RobotsAsia Core-4 category grids (JS-rendered, paginated). Read-only. */
import { writeFile } from 'node:fs/promises'
import puppeteer from '../tests/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js'

const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const UA = 'IranRobotImporter/1.0 (+contact)'
const OUTDIR = '/Users/pouyanshams/Desktop/hooshafarin/iran-robota/tmp'

const CATS = [
  { cat: 'humanoids', url: 'https://www.robotsasia.com/Humanoid-Robots.htm' },
  { cat: 'quadrupeds', url: 'https://www.robotsasia.com/Quadruped-Robots.htm' },
  { cat: 'amrs', url: 'https://www.robotsasia.com/Autonomous-Mobile-Robots-AMRs.htm' },
  { cat: 'drones', url: 'https://www.robotsasia.com/Drones.htm' },
]

const browser = await puppeteer.launch({ executablePath: CHROME, headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] })
try {
  const page = await browser.newPage()
  await page.setUserAgent(UA)
  for (const { cat, url } of CATS) {
    const byUrl = new Map()
    let title = '', total = null
    for (let p = 1; p <= 6; p++) {
      const pageUrl = `${url}?p=${p}`
      try {
        await page.goto(pageUrl, { waitUntil: 'networkidle2', timeout: 60000 })
      } catch { break }
      await page.evaluate(async () => { for (let y = 0; y < document.body.scrollHeight; y += 800) { window.scrollTo(0, y); await new Promise((r) => setTimeout(r, 90)) } })
      await new Promise((r) => setTimeout(r, 1000))
      title = await page.title()
      const r = await page.evaluate(() => {
        const out = []
        document.querySelectorAll('a.product-item-link').forEach((a) => {
          const item = a.closest('.product-item, .product-item-info, li')
          let price = null
          if (item) { const pe = item.querySelector('.price'); price = pe ? pe.textContent.trim().replace(/\s+/g, ' ') : null }
          out.push({ name: a.textContent.trim().replace(/\s+/g, ' '), url: a.href, price })
        })
        const tn = [...document.querySelectorAll('.toolbar-number')].map((e) => e.textContent.trim())
        return { out, tn }
      })
      const before = byUrl.size
      for (const f of r.out) if (f.url && !byUrl.has(f.url)) byUrl.set(f.url, f)
      if (r.tn.length >= 3) total = r.tn[2]
      // stop if this page added nothing new (past the last real page)
      if (byUrl.size === before) break
    }
    const products = [...byUrl.values()]
    await writeFile(`${OUTDIR}/robotsasia-${cat}-listing.json`, JSON.stringify({ cat, url, title, total, count: products.length, products }, null, 2))
    console.log(`\n=== ${cat} (${title}) total=${total} collected=${products.length} ===`)
    for (const p of products) console.log('  ', (p.price || '—').padEnd(14), p.name.slice(0, 64), '||', p.url.split('/').pop())
  }
} finally { await browser.close() }
