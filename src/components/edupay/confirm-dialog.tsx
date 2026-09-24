"use client";

import * as React from "react";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { cn } from "@/lib/utils";

interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: React.ReactNode;
  /** Label on the destructive confirm button. */
  actionLabel?: string;
  cancelLabel?: string;
  /** Variant of the confirm button (defaults to default). */
  actionVariant?: "default" | "destructive" | "outline";
  actionClassName?: string;
  /** Disable the action button (e.g. while waiting for a network call). */
  loading?: boolean;
  /** Called when the user confirms. Awaitable. */
  onConfirm: () => void | Promise<void>;
}

/**
 * Reusable confirmation dialog for destructive / financial actions:
 * reversal requests, reversal approval, payment verify, reconciliation
 * line resolution, user deactivation.
 *
 * Per the brief: must show the action + entity + amount (for financial)
 * and require a second click to confirm. The dialog itself is the first
 * click (the trigger); the Action button inside is the second click.
 */
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  actionLabel = "Confirm",
  cancelLabel = "Cancel",
  actionVariant = "default",
  actionClassName,
  loading = false,
  onConfirm,
}: ConfirmDialogProps) {
  async function handleAction(e: React.MouseEvent) {
    e.preventDefault();
    try {
      await onConfirm();
      onOpenChange(false);
    } catch {
      // Caller is responsible for surfacing the error (toast/alert).
      // Keep the dialog open so the user can retry.
    }
  }

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div className="text-sm text-slate-600 space-y-1">
              {description}
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={loading}>{cancelLabel}</AlertDialogCancel>
          <AlertDialogAction
            onClick={handleAction}
            disabled={loading}
            className={cn(
              actionVariant === "destructive" &&
                "bg-rose-600 text-white hover:bg-rose-700",
              actionVariant === "outline" &&
                "border-slate-300 bg-white text-slate-800 hover:bg-slate-100",
              actionClassName,
            )}
          >
            {loading ? (
              <Loader2 className="size-4 animate-spin" />
            ) : null}
            {actionLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

/** Convenience Button used inside a dialog body to open a nested confirm. */
export function ConfirmTriggerButton({
  children,
  onClick,
  className,
  disabled,
}: {
  children: React.ReactNode;
  onClick: () => void;
  className?: string;
  disabled?: boolean;
}) {
  return (
    <Button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={className}
    >
      {children}
    </Button>
  );
}
