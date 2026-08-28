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
      <path
        d="M3 6.2h18M3 12h18M3 17.8h18"
        stroke="currentColor"
        strokeWidth="1"
        strokeLinecap="round"
        opacity="0.24"
      />
      <path
        d="M3.6 15.2c2.2 0 2.45-7.9 4.7-7.9 2.45 0 2.75 9.6 5.15 9.6 2.5 0 2.7-11.1 5.35-11.1 1.1 0 1.55 2.15 2.2 3.05"
        stroke="currentColor"
        strokeWidth="1.9"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="8.3" cy="7.3" r="1.15" fill="currentColor" />
      <circle cx="18.8" cy="5.8" r="1.15" fill="currentColor" />
    </svg>
  );
}
