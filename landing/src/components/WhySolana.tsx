import { Section, SectionTitle } from './ui'

const rows = [
  {
    cap: 'Single global state, low fees',
    use: 'Shared experiment, reward and dispute state for many contributors',
    why: 'Frequent, global, low-value claims without a separate application chain',
  },
  {
    cap: 'Large DePIN ecosystem',
    use: 'Pilot and integration targets align with existing Solana networks',
    why: 'Reduces distribution risk and keeps the public good relevant to active builders',
  },
  {
    cap: 'ZK Compression and Merkle claims',
    use: 'Scalable reward recipient and receipt patterns',
    why: 'Avoids one full account per participant at larger scale',
  },
  {
    cap: 'Solana Attestations',
    use: 'Evaluator, result and certification claims',
    why: 'Reuses a native credential system instead of building another',
  },
  {
    cap: 'Arcium',
    use: 'Optional encrypted aggregation of sensitive metrics',
    why: 'Private inputs stay hidden from any single compute operator',
  },
  {
    cap: 'Foundation Rewards Program',
    use: 'Reference adapter for claim and reward distribution',
    why: 'Builds on an existing open source settlement primitive',
  },
]

export function WhySolana() {
  return (
    <Section id="solana" className="mt-28">
      <SectionTitle
        num="04"
        eyebrow="Why Solana"
        title="The estimator is chain agnostic. The protocol is built for Solana on purpose."
        lead="The target market, the settlement pattern and the supporting primitives are all concentrated in the Solana ecosystem. The protocol integrates with these primitives rather than replacing them."
      />

      <div className="mt-12 overflow-x-auto">
        <table className="w-full min-w-[680px] border-collapse text-left">
          <thead>
            <tr>
              <th className="w-[26%] border-b-2 border-ink py-3 pr-4 font-mono text-[11px] font-medium uppercase tracking-[0.18em] text-faint">
                Capability
              </th>
              <th className="w-[37%] border-b-2 border-ink py-3 pr-4 font-mono text-[11px] font-medium uppercase tracking-[0.18em] text-faint">
                Use in the MVP
              </th>
              <th className="border-b-2 border-ink py-3 font-mono text-[11px] font-medium uppercase tracking-[0.18em] text-faint">
                Why it matters
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.cap} className="align-top transition-colors hover:bg-surface">
                <td className="border-b border-rule py-4 pr-4 font-medium text-ink">
                  {r.cap}
                </td>
                <td className="border-b border-rule py-4 pr-4 text-sm leading-relaxed text-soft">
                  {r.use}
                </td>
                <td className="border-b border-rule py-4 text-sm leading-relaxed text-soft">
                  {r.why}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Section>
  )
}
