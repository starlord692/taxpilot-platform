"use client";
import Link from "next/link";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { CheckCircle2, LoaderCircle } from "lucide-react";
import { useAuth } from "@/contexts/auth-context";
import { registerSchema, type RegisterFormValues } from "@/features/auth/schemas/register-schema";
import { ApiClientError } from "@/lib/api/errors";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PasswordField } from "./password-field";

function Field({ id, label, error, ...props }: React.ComponentProps<typeof Input> & { id: string; label: string; error?: string }) { return <div className="space-y-2"><Label htmlFor={id}>{label}</Label><Input id={id} aria-invalid={Boolean(error)} aria-describedby={error ? `${id}-error` : undefined} {...props} />{error && <p id={`${id}-error`} className="text-xs text-destructive">{error}</p>}</div>; }
export function RegisterForm() { const { register: createAccount } = useAuth(); const { register, handleSubmit, formState: { errors, isSubmitting, isSubmitSuccessful }, setError } = useForm<RegisterFormValues>({ resolver: zodResolver(registerSchema), defaultValues: { first_name: "", last_name: "", display_name: "", email: "", password: "", confirm_password: "" } });
  const submit = handleSubmit(async (values) => { try { const parsed = registerSchema.parse(values); await createAccount({ first_name: parsed.first_name, last_name: parsed.last_name, display_name: parsed.display_name || undefined, email: parsed.email, password: parsed.password }); } catch (error) { const apiError = error as ApiClientError; setError("root", { message: apiError.status === 409 ? "An account already exists for this email address." : apiError.message }); } });
  if (isSubmitSuccessful && !errors.root) return <div className="py-4 text-center" role="status"><span className="mx-auto grid size-11 place-items-center rounded-full bg-emerald-500/10 text-emerald-600"><CheckCircle2 className="size-6" /></span><h2 className="mt-4 text-lg font-semibold">Account created</h2><p className="mt-2 text-sm leading-6 text-muted-foreground">Your account was registered successfully. Continue to sign in when your account is active.</p><Button asChild className="mt-6 w-full"><Link href="/login">Continue to sign in</Link></Button></div>;
  return <form onSubmit={submit} className="space-y-5" noValidate>{errors.root?.message && <Alert>{errors.root.message}</Alert>}<div className="grid gap-4 sm:grid-cols-2"><Field id="first_name" label="First name" autoComplete="given-name" error={errors.first_name?.message} {...register("first_name")} /><Field id="last_name" label="Last name" autoComplete="family-name" error={errors.last_name?.message} {...register("last_name")} /></div><Field id="display_name" label="Display name (optional)" autoComplete="nickname" error={errors.display_name?.message} {...register("display_name")} /><Field id="register_email" label="Email address" type="email" autoComplete="email" autoCapitalize="none" placeholder="you@company.com" error={errors.email?.message} {...register("email")} /><PasswordField label="Password" id="new_password" autoComplete="new-password" error={errors.password?.message} {...register("password")} /><p className="-mt-3 text-xs leading-5 text-muted-foreground">At least 12 characters with uppercase, lowercase, number, and special character.</p><PasswordField label="Confirm password" id="confirm_password" autoComplete="new-password" error={errors.confirm_password?.message} {...register("confirm_password")} /><Button type="submit" className="w-full" disabled={isSubmitting}>{isSubmitting ? <><LoaderCircle className="animate-spin" />Creating account…</> : "Create account"}</Button></form>;
}
