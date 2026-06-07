/**
 * Phase 8D-3 E2E -- Pay Sales Invoice with Wallet from the invoice drawer.
 *
 * Pre-requisite: run the bench fixture seeder once so we have an isolated
 * customer + wallet (balance=$300) + submitted SI ($120) + linked QR:
 *
 *   bench --site iranrobot.localhost execute \
 *     iranrobot_backend.commands._phase8d3_e2e_fixtures.seed_phase8d3_e2e_fixture
 *
 * That writes `tests/artifacts/phase8d3_e2e_fixture.json` which this suite
 * reads at startup.
 */

import puppeteer from 'puppeteer-core'
import fs from 'node:fs'

const SHOTS = 'tests/artifacts/phase8d3-pay-invoice'
fs.rmSync(SHOTS, { recursive: true, force: true })
fs.mkdirSync(SHOTS, { recursive: true })

const FIX_PATH = 'tests/artifacts/phase8d3_e2e_fixture.json'
if (!fs.existsSync(FIX_PATH)) {
  console.error(`MISSING FIXTURE: ${FIX_PATH}`)
  console.error('Run: bench --site iranrobot.localhost execute iranrobot_backend.commands._phase8d3_e2e_fixtures.seed_phase8d3_e2e_fixture')
  process.exit(1)
}
const FIX = JSON.parse(fs.readFileSync(FIX_PATH, 'utf-8'))

const browser = await puppeteer.launch({
  executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  headless: 'new',
  args: ['--no-sandbox'],
})
const page = await browser.newPage()
await page.setViewport({ width: 1440, height: 900 })

// Auto-accept window.confirm dialogs from the PayWithWalletPanel
page.on('dialog', async (d) => { await d.accept() })

const pageErrors = []
const consoleErr = []
page.on('pageerror', e => pageErrors.push({ message: e.message }))
page.on('console', m => { if (m.type() === 'error') consoleErr.push({ text: m.text() }) })

async function dismissOnboarding() {
  await page.evaluate(() => {
    for (const d of document.querySelectorAll('[role="dialog"]')) {
      if (d.querySelector('[aria-labelledby="login-title"]')) continue
      for (const b of d.querySelectorAll('button')) {
        if (/(رد شدن|Skip|بستن|Close)/.test(b.textContent || '')) { b.click(); return }
      }
    }
  })
  await new Promise(r => setTimeout(r, 400))
}

async function reactSet(selector, value) {
  await page.evaluate((sel, val) => {
    const el = document.querySelector(sel)
    if (!el) return
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set
    setter.call(el, val)
    el.dispatchEvent(new Event('input', { bubbles: true }))
  }, selector, value)
}

async function snap(name, n) {
  await new Promise(r => setTimeout(r, 600))
  await page.screenshot({ path: `${SHOTS}/${String(n).padStart(2,'0')}_${name}.png` })
}

const PERSIAN_DIGIT_MAP = { '۰':'0','۱':'1','۲':'2','۳':'3','۴':'4','۵':'5','۶':'6','۷':'7','۸':'8','۹':'9','٠':'0','١':'1','٢':'2','٣':'3','٤':'4','٥':'5','٦':'6','٧':'7','٨':'8','٩':'9' }
function ascii(s) {
  return String(s || '').replace(/[۰-۹٠-٩]/g, (c) => PERSIAN_DIGIT_MAP[c] || c)
}

const PASS = []
const FAIL = []
function check(label, ok, extra='') {
  if (ok) { PASS.push(label); console.log(`  ✅ ${label}`) }
  else { FAIL.push(label); console.log(`  ❌ ${label} ${extra}`) }
}

console.log('=== Phase 8D-3 E2E -- Pay with Wallet ===\n')
console.log(`  fixture: ${FIX.email}  SI=${FIX.sales_invoice}  balance=$${FIX.expected_balance_before}  outstanding=$${FIX.expected_outstanding_before}`)

// ---------------------------------------------------------------- [1] login
console.log('\n[1] login as the fixture customer')
await page.goto('http://localhost:5173/', { waitUntil: 'load' })
await dismissOnboarding()
await new Promise(r => setTimeout(r, 700))
await page.evaluate(() => {
  for (const b of document.querySelectorAll('header button')) {
    if (b.querySelector('svg.lucide-log-in, svg[class*="lucide-log-in"]')) { b.click(); return }
  }
})
await new Promise(r => setTimeout(r, 800))
await page.waitForSelector('[aria-labelledby="login-title"] input[type="email"]', { timeout: 5000 })
await reactSet('[aria-labelledby="login-title"] input[type="email"]', FIX.email)
await reactSet('[aria-labelledby="login-title"] input[type="password"]', FIX.password)
await page.evaluate(() => {
  const form = document.querySelector('[aria-labelledby="login-title"] form')
  if (form) form.requestSubmit()
})
await new Promise(r => setTimeout(r, 2500))
await snap('logged_in', 1)

// ---------------------------------------------------------------- [2] open invoice drawer
console.log('\n[2] open the SI from invoices list')
await page.goto('http://localhost:5173/#/account/invoices', { waitUntil: 'load' })
await new Promise(r => setTimeout(r, 2000))
await snap('invoices_list', 2)
// Click the SI row that contains FIX.sales_invoice
const opened = await page.evaluate((siName) => {
  const rows = document.querySelectorAll('main ul li button')
  for (const r of rows) {
    if ((r.textContent || '').includes(siName)) { r.click(); return true }
  }
  return false
}, FIX.sales_invoice)
check('SI row found and clicked', opened)
await new Promise(r => setTimeout(r, 1500))
await snap('drawer_opened', 3)

// ---------------------------------------------------------------- [3] panel renders payable state
console.log('\n[3] Pay-with-Wallet panel shows payable state')
const panelText = await page.evaluate(() =>
  document.querySelector('[data-testid="wallet-pay-panel"]')?.innerText || '',
)
check('PayWithWalletPanel is rendered', panelText.length > 0, `text=${panelText.slice(0, 200)}`)
const panelAscii = ascii(panelText)
check('panel shows balance $300', /300/.test(panelAscii))
check('panel shows outstanding $120', /120/.test(panelAscii))
const submitDisabled = await page.evaluate(() =>
  document.querySelector('[data-testid="wallet-pay-submit"]')?.disabled,
)
check('Pay button enabled', submitDisabled === false)

// ---------------------------------------------------------------- [4] click Pay (full amount)
console.log('\n[4] click Pay (default amount = full $120)')
const balanceBefore = await pageBalanceFromPanel(page)
await page.evaluate(() => {
  document.querySelector('[data-testid="wallet-pay-submit"]')?.click()
})
await new Promise(r => setTimeout(r, 2500))
await snap('after_pay', 4)

// ---------------------------------------------------------------- [5] success banner + state
console.log('\n[5] success banner appears + invoice updates')
const successText = await page.evaluate(() =>
  document.querySelector('[data-testid="wallet-pay-success"]')?.innerText || '',
)
const successAscii = ascii(successText)
check('success banner rendered', successText.length > 0, `text=${successText.slice(0, 300)}`)
check('success banner mentions new balance', /180/.test(successAscii))
check('success banner shows transaction id', /WT-/.test(successAscii))

const drawerText = await page.evaluate(() =>
  document.querySelector('[role="dialog"]')?.innerText || '',
)
const drawerAscii = ascii(drawerText)
check('invoice status badge flipped to Paid', /Paid|تسویه|پرداخت شده/.test(drawerText), `text=${drawerText.slice(0, 200)}`)
check('drawer Outstanding now 0', /(?:Outstanding|باقی‌مانده)[^\d]*0(?:\.0+)?\b/.test(drawerAscii), `ascii=${drawerAscii.slice(0, 300)}`)

// ---------------------------------------------------------------- [6] Wallet payments row appears
console.log('\n[6] Wallet payments row appears in the drawer')
const walletPaymentsList = await page.evaluate(() =>
  document.querySelector('[data-testid="wallet-payments-list"]')?.innerText || '',
)
check('Wallet payments list rendered', walletPaymentsList.length > 0)
const walletPaymentsAscii = ascii(walletPaymentsList)
check('Wallet payments row shows amount -$120', /-?\$?\s?120/.test(walletPaymentsAscii))
check('Wallet payments row shows WT- id', /WT-/.test(walletPaymentsAscii))

// ---------------------------------------------------------------- [7] re-fetch payment status: blocked ALREADY_PAID
console.log('\n[7] payment status now shows ALREADY_PAID')
// Dismiss success first to force the next render path back to status check
await page.evaluate(() => {
  const btns = document.querySelectorAll('[data-testid="wallet-pay-success"] button')
  if (btns.length > 0) btns[btns.length - 1].click()
})
await new Promise(r => setTimeout(r, 800))
const blockedReason = await page.evaluate(() =>
  document.querySelector('[data-testid="wallet-pay-blocked"]')?.getAttribute('data-blocked-reason') || '',
)
check('panel switches to blocked=ALREADY_PAID', blockedReason === 'ALREADY_PAID', `got=${blockedReason}`)

// ---------------------------------------------------------------- summary
console.log('')
console.log(`  page errors:    ${pageErrors.length}`)
console.log(`  console errors: ${consoleErr.length}`)
pageErrors.forEach(e => console.log(`    ❌ ${e.message}`))
consoleErr.slice(0, 4).forEach(m => console.log(`    [err] ${m.text.slice(0, 300)}`))

console.log('')
console.log(`${PASS.length}/${PASS.length + FAIL.length} PASSED`)

await browser.close()
console.log(`\nscreenshots: ${SHOTS}/`)
process.exit(FAIL.length === 0 ? 0 : 1)

async function pageBalanceFromPanel(page) {
  return await page.evaluate(() => {
    const txt = document.querySelector('[data-testid="wallet-pay-panel"]')?.innerText || ''
    const m = txt.match(/[\d۰-۹٠-٩]+(?:[.,][\d۰-۹٠-٩]+)?/)
    return m ? m[0] : ''
  })
}
