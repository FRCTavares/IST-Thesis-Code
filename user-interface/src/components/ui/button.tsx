import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/utils/cn";

const buttonVariants = cva(
  "inline-flex items-center justify-center rounded-md border text-sm font-medium transition-all duration-150 disabled:pointer-events-none disabled:opacity-60",
  {
    variants: {
      variant: {
        default:
          "border-zinc-700 bg-zinc-900/80 text-zinc-200 hover:border-zinc-500 hover:bg-zinc-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-500/45",
        active:
          "border-zinc-500/70 bg-zinc-700/40 text-zinc-100 shadow-[0_0_14px_rgba(100,116,139,0.2)] hover:bg-zinc-700/55 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-400/60",
        danger:
          "border-red-500/60 bg-red-500/20 text-red-200 hover:bg-red-500/28 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400/55",
      },
      size: {
        default: "h-8 px-3 py-1",
        sm: "h-7 px-2.5 py-1",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => {
    return <button className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />;
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };
