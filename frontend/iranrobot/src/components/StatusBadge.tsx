/**
 * Phase 6 -- bilingual status badge for customer-facing Quote / Procurement /
 * Support records. Bilingual labels are picked by the caller through the i18n
 * helper passed in.
 *
 * Color tones intentionally reuse the existing `Badge` palette so the
 * dashboard doesn't introduce a new color story.
 */

import { Badge } from './Badge'
import type { ComponentProps } from 'react'
import { useI18n } from '../i18n'

type BadgeTone = NonNullable<ComponentProps<typeof Badge>['tone']>

type Kind = 'quote' | 'procurement' | 'support' | 'quotation'

const QUOTE_MAP: Record<string, { fa: string; en: string; tone: BadgeTone }> = {
  New: { fa: 'جدید', en: 'New', tone: 'warning' },
  Reviewing: { fa: 'در حال بررسی', en: 'Reviewing', tone: 'warning' },
  Pricing: { fa: 'برآورد قیمت', en: 'Pricing', tone: 'tech' },
  'Proposal Sent': { fa: 'پیشنهاد ارسال شد', en: 'Proposal Sent', tone: 'brand' },
  Accepted: { fa: 'پذیرفته شد', en: 'Accepted', tone: 'success' },
  Rejected: { fa: 'رد شد', en: 'Rejected', tone: 'neutral' },
  Closed: { fa: 'بسته شد', en: 'Closed', tone: 'neutral' },
}

const PROCUREMENT_MAP: Record<string, { fa: string; en: string; tone: BadgeTone }> = {
  New: { fa: 'جدید', en: 'New', tone: 'warning' },
  Reviewing: { fa: 'در حال بررسی', en: 'Reviewing', tone: 'warning' },
  Sourcing: { fa: 'تأمین', en: 'Sourcing', tone: 'tech' },
  'Supplier Found': { fa: 'تأمین‌کننده پیدا شد', en: 'Supplier Found', tone: 'tech' },
  'Proposal Sent': { fa: 'پیشنهاد ارسال شد', en: 'Proposal Sent', tone: 'brand' },
  Accepted: { fa: 'پذیرفته شد', en: 'Accepted', tone: 'success' },
  Rejected: { fa: 'رد شد', en: 'Rejected', tone: 'neutral' },
  Closed: { fa: 'بسته شد', en: 'Closed', tone: 'neutral' },
}

// Phase 7A -- mirrors Robot Quote Request.quotation_status options. The
// `Closed` row covers ERPNext's "Cancelled" mapping for defensive rendering.
const QUOTATION_MAP: Record<string, { fa: string; en: string; tone: BadgeTone }> = {
  Draft: { fa: 'پیش‌نویس', en: 'Draft', tone: 'neutral' },
  Sent: { fa: 'ارسال شد', en: 'Sent', tone: 'brand' },
  Accepted: { fa: 'پذیرفته شد', en: 'Accepted', tone: 'success' },
  Rejected: { fa: 'رد شد', en: 'Rejected', tone: 'neutral' },
  Expired: { fa: 'منقضی شد', en: 'Expired', tone: 'neutral' },
}

const SUPPORT_MAP: Record<string, { fa: string; en: string; tone: BadgeTone }> = {
  Open: { fa: 'باز', en: 'Open', tone: 'warning' },
  'In Progress': { fa: 'در حال بررسی', en: 'In Progress', tone: 'tech' },
  Hold: { fa: 'منتظر شما', en: 'Waiting for Customer', tone: 'warning' },
  Replied: { fa: 'پاسخ داده شد', en: 'Replied', tone: 'tech' },
  'Waiting for Customer': { fa: 'منتظر شما', en: 'Waiting for Customer', tone: 'warning' },
  Resolved: { fa: 'حل شد', en: 'Resolved', tone: 'success' },
  Closed: { fa: 'بسته شد', en: 'Closed', tone: 'neutral' },
}

function pick(kind: Kind, status: string | null | undefined) {
  if (!status) {
    return { fa: '—', en: '—', tone: 'neutral' as BadgeTone }
  }
  const map =
    kind === 'quote'
      ? QUOTE_MAP
      : kind === 'procurement'
        ? PROCUREMENT_MAP
        : kind === 'quotation'
          ? QUOTATION_MAP
          : SUPPORT_MAP
  return map[status] ?? { fa: status, en: status, tone: 'neutral' as BadgeTone }
}

export function StatusBadge({
  kind,
  status,
}: {
  kind: Kind
  status: string | null | undefined
}) {
  const { t } = useI18n()
  const entry = pick(kind, status)
  return (
    <Badge tone={entry.tone} dot>
      {t(entry.fa, entry.en)}
    </Badge>
  )
}
