import { Section, SectionTitle, Check } from './ui'

const criteria = [
  {
    k: 'Public good',
    v: 'Open protocol, simulator, benchmark, verifier and community dashboard, reusable by any Solana DePIN.',
  },
  {
    k: 'Open source',
    v: 'Core programs and libraries under permissive licenses, with public test vectors.',
  },
  {
    k: 'Why Solana',
    v: 'Built for Solana DePIN reward flows, compressed claims, attestations, Arcium and shared settlement.',
  },
  {
    k: 'Measurable milestones',
    v: 'Four milestones with devnet, reproducibility, scale, review and publication acceptance tests.',
  },
  {
    k: 'Responsible budget',
    v: '95,000 USDC tied to engineering, research, security review and pilot outputs.',
  },
  {
    k: 'Commercial clarity',
    v: 'No token or protocol fee in the MVP. Managed private experiments are a later SaaS layer.',
  },
]

const inScope = [
  'Experiment creation, funding, freeze and status transitions',
  'Commit and reveal assignment seed with reproducible allocation',
  'Signed telemetry schema and batch evidence commitments',
  'Deterministic estimation, confidence intervals and conservative rewards',
  'Reward root publication, claim verification and budget recovery',
  'Challenge window, bonds and administrative pause controls',
  'Verifier CLI, TypeScript SDK, Python package and web dashboard',
  'Devnet deployment and a reproducible benchmark report',
]

const outScope = [
  'A new token, token sale or protocol fee',
  'Mainnet launch or custody of production reward budgets',
  'A universal oracle for proving physical-world truth',
  'A claim of individual causal attribution for every device',
  'Automated governance of live production tokenomics',
  'Regulatory certification or carbon credit issuance',
]

export function GrantFit() {
  return (
    <Section id="grant" className="mt-28">
      <SectionTitle
        num="08"
        eyebrow="Grant fit"
        title="A milestone-based public good, with a transparent commercial path."
        lead="The public good is the protocol, benchmark and verification tooling. The commercial product is managed operation and private integration, kept fully out of the funded MVP scope."
      />

      <div className="mt-14 border-t border-rulehard">
        {criteria.map((c) => (
          <div
            key={c.k}
            className="grid grid-cols-1 gap-1 border-b border-rule py-4 sm:grid-cols-[14rem_1fr] sm:gap-6"
          >
            <div className="flex items-center gap-2.5 text-sm font-semibold text-ink">
              <Check className="h-4 w-4 text-good" />
              {c.k}
            </div>
            <div className="text-sm leading-relaxed text-soft">{c.v}</div>
          </div>
        ))}
      </div>

      <div className="mt-12 grid gap-10 lg:grid-cols-2">
        <ScopeList title="In scope" positive items={inScope} />
        <ScopeList title="Out of scope" positive={false} items={outScope} />
      </div>
    </Section>
  )
}

function ScopeList({
  title,
  positive,
  items,
}: {
  title: string
  positive: boolean
  items: string[]
}) {
  return (
    <div>
      <h3 className="flex items-baseline gap-2 border-b-2 border-ink pb-2 font-mono text-[11px] font-medium uppercase tracking-[0.18em] text-faint">
        <span className={positive ? 'text-good' : 'text-amber'}>
          {positive ? '+' : '−'}
        </span>
        {title}
        <span className="ml-auto">{items.length} items</span>
      </h3>
      <ul>
        {items.map((it) => (
          <li
            key={it}
            className="flex items-start gap-3 border-b border-rule py-2.5 text-sm text-soft"
          >
            <span
              className={`mt-0.5 font-mono text-xs ${
                positive ? 'text-good' : 'text-amber'
              }`}
            >
              {positive ? '+' : '−'}
            </span>
            <span>{it}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
