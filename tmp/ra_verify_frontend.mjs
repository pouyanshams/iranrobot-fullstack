#!/usr/bin/env node
/** Render the IranRobot catalog cobots route and confirm imported cards appear. */
import puppeteer from '../tests/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js'
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const SHOT = '/Users/pouyanshams/Desktop/hooshafarin/iran-robota/tests/artifacts/cobots-import-catalog.png'

const EXPECT = [
  'Fairino FR10', 'Fairino FR5', 'Fairino FR3', 'GCR16-960', 'GCR20-1400',
  'PiPER', 'myCobot Pro 630', 'myCobot 320 Pi', 'RM65-B', 'Galaxea A1',
]

const browser = await puppeteer.launch({ executablePath: CHROME, headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] })
try {
  const page = await browser.newPage()
  await page.setViewport({ width: 1440, height: 1600 })
  // Pre-set onboarding-seen so the intro modal doesn't overlay the grid.
  await page.evaluateOnNewDocument(() => {
    try { localStorage.setItem('iranrobot.v1.onboarding.seen', 'true') } catch {}
  })
  await page.goto('http://localhost:5173/#/catalog', { waitUntil: 'networkidle2', timeout: 60000 })
  await new Promise((r) => setTimeout(r, 1500))
  // Category is held in React state (not the URL): click the Cobots sidebar item.
  const clicked = await page.evaluate(() => {
    const target = [...document.querySelectorAll('button, a')].find(
      (el) => el.textContent && el.textContent.trim().includes('بازوهای همکار'),
    )
    if (target) { target.click(); return target.textContent.trim() }
    return null
  })
  console.log('clicked category control:', JSON.stringify(clicked))
  await new Promise((r) => setTimeout(r, 2500)) // let products API resolve + render
  const bodyText = await page.evaluate(() => document.body.innerText)
  // Count distinct product cards via the "Add"/"Details" CTA or card headings.
  const cardCount = await page.evaluate(() => {
    // Cards render a product name heading; count <h3>/<h2> inside the products grid area.
    const heads = [...document.querySelectorAll('h2, h3')].map((h) => h.textContent.trim())
    return heads.length
  })
  await page.screenshot({ path: SHOT, fullPage: true })
  const found = EXPECT.filter((name) => bodyText.includes(name))
  console.log('headings on page:', cardCount)
  console.log(`matched imported products: ${found.length}/${EXPECT.length}`)
  for (const n of EXPECT) console.log(`  ${found.includes(n) ? 'OK ' : '.. '} ${n}`)
  console.log('screenshot:', SHOT)
} finally { await browser.close() }
