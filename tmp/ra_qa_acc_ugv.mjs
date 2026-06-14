import puppeteer from '../tests/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js'
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const ART = '/Users/pouyanshams/Desktop/hooshafarin/iran-robota/tests/artifacts/'
// label_fa -> expected robotsasia brand tokens
const FILTERS = [
  { label: 'خودروهای زمینی', expect: ['Husarion', 'Guo Xing', 'Topsky'], shot: 'qa-ugvs.png', parent: null },
  { label: 'لوازم جانبی', expect: ['Inspire', 'Linkerbot', 'Shadow', 'BWSENSING'], shot: 'qa-accessories.png', parent: null },
  { label: 'دست‌های ربات', expect: ['Inspire', 'Shadow', 'Robotera'], shot: null, parent: 'لوازم جانبی' },
  { label: 'باتری ربات', expect: ['AgiBot X2'], shot: null, parent: 'لوازم جانبی' },
  { label: 'شارژر ربات', expect: ['Unitree R1'], shot: null, parent: 'لوازم جانبی' },
  { label: 'سنسورها', expect: ['BWS2700'], shot: null, parent: 'لوازم جانبی' },
]
const browser = await puppeteer.launch({ executablePath: CHROME, headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] })
async function clickLabel(page, label) {
  return page.evaluate((l) => {
    const el = [...document.querySelectorAll('button,a')].find((e) => e.textContent && e.textContent.trim() === l) ||
               [...document.querySelectorAll('button,a')].find((e) => e.textContent && e.textContent.trim().includes(l))
    if (el) { el.click(); return true } return false
  }, label)
}
try {
  const page = await browser.newPage()
  await page.setViewport({ width: 1440, height: 1700 })
  await page.evaluateOnNewDocument(() => { try { localStorage.setItem('iranrobot.v1.onboarding.seen', 'true') } catch {} })
  for (const f of FILTERS) {
    await page.goto('http://localhost:5173/#/catalog', { waitUntil: 'networkidle2', timeout: 60000 })
    await new Promise((r) => setTimeout(r, 1100))
    if (f.parent) { await clickLabel(page, f.parent); await new Promise((r) => setTimeout(r, 1200)) }
    const clicked = await clickLabel(page, f.label)
    await new Promise((r) => setTimeout(r, 2200))
    const r = await page.evaluate(() => ({ heads: document.querySelectorAll('h2,h3').length, addBtns: [...document.querySelectorAll('button')].filter((b) => /افزودن|Add/.test(b.textContent)).length, detailBtns: [...document.querySelectorAll('button,a')].filter((b) => /جزئیات|Details/.test(b.textContent)).length, text: document.body.innerText }))
    if (f.shot) await page.screenshot({ path: ART + f.shot, fullPage: true })
    const found = f.expect.filter((e) => r.text.includes(e))
    console.log(`[${f.label}] clicked=${clicked} cards~=${r.heads} add=${r.addBtns} details=${r.detailBtns} matched=${found.length}/${f.expect.length} [${found.join(',')}]`)
  }
  // ---- detail page check: open a UGV product detail ----
  await page.goto('http://localhost:5173/#/catalog', { waitUntil: 'networkidle2', timeout: 60000 })
  await new Promise((r) => setTimeout(r, 1000))
  await clickLabel(page, 'خودروهای زمینی'); await new Promise((r) => setTimeout(r, 2200))
  // click first "Details/جزئیات"
  await page.evaluate(() => { const b = [...document.querySelectorAll('button,a')].find((e) => /جزئیات|Details/.test(e.textContent)); if (b) b.click() })
  await new Promise((r) => setTimeout(r, 2000))
  const det = await page.evaluate(() => ({ hash: location.hash, hasSpecTable: /مشخصات|Spec|نوع|درجه|ابعاد/.test(document.body.innerText), addBtn: [...document.querySelectorAll('button')].some((b) => /افزودن|Add|استعلام|Quote/.test(b.textContent)), title: (document.querySelector('h1,h2')?.textContent || '').trim().slice(0, 50) }))
  await page.screenshot({ path: ART + 'qa-ugv-detail.png', fullPage: true })
  console.log(`[detail] hash=${det.hash} title="${det.title}" specsVisible=${det.hasSpecTable} addBtn=${det.addBtn}`)
} finally { await browser.close() }
