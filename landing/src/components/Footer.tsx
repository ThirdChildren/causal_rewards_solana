import { Logo } from './Logo'

const refs = [
  { n: 1, label: 'Solana Foundation, Decentralized Physical Infrastructure Networks', href: 'https://solana.com/solutions/depin' },
  { n: 2, label: 'Solana Foundation, DePIN Playbook', href: 'https://solana.com/developers/guides/depin/getting-started' },
  { n: 3, label: 'Solana Foundation, Grants and Funding', href: 'https://solana.org/grants-funding' },
  { n: 4, label: 'Solana Foundation, Rewards Program', href: 'https://github.com/solana-foundation/rewards' },
  { n: 5, label: 'Solana Documentation, Attestations', href: 'https://solana.com/docs/tools/attestations' },
  { n: 6, label: 'Arcium Documentation', href: 'https://docs.arcium.com/' },
  { n: 7, label: 'Light Protocol, ZK Compression', href: 'https://lightprotocol.com/overview/core-concepts/compressed-account-model' },
]

export function CtaFooter() {
  return (
    <footer className="mt-28">
      <div className="mx-auto w-full max-w-6xl px-6">
        <div className="border-t-2 border-ink pt-14 text-center">
          <p className="mx-auto max-w-3xl text-balance font-serif text-3xl font-semibold leading-tight tracking-tight text-ink sm:text-4xl">
            A measurement and settlement layer.{' '}
            <em className="font-medium italic text-violet">
              Not another DePIN, and not another token.
            </em>
          </p>
          <p className="mx-auto mt-5 max-w-xl text-soft">
            The MVP is complete only when an independent party can reproduce the
            full path from manifest to reward root. Everything else follows from
            that.
          </p>
          <div className="mt-9 flex flex-wrap items-center justify-center gap-4">
            <a
              href="#approach"
              className="inline-flex items-center gap-2.5 bg-ink px-6 py-3.5 text-sm font-semibold text-paper transition-colors hover:bg-violet"
            >
              Read the approach
            </a>
            <a
              href="#roadmap"
              className="text-sm font-semibold text-ink underline decoration-rulehard decoration-2 underline-offset-[6px] transition-colors hover:decoration-violet"
            >
              Review milestones
            </a>
          </div>
        </div>

        <div className="mt-20 grid gap-10 border-t border-rule pt-10 lg:grid-cols-[1fr_1.2fr]">
          <div>
            <div className="flex items-center gap-3">
              <Logo className="h-7 w-7" />
              <span className="font-semibold text-ink">
                Causal Rewards Protocol
              </span>
            </div>
            <p className="mt-4 max-w-sm text-sm leading-relaxed text-soft">
              Proof of Additionality for Solana DePIN networks. Concept note
              v1.0, prepared for Solana Foundation grant exploration.
            </p>
            <p className="mt-4 font-mono text-[11px] uppercase tracking-wider text-faint">
              Apache-2.0 protocol code / MIT SDKs and analysis libraries
            </p>
          </div>

          <div className="min-w-0">
            <div className="border-b-2 border-ink pb-2 font-mono text-[11px] font-medium uppercase tracking-[0.18em] text-faint">
              Selected references
            </div>
            <ol className="mt-3">
              {refs.map((r) => (
                <li key={r.n} className="border-b border-rule">
                  <a
                    href={r.href}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="group flex items-baseline gap-3 py-2.5 text-sm text-soft transition-colors hover:text-ink"
                  >
                    <span className="font-mono text-[11px] text-faint">
                      [{r.n}]
                    </span>
                    <span className="min-w-0 flex-1 truncate">{r.label}</span>
                    <svg
                      viewBox="0 0 20 20"
                      className="h-3 w-3 shrink-0 text-faint group-hover:text-violet"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                    >
                      <path d="M7 13 13 7 M8 7h5v5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </a>
                </li>
              ))}
            </ol>
          </div>
        </div>

        <div className="mt-12 flex flex-col items-start justify-between gap-2 border-t border-rule py-6 font-mono text-[11px] uppercase tracking-wider text-faint sm:flex-row sm:items-center">
          <span>Research date 16 July 2026. No public exact match found in the market scan.</span>
          <span>Devnet only. Mainnet requires a separate full audit.</span>
        </div>
      </div>
    </footer>
  )
}
