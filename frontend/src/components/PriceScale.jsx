import { money } from '../format.js'

// A simple three-part bar: below market, fair, above market. "Fair" is within
// 10% of our estimate, the same rule the backend uses for its verdict. If an
// asking price is given, a pin shows where it falls.
const FAIR = 0.1
const SPAN = 0.3 // the bar runs from 30% below our estimate to 30% above it

export default function PriceScale({ estimate, asking }) {
  const fairLow = estimate * (1 - FAIR)
  const fairHigh = estimate * (1 + FAIR)

  // where the asking price sits on the bar, from 0% to 100%
  let pin = null
  if (asking > 0) {
    const position = ((asking / estimate - 1) / SPAN + 1) * 50
    pin = {
      left: Math.min(Math.max(position, 2), 98),
      offBar: position < 0 ? 'below' : position > 100 ? 'above' : null,
      zone: asking < fairLow ? 'below' : asking > fairHigh ? 'above' : 'fair',
    }
  }

  return (
    <figure className="scale">
      <p className="scale-headline">
        Fair price: <strong>{money(fairLow)} – {money(fairHigh)}</strong>
      </p>

      <div className={'scale-bar-wrap' + (pin ? ' has-pin' : '')}>
        {pin && (
          <div
            className={'scale-pin scale-pin-' + pin.zone + (pin.left < 15 ? ' at-start' : pin.left > 85 ? ' at-end' : '')}
            style={{ left: pin.left + '%' }}
          >
            <span>
              {pin.offBar === 'below' && '← '}Seller {money(asking)}{pin.offBar === 'above' && ' →'}
            </span>
          </div>
        )}
        <div className="scale-bar" role="img" aria-label={'Fair price between ' + money(fairLow) + ' and ' + money(fairHigh) + (asking > 0 ? '. Asking price ' + money(asking) + '.' : '.')}>
          <span className="scale-zone scale-below">Cheap</span>
          <span className="scale-zone scale-fair">Fair</span>
          <span className="scale-zone scale-above">Costly</span>
        </div>
        <div className="scale-labels" aria-hidden="true">
          <span style={{ left: '33.333%' }}>{money(fairLow)}</span>
          <span style={{ left: '66.666%' }}>{money(fairHigh)}</span>
        </div>
      </div>
    </figure>
  )
}
