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

const GITHUB_URL = 'https://github.com/ThirdChildren/causal_rewards_solana'

function GithubIcon({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" className={className} fill="currentColor" aria-hidden="true">
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.6 7.6 0 0 1 4 0c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
    </svg>
  )
}

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

        <div className="flex items-center gap-2">
          <a
            href={GITHUB_URL}
            target="_blank"
            rel="noopener noreferrer"
            aria-label="View the project on GitHub"
            className="inline-flex h-9 items-center gap-2 border border-rule bg-surface px-2.5 text-sm font-medium text-ink transition-colors hover:border-ink sm:px-3.5"
          >
            <GithubIcon className="h-4 w-4" />
            <span className="hidden sm:inline">GitHub</span>
          </a>
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
        </div>
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
