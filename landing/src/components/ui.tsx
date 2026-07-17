import type { ReactNode } from 'react'

export function Section({
  id,
  children,
  className = '',
}: {
  id?: string
  children: ReactNode
  className?: string
}) {
  return (
    <section id={id} className={`mx-auto w-full max-w-6xl px-6 ${className}`}>
      {children}
    </section>
  )
}

/**
 * Section header in spec-sheet style: a full hairline rule on top,
 * a mono index number on the left and the section label on the right,
 * then a serif title.
 */
export function SectionTitle({
  num,
  eyebrow,
  title,
  lead,
}: {
  num: string
  eyebrow: string
  title: ReactNode
  lead?: ReactNode
}) {
  return (
    <div className="border-t border-rulehard pt-5">
      <div className="flex items-baseline justify-between font-mono text-[11px] font-medium uppercase tracking-[0.18em] text-faint">
        <span>{num}</span>
        <span>{eyebrow}</span>
      </div>
      <h2 className="mt-6 max-w-3xl text-balance font-serif text-3xl font-semibold leading-[1.15] tracking-tight text-ink sm:text-[2.6rem]">
        {title}
      </h2>
      {lead && (
        <p className="mt-5 max-w-2xl text-[1.05rem] leading-relaxed text-soft">
          {lead}
        </p>
      )}
    </div>
  )
}

export function Panel({
  children,
  className = '',
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <div className={`border border-rule bg-surface ${className}`}>{children}</div>
  )
}

export function MonoLabel({ children }: { children: ReactNode }) {
  return (
    <span className="font-mono text-[11px] font-medium uppercase tracking-[0.18em] text-faint">
      {children}
    </span>
  )
}

export function Check({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <path
        d="M4 10.5 8 14.5 16 6"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}
