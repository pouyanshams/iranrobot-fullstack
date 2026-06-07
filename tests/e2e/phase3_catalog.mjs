import puppeteer from 'puppeteer-core'
import fs from 'node:fs'

const SHOTS = 'tests/artifacts/phase3-catalog'
fs.rmSync(SHOTS, { recursive: true, force: true })
fs.mkdirSync(SHOTS, { recursive: true })

const browser = await puppeteer.launch({
  executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  headless: 'new',
  args: ['--no-sandbox'],
})
const page = await browser.newPage()
await page.setViewport({ width: 1400, height: 900 })

const errors = []
const console_ = []
page.on('pageerror', e => errors.push({ kind: 'pageerror', message: e.message, stack: e.stack?.split('\n').slice(0,8).join('\n') }))
page.on('console', m => console_.push({ type: m.type(), text: m.text() }))

// Pre-dismiss onboarding by seeding localStorage before the SPA boots
await page.goto('http://localhost:5173/', { waitUntil: 'load' })
await page.evaluate(() => {
  localStorage.setItem('ir.onboarding.v1', JSON.stringify({ seen: true, at: Date.now() }))
})

async function inspect(label, i) {
  await new Promise(r => setTimeout(r, 800))
  const info = await page.evaluate(() => {
    // walk all motion-style children of <main> and report the min opacity
    const main = document.querySelector('main')
    const kids = Array.from(main?.children ?? [])
    let minOp = 1
    let visKids = 0
    for (const k of kids) {
      const op = parseFloat(getComputedStyle(k).opacity ?? '1')
      if (op < minOp) minOp = op
      if (op > 0) visKids++
    }
    return {
      rootHtmlLen: document.getElementById('root')?.innerHTML?.length ?? 0,
      articles: document.querySelectorAll('article').length,
      h1: document.querySelector('h1')?.textContent?.trim() ?? null,
      mainKids: kids.length,
      minOpacity: minOp,
      visibleKids: visKids,
      solutionEmpty: document.body.textContent?.includes('No products linked to this solution') || document.body.textContent?.includes('هنوز محصولی به این راهکار'),
      url: location.hash,
    }
  })
  await page.screenshot({ path: `${SHOTS}/${String(i).padStart(2,'0')}_${label}.png` })
  const ok = info.minOpacity > 0.5 && info.visibleKids > 0
  const mark = ok ? '✅' : '❌ HIDDEN'
  console.log(`${mark} [${String(i).padStart(2,'0')} ${label.padEnd(28)}] minOp=${info.minOpacity}  visKids=${info.visibleKids}  articles=${String(info.articles).padStart(2)}  h1=${(info.h1||'').slice(0,20)}  url=${info.url}`)
  return info
}

async function clickByText(needles) {
  return await page.evaluate((needles) => {
    const buttons = Array.from(document.querySelectorAll('button'))
    for (const b of buttons) {
      const t = (b.textContent || '').trim()
      for (const n of needles) if (t.includes(n)) { b.click(); return t }
    }
    return null
  }, needles)
}

console.log('=== Final verification ===\n')

await page.goto('http://localhost:5173/#/catalog', { waitUntil: 'load' })
await inspect('catalog_default', 0)

const seq = [
  { label: 'humanoids',           needles: ['Humanoids', 'انسان‌نماها'] },
  { label: 'bipedal_humanoids',   needles: ['Bipedal Humanoids', 'انسان‌نمای دو پا'] },
  { label: 'wheeled_humanoids',   needles: ['Wheeled Humanoids', 'انسان‌نمای چرخ‌دار'] },
  { label: 'upper_body_humanoids',needles: ['Upper Body Humanoids', 'انسان‌نمای بالاتنه'] },
  { label: 'quadrupeds',          needles: ['Quadrupeds', 'چهارپاها'] },
  { label: 'standard_quadrupeds', needles: ['Standard Quadrupeds', 'چهارپای استاندارد'] },
  { label: 'wheeled_quadrupeds',  needles: ['Wheeled Quadrupeds', 'چهارپای چرخ‌دار'] },
  { label: 'accessories',         needles: ['Accessories', 'لوازم جانبی'] },
  { label: 'robot_hands',         needles: ['Robot Hands', 'دست‌های ربات'] },
  { label: 'drones',              needles: ['Drones', 'پهپادها'] },
  { label: 'ugvs',                needles: ['UGVs', 'خودروهای زمینی'] },
  { label: 'solutions',           needles: ['Solutions', 'راهکارها'] },
  { label: 'education',           needles: ['Education', 'آموزش و پژوهش'] },
  { label: 'warehouse',           needles: ['Warehouse', 'انبارداری'] },
  { label: 'healthcare',          needles: ['Healthcare', 'سلامت'] },
  { label: 'custom_solution',     needles: ['Custom Solution', 'راهکار سفارشی'] },
]

let i = 1
for (const c of seq) { await clickByText(c.needles); await inspect(c.label, i++) }

console.log('\n--- PDP cross-route transition ---')
await page.goto('http://localhost:5173/#/catalog', { waitUntil: 'load' })
await new Promise(r => setTimeout(r, 600))
await clickByText(['Bipedal Humanoids', 'انسان‌نمای دو پا'])
await inspect('catalog_bipedal', i++)
await page.evaluate(() => {
  const articles = Array.from(document.querySelectorAll('article'))
  if (articles[0]) {
    const btn = articles[0].querySelector('button[aria-label]')
    if (btn) btn.click()
  }
})
await inspect('pdp_first', i++)
await page.evaluate(() => {
  const main = document.querySelector('main')
  const articles = main?.querySelectorAll('article')
  if (articles && articles.length) {
    const btn = articles[articles.length - 1].querySelector('button[aria-label]')
    if (btn) btn.click()
  }
})
await inspect('pdp_related', i++)
await clickByText(['Shop', 'فروشگاه'])
await inspect('back_to_catalog', i++)

console.log('\n--- Rapid stress ---')
for (const c of [
  ['Bipedal Humanoids', 'انسان‌نمای دو پا'],
  ['Wheeled Humanoids', 'انسان‌نمای چرخ‌دار'],
  ['Standard Quadrupeds', 'چهارپای استاندارد'],
  ['Robot Hands', 'دست‌های ربات'],
  ['Drones', 'پهپادها'],
  ['Education', 'آموزش و پژوهش'],
  ['UGVs', 'خودروهای زمینی'],
  ['Bipedal Humanoids', 'انسان‌نمای دو پا'],
]) { await clickByText(c) }
await inspect('after_rapid', i++)

console.log('\n=== Summary ===')
console.log(`page errors: ${errors.length}`)
errors.filter(e => e.kind === 'pageerror').forEach(e => console.log(JSON.stringify(e, null, 2)))
const consoleErr = console_.filter(c => c.type === 'error')
console.log(`console errors: ${consoleErr.length}`)
consoleErr.slice(0,5).forEach(m => console.log(`  ${m.text.slice(0,500)}`))

await browser.close()
console.log(`\nscreenshots: ${SHOTS}/`)
