import { Section } from './ui'

const stats = [
  { value: '20', unit: 'weeks', label: 'MVP delivery timeline' },
  { value: '95,000', unit: 'USDC', label: 'Indicative grant request' },
  { value: '10,000', unit: 'devices', label: 'Virtual sensors in the reference run' },
  { value: '1,000,000', unit: 'obs.', label: 'Signed observations target' },
]

export function Stats() {
  return (
    <Section className="mt-20">
      <div className="grid grid-cols-2 border-y border-rulehard lg:grid-cols-4">
        {stats.map((s, i) => (
          <div
            key={s.label}
            className={`px-5 py-7 sm:px-6 ${
              i > 0 ? 'border-l border-rule' : ''
            } ${i === 2 ? 'max-lg:border-l-0 max-lg:border-t max-lg:border-rule' : ''} ${
              i === 3 ? 'max-lg:border-t max-lg:border-rule' : ''
            }`}
          >
            <div className="flex flex-wrap items-baseline gap-x-2">
              <span className="font-serif text-2xl font-semibold tracking-tight text-ink tabular-nums sm:text-4xl">
                {s.value}
              </span>
              <span className="font-mono text-[11px] uppercase tracking-wider text-faint">
                {s.unit}
              </span>
            </div>
            <div className="mt-2 text-sm text-soft">{s.label}</div>
          </div>
        ))}
      </div>
      <p className="mt-4 font-mono text-[11px] uppercase tracking-[0.14em] text-faint">
        Context: Solana reports ~400M USD in annual DePIN rewards across
        wireless, mapping, compute, bandwidth and positioning networks.
      </p>
    </Section>
  )
}
