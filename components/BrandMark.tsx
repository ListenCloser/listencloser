export default function BrandMark({ size = 22, className = "" }: { size?: number; className?: string }) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <path d="M3 6.25h18M3 12h18M3 17.75h18" stroke="currentColor" strokeWidth="1.15" strokeLinecap="round" opacity="0.38" />
      <path
        d="M4 15.4c1.55 0 2.25-7.4 4.15-7.4 1.75 0 2.3 8.4 4.2 8.4 1.85 0 2.4-10.3 4.35-10.3 1.15 0 1.7 3.05 3.3 3.05"
        stroke="currentColor"
        strokeWidth="1.85"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="8.15" cy="8" r="1.25" fill="currentColor" />
      <circle cx="12.35" cy="16.4" r="1.25" fill="currentColor" />
      <circle cx="16.7" cy="6.1" r="1.25" fill="currentColor" />
    </svg>
  );
}
