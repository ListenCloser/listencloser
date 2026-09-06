"use client";

import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import type { ReactElement, ReactNode } from "react";
import styles from "./Tooltip.module.css";

type TooltipTriggerProps = {
  disabled?: boolean;
};

type TooltipPlacement = "top" | "left";

const HOVER_DELAY_MS = 280;

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
  const disabled = children.props.disabled === true;

  return (
    <TooltipPrimitive.Provider delayDuration={HOVER_DELAY_MS} disableHoverableContent>
      <TooltipPrimitive.Root>
        {disabled ? (
          <TooltipPrimitive.Trigger asChild>
            <span
              className={`${styles.disabledAnchor}${stretch ? ` ${styles.stretchAnchor}` : ""}`}
              data-tooltip-disabled-trigger=""
            >
              {children}
            </span>
          </TooltipPrimitive.Trigger>
        ) : (
          <TooltipPrimitive.Trigger asChild className={stretch ? styles.stretchTrigger : undefined}>
            {children}
          </TooltipPrimitive.Trigger>
        )}

        <TooltipPrimitive.Portal>
          <TooltipPrimitive.Content
            className={styles.tooltip}
            side={placement}
            sideOffset={8}
            collisionPadding={8}
          >
            {content}
            {placement === "top" && (
              <TooltipPrimitive.Arrow className={styles.arrow} width={8} height={4} />
            )}
          </TooltipPrimitive.Content>
        </TooltipPrimitive.Portal>
      </TooltipPrimitive.Root>
    </TooltipPrimitive.Provider>
  );
}
