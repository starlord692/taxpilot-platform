import { Suspense } from "react";
import Link from "next/link";
import { AuthCard } from "@/components/auth/auth-card";
import { LoginForm } from "@/components/auth/login-form";
import { Skeleton } from "@/components/ui/skeleton";
import { isPreviewMode } from "@/lib/env";

export default function LoginPage() {
  const footer = isPreviewMode ? <span className="flex flex-col gap-2"><span>Development preview is enabled</span><Link className="font-medium text-primary hover:underline" href="/">Open preview workspace</Link></span> : <>New to TaxPilot? <Link className="font-medium text-primary hover:underline" href="/register">Create an account</Link></>;
  return <AuthCard title="Welcome back" description="Sign in to continue to your TaxPilot workspace." footer={footer}><Suspense fallback={<div className="space-y-5"><Skeleton className="h-16" /><Skeleton className="h-16" /><Skeleton className="h-10" /></div>}><LoginForm /></Suspense></AuthCard>;
}
