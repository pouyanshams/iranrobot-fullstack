#!/usr/bin/env node
/** Probe ONE rendered product page to learn the DOM structure (read-only). */
import puppeteer from '../tests/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js'
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const target = process.argv[2] || 'https://www.robotsasia.com/Fairino-FR10-Cobot.htm'

const browser = await puppeteer.launch({ executablePath: CHROME, headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] })
try {
  const page = await browser.newPage()
  await page.setUserAgent('IranRobotImporter/1.0 (+contact)')
  await page.goto(target, { waitUntil: 'networkidle2', timeout: 60000 })
  await page.evaluate(async () => { for (let y=0;y<document.body.scrollHeight;y+=700){window.scrollTo(0,y);await new Promise(r=>setTimeout(r,80))} })
  await new Promise((r) => setTimeout(r, 1500))
  const data = await page.evaluate(() => {
    const txt = (el) => (el ? el.textContent.replace(/\s+/g, ' ').trim() : null)
    // headings
    const h1 = txt(document.querySelector('h1'))
    // price candidates
    const priceEls = [...document.querySelectorAll('.price, [data-price-type="finalPrice"]')].map((e) => e.textContent.replace(/\s+/g,' ').trim()).filter(Boolean).slice(0, 5)
    // tables (spec candidates)
    const tables = [...document.querySelectorAll('table')].map((t, i) => {
      const rows = [...t.querySelectorAll('tr')].slice(0, 4).map((tr) => [...tr.querySelectorAll('th,td')].map((c) => c.textContent.replace(/\s+/g,' ').trim()).join(' | '))
      return { i, cls: t.className, rowsSample: rows, rowCount: t.querySelectorAll('tr').length }
    })
    // definition-list / attribute style spec blocks
    const dlCount = document.querySelectorAll('dl, .additional-attributes, .product.attribute').length
    // description-ish blocks
    const descSelectors = ['#description', '.product.attribute.description', '[itemprop="description"]', '.product-info-main .overview', '.value']
    const descs = descSelectors.map((s) => ({ s, t: txt(document.querySelector(s))?.slice(0, 160) || null }))
    // images on /media/catalog/product/
    const imgs = [...document.querySelectorAll('img')].map((im) => im.getAttribute('data-zoom-image') || im.src).filter((u) => u && /\/media\/catalog\/product\//.test(u))
    const imgUniq = [...new Set(imgs)].slice(0, 8)
    // meta
    const metaDesc = document.querySelector('meta[name="description"]')?.content?.slice(0, 200) || null
    const ogImg = document.querySelector('meta[property="og:image"]')?.content || null
    return { h1, priceEls, tables, dlCount, descs, imgCount: imgUniq.length, imgs: imgUniq, metaDesc, ogImg }
  })
  console.log(JSON.stringify(data, null, 2))
} finally { await browser.close() }
