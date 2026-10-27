"use client";
import { CircleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
export function ErrorState({ title, description, onRetry }: { title: string; description?: string; onRetry?: () => void }) { return <div className="grid min-h-[50vh] place-items-center p-6 text-center"><div className="max-w-sm"><CircleAlert className="mx-auto size-8 text-destructive" /><h2 className="mt-4 text-lg font-semibold">{title}</h2>{description && <p className="mt-2 text-sm text-muted-foreground">{description}</p>}{onRetry && <Button variant="outline" className="mt-5" onClick={onRetry}>Try again</Button>}</div></div>; }
