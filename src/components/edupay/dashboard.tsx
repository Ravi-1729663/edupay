"use client";

import * as React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { LogOut } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Nav, type ViewKey } from "@/components/edupay/nav";
import { IntegrityPanel } from "@/components/edupay/integrity-panel";
import { StudentsPanel } from "@/components/edupay/students-panel";
import { UsersPanel } from "@/components/edupay/users-panel";
import { StudentFees } from "@/components/edupay/student-fees";
import { ChaosPanel } from "@/components/edupay/chaos-panel";
import { FinanceDashboard } from "@/components/edupay/finance-dashboard";
import { PaymentHistory } from "@/components/edupay/payment-history";
import { PaymentDetailsModal } from "@/components/edupay/payment-details";
import { StudentFeeAccountModal } from "@/components/edupay/student-fee-account";
import { ReconciliationDashboard } from "@/components/edupay/reconciliation-dashboard";
import { ReconciliationExceptions } from "@/components/edupay/reconciliation-exceptions";
import { AuditHistory } from "@/components/edupay/audit-history";
import { Footer } from "@/components/edupay/footer";
import { clearToken, type Role, type User } from "@/lib/api";

interface DashboardProps {
  user: User;
  onSignOut: () => void;
}

interface ReconSubState {
  view: "list" | "exceptions";
  batchId: string | null;
}

export function Dashboard({ user, onSignOut }: DashboardProps) {
  const role: Role = user.role;
  const [activeView, setActiveView] = React.useState<ViewKey>(
    role === "STUDENT" ? "fees" : "students",
  );

  // Reconciliation sub-view: list or exceptions-for-batch.
  const [reconSub, setReconSub] = React.useState<ReconSubState>({
    view: "list",
    batchId: null,
  });

  // Modals.
  const [openPaymentId, setOpenPaymentId] = React.useState<string | null>(null);
  const [openStudentId, setOpenStudentId] = React.useState<string | null>(null);

  // For Payment History scoped to a student (when opened from Student Fee Account).
  const [scopedStudentId, setScopedStudentId] = React.useState<string | null>(null);

  function handleSignOut() {
    clearToken();
    onSignOut();
  }

  function openPayment(paymentId: string) {
    setOpenPaymentId(paymentId);
  }

  function openStudentAccount(studentId: string) {
    setOpenStudentId(studentId);
  }

  function openStudentPayments(studentId: string) {
    // Called from StudentFeeAccountModal's "view payments" button — the
    // first arg in that callback is the student id (a slight reuse from
    // the modal). Scope Payment History to this student + switch tab.
    setScopedStudentId(studentId);
    setOpenStudentId(null);
    setActiveView("payments");
  }

  // When the user clicks the "Students" tab, clear any scoped student id
  // for Payment History (so they see all payments again).
  React.useEffect(() => {
    if (activeView !== "payments") setScopedStudentId(null);
    if (activeView !== "recon") {
      setReconSub({ view: "list", batchId: null });
    }
  }, [activeView]);

  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      <Nav
        user={user}
        activeView={activeView}
        onChange={(v) => setActiveView(v)}
        onSignOut={handleSignOut}
      />

      <main className="flex-1 mx-auto max-w-7xl w-full px-4 sm:px-6 lg:px-8 py-6">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeView + (reconSub.view === "exceptions" ? reconSub.batchId ?? "" : "")}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.15 }}
          >
            {activeView === "finance" &&
            (role === "ADMIN" || role === "FINANCE_MANAGER") ? (
              <FinanceDashboard onOpenPayment={openPayment} />
            ) : null}

            {activeView === "students" &&
            (role === "ADMIN" ||
              role === "FINANCE_MANAGER" ||
              role === "FINANCE_STAFF") ? (
              <StudentsPanel onOpenStudent={openStudentAccount} />
            ) : null}

            {activeView === "fees" && role === "STUDENT" && user.student_id ? (
              <StudentFees studentId={user.student_id} />
            ) : null}

            {activeView === "fees" && role === "STUDENT" && !user.student_id ? (
              <NoStudentIdNote onSignOut={handleSignOut} />
            ) : null}

            {activeView === "payments" ? (
              <PaymentHistory
                role={role}
                studentId={
                  role === "STUDENT" ? user.student_id : scopedStudentId
                }
                onOpenPayment={openPayment}
              />
            ) : null}

            {activeView === "recon" &&
            (role === "ADMIN" || role === "FINANCE_MANAGER") ? (
              reconSub.view === "list" ? (
                <ReconciliationDashboard
                  onOpenBatch={(batchId) =>
                    setReconSub({ view: "exceptions", batchId })
                  }
                />
              ) : (
                <ReconciliationExceptions
                  batchId={reconSub.batchId!}
                  onBack={() => setReconSub({ view: "list", batchId: null })}
                />
              )
            ) : null}

            {activeView === "audit" &&
            (role === "ADMIN" || role === "FINANCE_MANAGER") ? (
              <AuditHistory />
            ) : null}

            {activeView === "integrity" &&
            (role === "ADMIN" || role === "FINANCE_MANAGER") ? (
              <IntegrityPanel />
            ) : null}

            {activeView === "users" && role === "ADMIN" ? <UsersPanel /> : null}

            {activeView === "chaos" && role === "ADMIN" ? (
              <ChaosPanel />
            ) : null}
          </motion.div>
        </AnimatePresence>
      </main>

      <Footer />

      {/* Modals */}
      <PaymentDetailsModal
        paymentId={openPaymentId}
        role={role}
        onClose={() => setOpenPaymentId(null)}
      />
      <StudentFeeAccountModal
        studentId={openStudentId}
        onClose={() => setOpenStudentId(null)}
        onOpenPayment={openStudentPayments}
      />
    </div>
  );
}

function NoStudentIdNote({ onSignOut }: { onSignOut: () => void }) {
  return (
    <div className="rounded-lg border border-amber-300 bg-amber-50 p-6 text-center">
      <h3 className="text-base font-semibold text-amber-900">
        No student profile linked
      </h3>
      <p className="text-sm text-amber-800 mt-1 max-w-md mx-auto">
        This user account isn&apos;t tied to a student record. Please ask an
        administrator to attach your <code>student_id</code>, or sign in with a
        seeded demo student.
      </p>
      <div className="mt-4">
        <Button
          type="button"
          variant="outline"
          onClick={onSignOut}
          className="border-amber-400 text-amber-800 hover:bg-amber-100"
        >
          <LogOut className="size-4" />
          Sign out
        </Button>
      </div>
    </div>
  );
}
