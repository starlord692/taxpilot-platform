import Link from "next/link";
import { Clock3 } from "lucide-react";
import { AuthCard } from "@/components/auth/auth-card";
import { Button } from "@/components/ui/button";
export default function SessionExpiredPage() { return <AuthCard title="Your session has expired" description="For your security, TaxPilot signed you out after your access token expired."><div className="rounded-xl border bg-muted/40 p-5 text-center"><Clock3 className="mx-auto size-7 text-muted-foreground" /><p className="mt-3 text-sm leading-6 text-muted-foreground">Sign in again to continue where you left off.</p></div><Button asChild className="mt-5 w-full"><Link href="/login">Sign in again</Link></Button></AuthCard>; }
