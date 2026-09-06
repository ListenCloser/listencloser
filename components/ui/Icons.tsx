import type { SVGProps } from "react";
import {
  ArrowRight,
  ChevronDown,
  Pause,
  Play,
  Plus,
  Repeat,
  Trash2,
  X,
} from "lucide-react";

export type IconProps = SVGProps<SVGSVGElement>;

const DEFAULT_SIZE = 16;
const DEFAULT_STROKE_WIDTH = 1.5;

function withDefaults(Icon: typeof X) {
  return function WrappedIcon(props: IconProps) {
    return <Icon size={DEFAULT_SIZE} strokeWidth={DEFAULT_STROKE_WIDTH} {...props} />;
  };
}

function withFilledDefaults(Icon: typeof Play) {
  return function WrappedIcon(props: IconProps) {
    return (
      <Icon
        size={DEFAULT_SIZE}
        strokeWidth={DEFAULT_STROKE_WIDTH}
        fill="currentColor"
        stroke="none"
        {...props}
      />
    );
  };
}

export const CloseIcon = withDefaults(X);
export const PlusIcon = withDefaults(Plus);
export const TrashIcon = withDefaults(Trash2);
export const LoopIcon = withDefaults(Repeat);
export const ChevronDownIcon = withDefaults(ChevronDown);
export const ArrowRightIcon = withDefaults(ArrowRight);
export const PlayIcon = withFilledDefaults(Play);
export const PauseIcon = withFilledDefaults(Pause);