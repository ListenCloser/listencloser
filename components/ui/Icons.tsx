import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

function IconBase({ children, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 16 16" fill="none" aria-hidden="true" {...props}>
      {children}
    </svg>
  );
}

export function CloseIcon(props: IconProps) {
  return <IconBase {...props}><path d="M3 3l10 10M13 3 3 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></IconBase>;
}

export function PlusIcon(props: IconProps) {
  return <IconBase {...props}><path d="M8 2.5v11M2.5 8h11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></IconBase>;
}

export function TrashIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M3.5 4.5h9M6 2.75h4M5 4.5l.5 8.25h5l.5-8.25M7 6.5v4M9 6.5v4" stroke="currentColor" strokeWidth="1.35" strokeLinecap="round" strokeLinejoin="round" />
    </IconBase>
  );
}

export function PlayIcon(props: IconProps) {
  return <IconBase {...props}><path d="M5 3.25 12.5 8 5 12.75z" fill="currentColor" /></IconBase>;
}

export function PauseIcon(props: IconProps) {
  return <IconBase {...props}><rect x="3" y="2.5" width="3" height="11" rx="0.8" fill="currentColor" /><rect x="10" y="2.5" width="3" height="11" rx="0.8" fill="currentColor" /></IconBase>;
}

export function LoopIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M11 3h3v3M14 3l-3.25 3.25M5 13H2v-3M2 13l3.25-3.25M13.5 6A5.5 5.5 0 0 0 4 3.75M2.5 10A5.5 5.5 0 0 0 12 12.25" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
    </IconBase>
  );
}

export function ChevronDownIcon(props: IconProps) {
  return <IconBase {...props}><path d="m4.5 6 3.5 3.5L11.5 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></IconBase>;
}

export function ArrowRightIcon(props: IconProps) {
  return <IconBase {...props}><path d="M3 8h9M8.5 3.5 13 8l-4.5 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></IconBase>;
}
