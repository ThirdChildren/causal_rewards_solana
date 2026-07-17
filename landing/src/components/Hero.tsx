import { useEffect, useState } from 'react'

export function Hero() {
  return (
    <div id="top" className="mx-auto w-full max-w-6xl px-6 pt-28 sm:pt-32">
      <div className="grid grid-cols-1 gap-14 lg:grid-cols-[1.05fr_0.95fr] lg:items-start lg:gap-12">
        <div>
          <p className="font-mono text-[11px] font-medium uppercase tracking-[0.18em] text-faint">
            Proof of Additionality for Solana DePIN networks
            <span className="mx-2 text-rulehard">/</span>
            prepared for Solana Foundation grant exploration
          </p>

          <h1 className="mt-8 text-balance font-serif text-[2.6rem] font-semibold leading-[1.08] tracking-tight text-ink sm:text-6xl">
            Reward the value a contribution{' '}
            <em className="font-medium italic text-violet">causes</em>, not the
            activity it reports.
          </h1>

          <p className="mt-7 max-w-xl text-lg leading-relaxed text-soft">
            Current DePIN reward systems can verify that a participant
            contributed. Causal Rewards Protocol adds a second question: did the
            contribution cause measurable additional value? An open source
            measurement and settlement layer, built for Solana.
          </p>

          <div className="mt-9 flex flex-wrap items-center gap-4">
            <a
              href="#approach"
              className="inline-flex items-center gap-2.5 bg-ink px-6 py-3.5 text-sm font-semibold text-paper transition-colors hover:bg-violet"
            >
              Explore the protocol
              <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M4 10h11 M11 5l5 5-5 5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </a>
            <a
              href="#roadmap"
              className="text-sm font-semibold text-ink underline decoration-rulehard decoration-2 underline-offset-[6px] transition-colors hover:decoration-violet"
            >
              Milestones and budget
            </a>
          </div>

          <dl className="mt-12 grid grid-cols-3 border-t border-rulehard">
            <HeroFact k="License" v="Apache-2.0 + MIT" />
            <HeroFact k="Network" v="Devnet, reproducible" />
            <HeroFact k="Token" v="None. No protocol fee" />
          </dl>
        </div>

        <SwitchbackPanel />
      </div>
    </div>
  )
}

function HeroFact({ k, v }: { k: string; v: string }) {
  return (
    <div className="border-r border-rule py-4 pr-4 last:border-r-0">
      <dt className="font-mono text-[10px] font-medium uppercase tracking-[0.18em] text-faint">
        {k}
      </dt>
      <dd className="mt-1 text-sm font-medium text-ink">{v}</dd>
    </div>
  )
}

/* Deterministic integer hash, so the animation is reproducible,
   which is rather the point of the whole protocol. */
function hash(n: number): number {
  let x = n | 0
  x = Math.imul(x ^ (x >>> 16), 0x45d9f3b)
  x = Math.imul(x ^ (x >>> 16), 0x45d9f3b)
  return (x ^ (x >>> 16)) >>> 0
}

const COLS = 12
const ROWS = 7
const CELLS = COLS * ROWS

type CellState = 'treatment' | 'control' | 'reference'

function cellState(i: number, epoch: number): CellState {
  if (hash(i * 271 + 13) % 9 === 0) return 'reference'
  return hash(i * 7919 + epoch * 104729) % 2 === 0 ? 'treatment' : 'control'
}

function SwitchbackPanel() {
  const [epoch, setEpoch] = useState(41)

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const t = setInterval(() => setEpoch((e) => e + 1), 2200)
    return () => clearInterval(t)
  }, [])

  // A small, deterministic read-out derived from the epoch: effect,
  // standard error and the conservative lower bound the protocol pays on.
  const effect = (15 + (hash(epoch * 31) % 60)) / 1000
  const se = (8 + (hash(epoch * 57) % 22)) / 1000
  const lower = Math.max(0, effect - 1.96 * se)
  const payable = lower > 0

  const treated = Array.from({ length: CELLS }).filter(
    (_, i) => cellState(i, epoch) === 'treatment',
  ).length

  return (
    <div className="border border-rulehard bg-surface">
      <div className="flex items-baseline justify-between border-b border-rule px-5 py-3.5">
        <span className="font-mono text-[11px] font-medium uppercase tracking-[0.18em] text-faint">
          Fig. 1 Switchback assignment
        </span>
        <span className="font-mono text-[11px] text-soft tabular-nums">
          time_block {String(epoch).padStart(3, '0')}
        </span>
      </div>

      <div className="p-5">
        <div
          className="grid gap-[5px]"
          style={{ gridTemplateColumns: `repeat(${COLS}, minmax(0, 1fr))` }}
          aria-hidden="true"
        >
          {Array.from({ length: CELLS }).map((_, i) => {
            const s = cellState(i, epoch)
            return (
              <div key={i} className="relative aspect-square">
                <div
                  className={`h-full w-full transition-colors duration-700 ${
                    s === 'treatment'
                      ? 'bg-violet'
                      : s === 'reference'
                        ? 'bg-paper-2'
                        : 'border border-rulehard bg-transparent'
                  }`}
                />
                {s === 'reference' && (
                  <span className="absolute left-1/2 top-1/2 h-1.5 w-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-teal" />
                )}
              </div>
            )
          })}
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-1.5 font-mono text-[10px] uppercase tracking-wider text-faint">
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 bg-violet" /> cohort included
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 border border-rulehard" /> held out
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-teal" /> reference point
          </span>
        </div>
      </div>

      <div className="border-t border-rule px-5 py-4">
        <div className="grid grid-cols-2 gap-x-6 gap-y-2 font-mono text-xs tabular-nums sm:grid-cols-4">
          <Readout k="cohorts in" v={String(treated)} />
          <Readout k="effect" v={effect.toFixed(3)} />
          <Readout k="lower bound" v={lower.toFixed(3)} />
          <Readout
            k="payable"
            v={payable ? 'yes' : 'no'}
            tone={payable ? 'text-good' : 'text-amber'}
          />
        </div>
        <p className="mt-3 text-xs leading-relaxed text-faint">
          Geographic cohorts rotate in and out of the evaluation model each time
          block. Rewards settle only on the conservative lower confidence bound
          of the estimated effect. The live service is never degraded.
        </p>
      </div>
    </div>
  )
}

function Readout({
  k,
  v,
  tone = 'text-ink',
}: {
  k: string
  v: string
  tone?: string
}) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-faint">{k}</div>
      <div className={`mt-0.5 text-sm font-semibold ${tone}`}>{v}</div>
    </div>
  )
}
