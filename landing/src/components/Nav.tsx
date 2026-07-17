import { useEffect, useState } from 'react'
import { Logo } from './Logo'

const links = [
  { href: '#problem', label: 'Problem', num: '01' },
  { href: '#approach', label: 'Approach', num: '02' },
  { href: '#workflow', label: 'Workflow', num: '03' },
  { href: '#solana', label: 'Solana', num: '04' },
  { href: '#pilot', label: 'Pilot', num: '05' },
  { href: '#roadmap', label: 'Roadmap', num: '07' },
  { href: '#grant', label: 'Grant fit', num: '08' },
]

export function Nav() {
  const [scrolled, setScrolled] = useState(false)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <header
      className={`fixed inset-x-0 top-0 z-50 border-b transition-colors duration-300 ${
        scrolled
          ? 'border-rule bg-paper/95 backdrop-blur-sm'
          : 'border-transparent bg-paper'
      }`}
    >
      <nav className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-6">
        <a href="#top" className="flex items-center gap-3">
          <Logo className="h-7 w-7" />
          <span className="text-sm font-semibold tracking-tight text-ink">
            Causal Rewards Protocol
          </span>
          <span className="hidden font-mono text-[10px] font-medium uppercase tracking-[0.18em] text-faint sm:inline">
            Concept note v1.0
          </span>
        </a>

        <div className="hidden items-center gap-6 lg:flex">
          {links.map((l) => (
            <a
              key={l.href}
              href={l.href}
              className="group flex items-baseline gap-1.5 text-sm font-medium text-soft transition-colors hover:text-ink"
            >
              <span className="font-mono text-[10px] text-faint group-hover:text-violet">
                {l.num}
              </span>
              {l.label}
            </a>
          ))}
        </div>

        <button
          type="button"
          aria-label="Toggle menu"
          onClick={() => setOpen((v) => !v)}
          className="inline-flex h-9 w-9 items-center justify-center border border-rule bg-surface text-soft lg:hidden"
        >
          <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2">
            {open ? (
              <path d="M6 6 18 18 M18 6 6 18" strokeLinecap="round" />
            ) : (
              <path d="M4 7h16 M4 12h16 M4 17h16" strokeLinecap="round" />
            )}
          </svg>
        </button>
      </nav>

      {open && (
        <div className="border-t border-rule bg-paper px-6 py-4 lg:hidden">
          <div className="flex flex-col">
            {links.map((l) => (
              <a
                key={l.href}
                href={l.href}
                onClick={() => setOpen(false)}
                className="flex items-baseline gap-3 border-b border-rule py-3 text-sm font-medium text-soft last:border-b-0 hover:text-ink"
              >
                <span className="font-mono text-[10px] text-faint">{l.num}</span>
                {l.label}
              </a>
            ))}
          </div>
        </div>
      )}
    </header>
  )
}
