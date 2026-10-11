import { lazy, StrictMode, Suspense } from "react";
import { createRoot, type Root } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { ClauseViewerProvider } from "./components/ClauseViewer";
import { Shell } from "./components/Shell";
import "./index.css";
import { installFx } from "./lib/fx";
import { initPwa } from "./lib/pwa";
import { initNative } from "./lib/native";
import { AppProvider } from "./lib/store";

installFx();
initPwa();
void initNative();

// Route-level code splitting: the landing page's 3D scene and each workspace load only when visited.
const Landing = lazy(() => import("./pages/Landing"));
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Documents = lazy(() => import("./pages/Documents"));
const ClaimWorkspace = lazy(() => import("./pages/ClaimWorkspace"));
const WhatIf = lazy(() => import("./pages/WhatIf"));
const Assistant = lazy(() => import("./pages/Assistant"));
const Reports = lazy(() => import("./pages/Reports"));
const ActionCenter = lazy(() => import("./pages/ActionCenter"));
const Settings = lazy(() => import("./pages/Settings"));
const AuthPages = import("./pages/Auth");
const LegalPages = () => import("./pages/Legal");
const Privacy = lazy(() => LegalPages().then((m) => ({ default: m.Privacy })));
const Terms = lazy(() => LegalPages().then((m) => ({ default: m.Terms })));
const Login = lazy(() => AuthPages.then((m) => ({ default: m.Login })));

// During development, hot reloads can re-run this file. Reuse the existing React root instead of creating a second
// one on the same container (two roots fight over the DOM and break later updates, such as uploads).
const container = document.getElementById("root")! as HTMLElement & { __nivaaranRoot?: Root };
const root = container.__nivaaranRoot ?? (container.__nivaaranRoot = createRoot(container));

root.render(
  <StrictMode>
    <BrowserRouter>
      <AppProvider>
        <ClauseViewerProvider>
          <Routes>
            <Route path="/" element={<Suspense fallback={<div className="min-h-dvh bg-void" />}><Landing /></Suspense>} />
            <Route path="/login" element={<Suspense fallback={null}><Login /></Suspense>} />
            <Route path="/privacy" element={<Suspense fallback={null}><Privacy /></Suspense>} />
            <Route path="/terms" element={<Suspense fallback={null}><Terms /></Suspense>} />
            <Route path="/register" element={<Navigate to="/login" replace />} />
            <Route path="/forgot-password" element={<Navigate to="/login" replace />} />
            <Route path="/reset-password" element={<Navigate to="/login" replace />} />
            <Route element={<Shell />}>
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/documents" element={<Documents />} />
              <Route path="/claim" element={<ClaimWorkspace />} />
              <Route path="/what-if" element={<WhatIf />} />
              <Route path="/assistant" element={<Assistant />} />
              <Route path="/reports" element={<Reports />} />
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
