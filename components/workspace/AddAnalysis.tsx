"use client";

import Button, { IconButton } from "@/components/ui/Button";
import { CloseIcon, PlusIcon } from "@/components/ui/Icons";
import InlineNotice from "@/components/ui/InlineNotice";
import Qualifier from "@/components/ui/Qualifier";
import styles from "./AddAnalysis.module.css";

export type AddAnalysisOption = {
  id: string;
  title: string;
  description: string;
  maturity: "Experimental";
  actionLabel: string;
  onAction: () => void;
  busy?: boolean;
  disabled?: boolean;
};

export default function AddAnalysis({
  open,
  onOpenChange,
  options,
  notice,
  noticeRole = "status",
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  options: AddAnalysisOption[];
  notice?: string | null;
  noticeRole?: "alert" | "status";
}) {
  const busy = options.some((option) => option.busy);
  const sharedMaturity =
    options.length > 1 && options.every((option) => option.maturity === options[0]?.maturity)
      ? options[0]?.maturity
      : null;

  return (
    <section className={`${styles.discovery}${open ? ` ${styles.open}` : ""}`} aria-label="Add analysis">
      {!open ? (
        <Button variant="ghost" size="compact" onClick={() => onOpenChange(true)} aria-expanded="false">
          <PlusIcon />
          <span>Add analysis</span>
        </Button>
      ) : (
        <div className={styles.chooser}>
          <div className={styles.chooserHeader}>
            <div className={styles.titleLine}>
              <strong>Add analysis</strong>
              {sharedMaturity && <Qualifier>{sharedMaturity}</Qualifier>}
            </div>
            {!busy && (
              <IconButton compact variant="ghost" onClick={() => onOpenChange(false)} aria-label="Close analysis chooser">
                <CloseIcon />
              </IconButton>
            )}
          </div>
          {options.map((option, index) => {
            const hasEarlierDuplicateAction = options
              .slice(0, index)
              .some((candidate) => candidate.actionLabel === option.actionLabel);

            return (
              <div className={styles.choice} key={option.id}>
                <div>
                  <div className={styles.titleLine}>
                    <strong>{option.title}</strong>
                    {!sharedMaturity && <Qualifier>{option.maturity}</Qualifier>}
                  </div>
                  <p>{option.description}</p>
                </div>
                <Button
                  size="compact"
                  onClick={option.onAction}
                  disabled={option.disabled || option.busy}
                  aria-label={
                    hasEarlierDuplicateAction ? `${option.actionLabel} ${option.title}` : undefined
                  }
                >
                  {option.actionLabel}
                </Button>
              </div>
            );
          })}
          {notice && (
            <div className={styles.notice}>
              <InlineNotice tone={noticeRole === "alert" ? "danger" : "quiet"} role={noticeRole}>
                {notice}
              </InlineNotice>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
