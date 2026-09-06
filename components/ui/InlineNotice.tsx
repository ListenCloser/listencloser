import type { HTMLAttributes, ReactNode } from "react";
import styles from "./InlineNotice.module.css";

export default function InlineNotice({
  children,
  tone = "default",
  className = "",
  ...props
}: HTMLAttributes<HTMLDivElement> & {
  children: ReactNode;
  tone?: "default" | "danger" | "quiet";
}) {
  return (
    <div
      className={`${styles.notice} ${tone === "default" ? "" : styles[tone]} ${className}`.trim()}
      {...props}
    >
      {children}
    </div>
  );
}
