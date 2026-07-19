import Link from "next/link";
import { Button } from "@/components/ui/button";
export default function NotFound() { return <div className="grid min-h-full place-items-center p-8 text-center"><div><p className="text-sm font-medium text-primary">404</p><h1 className="mt-2 text-3xl font-semibold">Page not found</h1><p className="mt-3 text-sm text-muted-foreground">The page you requested does not exist.</p><Button asChild className="mt-6"><Link href="/">Return home</Link></Button></div></div>; }
