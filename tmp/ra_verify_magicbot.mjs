import puppeteer from '../tests/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js'
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const ART = '/Users/pouyanshams/Desktop/hooshafarin/iran-robota/tests/artifacts/'
const b = await puppeteer.launch({ executablePath: CHROME, headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] })
try {
  const page = await b.newPage()
  await page.setViewport({ width: 1280, height: 1400 })
  await page.evaluateOnNewDocument(() => { try { localStorage.setItem('iranrobot.v1.onboarding.seen', 'true') } catch {} })
  // Detail page
  await page.goto('http://localhost:5173/#/robot/magiclab-magicbot-g1', { waitUntil: 'networkidle2', timeout: 60000 })
  await new Promise((r) => setTimeout(r, 2500))
  const det = await page.evaluate(() => {
    const t = document.body.innerText
    return {
      hasBipedalEn: t.includes('Bipedal Humanoid'),
      hasBipedalFa: t.includes('انسان‌نمای دو پا'),
      hasWheeled: t.includes('Wheeled Humanoid') || t.includes('چرخ‌دار'),
      title: document.querySelector('h1')?.textContent?.trim() || '',
    }
  })
  await page.screenshot({ path: ART + 'magicbot-g1-detail-fixed.png', fullPage: true })
  console.log('DETAIL:', JSON.stringify(det))

  // bipedal-humanoids listing (catalog -> click humanoids -> click Bipedal Humanoids sub)
  await page.goto('http://localhost:5173/#/catalog', { waitUntil: 'networkidle2', timeout: 60000 })
  await new Promise((r) => setTimeout(r, 1200))
  await page.evaluate(() => { const e = [...document.querySelectorAll('button,a')].find((x) => x.textContent && x.textContent.includes('انسان‌نماها')); e && e.click() })
  await new Promise((r) => setTimeout(r, 800))
  const clickedSub = await page.evaluate(() => { const e = [...document.querySelectorAll('button,a')].find((x) => x.textContent && x.textContent.trim().includes('انسان‌نمای دو پا')); if (e) { e.click(); return true } return false })
  await new Promise((r) => setTimeout(r, 2500))
  const list = await page.evaluate(() => ({ hasG1: document.body.innerText.includes('MagicBot G1'), heads: document.querySelectorAll('h2,h3').length }))
  console.log('BIPEDAL LISTING: clickedSub=' + clickedSub, JSON.stringify(list))
} finally { await b.close() }
