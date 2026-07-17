import { Section, SectionTitle } from './ui'

const onchain = [
  { name: 'Experiment Registry', role: 'Frozen manifest hash, funding, status, windows and authorities' },
  { name: 'Evidence Registry', role: 'Batch roots, time ranges, signer commitments and artifact hashes' },
  { name: 'Settlement Program', role: 'Reward root, claims, expiry and unused budget recovery' },
  { name: 'Challenge Module', role: 'Challenge records, bond locks, finality pause and resolution' },
]

const offchain = [
  { name: 'Coordinator service', role: 'Enrolment, seed commitment, cohort assignment and orchestration' },
  { name: 'Evidence service', role: 'Signature checks, normalization and content-addressed Merkle batches' },
  { name: 'Causal engine', role: 'Balance checks, effect estimation, uncertainty and sensitivity' },
  { name: 'Verifier CLI', role: 'Reproduces assignments, hashes, estimates and reward roots' },
]

export function Architecture() {
  return (
    <Section id="architecture" className="mt-28">
      <SectionTitle
        num="06"
        eyebrow="Technical architecture"
        title="Solana stores compact state. Telemetry and statistical artifacts stay content-addressed off-chain."
        lead="Only hashes, roots, result summaries and claim state are placed on Solana. No raw telemetry, coordinates or personal data ever land in on-chain accounts."
      />

      <div className="mt-14 grid border-t border-rulehard lg:grid-cols-2">
        <Column
          label="On-chain"
          sub="Rust programs on Solana"
          accent="text-teal"
          dot="bg-teal"
          items={onchain}
          className="lg:border-r lg:border-rule lg:pr-10"
        />
        <Column
          label="Off-chain"
          sub="Reproducible, content-addressed"
          accent="text-violet"
          dot="bg-violet"
          items={offchain}
          className="border-t border-rule pt-2 lg:border-t-0 lg:pl-10 lg:pt-6"
        />
      </div>

      <div className="mt-12 flex flex-col gap-4 border border-rulehard bg-surface px-6 py-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="text-sm font-semibold text-ink">
            Every experiment produces an immutable audit bundle
          </div>
          <p className="mt-1 max-w-xl text-sm leading-relaxed text-soft">
            Manifest, participants, assignment, evidence, analysis, rewards,
            roots and provenance. Mirrored by multiple storage providers,
            replayable by anyone.
          </p>
        </div>
        <code className="whitespace-nowrap font-mono text-xs text-soft">
          roots.json + provenance.json
        </code>
      </div>
    </Section>
  )
}

function Column({
  label,
  sub,
  accent,
  dot,
  items,
  className = '',
}: {
  label: string
  sub: string
  accent: string
  dot: string
  items: { name: string; role: string }[]
  className?: string
}) {
  return (
    <div className={`pt-6 ${className}`}>
      <div className="flex items-baseline justify-between">
        <h3 className="flex items-center gap-2.5 font-serif text-xl font-semibold text-ink">
          <span className={`h-2 w-2 ${dot}`} />
          {label}
        </h3>
        <span className={`font-mono text-[11px] ${accent}`}>{sub}</span>
      </div>
      <div className="mt-5">
        {items.map((it) => (
          <div
            key={it.name}
            className="grid gap-1 border-t border-rule py-3.5 sm:grid-cols-[11.5rem_1fr] sm:gap-4"
          >
            <div className="text-sm font-semibold text-ink">{it.name}</div>
            <div className="text-sm leading-relaxed text-soft">{it.role}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
