/**
 * Typed wrappers around the Phase 2 Frappe catalog APIs +
 * mapping functions that adapt the API payload to the existing
 * frontend `Robot` shape so existing components keep working.
 *
 * The frontend `Robot` interface is wider than the Phase 1 schema -- fields
 * such as `useCases`, `tags`, `editorialBullets`, `bestFor`, `highlights` are
 * not yet served by the backend. The mappers populate them with empty arrays /
 * undefined so consumer components can keep their conditional render logic.
 */

import type { Robot, RobotCategory, RobotSpec } from '../types'
import { frappeFetch } from '../lib/frappeApi'

// ---------------------------------------------------------------------------
// API response types -- one-to-one with the Python catalog.py output shape.
// ---------------------------------------------------------------------------

export interface ApiProductImage {
  image: string
  is_hero: boolean
  alt_fa?: string | null
  alt_en?: string | null
}

export interface ApiProductSpec {
  label_fa: string
  value_fa: string
  label_en: string
  value_en: string
}

export interface ApiProductCard {
  product_id: string
  slug: string
  product_name_fa: string
  product_name_en: string
  tagline_fa?: string
  tagline_en?: string
  brand: string
  model?: string | null
  category: string
  subcategory?: string | null
  price_usd?: number | null
  price_label_fa?: string | null
  price_label_en?: string | null
  rent_per_day_usd?: number | null
  in_stock: boolean
  lead_time_days: number
  is_new_arrival: boolean
  is_featured: boolean
  rating?: number | null
  mode_buy: boolean
  mode_rent: boolean
  mode_procure: boolean
  display_order?: number | null
  hero_image?: string | null
}

export interface ApiProductDetail extends ApiProductCard {
  description_fa?: string
  description_en?: string
  origin_fa?: string
  origin_en?: string
  images: ApiProductImage[]
  specs: ApiProductSpec[]
  related_products: ApiProductCard[]
}

export interface ApiCategoryNode {
  name: string
  slug: string
  label_fa: string
  label_en: string
  parent_category: string | null
  display_order: number
  is_published: boolean
  icon?: string | null
  image?: string | null
  product_count: number
  children: ApiCategoryNode[]
}

export interface ApiPagination {
  total: number
  page: number
  limit: number
  offset: number
  returned: number
  has_next: boolean
}

export interface ApiProductList {
  products: ApiProductCard[]
  pagination: ApiPagination
  filters_applied: Record<string, unknown>
}

export interface ApiCategoriesPayload {
  categories: ApiCategoryNode[]
  count: number
}

export interface ApiHomepagePayload {
  featured: ApiProductDetail | null
  new_arrivals: ApiProductCard[]
  categories: ApiCategoryNode[]
  counts: { categories_top_level: number; new_arrivals: number }
}

// ---------------------------------------------------------------------------
// Plural API slug -> singular frontend RobotCategory.
// (Frappe uses plural slugs; the existing frontend Robot.category enum is singular.)
// ---------------------------------------------------------------------------

const API_TO_FRONTEND_CATEGORY: Record<string, RobotCategory> = {
  humanoids: 'humanoid',
  quadrupeds: 'quadruped',
  amrs: 'amr',
  cobots: 'cobots',
  drones: 'drone',
  ugvs: 'ugv',
  accessories: 'accessories',
  solutions: 'solutions',
}

const FRONTEND_TO_PLP_CATEGORY: Partial<Record<RobotCategory, string>> = {
  humanoid: 'humanoids',
  quadruped: 'quadrupeds',
  amr: 'amrs',
  cobots: 'cobots',
  drone: 'drones',
  ugv: 'ugvs',
  accessories: 'accessories',
  solutions: 'solutions',
}

function toFrontendCategory(apiSlug: string | null | undefined): RobotCategory {
  if (!apiSlug) return 'accessories'
  return API_TO_FRONTEND_CATEGORY[apiSlug] ?? (apiSlug as RobotCategory)
}

/**
 * Reverse of the mapping above -- used when the RobotDetail breadcrumb wants
 * to navigate back to the catalog with the right `category` URL param.
 */
export function categoryToPlpSlug(category: RobotCategory): string | null {
  return FRONTEND_TO_PLP_CATEGORY[category] ?? null
}

// ---------------------------------------------------------------------------
// Card / detail -> Robot mapper
// ---------------------------------------------------------------------------

function unzipSpecs(apiSpecs: ApiProductSpec[] | undefined): {
  specs: RobotSpec[]
  specsEn: RobotSpec[]
} {
  if (!apiSpecs?.length) return { specs: [], specsEn: [] }
  return {
    specs: apiSpecs.map((s) => ({ label: s.label_fa, value: s.value_fa })),
    specsEn: apiSpecs.map((s) => ({ label: s.label_en, value: s.value_en })),
  }
}

function pickGallery(images: ApiProductImage[] | undefined): string[] {
  if (!images?.length) return []
  return images.filter((i) => !i.is_hero).map((i) => i.image)
}

export function mapApiCardToRobot(api: ApiProductCard): Robot {
  // Modes -- always have at least one so RobotCard's badge row never collapses.
  const modes: Robot['modes'] = []
  if (api.mode_buy) modes.push('buy')
  if (api.mode_rent) modes.push('rent')
  if (api.mode_procure) modes.push('procure')
  if (modes.length === 0) modes.push('procure')

  // Defensive fallbacks: every field RobotCard / RobotIllustration touches
  // gets a safe value even if the backend payload is partial. This prevents
  // a render-time crash from propagating into a blank screen.
  const product_id = api.product_id || api.slug || 'unknown'
  const slug = api.slug || product_id
  const nameEn = api.product_name_en || api.product_name_fa || product_id
  const nameFa = api.product_name_fa || api.product_name_en || product_id
  const brand = api.brand || '—'
  const hasPrice = typeof api.price_usd === 'number' && api.price_usd > 0

  return {
    id: product_id,
    slug,
    name: nameFa,
    nameEn,
    brand,
    model: api.model ?? undefined,
    origin: '',
    originEn: '',
    category: toFrontendCategory(api.category),
    subcategory: api.subcategory ?? undefined,
    isNewArrival: Boolean(api.is_new_arrival),
    tagline: api.tagline_fa ?? '',
    taglineEn: api.tagline_en ?? '',
    description: '',
    descriptionEn: '',
    priceUsd: hasPrice ? (api.price_usd as number) : undefined,
    priceLabel: api.price_label_fa ?? (hasPrice ? undefined : 'استعلام قیمت'),
    priceLabelEn: api.price_label_en ?? (hasPrice ? undefined : 'Request quote'),
    rentPerDayUsd: api.rent_per_day_usd ?? undefined,
    leadTimeDays: api.lead_time_days ?? 30,
    inStock: Boolean(api.in_stock),
    modes,
    specs: [],
    specsEn: [],
    highlights: [],
    highlightsEn: [],
    tags: [],
    useCases: [],
    image: api.hero_image ?? undefined,
    gallery: [],
    rating: typeof api.rating === 'number' ? api.rating : undefined,
  }
}

export function mapApiDetailToRobot(api: ApiProductDetail): Robot {
  const base = mapApiCardToRobot(api)
  const { specs, specsEn } = unzipSpecs(api.specs)
  return {
    ...base,
    origin: api.origin_fa ?? '',
    originEn: api.origin_en ?? '',
    description: api.description_fa ?? '',
    descriptionEn: api.description_en ?? '',
    specs,
    specsEn,
    gallery: pickGallery(api.images),
  }
}

// ---------------------------------------------------------------------------
// API method wrappers
// ---------------------------------------------------------------------------

const BASE = 'iranrobot_backend.api.catalog'

export async function fetchCategories(signal?: AbortSignal): Promise<ApiCategoriesPayload> {
  return frappeFetch<ApiCategoriesPayload>(`${BASE}.get_categories`, undefined, signal)
}

export interface GetProductsParams {
  category?: string
  subcategory?: string
  /** Filter by a single Robot Use Case slug (e.g. 'inspection'). */
  use_case?: string
  /** Return only products that have at least one use case (parent solutions route). */
  has_use_case?: boolean
  is_new_arrival?: boolean
  is_featured?: boolean
  search?: string
  limit?: number
  page?: number
  offset?: number
  sort?: 'display_order' | 'newest' | 'oldest' | 'name_en' | 'name_fa' | 'price_asc' | 'price_desc'
}

export async function fetchProducts(
  params: GetProductsParams = {},
  signal?: AbortSignal,
): Promise<ApiProductList> {
  return frappeFetch<ApiProductList>(
    `${BASE}.get_products`,
    {
      category: params.category,
      subcategory: params.subcategory,
      use_case: params.use_case,
      has_use_case: params.has_use_case,
      is_new_arrival: params.is_new_arrival,
      is_featured: params.is_featured,
      search: params.search,
      limit: params.limit,
      page: params.page,
      offset: params.offset,
      sort: params.sort,
    },
    signal,
  )
}

export async function fetchProductDetail(
  slug: string,
  signal?: AbortSignal,
): Promise<ApiProductDetail> {
  return frappeFetch<{ product: ApiProductDetail }>(
    `${BASE}.get_product_detail`,
    { slug },
    signal,
  ).then((d) => d.product)
}

export async function fetchFeaturedProduct(
  signal?: AbortSignal,
): Promise<ApiProductDetail> {
  return frappeFetch<{ product: ApiProductDetail }>(
    `${BASE}.get_featured_product`,
    undefined,
    signal,
  ).then((d) => d.product)
}

export async function fetchHomepageCatalog(
  signal?: AbortSignal,
): Promise<ApiHomepagePayload> {
  return frappeFetch<ApiHomepagePayload>(
    `${BASE}.get_homepage_catalog`,
    undefined,
    signal,
  )
}
