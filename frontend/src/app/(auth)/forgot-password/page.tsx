import Link from "next/link";
import { KeyRound } from "lucide-react";
import { AuthCard } from "@/components/auth/auth-card";
import { Button } from "@/components/ui/button";
export default function ForgotPasswordPage() { return <AuthCard title="Password recovery" description="Password recovery is not available yet."><div className="rounded-xl border bg-muted/40 p-5 text-center"><KeyRound className="mx-auto size-7 text-muted-foreground" /><p className="mt-3 text-sm leading-6 text-muted-foreground">Please contact your TaxPilot administrator for help accessing your account.</p></div><Button asChild variant="outline" className="mt-5 w-full"><Link href="/login">Return to sign in</Link></Button></AuthCard>; }
