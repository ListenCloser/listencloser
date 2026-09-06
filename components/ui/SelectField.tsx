import { forwardRef, type SelectHTMLAttributes } from "react";
import styles from "./SelectField.module.css";

const SelectField = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  function SelectField({ className = "", ...props }, ref) {
    return <select ref={ref} className={`${styles.select} ${className}`.trim()} {...props} />;
  },
);

export default SelectField;
