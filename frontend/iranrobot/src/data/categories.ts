import type { Robot } from '../types'

export interface PlpCategory {
  id: string
  label: string
  labelEn: string
  image: string
  /** Emoji fallback shown if the image is missing. */
  icon: string
  /** Predicate to filter robots for this category. */
  match: (r: Robot) => boolean
  /**
   * Top-level parent id when this entry is a subcategory.
   * Used by Shop directory (top-level only) and PLP breadcrumb.
   */
  parentId?: string
}

const byTag = (tag: string) => (r: Robot) => r.tags.includes(tag)
const bySub = (sub: string) => (r: Robot) => r.subcategory === sub
const byUseCase = (uc: string) => (r: Robot) => r.useCases?.includes(uc) ?? false

export const PLP_CATEGORIES: PlpCategory[] = [
  // ===== Top-level categories (no parentId — shown in Shop directory) =====
  { id: 'solutions', label: 'راهکارها', labelEn: 'Solutions', image: '/assets/categories/solutions.webp', icon: '🧩', match: (r) => (r.useCases?.length ?? 0) > 0 },
  { id: 'humanoids', label: 'انسان‌نماها', labelEn: 'Humanoids', image: '/assets/categories/humanoids.webp', icon: '🤖', match: (r) => r.category === 'humanoid' },
  { id: 'quadrupeds', label: 'چهارپاها', labelEn: 'Quadrupeds', image: '/assets/categories/quadrupeds.webp', icon: '🐕', match: (r) => r.category === 'quadruped' },
  { id: 'amrs', label: 'ربات‌های متحرک خودران', labelEn: 'AMRs', image: '/assets/categories/amrs.webp', icon: '🛻', match: (r) => r.category === 'amr' },
  { id: 'cobots', label: 'بازوهای همکار', labelEn: 'Cobots', image: '/assets/categories/cobots.webp', icon: '🦾', match: (r) => r.category === 'cobots' },
  { id: 'drones', label: 'پهپادها', labelEn: 'Drones', image: '/assets/categories/drones.webp', icon: '🛸', match: (r) => r.category === 'drone' },
  { id: 'ugvs', label: 'خودروهای زمینی', labelEn: 'UGVs', image: '/assets/categories/ugvs.webp', icon: '🚙', match: (r) => r.category === 'ugv' },
  { id: 'accessories', label: 'لوازم جانبی', labelEn: 'Accessories', image: '/assets/categories/accessories.webp', icon: '🔌', match: (r) => r.category === 'accessories' },
  { id: 'regional', label: 'منطقه‌ای', labelEn: 'Regional', image: '/assets/categories/regional.webp', icon: '🌍', match: byTag('regional') },
  { id: 'new', label: 'تازه‌واردها', labelEn: 'New Arrivals', image: '/assets/categories/new-arrivals.webp', icon: '✨', match: (r) => r.isNewArrival === true },

  // ===== Subs (filter-routing only, hidden from directory) =====
  { id: 'bipedal-humanoids', label: 'انسان‌نمای دو پا', labelEn: 'Bipedal Humanoids', image: '/assets/categories/humanoids.webp', icon: '🤖', parentId: 'humanoids', match: bySub('bipedal-humanoids') },
  { id: 'wheeled-humanoids', label: 'انسان‌نمای چرخ‌دار', labelEn: 'Wheeled Humanoids', image: '/assets/categories/humanoids.webp', icon: '🤖', parentId: 'humanoids', match: bySub('wheeled-humanoids') },
  { id: 'upper-body-humanoids', label: 'انسان‌نمای بالاتنه', labelEn: 'Upper Body Humanoids', image: '/assets/categories/humanoids.webp', icon: '🤖', parentId: 'humanoids', match: bySub('upper-body-humanoids') },
  { id: 'standard-quadrupeds', label: 'چهارپای استاندارد', labelEn: 'Standard Quadrupeds', image: '/assets/categories/quadrupeds.webp', icon: '🐕', parentId: 'quadrupeds', match: bySub('standard-quadrupeds') },
  { id: 'wheeled-quadrupeds', label: 'چهارپای چرخ‌دار', labelEn: 'Wheeled Quadrupeds', image: '/assets/categories/quadrupeds.webp', icon: '🐕', parentId: 'quadrupeds', match: bySub('wheeled-quadrupeds') },
  { id: 'robot-arms', label: 'بازوهای ربات', labelEn: 'Robot Arms', image: '/assets/categories/accessories.webp', icon: '🦾', parentId: 'accessories', match: bySub('robot-arms') },
  { id: 'robot-batteries', label: 'باتری ربات', labelEn: 'Robot Batteries', image: '/assets/categories/accessories.webp', icon: '🔋', parentId: 'accessories', match: bySub('robot-batteries') },
  { id: 'robot-chargers', label: 'شارژر ربات', labelEn: 'Robot Chargers', image: '/assets/categories/accessories.webp', icon: '⚡', parentId: 'accessories', match: bySub('robot-chargers') },
  { id: 'robot-hands', label: 'دست‌های ربات', labelEn: 'Robot Hands', image: '/assets/categories/accessories.webp', icon: '🖐️', parentId: 'accessories', match: bySub('robot-hands') },
  { id: 'sensors', label: 'سنسورها', labelEn: 'Sensors', image: '/assets/categories/accessories.webp', icon: '📡', parentId: 'accessories', match: bySub('sensors') },
  { id: 'education', label: 'آموزش و پژوهش', labelEn: 'Education & Research', image: '/assets/categories/solutions.webp', icon: '🎓', parentId: 'solutions', match: byUseCase('education') },
  { id: 'warehouse', label: 'انبارداری و لجستیک', labelEn: 'Warehouse & Logistics', image: '/assets/categories/solutions.webp', icon: '📦', parentId: 'solutions', match: byUseCase('warehouse') },
  { id: 'inspection', label: 'بازرسی و پایش', labelEn: 'Inspection & Monitoring', image: '/assets/categories/solutions.webp', icon: '🔍', parentId: 'solutions', match: byUseCase('inspection') },
  { id: 'security', label: 'امنیت و گشت‌زنی', labelEn: 'Security & Patrol', image: '/assets/categories/solutions.webp', icon: '🛡️', parentId: 'solutions', match: byUseCase('security') },
  { id: 'healthcare', label: 'سلامت و خدمات', labelEn: 'Healthcare & Services', image: '/assets/categories/solutions.webp', icon: '🏥', parentId: 'solutions', match: byUseCase('healthcare') },
  { id: 'custom', label: 'راهکار سفارشی', labelEn: 'Custom Solution', image: '/assets/categories/solutions.webp', icon: '🧩', parentId: 'solutions', match: byUseCase('custom') },
]
