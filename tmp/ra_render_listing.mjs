#!/usr/bin/env node
/**
 * Read-only enumerator: render the RobotsAsia "Cobots" category grid (JS-rendered)
 * and dump every product-item {name, url, price} to tmp/robotsasia-cobots-listing.json.
 * No writes to the target site; respects polite UA. Discovery only.
 */
import { writeFile } from 'node:fs/promises'
import puppeteer from '../tests/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js'

const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const UA = 'IranRobotImporter/1.0 (+contact)'
const PAGES = [1, 2, 3, 4] // 15/page, 52 total -> 4 pages

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: true,
  args: ['--no-sandbox', '--disable-dev-shm-usage'],
})
try {
  const page = await browser.newPage()
  await page.setUserAgent(UA)
  const byUrl = new Map()
  let title = ''
  for (const p of PAGES) {
    const pageUrl = `https://www.robotsasia.com/Cobots.htm?p=${p}`
    await page.goto(pageUrl, { waitUntil: 'networkidle2', timeout: 60000 })
    await page.evaluate(async () => {
      for (let y = 0; y < document.body.scrollHeight; y += 800) {
        window.scrollTo(0, y); await new Promise((r) => setTimeout(r, 100))
      }
    })
    await new Promise((r) => setTimeout(r, 1200))
    title = await page.title()
    const found = await page.evaluate(() => {
      const out = []
      document.querySelectorAll('a.product-item-link').forEach((a) => {
        const item = a.closest('.product-item, .product-item-info, li')
        let price = null
        if (item) {
          const pe = item.querySelector('.price, [data-price-type="finalPrice"] .price, .price-wrapper')
          price = pe ? pe.textContent.trim().replace(/\s+/g, ' ') : null
        }
        out.push({ name: a.textContent.trim().replace(/\s+/g, ' '), url: a.href, price })
      })
      return out
    })
    for (const f of found) if (f.url && !byUrl.has(f.url)) byUrl.set(f.url, f)
    console.error(`  page ${p}: +${found.length} (total ${byUrl.size})`)
  }
  const products = [...byUrl.values()]
  await writeFile(
    '/Users/pouyanshams/Desktop/hooshafarin/iran-robota/tmp/robotsasia-cobots-listing.json',
    JSON.stringify({ title, count: products.length, products }, null, 2),
  )
  console.log(`title="${title}" products=${products.length}`)
  for (const p of products) console.log(' -', (p.price || '—').padEnd(16), p.name.slice(0, 60), '||', p.url.split('/').pop())
} finally {
  await browser.close()
}
