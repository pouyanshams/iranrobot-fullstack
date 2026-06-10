import { useMemo } from 'react'
import { ChevronRight } from 'lucide-react'
import { Section } from '../components/Section'
import { RobotCard } from '../components/RobotCard'
import { ApiError, ApiLoading, ApiEmpty } from '../components/ApiState'
import { useApp } from '../context/AppContext'
import { useI18n } from '../i18n'
import { useApi } from '../lib/useApi'
import {
  fetchCategories,
  fetchProducts,
  mapApiCardToRobot,
  type ApiCategoryNode,
} from '../api/catalog'

interface TreeNode {
  /** Matches a Robot Category slug in the backend (or 'new' for the virtual entry). */
  plpId: string
  children?: TreeNode[]
}

/**
 * Shop sidebar structure. Order, hierarchy, and which entries appear are defined
 * here. Labels come from the Frappe categories API; the special `new` entry is
 * a virtual filter (`category=new` -> `is_new_arrival=1`) handled server-side.
 */
const SHOP_TREE: TreeNode[] = [
  {
    plpId: 'solutions',
    children: [
      { plpId: 'education' },
      { plpId: 'warehouse' },
      { plpId: 'inspection' },
      { plpId: 'security' },
      { plpId: 'healthcare' },
      { plpId: 'custom' },
    ],
  },
  {
    plpId: 'humanoids',
    children: [
      { plpId: 'bipedal-humanoids' },
      { plpId: 'wheeled-humanoids' },
      { plpId: 'upper-body-humanoids' },
    ],
  },
  {
    plpId: 'quadrupeds',
    children: [{ plpId: 'standard-quadrupeds' }, { plpId: 'wheeled-quadrupeds' }],
  },
  { plpId: 'amrs' },
  { plpId: 'cobots' },
  { plpId: 'drones' },
  { plpId: 'ugvs' },
  {
    plpId: 'accessories',
    children: [
      { plpId: 'robot-arms' },
      { plpId: 'robot-batteries' },
      { plpId: 'robot-chargers' },
      { plpId: 'robot-hands' },
      { plpId: 'sensors' },
    ],
  },
  { plpId: 'new' },
]

const FLAT_IDS = SHOP_TREE.flatMap((n) => [n.plpId, ...(n.children?.map((c) => c.plpId) ?? [])])
const DEFAULT_PLP_ID = 'humanoids'

/**
 * Static lookup of which plpIds are subcategories vs top-level vs virtual.
 * Derived from SHOP_TREE so we don't depend on the categories API arriving
 * before we know how to query the products API. Previously this was inferred
 * from the categories API response, which caused a brief wrong query (and
 * empty flash of results) on the very first render of a subcategory URL.
 */
const SUBCATEGORY_IDS: ReadonlySet<string> = new Set(
  SHOP_TREE.flatMap((n) => n.children?.map((c) => c.plpId) ?? []),
)

/**
 * Use-case slugs (child Solutions entries). Each one corresponds to a row in
 * the backend Robot Use Case table; the catalog API filters via the
 * `Robot Product Use Case` child table.
 *
 * The parent `solutions` route is handled separately -- it asks the backend
 * for any product that has at least one use case (`has_use_case=1`).
 */
const USE_CASE_IDS: ReadonlySet<string> = new Set(
  SHOP_TREE.find((n) => n.plpId === 'solutions')?.children?.map((c) => c.plpId) ?? [],
)
const PARENT_SOLUTIONS_ID = 'solutions'

/** Hardcoded label for the virtual `new` entry (not a real Robot Category row). */
const VIRTUAL_NEW_LABELS = { label_fa: 'تازه‌واردها', label_en: 'New Arrivals' }

interface LabelEntry {
  label_fa: string
  label_en: string
}

function buildLabelMap(
  apiCategories: ApiCategoryNode[] | undefined,
): Map<string, LabelEntry> {
  const map = new Map<string, LabelEntry>()
  if (apiCategories) {
    for (const top of apiCategories) {
      map.set(top.name, { label_fa: top.label_fa, label_en: top.label_en })
      for (const sub of top.children) {
        map.set(sub.name, { label_fa: sub.label_fa, label_en: sub.label_en })
      }
    }
  }
  // The virtual `new` entry never appears in the API category list -- supply it
  // here so the sidebar can render its label and the PLP can resolve the filter.
  if (!map.has('new')) map.set('new', VIRTUAL_NEW_LABELS)
  return map
}

export function CatalogView() {
  const { route, go } = useApp()
  const { t, n } = useI18n()

  // ----- Categories (sidebar labels + filter routing) -----
  const cats = useApi((signal) => fetchCategories(signal), [])
  const labelMap = useMemo(
    () => buildLabelMap(cats.data?.categories),
    [cats.data],
  )

  // ----- Active filter (URL is the source of truth) -----
  const urlSelected =
    route.name === 'catalog' && route.param && FLAT_IDS.includes(route.param)
      ? route.param
      : null
  const activeId = urlSelected ?? DEFAULT_PLP_ID
  // Pick the right axis from SHOP_TREE (synchronous) rather than from the
  // categories API response. This eliminates the brief render where a
  // subcategory URL was incorrectly queried as a top-level category before
  // categories loaded, which used to flash an empty grid then re-render.
  //
  // The Solutions axis is orthogonal to category/subcategory:
  //   `#/catalog/solutions`  -> has_use_case=1   (all products with any use case)
  //   `#/catalog/inspection` -> use_case=inspection
  //   `#/catalog/security`   -> use_case=security    ... etc.
  const productsQuery = useMemo<{
    category?: string
    subcategory?: string
    use_case?: string
    has_use_case?: boolean
  }>(() => {
    if (activeId === 'new') return { category: 'new' }
    if (activeId === PARENT_SOLUTIONS_ID) return { has_use_case: true }
    if (USE_CASE_IDS.has(activeId)) return { use_case: activeId }
    return SUBCATEGORY_IDS.has(activeId)
      ? { subcategory: activeId }
      : { category: activeId }
  }, [activeId])

  // ----- Products for the active filter -----
  const products = useApi(
    (signal) =>
      fetchProducts({ ...productsQuery, limit: 100, sort: 'display_order' }, signal),
    [
      productsQuery.category,
      productsQuery.subcategory,
      productsQuery.use_case,
      productsQuery.has_use_case,
    ],
  )

  function handleClick(id: string) {
    go('catalog', id)
  }

  function isAncestorOfActive(node: TreeNode) {
    return node.children?.some((c) => c.plpId === activeId) ?? false
  }

  const labelFor = (id: string) => {
    const e = labelMap.get(id)
    return { label: e?.label_fa ?? id, labelEn: e?.label_en ?? id }
  }

  const activeLabel = labelFor(activeId)
  const productCount = products.data?.pagination.total ?? 0

  return (
    <Section spacing="md">
      {/* ===== Mobile: horizontal top-level cat strip ===== */}
      <div className="-mx-4 mb-6 overflow-x-auto px-4 lg:hidden">
        <div className="flex min-w-max gap-2">
          {SHOP_TREE.map((node) => {
            const { label, labelEn } = labelFor(node.plpId)
            const isActive = activeId === node.plpId || isAncestorOfActive(node)
            return (
              <button
                key={node.plpId}
                type="button"
                onClick={() => handleClick(node.plpId)}
                className={[
                  'h-10 whitespace-nowrap rounded-lg px-4 text-sm font-semibold transition-colors',
                  isActive
                    ? 'bg-brand-50 text-brand-700'
                    : 'border border-line bg-white text-ink-700 hover:bg-brand-50 hover:text-brand-700',
                ].join(' ')}
              >
                {t(label, labelEn)}
              </button>
            )
          })}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-[260px_1fr]">
        {/* ===== Left: desktop sticky category nav ===== */}
        <aside className="hidden lg:sticky lg:top-28 lg:block lg:self-start">
          <nav className="space-y-5" aria-label={t('دسته‌بندی فروشگاه', 'Shop categories')}>
            {SHOP_TREE.map((node) => {
              const { label, labelEn } = labelFor(node.plpId)
              const isActive = activeId === node.plpId
              const hasChildren = !!node.children?.length

              return (
                <div key={node.plpId}>
                  <button
                    type="button"
                    onClick={() => handleClick(node.plpId)}
                    className={[
                      'flex w-full items-center justify-between rounded-xl px-3 py-2.5',
                      'text-sm font-semibold transition-colors',
                      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/40',
                      isActive
                        ? 'bg-brand-50 text-brand-700'
                        : 'text-ink-800 hover:bg-ink-50 hover:text-brand-700',
                    ].join(' ')}
                  >
                    <span className="text-start">{t(label, labelEn)}</span>
                    {hasChildren ? (
                      <ChevronRight
                        size={14}
                        className="shrink-0 opacity-60 rtl:-scale-x-100"
                      />
                    ) : null}
                  </button>

                  {hasChildren ? (
                    <div className="mt-1 space-y-0.5">
                      {node.children!.map((child) => {
                        const childLabel = labelFor(child.plpId)
                        const isChildActive = activeId === child.plpId
                        return (
                          <button
                            key={child.plpId}
                            type="button"
                            onClick={() => handleClick(child.plpId)}
                            className={[
                              'ms-3 flex w-[calc(100%-0.75rem)] items-center justify-between',
                              'rounded-lg px-3 py-2 text-start text-sm transition-colors',
                              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/40',
                              isChildActive
                                ? 'bg-brand-50 font-semibold text-brand-700'
                                : 'text-ink-500 hover:bg-brand-50/60 hover:text-brand-700',
                            ].join(' ')}
                          >
                            <span>{t(childLabel.label, childLabel.labelEn)}</span>
                          </button>
                        )
                      })}
                    </div>
                  ) : null}
                </div>
              )
            })}
          </nav>
        </aside>

        {/* ===== Right: products panel ===== */}
        <div className="lg:min-h-[600px]">
          <div className="mb-6 flex items-end justify-between gap-4">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.2em] text-brand-600">
                {t('فروشگاه', 'Shop')}
              </p>
              <h1 className="mt-2 text-3xl font-bold text-fg leading-tight sm:text-4xl">
                {t(activeLabel.label, activeLabel.labelEn)}
              </h1>
              <p className="mt-2 text-sm text-muted">
                <span className="num-fa font-bold text-fg">{n(productCount)}</span>{' '}
                {t('محصول', productCount === 1 ? 'product' : 'products')}
              </p>
            </div>
          </div>

          {products.loading ? (
            <ApiLoading rows={6} />
          ) : products.error ? (
            <ApiError error={products.error} onRetry={products.refetch} />
          ) : (products.data?.products.length ?? 0) > 0 ? (
            <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-3">
              {products.data!.products.map(mapApiCardToRobot).map((r) => (
                <RobotCard key={r.id} robot={r} />
              ))}
            </div>
          ) : (
            <ApiEmpty />
          )}
        </div>
      </div>
    </Section>
  )
}
