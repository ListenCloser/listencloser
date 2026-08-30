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
      <g
        stroke="currentColor"
        strokeWidth="1.35"
        strokeLinecap="round"
      >
        <path d="M3.8 5.4h6.3M14.7 5.4h4.6" opacity="0.62" />
        <path d="M2.9 9.8h7.2M14.7 9.8h6.4" opacity="0.82" />
        <path d="M4.2 14.2h5.9M14.7 14.2h5.2" opacity="0.82" />
        <path d="M3.4 18.6h6.7M14.7 18.6h5.9" opacity="0.62" />
      </g>
      <path
        d="M12.4 3.2v17.6"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    </svg>
  );
}
