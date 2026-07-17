import { Section, SectionTitle } from './ui'

const ladder = [
  { name: 'Activity', q: 'Was the work performed?', solved: true },
  { name: 'Quality', q: 'Did the work meet a technical standard?', solved: true },
  { name: 'Scarcity', q: 'Did it come from an under-supplied area?', solved: true },
  { name: 'Demand linkage', q: 'Did customers consume related output?', solved: true },
  {
    name: 'Causal additionality',
    q: 'Did the contribution change the outcome against a credible baseline?',
    solved: false,
  },
]

export function Problem() {
  return (
    <Section id="problem" className="mt-28">
      <SectionTitle
        num="01"
        eyebrow="Problem and market gap"
        title="Contribution verification is necessary. It is not the same as measuring additional value."
        lead="A network can correctly verify that a device was online and produced valid observations, and still allocate capital poorly. Redundant devices can earn heavily without improving coverage, accuracy or demand, while a device in a sparse area can create high value with less activity."
      />

      <div className="mt-14 grid gap-12 lg:grid-cols-[1.1fr_0.9fr] lg:items-start">
        <div>
          <div className="mb-3 flex items-baseline justify-between font-mono text-[10px] uppercase tracking-[0.18em] text-faint">
            <span>What reward systems ask</span>
            <span>status</span>
          </div>
          <ol className="border-t border-rulehard">
            {ladder.map((step, i) => (
              <li
                key={step.name}
                className={`grid grid-cols-[2rem_1fr_auto] items-baseline gap-4 border-b py-4 ${
                  step.solved
                    ? 'border-rule'
                    : 'border-violet/40 bg-violet/[0.04] px-3 -mx-3'
                }`}
              >
                <span className="font-mono text-xs text-faint tabular-nums">
                  {String(i + 1).padStart(2, '0')}
                </span>
                <div>
                  <span
                    className={`font-medium ${
                      step.solved ? 'text-ink' : 'font-semibold text-violet'
                    }`}
                  >
                    {step.name}
                  </span>
                  <p className="mt-0.5 text-sm text-soft">{step.q}</p>
                </div>
                <span
                  className={`font-mono text-[10px] uppercase tracking-wider ${
                    step.solved ? 'text-faint' : 'text-violet'
                  }`}
                >
                  {step.solved ? 'handled' : 'missing'}
                </span>
              </li>
            ))}
          </ol>
        </div>

        <div className="lg:pt-8">
          <blockquote className="border-l-2 border-ink pl-6">
            <p className="font-serif text-xl font-medium italic leading-snug text-ink">
              A quality score can be high when marginal value is close to zero.
            </p>
          </blockquote>
          <p className="mt-6 text-sm leading-relaxed text-soft">
            Additionality asks a counterfactual question, and the counterfactual
            outcome is never directly observable. It has to be estimated through
            a pre-specified experiment or a carefully justified observational
            design.
          </p>
          <p className="mt-4 text-sm leading-relaxed text-soft">
            The Solana DePIN Playbook already separates proof of contribution
            from reward distribution. The missing component sits exactly between
            the two: a layer that decides how much of the outcome a cohort of
            contributors actually caused, before settlement.
          </p>
        </div>
      </div>
    </Section>
  )
}
