import Link from "next/link";
import { AuthCard } from "@/components/auth/auth-card";
import { RegisterForm } from "@/components/auth/register-form";
export default function RegisterPage() { return <AuthCard className="max-w-[520px]" title="Create your account" description="Set up your TaxPilot identity. Your organization can activate access after registration." footer={<>Already have an account? <Link className="font-medium text-primary hover:underline" href="/login">Sign in</Link></>}><RegisterForm /></AuthCard>; }
