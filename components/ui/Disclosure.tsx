import {
  Disclosure as HeadlessDisclosure,
  DisclosureButton,
  DisclosurePanel,
} from "@headlessui/react";
import type { ReactNode } from "react";
import { ChevronDownIcon } from "./Icons";
import styles from "./Disclosure.module.css";

export default function Disclosure({
  label,
  children,
  className = "",
}: {
  label: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <HeadlessDisclosure>
      {({ open }) => (
        <div className={`${styles.root} ${open ? styles.open : ""} ${className}`.trim()}>
          <DisclosureButton className={styles.button}>
            <span>{label}</span>
            <ChevronDownIcon className={styles.chevron} />
          </DisclosureButton>
          <DisclosurePanel className={styles.panel}>{children}</DisclosurePanel>
        </div>
      )}
    </HeadlessDisclosure>
  );
}
