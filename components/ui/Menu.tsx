import {
  Menu as HeadlessMenu,
  MenuButton as HeadlessMenuButton,
  MenuItem as HeadlessMenuItem,
  MenuItems as HeadlessMenuItems,
} from "@headlessui/react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import Button, { type ButtonVariant } from "./Button";
import styles from "./Menu.module.css";

export function Menu({ children }: { children: ReactNode }) {
  return <HeadlessMenu as="div" className={styles.root}>{children}</HeadlessMenu>;
}

export function MenuButton({
  children,
  variant = "secondary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }) {
  return (
    <HeadlessMenuButton
      as={Button}
      variant={variant}
      className={className}
      {...props}
    >
      {children}
    </HeadlessMenuButton>
  );
}

export function MenuItems({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <HeadlessMenuItems className={`${styles.items} ${className}`.trim()}>{children}</HeadlessMenuItems>;
}

export function MenuItem({
  children,
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <HeadlessMenuItem>
      <button type="button" className={`${styles.item} ${className}`.trim()} {...props}>
        {children}
      </button>
    </HeadlessMenuItem>
  );
}
