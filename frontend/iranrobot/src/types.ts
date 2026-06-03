export type Lang = 'fa' | 'en'

export type RobotCategory =
  | 'industrial'
  | 'service'
  | 'humanoid'
  | 'quadruped'
  | 'amr'
  | 'cobots'
  | 'ugv'
  | 'solutions'
  | 'accessories'
  | 'mobile'
  | 'educational'
  | 'drone'

export type AvailabilityMode = 'buy' | 'rent' | 'procure'

export interface RobotSpec {
  label: string
  value: string
}

export interface Robot {
  id: string
  slug: string
  name: string
  nameEn: string
  brand: string
  /** Optional model name (e.g. "Mornine"). */
  model?: string
  origin: string
  originEn: string
  category: RobotCategory
  /**
   * Canonical sub-bucket id matching a Shop dropdown sub entry
   * (e.g. 'bipedal-humanoids', 'wheeled-humanoids', 'upper-body-humanoids').
   * Used by PLP_CATEGORIES to filter precisely.
   */
  subcategory?: string
  /** Flag for the New Arrivals PLP entry. Independent of tags. */
  isNewArrival?: boolean
  tagline: string
  taglineEn: string
  description: string
  descriptionEn: string
  /** Omit for quote-only products; UI falls back to priceLabel or "Request quote". */
  priceUsd?: number
  /** Shown when priceUsd is missing (e.g. "Request quote"). */
  priceLabel?: string
  priceLabelEn?: string
  rentPerDayUsd?: number
  leadTimeDays: number
  inStock: boolean
  modes: AvailabilityMode[]
  specs: RobotSpec[]
  specsEn: RobotSpec[]
  highlights: string[]
  highlightsEn: string[]
  /** PLP category ids this robot belongs to (see data/categories). */
  tags: string[]
  /**
   * Orthogonal use-case taxonomy. Independent of `category`/`subcategory`.
   * Powers the Solutions PLP subs (education, warehouse, inspection, security, healthcare, custom).
   * A humanoid that ships to schools can have `category: 'humanoid'` + `useCases: ['education']`.
   */
  useCases?: string[]
  /** Tailwind gradient classes for the illustration accent. Optional. */
  accent?: string
  /** Optional real product photo. Renders instead of the vector illustration. */
  image?: string
  /** Optional additional images for the gallery. */
  gallery?: string[]
  /** Optional star rating (omit for products with no reviews yet). */
  rating?: number
  /**
   * Editorial bullets shown on the featured-variant card on the homepage Editor's Pick.
   * Populate ONLY when curating a product for the featured slot. Optional everywhere else.
   */
  editorialBullets?: string[]
  editorialBulletsEn?: string[]
  /** Short use-case chips shown alongside editorial bullets on the featured card. */
  bestFor?: string[]
  bestForEn?: string[]
}

export interface CartLine {
  id: string
  robotId: string
  mode: AvailabilityMode
  qty: number
  days?: number
  notes?: string
  addedAt: number
}

export interface WalletTx {
  id: string
  amountUsd: number
  type: 'topup' | 'spend' | 'refund'
  label: string
  at: number
}

export type RouteName =
  | 'home'
  | 'catalog'
  | 'procurement'
  | 'rent'
  | 'finder'
  | 'wallet'
  | 'support'
  | 'robot'
  | 'account'

// ---------------------------------------------------------------------------
// Phase 4 authentication types
// ---------------------------------------------------------------------------

/** Customer-safe view of the currently authenticated user, returned by whoami. */
export interface CurrentUser {
  email: string
  full_name: string
  first_name: string
  last_name: string
  preferred_language: 'fa' | 'en'
  phone: string
  marketing_opt_in: boolean
  /** Linked ERPNext Contact id (lazy-created on first whoami). */
  contact: string | null
  /** Linked ERPNext Customer id (lazy-created on first whoami). */
  customer: string | null
  /** Display name of the linked Customer (may differ from full_name). */
  customer_name: string | null
  /** True iff the user has the System Manager role (staff). Customer-side UI
   * usually wants to hide itself for staff sessions. */
  is_system_manager: boolean
}

/** Payload returned by login / logout / whoami. */
export interface WhoAmIPayload {
  is_authenticated: boolean
  user: CurrentUser | null
  csrf_token: string
}

/** Fields a logged-in customer can patch via update_profile. */
export interface ProfilePatch {
  first_name?: string
  last_name?: string
  full_name?: string
  phone?: string
  preferred_language?: 'fa' | 'en'
  marketing_opt_in?: boolean
}

/** Phase 4.5 -- signup input. */
export interface SignupInput {
  email: string
  password: string
  confirm_password: string
  first_name: string
  last_name?: string
  phone?: string
  preferred_language?: 'fa' | 'en'
}
