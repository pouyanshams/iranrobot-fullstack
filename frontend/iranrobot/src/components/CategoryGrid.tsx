import { PLP_CATEGORIES } from '../data/categories'
import { ROBOTS } from '../data/robots'
import { CategoryCard } from './CategoryCard'

interface CategoryGridProps {
  /** Currently selected category id, or null when none is active. */
  selected: string | null
  /** Toggles the category: selecting the active one again clears it. */
  onSelect: (id: string | null) => void
}

export function CategoryGrid({ selected, onSelect }: CategoryGridProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 sm:gap-5">
      {PLP_CATEGORIES.filter((c) => !c.parentId).map((c) => {
        const count = ROBOTS.filter(c.match).length
        const active = selected === c.id
        return (
          <CategoryCard
            key={c.id}
            category={c}
            active={active}
            count={count}
            onClick={() => onSelect(active ? null : c.id)}
          />
        )
      })}
    </div>
  )
}
