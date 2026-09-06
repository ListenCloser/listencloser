import styles from "./EmptyWorkspaceSignal.module.css";

const LANES = ["Audio", "Notes", "Notation", "Evidence"] as const;

export default function EmptyWorkspaceSignal() {
  return (
    <div className={styles.signal} data-testid="empty-workspace-signal" aria-hidden="true">
      <div className={styles.header}>
        <span>One recording</span>
        <span>Shared musical time</span>
      </div>

      <div className={styles.body}>
        <div className={styles.ruler}>
          {Array.from({ length: 9 }, (_, index) => (
            <span key={index} className={styles.tick} />
          ))}
        </div>

        <div className={styles.lanes}>
          {LANES.map((lane) => (
            <div key={lane} className={styles.lane} data-lane={lane.toLowerCase()}>
              <span className={styles.label}>{lane}</span>
              <span className={styles.rail} />
            </div>
          ))}
          <span className={styles.alignmentGuide} />
        </div>
      </div>

      <div className={styles.footer}>Different views stay oriented to the same moment.</div>
    </div>
  );
}
