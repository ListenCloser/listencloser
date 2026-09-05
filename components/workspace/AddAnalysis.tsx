"use client";

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
    <section
      className={`${styles.discovery}${open ? ` ${styles.open}` : ""}`}
      aria-label="Add analysis"
    >
      {!open ? (
        <button
          type="button"
          className={styles.addAnalysis}
          onClick={() => onOpenChange(true)}
          aria-expanded="false"
        >
          + Add analysis
        </button>
      ) : (
        <div className={styles.chooser}>
          <div className={styles.chooserHeader}>
            <div className={styles.titleLine}>
              <strong>Add analysis</strong>
              {sharedMaturity && <span className={styles.experimental}>{sharedMaturity}</span>}
            </div>
            {!busy && (
              <button
                type="button"
                className={styles.closeChooser}
                onClick={() => onOpenChange(false)}
                aria-label="Close analysis chooser"
              >
                ×
              </button>
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
                    {!sharedMaturity && <span className={styles.experimental}>{option.maturity}</span>}
                  </div>
                  <p>{option.description}</p>
                </div>
                <button
                  type="button"
                  className={styles.action}
                  onClick={option.onAction}
                  disabled={option.disabled || option.busy}
                  aria-label={
                    hasEarlierDuplicateAction ? `${option.actionLabel} ${option.title}` : undefined
                  }
                >
                  {option.actionLabel}
                </button>
              </div>
            );
          })}
          {notice && (
            <p className={styles.notice} role={noticeRole}>
              {notice}
            </p>
          )}
        </div>
      )}
    </section>
  );
}
