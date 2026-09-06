"use client";

import Button, { IconButton } from "@/components/ui/Button";
import Dialog, { DialogBody, DialogHeader, DialogHeading } from "@/components/ui/Dialog";
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

  const close = () => {
    if (!busy) onOpenChange(false);
  };

  return (
    <>
      <section className={styles.discovery} aria-label="Add analysis">
        {!open && (
          <Button
            variant="ghost"
            size="compact"
            onClick={() => onOpenChange(true)}
            aria-expanded="false"
            aria-label="+ Add analysis"
          >
            <PlusIcon />
            <span>Add analysis</span>
          </Button>
        )}
      </section>

      <Dialog open={open} onClose={close} compact>
        <DialogHeader>
          <DialogHeading
            title={
              <span className={styles.dialogTitle}>
                <span>Add analysis</span>
                {sharedMaturity && <Qualifier>{sharedMaturity}</Qualifier>}
              </span>
            }
          />
          {!busy && (
            <IconButton compact variant="ghost" onClick={close} aria-label="Close analysis chooser">
              <CloseIcon />
            </IconButton>
          )}
        </DialogHeader>

        <DialogBody>
          <div className={styles.choices}>
            {options.map((option, index) => {
              const hasEarlierDuplicateAction = options
                .slice(0, index)
                .some((candidate) => candidate.actionLabel === option.actionLabel);

              return (
                <div className={styles.choice} key={option.id}>
                  <div className={styles.choiceCopy}>
                    <div className={styles.titleLine}>
                      <strong>{option.title}</strong>
                      {!sharedMaturity && <Qualifier>{option.maturity}</Qualifier>}
                    </div>
                    <p>{option.description}</p>
                  </div>
                  <Button
                    className={styles.choiceAction}
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
          </div>

          {notice && (
            <div className={styles.notice}>
              <InlineNotice tone={noticeRole === "alert" ? "danger" : "quiet"} role={noticeRole}>
                {notice}
              </InlineNotice>
            </div>
          )}
        </DialogBody>
      </Dialog>
    </>
  );
}
