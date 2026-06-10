import type { Robot } from '../types'

/**
 * Vector "portrait" stand-in for each robot, rendered as a clean product
 * cutout on a pale gradient stage (commercial / ecommerce look).
 *
 * `flat` mode strips the gradient stage, decorative blobs, grid overlay, and
 * corner brand/name text so the artwork blends into a plain white card surface
 * (used by the compact catalog grid card to avoid a box-inside-box look).
 */
export function RobotIllustration({
  robot,
  className = '',
  flat = false,
}: {
  robot: Robot
  className?: string
  flat?: boolean
}) {
  const Body =
    robot.category === 'humanoid'
      ? HumanoidBody
      : robot.category === 'drone'
        ? DroneBody
        : robot.category === 'mobile'
          ? robot.id === 'r-quad'
            ? QuadBody
            : MobileBody
          : robot.category === 'service'
            ? ServiceBody
            : robot.category === 'educational'
              ? EducationalBody
              : ArmBody

  if (robot.image) {
    return (
      <div
        className={['relative w-full h-full overflow-hidden', flat ? 'bg-white' : '', className].join(' ')}
        style={
          flat
            ? undefined
            : { background: 'radial-gradient(120% 95% at 50% 12%, #ffffff 0%, #f6f8fb 70%, #e9eef5 100%)' }
        }
      >
        <img
          src={robot.image}
          alt={robot.nameEn || robot.name}
          loading="lazy"
          className={['absolute inset-0 h-full w-full object-contain', flat ? 'p-2' : 'p-4'].join(' ')}
        />
      </div>
    )
  }

  if (flat) {
    return (
      <div className={['relative w-full h-full overflow-hidden bg-white', className].join(' ')}>
        <div className="relative h-full w-full grid place-items-center p-3">
          <Body />
        </div>
      </div>
    )
  }

  return (
    <div
      className={['relative w-full h-full overflow-hidden', className].join(' ')}
      style={{ background: 'radial-gradient(120% 95% at 50% 12%, #ffffff 0%, #eef2f7 70%, #e2e8f0 100%)' }}
    >
      <div className="absolute inset-0 grid-faint opacity-40" />
      {/* subtle cyan stage glow at the base */}
      <div
        className="absolute -bottom-10 left-1/2 -translate-x-1/2 w-2/3 h-24 rounded-full blur-2xl"
        style={{ background: 'radial-gradient(ellipse, rgba(56,189,248,0.20), transparent 70%)' }}
      />
      {/* faint red top accent */}
      <div
        className="absolute -top-8 right-2 w-1/2 h-20 rounded-full blur-2xl"
        style={{ background: 'radial-gradient(ellipse, rgba(127, 24, 16,0.10), transparent 70%)' }}
      />
      <div className="relative h-full w-full grid place-items-center p-8">
        <Body />
      </div>
      <div className="absolute top-3 left-3 right-3 flex items-center justify-between text-[10px] font-mono text-ink-400">
        <span>{robot.nameEn}</span>
        <span>{robot.brand}</span>
      </div>
    </div>
  )
}

const STROKE = '#334155'
const FILL = '#ffffff'
const PANEL = '#f1f5f9'
const BRAND = '#7f1810'
const CYAN = '#38bdf8'

function ArmBody() {
  return (
    <svg viewBox="0 0 220 200" className="w-full h-full max-w-[260px]" fill="none">
      <rect x="60" y="160" width="100" height="20" rx="4" fill={PANEL} stroke={STROKE} strokeWidth="2.2" />
      <rect x="95" y="120" width="30" height="44" rx="4" fill={FILL} stroke={STROKE} strokeWidth="2.2" />
      <rect x="80" y="70" width="60" height="58" rx="10" fill={FILL} stroke={STROKE} strokeWidth="2.2" />
      <rect x="60" y="40" width="100" height="38" rx="10" fill={FILL} stroke={CYAN} strokeWidth="2.5" />
      <circle cx="80" cy="59" r="4" fill={CYAN} />
      <circle cx="140" cy="59" r="4" fill={CYAN} />
      <path d="M150 78 L188 30" stroke={STROKE} strokeWidth="2.2" strokeLinecap="round" />
      <circle cx="190" cy="28" r="6" fill={BRAND} stroke={STROKE} strokeWidth="2" />
    </svg>
  )
}

function HumanoidBody() {
  return (
    <svg viewBox="0 0 220 220" className="w-full h-full max-w-[240px]" fill="none">
      <rect x="80" y="22" width="60" height="60" rx="14" fill={FILL} stroke={CYAN} strokeWidth="2.5" />
      <circle cx="100" cy="48" r="4" fill={CYAN} />
      <circle cx="120" cy="48" r="4" fill={CYAN} />
      <rect x="96" y="62" width="28" height="4" rx="2" fill={STROKE} />
      <rect x="72" y="82" width="76" height="62" rx="12" fill={FILL} stroke={STROKE} strokeWidth="2.2" />
      <rect x="86" y="96" width="48" height="30" rx="6" fill="none" stroke={BRAND} strokeWidth="2" opacity="0.55" />
      <rect x="54" y="86" width="14" height="54" rx="6" fill={PANEL} stroke={STROKE} strokeWidth="2.2" />
      <rect x="152" y="86" width="14" height="54" rx="6" fill={PANEL} stroke={STROKE} strokeWidth="2.2" />
      <rect x="84" y="148" width="22" height="50" rx="6" fill={PANEL} stroke={STROKE} strokeWidth="2.2" />
      <rect x="114" y="148" width="22" height="50" rx="6" fill={PANEL} stroke={STROKE} strokeWidth="2.2" />
    </svg>
  )
}

function DroneBody() {
  return (
    <svg viewBox="0 0 220 180" className="w-full h-full max-w-[280px]" fill="none">
      <circle cx="40" cy="50" r="22" fill={FILL} stroke={STROKE} strokeWidth="2.2" />
      <circle cx="180" cy="50" r="22" fill={FILL} stroke={STROKE} strokeWidth="2.2" />
      <circle cx="40" cy="140" r="22" fill={FILL} stroke={STROKE} strokeWidth="2.2" />
      <circle cx="180" cy="140" r="22" fill={FILL} stroke={STROKE} strokeWidth="2.2" />
      <path d="M40 50 L180 140 M180 50 L40 140" stroke={STROKE} strokeWidth="2.2" opacity="0.5" />
      <rect x="80" y="70" width="60" height="50" rx="14" fill={FILL} stroke={CYAN} strokeWidth="2.5" />
      <circle cx="110" cy="95" r="10" fill="none" stroke={BRAND} strokeWidth="2.5" />
    </svg>
  )
}

function MobileBody() {
  return (
    <svg viewBox="0 0 220 160" className="w-full h-full max-w-[280px]" fill="none">
      <rect x="25" y="40" width="170" height="70" rx="14" fill={FILL} stroke={STROKE} strokeWidth="2.2" />
      <rect x="40" y="20" width="140" height="24" rx="8" fill={PANEL} stroke={CYAN} strokeWidth="2.5" />
      <circle cx="60" cy="120" r="18" fill={PANEL} stroke={STROKE} strokeWidth="2.2" />
      <circle cx="160" cy="120" r="18" fill={PANEL} stroke={STROKE} strokeWidth="2.2" />
      <circle cx="60" cy="120" r="6" fill={CYAN} />
      <circle cx="160" cy="120" r="6" fill={CYAN} />
      <circle cx="160" cy="75" r="6" fill={BRAND} />
      <rect x="55" y="60" width="60" height="10" rx="3" fill={STROKE} opacity="0.16" />
      <rect x="55" y="78" width="40" height="6" rx="2" fill={STROKE} opacity="0.16" />
    </svg>
  )
}

function QuadBody() {
  return (
    <svg viewBox="0 0 240 180" className="w-full h-full max-w-[280px]" fill="none">
      <rect x="50" y="70" width="140" height="40" rx="12" fill={FILL} stroke={CYAN} strokeWidth="2.5" />
      <rect x="58" y="40" width="40" height="30" rx="8" fill={PANEL} stroke={STROKE} strokeWidth="2.2" />
      <circle cx="78" cy="55" r="4" fill={BRAND} />
      <path d="M60 110 L40 150" stroke={STROKE} strokeWidth="3" strokeLinecap="round" />
      <path d="M100 110 L85 150" stroke={STROKE} strokeWidth="3" strokeLinecap="round" />
      <path d="M140 110 L155 150" stroke={STROKE} strokeWidth="3" strokeLinecap="round" />
      <path d="M180 110 L200 150" stroke={STROKE} strokeWidth="3" strokeLinecap="round" />
      <circle cx="40" cy="150" r="6" fill={CYAN} />
      <circle cx="85" cy="150" r="6" fill={CYAN} />
      <circle cx="155" cy="150" r="6" fill={CYAN} />
      <circle cx="200" cy="150" r="6" fill={CYAN} />
    </svg>
  )
}

function ServiceBody() {
  return (
    <svg viewBox="0 0 200 220" className="w-full h-full max-w-[220px]" fill="none">
      <rect x="40" y="40" width="120" height="130" rx="20" fill={FILL} stroke={STROKE} strokeWidth="2.2" />
      <rect x="55" y="60" width="90" height="22" rx="4" fill={CYAN} opacity="0.16" />
      <rect x="55" y="90" width="90" height="22" rx="4" fill={STROKE} opacity="0.08" />
      <rect x="55" y="120" width="90" height="22" rx="4" fill={STROKE} opacity="0.08" />
      <rect x="70" y="20" width="60" height="24" rx="10" fill={PANEL} stroke={CYAN} strokeWidth="2.5" />
      <circle cx="86" cy="32" r="3" fill={CYAN} />
      <circle cx="114" cy="32" r="3" fill={CYAN} />
      <circle cx="65" cy="190" r="16" fill={PANEL} stroke={STROKE} strokeWidth="2.2" />
      <circle cx="135" cy="190" r="16" fill={PANEL} stroke={STROKE} strokeWidth="2.2" />
    </svg>
  )
}

function EducationalBody() {
  return (
    <svg viewBox="0 0 200 180" className="w-full h-full max-w-[240px]" fill="none">
      <rect x="40" y="50" width="120" height="80" rx="18" fill={FILL} stroke={CYAN} strokeWidth="2.5" />
      <circle cx="75" cy="80" r="10" fill={PANEL} stroke={STROKE} strokeWidth="2.2" />
      <circle cx="125" cy="80" r="10" fill={PANEL} stroke={STROKE} strokeWidth="2.2" />
      <circle cx="75" cy="80" r="4" fill={CYAN} />
      <circle cx="125" cy="80" r="4" fill={CYAN} />
      <rect x="80" y="105" width="40" height="8" rx="4" fill={STROKE} opacity="0.35" />
      <rect x="60" y="130" width="80" height="20" rx="6" fill={PANEL} stroke={STROKE} strokeWidth="2.2" />
      <circle cx="75" cy="160" r="10" fill={PANEL} stroke={STROKE} strokeWidth="2.2" />
      <circle cx="125" cy="160" r="10" fill={PANEL} stroke={STROKE} strokeWidth="2.2" />
      <path d="M100 30 L100 50" stroke={STROKE} strokeWidth="2.2" />
      <circle cx="100" cy="25" r="6" fill={BRAND} stroke={STROKE} strokeWidth="2" />
    </svg>
  )
}
