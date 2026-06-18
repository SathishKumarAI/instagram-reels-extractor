import * as React from "react";
import { cn } from "@/lib/utils";

export const Input = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(({ className, ...props }, ref) => (
  <input
    ref={ref}
    className={cn(
      "h-10 w-full rounded-lg border border-surface1 bg-mantle px-3 text-sm text-text",
      "placeholder:text-overlay0 focus:border-mauve focus:outline-none",
      className,
    )}
    {...props}
  />
));
Input.displayName = "Input";
