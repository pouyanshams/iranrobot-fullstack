import puppeteer from '../tests/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js'
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const CATS = [
  { label: 'انسان‌نماها', expect: ['Unitree H1', 'RobotEra L7', 'Fourier'], shot: 'cobots-import-humanoids.png' },
  { label: 'چهارپاها', expect: ['Go2', 'Lite3', 'AlienGo'], shot: 'cobots-import-quadrupeds.png' },
  { label: 'ربات‌های متحرک خودران', expect: ['Keenon S100', 'T300', 'BellaBot'], shot: 'cobots-import-amrs.png' },
  { label: 'پهپادها', expect: ['P150', 'P100'], shot: 'cobots-import-drones.png' },
]
const ART = '/Users/pouyanshams/Desktop/hooshafarin/iran-robota/tests/artifacts/'
const browser = await puppeteer.launch({ executablePath: CHROME, headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] })
try {
  const page = await browser.newPage()
  await page.setViewport({ width: 1440, height: 1700 })
  await page.evaluateOnNewDocument(() => { try { localStorage.setItem('iranrobot.v1.onboarding.seen', 'true') } catch {} })
  for (const c of CATS) {
    await page.goto('http://localhost:5173/#/catalog', { waitUntil: 'networkidle2', timeout: 60000 })
    await new Promise((r) => setTimeout(r, 1200))
    const clicked = await page.evaluate((label) => {
      const el = [...document.querySelectorAll('button,a')].find((e) => e.textContent && e.textContent.trim().includes(label))
      if (el) { el.click(); return true }
      return false
    }, c.label)
    await new Promise((r) => setTimeout(r, 2500))
    const r = await page.evaluate(() => ({
      heads: document.querySelectorAll('h2,h3').length,
      text: document.body.innerText,
    }))
    await page.screenshot({ path: ART + c.shot, fullPage: true })
    const found = c.expect.filter((e) => r.text.includes(e))
    console.log(`${c.label}: clicked=${clicked} headings=${r.heads} matched=${found.length}/${c.expect.length} [${found.join(', ')}]`)
  }
} finally { await browser.close() }
