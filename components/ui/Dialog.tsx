import {
  Dialog as HeadlessDialog,
  DialogBackdrop,
  DialogPanel,
  DialogTitle,
} from "@headlessui/react";
import type { ReactNode } from "react";
import styles from "./Dialog.module.css";

export default function Dialog({
  open,
  onClose,
  children,
  compact = false,
}: {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  compact?: boolean;
}) {
  return (
    <HeadlessDialog open={open} onClose={onClose}>
      <DialogBackdrop className={styles.backdrop} />
      <div className={styles.viewport}>
        <DialogPanel className={`${styles.panel}${compact ? ` ${styles.compact}` : ""}`}>
          {children}
        </DialogPanel>
      </div>
    </HeadlessDialog>
  );
}

export function DialogHeader({ children }: { children: ReactNode }) {
  return <div className={styles.header}>{children}</div>;
}

export function DialogHeading({
  title,
  description,
}: {
  title: ReactNode;
  description?: ReactNode;
}) {
  return (
    <div className={styles.heading}>
      <DialogTitle className={styles.title}>{title}</DialogTitle>
      {description ? <p className={styles.description}>{description}</p> : null}
    </div>
  );
}

export function DialogBody({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`${styles.body} ${className}`.trim()}>{children}</div>;
}

export function DialogFooter({ children }: { children: ReactNode }) {
  return <div className={styles.footer}>{children}</div>;
}
