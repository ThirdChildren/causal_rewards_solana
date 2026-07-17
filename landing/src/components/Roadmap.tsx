import { Section, SectionTitle } from './ui'

const milestones = [
  {
    id: 'M1',
    title: 'Specification and benchmark',
    weeks: 'Weeks 1 to 4',
    budget: '18,000',
    deliver:
      'Threat model, manifest schema, state machine, simulator alpha and benchmark plan.',
    accept: 'Frozen public spec, test scenarios and a reproducible baseline run.',
  },
  {
    id: 'M2',
    title: 'Solana programs and SDK',
    weeks: 'Weeks 5 to 9',
    budget: '27,000',
    deliver:
      'Experiment registry, assignment, evidence, settlement, challenge module and TypeScript SDK.',
    accept: 'Devnet deployment, integration tests and deterministic assignment vectors.',
  },
  {
    id: 'M3',
    title: 'Evidence and causal engine',
    weeks: 'Weeks 10 to 14',
    budget: '28,000',
    deliver:
      'Signed evidence schema, batch commitments, causal engine, reward compiler, verifier CLI and Arcium proof of concept.',
    accept: 'Independent reproduction of result and reward roots from an audit bundle.',
  },
  {
    id: 'M4',
    title: 'Pilot, hardening and release',
    weeks: 'Weeks 15 to 20',
    budget: '22,000',
    deliver:
      'Dashboard, benchmark at target scale, security review, pilot validation, documentation and final report.',
    accept: 'Tagged open source release, public dashboard, benchmark report and resolved findings.',
  },
]

const budget = [
  { name: 'Solana protocol engineering', amount: '30,000', share: 31.6 },
  { name: 'Causal inference and simulator', amount: '22,000', share: 23.2 },
  { name: 'Backend and data engineering', amount: '16,000', share: 16.8 },
  { name: 'Frontend and developer experience', amount: '9,000', share: 9.5 },
  { name: 'External security review', amount: '8,000', share: 8.4 },
  { name: 'Pilot and documentation', amount: '6,000', share: 6.3 },
  { name: 'Infrastructure and data', amount: '4,000', share: 4.2 },
]

export function Roadmap() {
  return (
    <Section id="roadmap" className="mt-28">
      <SectionTitle
        num="07"
        eyebrow="Roadmap and budget"
        title="Four milestones, each with an independent acceptance test."
        lead="The roadmap separates the statistical benchmark from the settlement code, so payment for each milestone rests on a concrete, verifiable result."
      />

      <div className="mt-14 border-t border-rulehard">
        {milestones.map((m) => (
          <div
            key={m.id}
            className="grid gap-x-8 gap-y-3 border-b border-rule py-7 lg:grid-cols-[7rem_1fr_1fr_7rem]"
          >
            <div>
              <div className="font-serif text-2xl font-semibold text-ink">
                {m.id}
              </div>
              <div className="mt-1 font-mono text-[10px] uppercase tracking-wider text-faint">
                {m.weeks}
              </div>
            </div>
            <div>
              <h3 className="text-base font-semibold text-ink">{m.title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-soft">
                {m.deliver}
              </p>
            </div>
            <div>
              <div className="font-mono text-[10px] uppercase tracking-wider text-faint">
                Acceptance
              </div>
              <p className="mt-1.5 text-sm leading-relaxed text-soft">
                {m.accept}
              </p>
            </div>
            <div className="lg:text-right">
              <div className="font-mono text-sm font-semibold text-ink tabular-nums">
                {m.budget}
              </div>
              <div className="font-mono text-[10px] uppercase tracking-wider text-faint">
                USDC
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-16 grid gap-10 lg:grid-cols-[1fr_16rem]">
        <div>
          <div className="flex items-baseline justify-between">
            <h3 className="font-serif text-xl font-semibold text-ink">
              Budget by workstream
            </h3>
          </div>
          <div className="mt-6 space-y-4">
            {budget.map((b) => (
              <div key={b.name}>
                <div className="flex items-baseline justify-between gap-4">
                  <span className="text-sm text-soft">{b.name}</span>
                  <span className="font-mono text-sm text-ink tabular-nums">
                    {b.amount}
                    <span className="ml-1.5 text-[10px] text-faint">
                      {b.share.toFixed(1)}%
                    </span>
                  </span>
                </div>
                <div className="mt-1.5 h-[5px] bg-paper-2">
                  <div
                    className="h-full bg-ink"
                    style={{ width: `${(b.share / 31.6) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="border border-rulehard bg-surface px-6 py-6 lg:self-start">
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-faint">
            Total request
          </div>
          <div className="mt-2 font-serif text-4xl font-semibold text-ink tabular-nums">
            95,000
          </div>
          <div className="font-mono text-[11px] uppercase tracking-wider text-faint">
            USDC
          </div>
          <div className="mt-4 border-t border-rule pt-4 text-xs leading-relaxed text-soft">
            No token issuance and no marketing allocation. Payments released per
            accepted milestone.
          </div>
        </div>
      </div>
    </Section>
  )
}
