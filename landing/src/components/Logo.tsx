export function Logo({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden="true">
      <rect width="32" height="32" rx="3" fill="#1c1d21" />
      <path
        d="M7 21 L13 12 L19 17 L25 8"
        fill="none"
        stroke="#f6f4ed"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="7" cy="21" r="2.1" fill="#5b21b6" />
      <circle cx="25" cy="8" r="2.1" fill="#0f766e" />
    </svg>
  )
}
