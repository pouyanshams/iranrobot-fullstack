import puppeteer from '../tests/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js'
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const browser = await puppeteer.launch({ executablePath: CHROME, headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] })
try {
  const page = await browser.newPage()
  await page.setViewport({ width: 1440, height: 1600 })
  const apiCalls = []
  page.on('response', (r) => { const u = r.url(); if (u.includes('/api/method/')) apiCalls.push(`${r.status()} ${u.split('/api/method/')[1].split('?')[0]} ${u.includes('category=') ? '?' + u.split('?')[1].slice(0,60) : ''}`) })
  page.on('console', (m) => { if (m.type() === 'error') console.log('CONSOLE-ERR:', m.text().slice(0, 160)) })
  await page.evaluateOnNewDocument(() => { try { localStorage.setItem('iranrobot.v1.onboarding.seen', 'true') } catch {} })
  await page.goto('http://localhost:5173/#/catalog/cobots', { waitUntil: 'networkidle2', timeout: 60000 })
  await new Promise((r) => setTimeout(r, 3000))
  const info = await page.evaluate(() => ({
    hash: location.hash,
    h2h3: [...document.querySelectorAll('h2,h3')].map((h) => h.textContent.trim()).filter(Boolean).slice(0, 30),
    hasFairino: document.body.innerText.includes('Fairino'),
    hasKoobat: document.body.innerText.includes('کوبات'),
    bodyStart: document.body.innerText.replace(/\s+/g, ' ').slice(0, 400),
  }))
  console.log('hash:', info.hash)
  console.log('API calls:'); apiCalls.forEach((c) => console.log('   ', c))
  console.log('hasFairino:', info.hasFairino, '| hasکوبات:', info.hasKoobat)
  console.log('h2/h3:', JSON.stringify(info.h2h3))
  console.log('bodyStart:', info.bodyStart)
} finally { await browser.close() }
