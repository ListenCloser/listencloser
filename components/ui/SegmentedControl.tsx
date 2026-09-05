import { Radio, RadioGroup } from "@headlessui/react";
import styles from "./SegmentedControl.module.css";

type SegmentedOption<T extends string> = {
  value: T;
  label: string;
  disabled?: boolean;
};

export default function SegmentedControl<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: SegmentedOption<T>[];
  onChange: (value: T) => void;
}) {
  return (
    <RadioGroup
      aria-label={label}
      value={value}
      onChange={(next) => onChange(next as T)}
      className={styles.root}
    >
      {options.map((option) => (
        <Radio
          key={option.value}
          value={option.value}
          disabled={option.disabled}
          className={styles.option}
        >
          {option.label}
        </Radio>
      ))}
    </RadioGroup>
  );
}
