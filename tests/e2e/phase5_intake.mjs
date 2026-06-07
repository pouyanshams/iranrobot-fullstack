import puppeteer from 'puppeteer-core'
import fs from 'node:fs'

const SHOTS = 'tests/artifacts/phase5-intake'
fs.rmSync(SHOTS, { recursive: true, force: true })
fs.mkdirSync(SHOTS, { recursive: true })

const browser = await puppeteer.launch({
  executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  headless: 'new',
  args: ['--no-sandbox'],
})
const page = await browser.newPage()
await page.setViewport({ width: 1400, height: 900 })

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

async function reactSetValue(selector, value) {
  await page.evaluate((sel, val) => {
    const el = document.querySelector(sel)
    if (!el) return
    const proto = el.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype
    const setter = Object.getOwnPropertyDescriptor(proto, 'value').set
    setter.call(el, val)
    el.dispatchEvent(new Event('input', { bubbles: true }))
  }, selector, value)
}

async function snap(name, n) {
  await new Promise(r => setTimeout(r, 600))
  await page.screenshot({ path: `${SHOTS}/${String(n).padStart(2,'0')}_${name}.png` })
}

const PASS = []
const FAIL = []
function check(label, ok, extra='') {
  if (ok) { PASS.push(label); console.log(`  ✅ ${label}`) }
  else    { FAIL.push(label); console.log(`  ❌ ${label} ${extra}`) }
}

console.log('=== Phase 5 E2E ===\n')

// ===================== GUEST PROCUREMENT FLOW =====================
console.log('[A] Guest procurement submission')
await page.goto('http://localhost:5173/#/procurement', { waitUntil: 'load' })
await dismissOnboarding()
await snap('procurement_step0', 1)

// The Input component renders <input> with no `type` attribute, so the
// browser defaults to type=text but the `[type=text]` selector won't match.
// Use a selector that matches plain text inputs (no type, or type=text).
const TEXT_INPUT = 'main input:not([type=email]):not([type=password]):not([type=number]):not([type=tel])'

// Step 0: product details
async function fillByIndex(selector, values) {
  await page.evaluate((sel, vals) => {
    const inputs = Array.from(document.querySelectorAll(sel))
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set
    for (let i = 0; i < vals.length && i < inputs.length; i++) {
      if (vals[i] === undefined) continue
      setter.call(inputs[i], vals[i])
      inputs[i].dispatchEvent(new Event('input', { bubbles: true }))
    }
  }, selector, values)
}

await fillByIndex(TEXT_INPUT, ['FANUC LR Mate 200iD/7L', 'FANUC'])

// Click "Next step"
async function clickButtonByText(needles) {
  return page.evaluate((needles) => {
    for (const b of document.querySelectorAll('button')) {
      const t = (b.textContent || '').trim()
      for (const n of needles) {
        if (t.includes(n)) { b.click(); return t }
      }
    }
    return null
  }, needles)
}

await clickButtonByText(['مرحله بعد', 'Next step'])
await new Promise(r => setTimeout(r, 500))
await snap('procurement_step1', 2)

// Step 1: quantity (already 1) + country (already first), budget optional. Just click next.
await clickButtonByText(['مرحله بعد', 'Next step'])
await new Promise(r => setTimeout(r, 500))
await snap('procurement_step2', 3)

// Step 2: contact details (guest)
const textInputs2 = await page.$$(TEXT_INPUT)
console.log(`    plain text inputs on step 2: ${textInputs2.length}`)
await page.evaluate(() => {
  const setVal = (el, val) => {
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set
    setter.call(el, val)
    el.dispatchEvent(new Event('input', { bubbles: true }))
  }
  const txts = document.querySelectorAll('main input:not([type=email]):not([type=password]):not([type=number]):not([type=tel])')
  const email = document.querySelector('main input[type="email"]')
  const tel = document.querySelector('main input[inputmode="tel"]')
  if (txts[0]) setVal(txts[0], 'E2E Procurement Guest')
  if (email) setVal(email, 'e2e-procure@example.com')
  if (tel) setVal(tel, '09125551234')
})

await snap('procurement_step2_filled', 4)
await clickButtonByText(['ثبت درخواست', 'Submit request'])
await new Promise(r => setTimeout(r, 2500))
await snap('procurement_success', 5)

const procText = await page.evaluate(() => document.querySelector('main')?.innerText || '')
const procIdMatch = procText.match(/PR-\d+-\d+/)
check('Guest procurement -> success with PR id', !!procIdMatch, `text=${procText.slice(0,200)}`)

// ===================== GUEST SUPPORT FLOW =====================
console.log('\n[B] Guest support submission')
await page.goto('http://localhost:5173/#/support', { waitUntil: 'load' })
await dismissOnboarding()
await new Promise(r => setTimeout(r, 600))
await snap('support_form', 6)

await page.evaluate(() => {
  const setVal = (el, val, isTextArea = false) => {
    const proto = isTextArea ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype
    const setter = Object.getOwnPropertyDescriptor(proto, 'value').set
    setter.call(el, val)
    el.dispatchEvent(new Event('input', { bubbles: true }))
  }
  const name = document.querySelector('form input:not([type=email]):not([type=password]):not([type=number]):not([type=tel])')
  const email = document.querySelector('form input[type="email"]')
  const textarea = document.querySelector('form textarea')
  if (name) setVal(name, 'E2E Support Guest')
  if (email) setVal(email, 'e2e-support@example.com')
  if (textarea) setVal(textarea, 'Hello support team, this is an E2E test message.', true)
})

await snap('support_filled', 7)
await clickButtonByText(['ارسال تیکت', 'Send ticket'])
await new Promise(r => setTimeout(r, 2500))
await snap('support_success', 8)

const supText = await page.evaluate(() => document.querySelector('main')?.innerText || '')
const supIdMatch = supText.match(/ISS-\d+-\d+/)
check('Guest support -> success with ISS id', !!supIdMatch, `text=${supText.slice(0,200)}`)

// ===================== LOGIN -> QUOTE FLOW =====================
console.log('\n[C] Logged-in quote submission via cart drawer')
await page.goto('http://localhost:5173/', { waitUntil: 'load' })
await dismissOnboarding()

// Open login modal
await page.evaluate(() => {
  for (const b of document.querySelectorAll('header button')) {
    if (b.querySelector('svg.lucide-log-in, svg[class*="lucide-log-in"]')) { b.click(); return }
  }
})
await new Promise(r => setTimeout(r, 400))
await reactSetValue('input[type="email"]', 'customer1@example.com')
await reactSetValue('input[type="password"]', 'ChangeMe-123')
await page.click('button[type="submit"]')
await new Promise(r => setTimeout(r, 2200))
await snap('quote_logged_in', 9)

// Add a product to cart from a PDP
await page.goto('http://localhost:5173/#/robot/aimoga-mornine', { waitUntil: 'load' })
await dismissOnboarding()
await new Promise(r => setTimeout(r, 800))
await snap('quote_pdp', 10)
// Click "Add to cart" / "افزودن به سبد"
await clickButtonByText(['افزودن به سبد', 'Add to cart', 'افزودن', 'Add'])
await new Promise(r => setTimeout(r, 800))
await snap('quote_drawer_open', 11)

// Check drawer is open
const drawerHasItems = await page.evaluate(() => {
  return !!document.querySelector('[role="dialog"] ul li, [role="dialog"] [class*="rounded-3xl"]')
})
console.log(`    drawer shows items: ${drawerHasItems}`)

// Click "Submit quote request" / "ثبت درخواست استعلام"
await clickButtonByText(['ثبت درخواست استعلام', 'Submit quote request'])
await new Promise(r => setTimeout(r, 2500))
await snap('quote_submitted', 12)

const quoteText = await page.evaluate(() => document.querySelector('[role="dialog"]')?.innerText || '')
const qrIdMatch = quoteText.match(/QR-\d+-\d+/)
check('Logged-in quote -> success with QR id in drawer', !!qrIdMatch, `text=${quoteText.slice(0,200)}`)

// ===================== ERRORS + STATE CHECKS =====================
console.log('\n[D] Error / state checks')

// Guest support with empty message -> validation message
await page.evaluate(() => {
  for (const b of document.querySelectorAll('button')) {
    if (/(خروج|Sign out)/.test(b.textContent || '')) {
      const menuTrigger = Array.from(document.querySelectorAll('header button[aria-haspopup="menu"]'))
        .find(b => b.querySelector('svg.lucide-user, svg[class*="lucide-user"]'))
      if (menuTrigger) menuTrigger.click()
      setTimeout(() => b.click(), 200)
      return
    }
  }
})

console.log('')
console.log(`  page errors:    ${pageErrors.length}`)
console.log(`  console errors: ${consoleErr.length}`)
pageErrors.forEach(e => console.log(`    ❌ ${e.message}`))
consoleErr.slice(0,4).forEach(m => console.log(`    [err] ${m.text.slice(0,300)}`))

console.log('')
console.log(`${PASS.length}/${PASS.length + FAIL.length} PASSED`)

await browser.close()
console.log(`\nscreenshots: ${SHOTS}/`)
process.exit(FAIL.length === 0 ? 0 : 1)
