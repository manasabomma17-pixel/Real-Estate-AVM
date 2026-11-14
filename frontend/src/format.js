// Small helpers that turn numbers into the way people in India read prices.

// 85.4 -> "₹85.4 L", 156.6 -> "₹1.57 Cr"  (1 Crore = 100 Lakhs)
export function money(lakhs, digits) {
  if (lakhs == null || Number.isNaN(lakhs)) return '–'
  if (Math.abs(lakhs) >= 100) return '₹' + (lakhs / 100).toFixed(digits ?? 2) + ' Cr'
  return '₹' + lakhs.toFixed(digits ?? (lakhs < 10 ? 1 : 0)) + ' L'
}

// 13054 -> "13,054" with Indian digit grouping (1,23,456)
export function rupees(value) {
  if (value == null) return '–'
  return Math.round(value).toLocaleString('en-IN')
}

export function distance(km) {
  if (km == null) return 'not known'
  if (km < 0.05) return 'under 50 m'
  if (km < 1) return Math.round(km * 1000) + ' m'
  return km.toFixed(1) + ' km'
}

export function signed(value, digits = 1) {
  const text = Math.abs(value).toFixed(digits)
  return (value >= 0 ? '+' : '−') + text
}
