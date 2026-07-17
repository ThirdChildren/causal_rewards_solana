import { Section, SectionTitle, Panel } from './ui'

const scenarios = [
  {
    name: 'Sparse coverage',
    inject: 'Few sensors, high baseline error',
    expect: 'Higher causal value for informative cohorts',
  },
  {
    name: 'Redundant coverage',
    inject: 'Many correlated sensors in the same cells',
    expect: 'Lower value for duplicative cohorts',
  },
  {
    name: 'Quality degradation',
    inject: 'Noise, drift and missing observations',
    expect: 'Low-quality cohorts lose eligibility or effect',
  },
  {
    name: 'Sybil replication',
    inject: 'Devices replay highly correlated data',
    expect: 'Extra identities do not create proportional value',
  },
  {
    name: 'Demand shift',
    inject: 'Reference points move to a new region',
    expect: 'Allocation follows the frozen outcome window',
  },
  {
    name: 'Interference',
    inject: 'Neighbouring sensors affect shared predictions',
    expect: 'Bias and sensitivity are reported, not hidden',
  },
]

export function UseCase() {
  return (
    <Section id="pilot" className="mt-28">
      <SectionTitle
        num="05"
        eyebrow="Reference pilot"
        title="Environmental sensors, measured in shadow mode."
        lead="The pilot simulates a sensor network across geographic cells with different coverage, redundancy, hardware quality and fault risk. A prediction service estimates a physical field, such as temperature or air quality, at independent reference points."
      />

      <div className="mt-14 grid gap-12 lg:grid-cols-[0.9fr_1.1fr] lg:items-start">
        <div>
          <p className="text-sm leading-relaxed text-soft">
            The production path is never degraded. All valid observations stay
            available to the live service. Randomized assignment applies only to
            the evaluation pipeline, which includes or holds out geographic
            cohorts across time blocks. The treatment effect is the change in
            out-of-sample prediction error caused by including those cohorts.
          </p>

          <dl className="mt-8 grid grid-cols-2 border-t border-rulehard">
            <MiniStat value="10,000" label="virtual sensors" />
            <MiniStat value="250" label="geographic cohorts" border />
            <MiniStat value="1,000,000" label="signed observations" top />
            <MiniStat value="4" label="reward baselines compared" border top />
          </dl>

          <p className="mt-6 text-sm leading-relaxed text-soft">
            The benchmark compares activity-only, quality-weighted,
            scarcity-weighted and causal allocation under one fixed budget.{' '}
            <span className="font-medium text-ink">
              Results are published even when causal allocation does not win.
            </span>
          </p>
        </div>

        <Panel>
          <div className="flex items-baseline justify-between border-b border-rule px-5 py-3.5">
            <span className="font-mono text-[11px] font-medium uppercase tracking-[0.18em] text-faint">
              Simulation scenarios
            </span>
            <span className="font-mono text-[11px] text-faint">6 of 6 in scope</span>
          </div>
          <div className="divide-y divide-rule">
            {scenarios.map((s, i) => (
              <div key={s.name} className="grid gap-1 px-5 py-4 sm:grid-cols-[10.5rem_1fr]">
                <div className="flex items-baseline gap-2.5">
                  <span className="font-mono text-[11px] text-faint tabular-nums">
                    S{i + 1}
                  </span>
                  <span className="text-sm font-semibold text-ink">{s.name}</span>
                </div>
                <div className="text-sm leading-relaxed text-soft sm:pl-0">
                  {s.inject}.{' '}
                  <span className="text-teal">Expected: {s.expect.toLowerCase()}.</span>
                </div>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </Section>
  )
}

function MiniStat({
  value,
  label,
  border = false,
  top = false,
}: {
  value: string
  label: string
  border?: boolean
  top?: boolean
}) {
  return (
    <div
      className={`py-4 pr-4 ${border ? 'border-l border-rule pl-4' : ''} ${
        top ? 'border-t border-rule' : ''
      }`}
    >
      <dd className="font-serif text-2xl font-semibold text-ink tabular-nums">
        {value}
      </dd>
      <dt className="mt-0.5 font-mono text-[10px] uppercase tracking-wider text-faint">
        {label}
      </dt>
    </div>
  )
}
