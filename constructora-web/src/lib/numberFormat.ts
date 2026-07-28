const mexicanNumberLocale = 'es-MX-u-nu-latn'

export type MexicanNumberFormatOptions = {
  maximumFractionDigits?: number
  minimumFractionDigits?: number
}

export function parseMexicanNumber(value: string | number | null | undefined): number | null {
  if (typeof value === 'number') return Number.isFinite(value) ? value : null

  const source = String(value ?? '')
    .trim()
    .replace(/\s/g, '')
    .replace(/[$%]/g, '')

  if (!source) return null

  let normalized = source
  if (source.includes('.')) {
    normalized = source.replace(/,/g, '')
  } else if (source.includes(',')) {
    const groupedInteger = /^[+-]?\d{1,3}(,\d{3})+$/.test(source)
    normalized = groupedInteger
      ? source.replace(/,/g, '')
      : source.replace(/,/g, (match, offset) =>
          offset === source.lastIndexOf(',') ? '.' : '',
        )
  }

  const parsed = Number(normalized)
  return Number.isFinite(parsed) ? parsed : null
}

export function normalizeMexicanNumber(value: string | number | null | undefined): string {
  if (value === '' || value === null || value === undefined) return ''
  const parsed = parseMexicanNumber(value)
  return parsed === null ? '' : String(parsed)
}

export function formatMexicanNumber(
  value: string | number | null | undefined,
  options: MexicanNumberFormatOptions = {},
) {
  const parsed = parseMexicanNumber(value)
  if (parsed === null) return ''

  return new Intl.NumberFormat(mexicanNumberLocale, {
    maximumFractionDigits: options.maximumFractionDigits ?? 4,
    minimumFractionDigits: options.minimumFractionDigits ?? 0,
  }).format(parsed)
}

export function formatMexicanMoney(value: string | number | null | undefined) {
  const parsed = parseMexicanNumber(value) ?? 0
  return new Intl.NumberFormat(mexicanNumberLocale, {
    style: 'currency',
    currency: 'MXN',
    maximumFractionDigits: 2,
    minimumFractionDigits: 2,
  }).format(parsed)
}
