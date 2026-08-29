"use client";

import { cloneElement, useId, type ReactElement, type ReactNode } from "react";
import styles from "./Tooltip.module.css";

type TooltipTriggerProps = {
  "aria-describedby"?: string;
};

export default function Tooltip({
  content,
  children,
}: {
  content: ReactNode;
  children: ReactElement<TooltipTriggerProps>;
}) {
  const id = useId();
  const existingDescription = children.props["aria-describedby"];
  const describedBy = [existingDescription, id].filter(Boolean).join(" ");

  return (
    <span className={styles.anchor}>
      {cloneElement(children, { "aria-describedby": describedBy })}
      <span id={id} className={styles.tooltip} role="tooltip">
        {content}
      </span>
    </span>
  );
}
