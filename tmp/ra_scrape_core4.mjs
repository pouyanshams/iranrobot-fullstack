#!/usr/bin/env node
/** Scrape the selected standalone robots for humanoids/quadrupeds/amrs/drones (read-only). */
import { writeFile } from 'node:fs/promises'
import puppeteer from '../tests/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js'

const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const UA = 'IranRobotImporter/1.0 (+contact)'
const OUT = '/Users/pouyanshams/Desktop/hooshafarin/iran-robota/tmp/robotsasia-core4-raw.json'
const B = 'https://www.robotsasia.com/'

const TARGETS = [
  // ---------- humanoids ----------
  { product_id: 'robotsasia-humanoid-unitree-g1-basic', category: 'humanoids', subcategory: 'bipedal-humanoids', url: B + 'Unitree-G1-Basic-Humanoid-Robot.htm' },
  { product_id: 'robotsasia-humanoid-unitree-h1', category: 'humanoids', subcategory: 'bipedal-humanoids', url: B + 'Unitree-H1.htm' },
  { product_id: 'robotsasia-humanoid-ubtech-walker-s2', category: 'humanoids', subcategory: 'bipedal-humanoids', url: B + 'UBTECH-Walker-S2.htm' },
  { product_id: 'robotsasia-humanoid-fourier-gr2', category: 'humanoids', subcategory: 'bipedal-humanoids', url: B + 'Fourier-GR2.htm' },
  { product_id: 'robotsasia-humanoid-booster-t1', category: 'humanoids', subcategory: 'bipedal-humanoids', url: B + 'Booster-T1-Standard-Humanoid-Robot.htm' },
  { product_id: 'robotsasia-humanoid-agibot-x2', category: 'humanoids', subcategory: 'bipedal-humanoids', url: B + 'Agibot-X2-Full-Stack-Open-Source-Humanoid-Robot.htm' },
  { product_id: 'robotsasia-humanoid-robotera-l7', category: 'humanoids', subcategory: 'bipedal-humanoids', url: B + 'RobotEra-L7-Bipedal-Humanoid-Robot.htm' },
  { product_id: 'robotsasia-humanoid-unitree-g1-d-wheeled', category: 'humanoids', subcategory: 'wheeled-humanoids', url: B + 'Unitree-G1-D-Wheeled-Humanoid-Robot.htm' },
  { product_id: 'robotsasia-humanoid-elephant-mercury-x1', category: 'humanoids', subcategory: 'wheeled-humanoids', url: B + 'Elephant-Robotics-Mercury-Humanoid-Robot-X1-4011300003.htm' },
  { product_id: 'robotsasia-humanoid-elephant-mercury-a1', category: 'humanoids', subcategory: 'upper-body-humanoids', url: B + 'Elephant-Robotics-Mercury-Humanoid-Robot-A1-4011300001.htm' },
  // ---------- quadrupeds ----------
  { product_id: 'robotsasia-quadruped-unitree-go2-air', category: 'quadrupeds', subcategory: 'standard-quadrupeds', url: B + 'Unitree-Go2-Air-Quadruped-Robot-Dog.htm' },
  { product_id: 'robotsasia-quadruped-unitree-go2-pro', category: 'quadrupeds', subcategory: 'standard-quadrupeds', url: B + 'Unitree-Go2-PRO-Robot-Dog.htm' },
  { product_id: 'robotsasia-quadruped-unitree-b2', category: 'quadrupeds', subcategory: 'standard-quadrupeds', url: B + 'Unitree-B2.htm' },
  { product_id: 'robotsasia-quadruped-unitree-aliengo', category: 'quadrupeds', subcategory: 'standard-quadrupeds', url: B + 'Unitree-Aliengo.htm' },
  { product_id: 'robotsasia-quadruped-unitree-b1', category: 'quadrupeds', subcategory: 'standard-quadrupeds', url: B + 'Unitree-B1.htm' },
  { product_id: 'robotsasia-quadruped-deeprobotics-lite3', category: 'quadrupeds', subcategory: 'standard-quadrupeds', url: B + 'Deep-Robotics-Lite3-Basic-Quadruped-Robot-Dog.htm' },
  { product_id: 'robotsasia-quadruped-deeprobotics-x30-pro', category: 'quadrupeds', subcategory: 'standard-quadrupeds', url: B + 'Deep-Robotics-X30-Pro-Industrial-Quadruped-Robot-Dog.htm' },
  { product_id: 'robotsasia-quadruped-agibot-d1-pro', category: 'quadrupeds', subcategory: 'standard-quadrupeds', url: B + 'AgiBot-D1-Pro-Quadruped-Robot-Dog.htm' },
  { product_id: 'robotsasia-quadruped-magiclab-magicdog-w', category: 'quadrupeds', subcategory: 'wheeled-quadrupeds', url: B + 'MagicLab-MagicDog-W-Wheeled-Quadruped-Robot.htm' },
  { product_id: 'robotsasia-quadruped-unitree-go2-w', category: 'quadrupeds', subcategory: 'wheeled-quadrupeds', url: B + 'Unitree-Go2-W-Standard-Wheeled-Robot-Dog-Go2-W-U1.htm' },
  // ---------- amrs ----------
  { product_id: 'robotsasia-amr-seer-amb-150', category: 'amrs', subcategory: null, url: B + 'SEER-Robotics-AMB-150.htm' },
  { product_id: 'robotsasia-amr-seer-amb-300', category: 'amrs', subcategory: null, url: B + 'SEER-Robotics-AMB-300.htm' },
  { product_id: 'robotsasia-amr-seer-amb-300xs', category: 'amrs', subcategory: null, url: B + 'SEER-Robotics-AMB-300XS.htm' },
  { product_id: 'robotsasia-amr-seer-sfl-300l', category: 'amrs', subcategory: null, url: B + 'SEER-Robotics-SFL-300L.htm' },
  { product_id: 'robotsasia-amr-keenon-s100', category: 'amrs', subcategory: null, url: B + 'KEENON-S100.htm' },
  { product_id: 'robotsasia-amr-keenon-s300', category: 'amrs', subcategory: null, url: B + 'KEENON-S300.htm' },
  { product_id: 'robotsasia-amr-pudu-pudubot-2', category: 'amrs', subcategory: null, url: B + 'PUDU-Pudubot-2-Universal-Delivery-Robot.htm' },
  { product_id: 'robotsasia-amr-pudu-t300', category: 'amrs', subcategory: null, url: B + 'PUDU-T300-Standard-Industrial-Delivery-Robot.htm' },
  { product_id: 'robotsasia-amr-keenon-dinerbot-t9', category: 'amrs', subcategory: null, url: B + 'Keenon-DINERBOT-T9.htm' },
  { product_id: 'robotsasia-amr-pudu-bellabot', category: 'amrs', subcategory: null, url: B + 'PUDU-Bellabot-Premium-Delivery-Robot.htm' },
  // ---------- drones (9 valid) ----------
  { product_id: 'robotsasia-drone-xag-p150-max-starter', category: 'drones', subcategory: null, url: B + 'XAG-P150-Max-Starter-7KW-2B2C-Kit.htm' },
  { product_id: 'robotsasia-drone-xag-p150-standard-14kw', category: 'drones', subcategory: null, url: B + 'XAG-P150-Standard-14KW-4B4C.htm' },
  { product_id: 'robotsasia-drone-xag-p150-standard-7kw', category: 'drones', subcategory: null, url: B + 'XAG-P150-Standard-7KW-6B2C.htm' },
  { product_id: 'robotsasia-drone-xag-p150-ultimate', category: 'drones', subcategory: null, url: B + 'XAG-P150-Ultimate-14KW-6B4C-P150-Ultimate-14KW-6B4C-Kit.htm' },
  { product_id: 'robotsasia-drone-xag-p150-swarm', category: 'drones', subcategory: null, url: B + 'XAG-XAG-P150-Swarm-28KW-8B8C-P150-Swarm-28KW-8B8C-Kit.htm' },
  { product_id: 'robotsasia-drone-xag-p100-pro-standard', category: 'drones', subcategory: null, url: B + 'XAG-XAG-P100-Pro-Lite-P100-Pro-60L-Standard-6B2C-Kit.htm' },
  { product_id: 'robotsasia-drone-xag-p100-pro-premium-a', category: 'drones', subcategory: null, url: B + 'XAG-XAG-P100-Pro-Standard-P100-Pro-60L-Premium-8B3C-Kit.htm' },
  { product_id: 'robotsasia-drone-xag-p100-pro-premium-b', category: 'drones', subcategory: null, url: B + 'XAG-XAG-P100-Pro-Premium-P100-Pro-60L-Premium-8B3C-Kit.htm' },
  { product_id: 'robotsasia-drone-xag-p150-max-revospray', category: 'drones', subcategory: null, url: B + 'XAG-09-007-00158-P150-Max-Agricultural-Drone-With-Revospray-5.htm' },
]

const browser = await puppeteer.launch({ executablePath: CHROME, headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] })
const results = []
try {
  const page = await browser.newPage()
  await page.setUserAgent(UA)
  for (const [i, tgt] of TARGETS.entries()) {
    process.stderr.write(`[${i + 1}/${TARGETS.length}] ${tgt.product_id}\n`)
    try {
      await page.goto(tgt.url, { waitUntil: 'networkidle2', timeout: 60000 })
      await page.evaluate(async () => { for (let y = 0; y < document.body.scrollHeight; y += 700) { window.scrollTo(0, y); await new Promise((r) => setTimeout(r, 70)) } })
      await new Promise((r) => setTimeout(r, 1100))
      const d = await page.evaluate(() => {
        const clean = (s) => (s || '').replace(/\s+/g, ' ').trim()
        const h1 = clean(document.querySelector('h1')?.textContent)
        const priceRaw = clean(document.querySelector('.price, [data-price-type="finalPrice"] .price')?.textContent)
        const specs = []
        document.querySelectorAll('table tr').forEach((tr) => {
          const c = [...tr.querySelectorAll('th,td')].map((x) => (x.textContent || '').replace(/\s+/g, ' ').trim())
          if (c.length >= 2 && c[0] && c[1] && c[0] !== c[1]) specs.push({ label: c[0], value: c.slice(1).join(' ') })
        })
        const description = clean(document.querySelector('#description')?.textContent)
        const metaDesc = document.querySelector('meta[name="description"]')?.content || null
        const ogImage = document.querySelector('meta[property="og:image"]')?.content || null
        return { h1, priceRaw, specs, description, metaDesc, ogImage }
      })
      results.push({ ...tgt, ...d })
      process.stderr.write(`    ok "${d.h1}" specs=${d.specs.length} desc=${(d.description || '').length}c img=${d.ogImage ? 'Y' : 'n'}\n`)
    } catch (e) {
      results.push({ ...tgt, error: String(e).slice(0, 150) })
      process.stderr.write(`    FAIL ${e}\n`)
    }
    await new Promise((r) => setTimeout(r, 1800))
  }
  await writeFile(OUT, JSON.stringify({ count: results.length, products: results }, null, 2))
  process.stderr.write(`\nwrote ${OUT}\n`)
} finally { await browser.close() }
