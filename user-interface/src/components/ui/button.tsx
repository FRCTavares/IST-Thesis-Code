import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/utils/cn";

const buttonVariants = cva(
  "inline-flex items-center justify-center rounded-md border text-sm font-medium transition-all duration-150 disabled:pointer-events-none disabled:opacity-60",
  {
    variants: {
      variant: {
        default:
          "border-slate-700 bg-slate-900/80 text-slate-200 hover:border-slate-500 hover:bg-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/45",
        active:
          "border-sky-400/60 bg-sky-500/20 text-sky-200 shadow-[0_0_18px_rgba(56,189,248,0.2)] hover:bg-sky-500/28 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/60",
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
