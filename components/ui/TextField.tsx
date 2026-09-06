import { forwardRef, type InputHTMLAttributes } from "react";
import styles from "./TextField.module.css";

type TextFieldProps = InputHTMLAttributes<HTMLInputElement>;

const TextField = forwardRef<HTMLInputElement, TextFieldProps>(function TextField(
  { className = "", ...props },
  ref,
) {
  return <input ref={ref} className={`${styles.field} ${className}`.trim()} {...props} />;
});

export default TextField;
