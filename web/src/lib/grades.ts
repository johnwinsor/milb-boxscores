/**
 * The 20-80 scouting scale: 50 is major-league average and every 10 points is
 * roughly a standard deviation. Grades are conventionally written in 5-point
 * steps, so the pickers offer those rather than a free number field.
 */
export const SCALE = [20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80]

/** Colour by distance from average, so a report reads at a glance. */
export function gradeClass(v: number | undefined | null): string {
  if (v == null) return 'text-neutral-600'
  if (v >= 70) return 'text-violet-400'
  if (v >= 60) return 'text-emerald-400'
  if (v >= 55) return 'text-emerald-500/80'
  if (v >= 45) return 'text-neutral-200'
  if (v >= 40) return 'text-amber-500'
  return 'text-red-400'
}

export const RISK_CLASS: Record<string, string> = {
  low: 'bg-emerald-950 text-emerald-400',
  medium: 'bg-sky-950 text-sky-400',
  high: 'bg-amber-950 text-amber-400',
  extreme: 'bg-red-950 text-red-400',
}

/** '45/55' when a present grade is recorded, otherwise just the future value. */
export function formatGrade(g?: { present?: number; future?: number }): string {
  if (!g) return '—'
  if (g.present != null && g.future != null && g.present !== g.future) {
    return `${g.present}/${g.future}`
  }
  return String(g.future ?? g.present ?? '—')
}

/** Future Value is the headline number; describe what it means in words. */
export function fvLabel(fv: number | null | undefined): string {
  if (fv == null) return ''
  if (fv >= 70) return 'Elite'
  if (fv >= 60) return 'All-Star'
  if (fv >= 55) return 'Above-average regular'
  if (fv >= 50) return 'Regular'
  if (fv >= 45) return 'Second-division regular'
  if (fv >= 40) return 'Bench / middle reliever'
  return 'Org depth'
}
