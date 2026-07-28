import {
  ChangeEvent,
  FocusEvent,
  InputHTMLAttributes,
  useEffect,
  useMemo,
  useState,
} from 'react'

import {
  formatMexicanNumber,
  normalizeMexicanNumber,
  parseMexicanNumber,
} from '../lib/numberFormat'

type MexicanNumberInputProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> & {
  maximumFractionDigits?: number
  minimumFractionDigits?: number
}

function decimalsFromStep(step: InputHTMLAttributes<HTMLInputElement>['step']) {
  if (step === undefined || step === 'any') return 4
  const source = String(step)
  const decimal = source.split('.')[1]
  return decimal?.length ?? 0
}

function inputText(value: string | number | readonly string[] | undefined) {
  if (Array.isArray(value)) return value.join('')
  return String(value ?? '')
}

export default function MexicanNumberInput({
  value,
  onChange,
  onFocus,
  onBlur,
  min,
  max,
  step,
  maximumFractionDigits,
  minimumFractionDigits = 0,
  ...props
}: MexicanNumberInputProps) {
  const fractionDigits = maximumFractionDigits ?? decimalsFromStep(step)
  const formattedValue = useMemo(
    () =>
      formatMexicanNumber(inputText(value), {
        maximumFractionDigits: fractionDigits,
        minimumFractionDigits,
      }),
    [fractionDigits, minimumFractionDigits, value],
  )
  const [displayValue, setDisplayValue] = useState(formattedValue)
  const [editing, setEditing] = useState(false)

  useEffect(() => {
    if (!editing) setDisplayValue(formattedValue)
  }, [editing, formattedValue])

  function emitChange(event: ChangeEvent<HTMLInputElement>, normalizedValue: string) {
    if (!onChange) return
    const input = event.currentTarget
    const visibleValue = input.value
    input.value = normalizedValue
    onChange(event)
    input.value = visibleValue
  }

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    const nextDisplay = event.currentTarget.value
      .replace(/[^\d.,+-]/g, '')
      .replace(/(?!^)[+-]/g, '')
    setDisplayValue(nextDisplay)
    if (!nextDisplay || nextDisplay === '-' || nextDisplay === '+') {
      emitChange(event, '')
      return
    }

    const normalized = normalizeMexicanNumber(nextDisplay)
    if (normalized) emitChange(event, normalized)
  }

  function handleFocus(event: FocusEvent<HTMLInputElement>) {
    setEditing(true)
    onFocus?.(event)
  }

  function handleBlur(event: FocusEvent<HTMLInputElement>) {
    setEditing(false)
    const parsed = parseMexicanNumber(displayValue)
    if (parsed !== null) {
      const minimum = min === undefined ? null : parseMexicanNumber(String(min))
      const maximum = max === undefined ? null : parseMexicanNumber(String(max))
      const clamped = Math.min(
        maximum ?? Number.POSITIVE_INFINITY,
        Math.max(minimum ?? Number.NEGATIVE_INFINITY, parsed),
      )
      const normalized = String(clamped)
      const input = event.currentTarget
      const visibleValue = input.value
      input.value = normalized
      onChange?.(event as unknown as ChangeEvent<HTMLInputElement>)
      input.value = visibleValue
      setDisplayValue(
        formatMexicanNumber(normalized, {
          maximumFractionDigits: fractionDigits,
          minimumFractionDigits,
        }),
      )
    } else if (!displayValue) {
      setDisplayValue('')
    }
    onBlur?.(event)
  }

  return (
    <input
      {...props}
      type="text"
      inputMode="decimal"
      value={displayValue}
      onChange={handleChange}
      onFocus={handleFocus}
      onBlur={handleBlur}
      min={min}
      max={max}
      step={step}
    />
  )
}
