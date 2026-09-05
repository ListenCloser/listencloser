import type { ReactNode } from "react";
import styles from "./Qualifier.module.css";

export default function Qualifier({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <span className={`${styles.qualifier} ${className}`.trim()}>{children}</span>;
}
