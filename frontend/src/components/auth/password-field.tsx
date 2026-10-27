"use client";
import { forwardRef, useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
interface PasswordFieldProps extends Omit<React.ComponentProps<"input">, "type"> { label: string; error?: string; }
export const PasswordField = forwardRef<HTMLInputElement, PasswordFieldProps>(({ label, error, id, className, ...props }, ref) => { const [visible, setVisible] = useState(false); const inputId = id ?? props.name; return <div className="space-y-2"><Label htmlFor={inputId}>{label}</Label><div className="relative"><Input ref={ref} id={inputId} type={visible ? "text" : "password"} className={cn("pr-10", error && "border-destructive focus:border-destructive focus:ring-destructive/10", className)} aria-invalid={Boolean(error)} aria-describedby={error ? `${inputId}-error` : undefined} {...props} /><button type="button" className="absolute right-1 top-1 grid size-8 place-items-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" onClick={() => setVisible((value) => !value)} aria-label={visible ? "Hide password" : "Show password"}>{visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}</button></div>{error && <p id={`${inputId}-error`} className="text-xs text-destructive">{error}</p>}</div>; });
PasswordField.displayName = "PasswordField";
