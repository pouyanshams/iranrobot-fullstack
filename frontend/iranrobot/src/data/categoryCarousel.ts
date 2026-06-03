export interface CarouselCategory {
  id: string
  title: string
  titleFa: string
  /**
   * Square image (1200×1200 preferred, min 800×800).
   * Drop files at /public/assets/categories/<file>.webp
   * The card has a graceful fallback if the file is missing.
   */
  image: string
  /** Optional drill-down children (only Solutions uses this for now). */
  subcategories?: CarouselCategory[]
}

/** Mosaic categories shown in the bento section under the hero. */
export const categories: CarouselCategory[] = [
  {
    id: 'solutions',
    title: 'Solutions',
    titleFa: 'راهکارها',
    image: '/assets/categories/solutions.webp',
    subcategories: [
      { id: 'agricultural-robots', title: 'Agricultural Robots', titleFa: 'ربات‌های کشاورزی', image: '/assets/solutions/agricultural-robots.webp' },
      { id: 'commercial-robots',   title: 'Commercial Robots',   titleFa: 'ربات‌های تجاری',   image: '/assets/solutions/commercial-robots.webp' },
      { id: 'consumer-robots',     title: 'Consumer Robots',     titleFa: 'ربات‌های مصرفی',   image: '/assets/solutions/consumer-robots.webp' },
      { id: 'educational-robots',  title: 'Educational Robots',  titleFa: 'ربات‌های آموزشی',   image: '/assets/solutions/educational-robots.webp' },
      { id: 'government-robots',   title: 'Government Robots',   titleFa: 'ربات‌های دولتی',   image: '/assets/solutions/government-robots.webp' },
      { id: 'health-care',         title: 'Health Care',         titleFa: 'مراقبت سلامت',     image: '/assets/solutions/health-care.webp' },
      { id: 'industrial-robots',   title: 'Industrial Robots',   titleFa: 'ربات‌های صنعتی',   image: '/assets/solutions/industrial-robots.webp' },
      { id: 'sports-robots',       title: 'Sports Robots',       titleFa: 'ربات‌های ورزشی',   image: '/assets/solutions/sports-robots.webp' },
    ],
  },
  { id: 'humanoids',    title: 'Humanoids',    titleFa: 'انسان‌نماها',          image: '/assets/categories/humanoids.webp' },
  { id: 'quadrupeds',   title: 'Quadrupeds',   titleFa: 'چهارپاها',             image: '/assets/categories/quadrupeds.webp' },
  { id: 'amrs',         title: 'AMRs',         titleFa: 'ربات‌های متحرک خودران', image: '/assets/categories/amrs.webp' },
  { id: 'cobots',       title: 'Cobots',       titleFa: 'بازوهای همکار',         image: '/assets/categories/cobots.webp' },
  { id: 'drones',       title: 'Drones',       titleFa: 'پهپادها',              image: '/assets/categories/drones.webp' },
  { id: 'ugvs',         title: 'UGVs',         titleFa: 'خودروهای زمینی',        image: '/assets/categories/ugvs.webp' },
  { id: 'accessories',  title: 'Accessories',  titleFa: 'لوازم جانبی',           image: '/assets/categories/accessories.webp' },
  { id: 'new-arrivals', title: 'New Arrivals', titleFa: 'تازه‌واردها',           image: '/assets/categories/new-arrivals.webp' },
]
