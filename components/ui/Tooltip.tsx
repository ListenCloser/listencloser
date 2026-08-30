"use client";

import { cloneElement, useId, type CSSProperties, type ReactElement, type ReactNode } from "react";
import styles from "./Tooltip.module.css";

type TooltipTriggerProps = {
  "aria-describedby"?: string;
  style?: CSSProperties;
};

type TooltipPlacement = "top" | "left";

export default function Tooltip({
  content,
  children,
  placement = "top",
  stretch = false,
}: {
  content: ReactNode;
  children: ReactElement<TooltipTriggerProps>;
  placement?: TooltipPlacement;
  stretch?: boolean;
}) {
  const id = useId();
  const existingDescription = children.props["aria-describedby"];
  const describedBy = [existingDescription, id].filter(Boolean).join(" ");
  const tooltipClassName = placement === "left"
    ? `${styles.tooltip} ${styles.tooltipLeft}`
    : styles.tooltip;
  const trigger = cloneElement(children, {
    "aria-describedby": describedBy,
    ...(stretch ? { style: { ...children.props.style, width: "100%" } } : {}),
  });

  return (
    <span className={styles.anchor} style={stretch ? { width: "100%" } : undefined}>
      {trigger}
      <span id={id} className={tooltipClassName} role="tooltip">
        {content}
      </span>
    </span>
  );
}
