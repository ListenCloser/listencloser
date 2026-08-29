"use client";

import { cloneElement, useId, type ReactElement, type ReactNode } from "react";
import styles from "./Tooltip.module.css";

type TooltipTriggerProps = {
  "aria-describedby"?: string;
};

type TooltipPlacement = "top" | "left";

export default function Tooltip({
  content,
  children,
  placement = "top",
}: {
  content: ReactNode;
  children: ReactElement<TooltipTriggerProps>;
  placement?: TooltipPlacement;
}) {
  const id = useId();
  const existingDescription = children.props["aria-describedby"];
  const describedBy = [existingDescription, id].filter(Boolean).join(" ");
  const tooltipClassName = placement === "left"
    ? `${styles.tooltip} ${styles.tooltipLeft}`
    : styles.tooltip;

  return (
    <span className={styles.anchor}>
      {cloneElement(children, { "aria-describedby": describedBy })}
      <span id={id} className={tooltipClassName} role="tooltip">
        {content}
      </span>
    </span>
  );
}
