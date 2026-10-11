import { ArrowLeft, ShieldCheck } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useState, type ReactNode } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { LanguagePicker } from "../components/LanguagePicker";
import { LogoMark } from "../components/Shell";
import { ErrorNote } from "../components/ui";
import { api } from "../lib/api";
import { isNativeApp, openGoogleSignIn } from "../lib/native";
import { useApp } from "../lib/store";
import type { AuthProviders } from "../lib/types";

function AuthFrame({ title, subtitle, children }: { title: string; subtitle: ReactNode; children: ReactNode }) {
  return (
    <div className="grid min-h-dvh bg-paper lg:grid-cols-[1.05fr_1fr]">
      <aside className="theme-forest relative hidden overflow-hidden bg-forest lg:block">
        <div className="absolute inset-0 [background-image:linear-gradient(rgb(245_242_234/0.04)_1px,transparent_1px),linear-gradient(90deg,rgb(245_242_234/0.04)_1px,transparent_1px)] [background-size:44px_44px] [mask-image:radial-gradient(ellipse_at_40%_40%,black_25%,transparent_75%)]" aria-hidden />
        <div className="relative flex h-full flex-col justify-between p-12">
          <Link to="/" className="flex items-center gap-2.5"><LogoMark /><span className="font-display text-[28px] leading-none text-ivory" translate="no">Nivaaran</span></Link>
          <div>
            <svg viewBox="0 0 460 260" className="w-full max-w-md" aria-hidden>
              <rect x="10" y="20" width="150" height="200" rx="14" fill="#1a3830" stroke="#2c4a41" />
              {[0, 1, 2, 3, 4, 5].map((i) => <rect key={i} x="26" y={52 + i * 26} width={90 + (i * 23) % 40} height="8" rx="4" fill={i === 2 ? "#b69a62" : "#2c4a41"} opacity={i === 2 ? 0.9 : 1} />)}
              <rect x="300" y="40" width="150" height="70" rx="12" fill="#1a3830" stroke="#2c4a41" />
              <rect x="316" y="62" width="100" height="8" rx="4" fill="#f5f2ea" opacity=".7" /><rect x="316" y="80" width="60" height="8" rx="4" fill="#dcb66e" />
              <rect x="300" y="150" width="150" height="70" rx="12" fill="#1a3830" stroke="#2c4a41" />
              <rect x="316" y="172" width="80" height="8" rx="4" fill="#b69a62" /><rect x="316" y="190" width="110" height="8" rx="4" fill="#2c4a41" />
              <motion.path d="M160 104 C 230 104, 230 75, 300 75" stroke="#b69a62" strokeWidth="2" fill="none" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 1.4, delay: 0.3 }} />
              <motion.path d="M375 110 L 375 150" stroke="#b69a62" strokeWidth="2" fill="none" strokeDasharray="4 4" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.8, delay: 1.6 }} />
            </svg>
            <p className="mt-10 max-w-md font-display text-[44px] leading-[1.02] tracking-[-0.015em] text-ivory">Every estimate traced to the clause behind it.</p>
            <p className="mt-4 flex max-w-md items-start gap-2 text-sm text-muted"><ShieldCheck className="mt-0.5 size-4 shrink-0 text-accent" />Your documents and analyses are visible only to your account. You sign in with your Google account, so there is no new password to remember or leak.</p>
          </div>
          <p className="text-xs text-faint">Decision-support estimates only. Not an insurer decision.</p>
        </div>
      </aside>
      <main className="flex items-center justify-center px-5 py-12">
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }} className="w-full max-w-[420px]">
          <div className="mb-8 flex items-center justify-between gap-3">
            <Link to="/" className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink"><ArrowLeft className="size-4" /> Back to Nivaaran</Link>
            <LanguagePicker />
          </div>
          <h1 className="h-display text-[34px] leading-tight">{title}</h1>
          <div className="mt-2 text-sm text-muted">{subtitle}</div>
          <div className="mt-8">{children}</div>
        </motion.div>
      </main>
    </div>
  );
}

function GoogleMark() {
  return (
    <svg viewBox="0 0 48 48" className="size-[18px]" aria-hidden>
      <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
      <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
      <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
    </svg>
  );
}

export function Login() {
  const [params] = useSearchParams();
  const nav = useNavigate();
  const { user, signOut } = useApp();
  const [prov, setProv] = useState<AuthProviders | null>(null);
  const [provErr, setProvErr] = useState<string | null>(null);
  const next = params.get("next") || "/dashboard";
  const error = params.get("error");
  const expired = params.get("reason") === "expired";
  useEffect(() => { api.authProviders().then(setProv).catch((e) => setProvErr((e as Error).message)); }, []);

  return (
    <AuthFrame title="Sign in to Nivaaran" subtitle="New here? Signing in with Google creates your account. Use the same Google account next time to come back to it.">
      {user && (
        <div className="mb-6 rounded-[4px] border border-line-2 bg-card p-4" role="status" data-testid="signed-in-notice">
          <p className="text-sm text-text">You're already signed in{user.name ? <> as <span className="font-semibold text-ink">{user.name}</span></> : ""}.</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button type="button" className="btn-primary" onClick={() => nav("/dashboard")}>Go to dashboard</button>
            <button type="button" className="btn-secondary" onClick={() => signOut()}>Sign out</button>
          </div>
        </div>
      )}
      {expired && !user && <p role="status" className="mb-4 rounded-[3px] border border-line-2 bg-card px-3 py-2 text-sm text-text">Your session ended. Please sign in again to continue.</p>}
      {error && <ErrorNote error={error} className="mb-4" />}
      {provErr && <ErrorNote error={`Couldn't reach Nivaaran to load the sign-in options: ${provErr}`} className="mb-4" />}
      <div className="space-y-3" data-testid="sign-in-options">
        <a href={prov?.google ? api.googleStartUrl(next) : undefined} aria-disabled={!prov?.google}
          onClick={(e) => {
            if (!prov?.google) { e.preventDefault(); return; }
            if (isNativeApp()) { e.preventDefault(); void openGoogleSignIn(next); }   // the app signs in through the phone's browser
          }}
          className={`btn-secondary h-12 w-full justify-center gap-2.5 text-[15px] font-medium ${prov && !prov.google ? "pointer-events-none opacity-50" : ""}`} data-testid="google-signin">
          <GoogleMark /> Continue with Google
        </a>
        {prov && !prov.google && (
          <p className="text-[12.5px] leading-relaxed text-muted" data-testid="provider-note">Google sign-in isn't available yet: the site operator still needs to connect it.</p>
        )}
        <p className="pt-3 text-xs text-faint">By continuing you agree to the <Link to="/terms" className="underline hover:text-ink">terms</Link> and <Link to="/privacy" className="underline hover:text-ink">privacy policy</Link>. Nivaaran's results are estimates to help you understand your policy, not an insurer's decision.</p>
      </div>
    </AuthFrame>
  );
}
