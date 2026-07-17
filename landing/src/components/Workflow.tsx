import { Section, SectionTitle } from './ui'

const steps = [
  { fn: 'create_experiment', text: 'Create the draft and fund the vault.' },
  { fn: 'freeze_experiment', text: 'Lock the manifest, participant rules and seed commitment.' },
  { fn: 'publish_cohort_root', text: 'Record the enrolled cohort set.' },
  { fn: 'reveal_seed', text: 'Derive and publish the assignment root.' },
  { fn: 'post_evidence_epoch', text: 'Anchor each signed evidence batch.' },
  { fn: 'submit_evaluation', text: 'Commit the result artifact and candidate reward root.' },
  { fn: 'open_challenge', text: 'Lock a bond and pause finality.' },
  { fn: 'resolve_challenge', text: 'Accept, replace or reject the evaluation.' },
  { fn: 'finalize_distribution', text: 'Publish the final claim root.' },
  { fn: 'claim_reward', text: 'Verify the proof, transfer the reward, prevent replay.' },
  { fn: 'close_experiment', text: 'Recover unused funds after expiry.' },
]

const guarantees = [
  {
    title: 'Nothing changes after freeze',
    body: 'Metric, assignment method, analysis plan and reward curve are fixed by hash before results exist.',
  },
  {
    title: 'Reproducible by anyone',
    body: 'A public verifier CLI re-derives the assignment root, result hash and every reward leaf.',
  },
  {
    title: 'Challenge without exposure',
    body: 'Participants can dispute a result by bonding and referencing artifacts, with no raw data on-chain.',
  },
]

export function Workflow() {
  return (
    <Section id="workflow" className="mt-28">
      <SectionTitle
        num="03"
        eyebrow="Instruction flow"
        title="Freeze the experiment first. Then every step reproduces from public artifacts."
        lead="The manifest is frozen before the assignment seed is revealed and before any outcome data is analysed. From there, an independent verifier can reproduce assignment, evidence, effect estimates and the reward root."
      />

      <div className="mt-14 border border-rulehard bg-surface">
        <div className="flex items-baseline justify-between border-b border-rule px-5 py-3.5">
          <span className="font-mono text-[11px] font-medium uppercase tracking-[0.18em] text-faint">
            Core instructions, in order
          </span>
          <span className="font-mono text-[11px] text-faint">11 total</span>
        </div>
        <ol className="grid sm:grid-cols-2 lg:grid-cols-3">
          {steps.map((s, i) => (
            <li
              key={s.fn}
              className="border-b border-rule px-5 py-4 sm:[&:nth-child(2n)]:border-l sm:[&:nth-child(2n)]:border-l-rule lg:[&:nth-child(2n)]:border-l-0 lg:[&:nth-child(3n+2)]:border-l lg:[&:nth-child(3n)]:border-l lg:[&:nth-child(3n+2)]:border-l-rule lg:[&:nth-child(3n)]:border-l-rule"
            >
              <div className="flex items-baseline gap-3">
                <span className="font-mono text-[11px] text-faint tabular-nums">
                  {String(i + 1).padStart(2, '0')}
                </span>
                <code className="font-mono text-[13px] font-semibold text-violet">
                  {s.fn}
                </code>
              </div>
              <p className="mt-1.5 pl-[calc(0.75rem+22px)] text-sm leading-relaxed text-soft sm:pl-0 sm:ml-[2.1rem]">
                {s.text}
              </p>
            </li>
          ))}
        </ol>
      </div>

      <div className="mt-10 grid gap-8 border-t border-rule pt-8 sm:grid-cols-3">
        {guarantees.map((g) => (
          <div key={g.title}>
            <h3 className="flex items-center gap-2 text-sm font-semibold text-ink">
              <span className="h-1.5 w-1.5 bg-teal" />
              {g.title}
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-soft">{g.body}</p>
          </div>
        ))}
      </div>
    </Section>
  )
}
