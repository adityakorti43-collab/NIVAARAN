import { lazy, StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { ClauseViewerProvider } from "./components/ClauseViewer";
import { Shell } from "./components/Shell";
import "./index.css";
import { installFx } from "./lib/fx";
import { AppProvider } from "./lib/store";

installFx();

// Route-level code splitting: the landing page's 3D scene and each workspace load only when visited.
const Landing = lazy(() => import("./pages/Landing"));
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Documents = lazy(() => import("./pages/Documents"));
const ClaimWorkspace = lazy(() => import("./pages/ClaimWorkspace"));
const EvidenceExplorer = lazy(() => import("./pages/EvidenceExplorer"));
const Constellation = lazy(() => import("./pages/Constellation"));
const MoneyFlow = lazy(() => import("./pages/MoneyFlow"));
const WhatIf = lazy(() => import("./pages/WhatIf"));
const Assistant = lazy(() => import("./pages/Assistant"));
const Costs = lazy(() => import("./pages/Costs"));
const Evaluation = lazy(() => import("./pages/Evaluation"));
const Reports = lazy(() => import("./pages/Reports"));
const Fairness = lazy(() => import("./pages/Fairness"));
const ActionCenter = lazy(() => import("./pages/ActionCenter"));
const Settings = lazy(() => import("./pages/Settings"));
const AuthPages = import("./pages/Auth");
const Login = lazy(() => AuthPages.then((m) => ({ default: m.Login })));
const Register = lazy(() => AuthPages.then((m) => ({ default: m.Register })));
const ForgotPassword = lazy(() => AuthPages.then((m) => ({ default: m.ForgotPassword })));
const ResetPassword = lazy(() => AuthPages.then((m) => ({ default: m.ResetPassword })));

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <AppProvider>
        <ClauseViewerProvider>
          <Routes>
            <Route path="/" element={<Suspense fallback={<div className="min-h-dvh bg-void" />}><Landing /></Suspense>} />
            <Route path="/login" element={<Suspense fallback={null}><Login /></Suspense>} />
            <Route path="/register" element={<Suspense fallback={null}><Register /></Suspense>} />
            <Route path="/forgot-password" element={<Suspense fallback={null}><ForgotPassword /></Suspense>} />
            <Route path="/reset-password" element={<Suspense fallback={null}><ResetPassword /></Suspense>} />
            <Route element={<Shell />}>
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/documents" element={<Documents />} />
              <Route path="/claim" element={<ClaimWorkspace />} />
              <Route path="/evidence" element={<EvidenceExplorer />} />
              <Route path="/constellation" element={<Constellation />} />
              <Route path="/money-flow" element={<MoneyFlow />} />
              <Route path="/what-if" element={<WhatIf />} />
              <Route path="/assistant" element={<Assistant />} />
              <Route path="/costs" element={<Costs />} />
              <Route path="/evaluation" element={<Evaluation />} />
              <Route path="/reports" element={<Reports />} />
              <Route path="/fairness" element={<Fairness />} />
              <Route path="/actions" element={<ActionCenter />} />
              <Route path="/settings" element={<Settings />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </ClauseViewerProvider>
      </AppProvider>
    </BrowserRouter>
  </StrictMode>,
);
