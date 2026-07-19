"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { ArrowRight, LoaderCircle } from "lucide-react";
import { useAuth } from "@/contexts/auth-context";
import { loginSchema, type LoginFormValues } from "@/features/auth/schemas/login-schema";
import { ApiClientError } from "@/lib/api/errors";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PasswordField } from "./password-field";

export function safeNextPath(value: string | null) { return value?.startsWith("/") && !value.startsWith("//") ? value : "/"; }
export function LoginForm() { const { login } = useAuth(); const router = useRouter(); const search = useSearchParams(); const { register, handleSubmit, formState: { errors, isSubmitting }, setError } = useForm<LoginFormValues>({ resolver: zodResolver(loginSchema), defaultValues: { email: "", password: "" } });
  const submit = handleSubmit(async (values) => { try { await login(loginSchema.parse(values)); router.replace(safeNextPath(search.get("next"))); } catch (error) { const apiError = error as ApiClientError; setError("root", { message: apiError.status === 401 ? "Email or password is incorrect." : apiError.status === 423 ? "Your account is temporarily locked. Please try again later." : apiError.message }); } });
  return <form onSubmit={submit} className="space-y-5" noValidate>{errors.root?.message && <Alert>{errors.root.message}</Alert>}<div className="space-y-2"><Label htmlFor="email">Email address</Label><Input id="email" type="email" autoComplete="email" autoCapitalize="none" aria-invalid={Boolean(errors.email)} aria-describedby={errors.email ? "email-error" : undefined} placeholder="you@company.com" {...register("email")} />{errors.email && <p id="email-error" className="text-xs text-destructive">{errors.email.message}</p>}</div><PasswordField label="Password" id="password" autoComplete="current-password" error={errors.password?.message} {...register("password")} /><div className="flex justify-end"><Link href="/forgot-password" className="text-xs font-medium text-primary hover:underline">Forgot password?</Link></div><Button type="submit" className="w-full" disabled={isSubmitting}>{isSubmitting ? <><LoaderCircle className="animate-spin" />Signing in…</> : <>Sign in<ArrowRight /></>}</Button></form>;
}
