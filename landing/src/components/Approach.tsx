import { Section, SectionTitle } from './ui'

const deliverables = [
  {
    n: 'A',
    title: 'Protocol specification',
    body: 'Schemas for experiment manifests, assignment commitments, evidence epochs, evaluation results, reward roots and challenges.',
  },
  {
    n: 'B',
    title: 'Solana programs',
    body: 'On-chain state for experiments, evidence commitments, settlement, claims and dispute controls.',
  },
  {
    n: 'C',
    title: 'Open causal engine',
    body: 'Deterministic analysis artifacts produced from a frozen manifest and dataset, with uncertainty and sensitivity checks.',
  },
  {
    n: 'D',
    title: 'Reference app and simulator',
    body: 'A working demonstration on an environmental sensor network, with configurable faults, redundancy and demand shifts.',
  },
]

export function Approach() {
  return (
    <Section id="approach" className="mt-28">
      <SectionTitle
        num="02"
        eyebrow="Product definition"
        title="A pre-registered experiment, turned into a reproducible reward distribution."
        lead="Proof of Additionality is a product concept, not a claim that causality can be proven cryptographically. The chain verifies commitments, process integrity and settlement. The causal claim stays valid only as far as the design, data and assumptions are valid."
      />

      <div className="mt-14 grid border-t border-rulehard sm:grid-cols-2 lg:grid-cols-4">
        {deliverables.map((d, i) => (
          <div
            key={d.n}
            className={`border-b border-rule py-6 pr-6 lg:border-b-0 ${
              i > 0 ? 'lg:border-l lg:border-rule lg:pl-6' : ''
            } ${i % 2 === 1 ? 'sm:border-l sm:border-rule sm:pl-6 lg:pl-6' : ''}`}
          >
            <div className="font-mono text-[11px] font-medium text-violet">
              Deliverable {d.n}
            </div>
            <h3 className="mt-3 font-serif text-lg font-semibold text-ink">
              {d.title}
            </h3>
            <p className="mt-2.5 text-sm leading-relaxed text-soft">{d.body}</p>
          </div>
        ))}
      </div>

      <div className="mt-14 grid gap-10 border-t border-rule pt-10 lg:grid-cols-[1fr_auto] lg:items-center">
        <div>
          <span className="font-mono text-[11px] font-medium uppercase tracking-[0.18em] text-faint">
            Core design rule
          </span>
          <p className="mt-4 max-w-2xl font-serif text-2xl font-medium leading-snug text-ink">
            The blockchain verifies commitments, process integrity and
            settlement. Additionality is measured against a predefined baseline,
            with transparent assumptions and{' '}
            <em className="italic text-violet">
              conservative treatment of uncertainty
            </em>
            .
          </p>
        </div>
        <div className="border border-rulehard bg-surface px-6 py-5 text-center lg:min-w-[15rem]">
          <div className="font-serif text-2xl font-semibold text-ink">
            Shadow mode
          </div>
          <p className="mx-auto mt-1.5 max-w-[13rem] text-xs leading-relaxed text-soft">
            Existing networks can run it before touching live incentives
          </p>
        </div>
      </div>
    </Section>
  )
}
