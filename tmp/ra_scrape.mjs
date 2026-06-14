#!/usr/bin/env node
/**
 * Scrape the 10 selected standalone cobot-arm product pages on RobotsAsia
 * (read-only) and dump full raw factual data to tmp/robotsasia-cobots-raw.json.
 * Polite: single browser, throttled, descriptive UA. No writes to the source.
 *
 * Captures per product: source url, h1 name, raw price, every spec-table row,
 * full #description prose, meta description, hero (og:image) + model-matched
 * gallery images. Description prose is captured for FACTUAL extraction only —
 * the IranRobot copy is rewritten by hand afterwards.
 */
import { writeFile } from 'node:fs/promises'
import puppeteer from '../tests/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js'

const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const UA = 'IranRobotImporter/1.0 (+contact)'
const OUT = '/Users/pouyanshams/Desktop/hooshafarin/iran-robota/tmp/robotsasia-cobots-raw.json'

const TARGETS = [
  'https://www.robotsasia.com/Fairino-FR10-Cobot.htm',
  'https://www.robotsasia.com/Fairino-FR5-Cobot.htm',
  'https://www.robotsasia.com/Fairino-FR3-Cobot.htm',
  'https://www.robotsasia.com/SIASUN-GCR16-960-SIASUN-Collaborative-Robot.htm',
  'https://www.robotsasia.com/SIASUN-GCR20-1400-SIASUN-Collaborative-Robot.htm',
  'https://www.robotsasia.com/Agilex-Piper.htm',
  'https://www.robotsasia.com/Elephant-Robotics-myCobot-Pro-630-Robot-Arm-4010200011.htm',
  'https://www.robotsasia.com/Elephant-Robotics-Technology-4010100023-Mycobot-320-Pi-Robot-Arm.htm',
  'https://www.robotsasia.com/Realman-Robotics-RM65-B-Ultra-Lightweight-Humanoid-Robotic-Arm.htm',
  'https://www.robotsasia.com/Galaxea-A1-A1-Robotic-Arm.htm',
]

const browser = await puppeteer.launch({ executablePath: CHROME, headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] })
const results = []
try {
  const page = await browser.newPage()
  await page.setUserAgent(UA)
  for (const [i, url] of TARGETS.entries()) {
    process.stderr.write(`[${i + 1}/${TARGETS.length}] ${url}\n`)
    try {
      await page.goto(url, { waitUntil: 'networkidle2', timeout: 60000 })
      await page.evaluate(async () => { for (let y = 0; y < document.body.scrollHeight; y += 700) { window.scrollTo(0, y); await new Promise((r) => setTimeout(r, 80)) } })
      await new Promise((r) => setTimeout(r, 1200))
      const d = await page.evaluate(() => {
        const clean = (s) => (s || '').replace(/\s+/g, ' ').trim()
        const h1 = clean(document.querySelector('h1')?.textContent)
        const priceRaw = clean(document.querySelector('.price, [data-price-type="finalPrice"] .price')?.textContent)
        // All spec rows from all tables
        const specs = []
        document.querySelectorAll('table tr').forEach((tr) => {
          const cells = [...tr.querySelectorAll('th,td')].map((c) => (c.textContent || '').replace(/\s+/g, ' ').trim())
          if (cells.length >= 2 && cells[0] && cells[1] && cells[0] !== cells[1]) specs.push({ label: cells[0], value: cells.slice(1).join(' ') })
        })
        const description = clean(document.querySelector('#description')?.textContent)
        const metaDesc = document.querySelector('meta[name="description"]')?.content || null
        const ogImage = document.querySelector('meta[property="og:image"]')?.content || null
        const allImgs = [...new Set([...document.querySelectorAll('img')].map((im) => im.getAttribute('data-zoom-image') || im.src).filter((u) => u && /\/media\/catalog\/product\//.test(u) && !/placeholder|swatch|thumbnail/i.test(u)))]
        return { h1, priceRaw, specs, description, metaDesc, ogImage, allImgs }
      })
      results.push({ sourceUrl: url, slug: url.split('/').pop().replace('.htm', ''), ...d })
      process.stderr.write(`    ok: "${d.h1}" specs=${d.specs.length} desc=${(d.description || '').length}c imgs=${d.allImgs.length}\n`)
    } catch (e) {
      results.push({ sourceUrl: url, error: String(e).slice(0, 160) })
      process.stderr.write(`    FAIL: ${e}\n`)
    }
    await new Promise((r) => setTimeout(r, 2000)) // politeness throttle
  }
  await writeFile(OUT, JSON.stringify({ scrapedCount: results.length, products: results }, null, 2))
  process.stderr.write(`\nwrote ${OUT}\n`)
} finally { await browser.close() }
