import { ArrowLeft, Eye, EyeOff, Loader2, ShieldCheck, Smartphone } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { LogoMark } from "../components/Shell";
import { ErrorNote } from "../components/ui";
import { api } from "../lib/api";
import { useApp } from "../lib/store";
import type { AuthProviders } from "../lib/types";

function AuthFrame({ title, subtitle, children }: { title: string; subtitle: ReactNode; children: ReactNode }) {
  return (
    <div className="grid min-h-dvh bg-paper lg:grid-cols-[1.05fr_1fr]">
      <aside className="theme-forest relative hidden overflow-hidden bg-forest lg:block">
        <div className="absolute inset-0 [background-image:linear-gradient(rgb(245_242_234/0.04)_1px,transparent_1px),linear-gradient(90deg,rgb(245_242_234/0.04)_1px,transparent_1px)] [background-size:44px_44px] [mask-image:radial-gradient(ellipse_at_40%_40%,black_25%,transparent_75%)]" aria-hidden />
        <div className="relative flex h-full flex-col justify-between p-12">
          <Link to="/" className="flex items-center gap-2.5"><LogoMark /><span className="font-display text-[28px] leading-none text-ivory">Nivaaran</span></Link>
          <div>
            {/* An evidence trail: document clause -> bill line -> calculation. Illustrative. */}
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
            <p className="mt-4 flex max-w-md items-start gap-2 text-sm text-muted"><ShieldCheck className="mt-0.5 size-4 shrink-0 text-accent" />Your documents and analyses are visible only to your account. Sign in with Google, Apple, a phone code or a password; sessions use secure, HTTP-only cookies.</p>
          </div>
          <p className="text-xs text-faint">Decision-support estimates only. Not an insurer decision.</p>
        </div>
      </aside>
      <main className="flex items-center justify-center px-5 py-12">
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }} className="w-full max-w-[420px]">
          <Link to="/" className="mb-8 inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink"><ArrowLeft className="size-4" /> Back to Nivaaran</Link>
          <h1 className="h-display text-[34px] leading-tight">{title}</h1>
          <div className="mt-2 text-sm text-muted">{subtitle}</div>
          <div className="mt-8">{children}</div>
        </motion.div>
      </main>
    </div>
  );
}

function PasswordInput({ id, value, onChange, autoComplete }: { id: string; value: string; onChange: (v: string) => void; autoComplete: string }) {
  const [show, setShow] = useState(false);
  return (
    <div className="relative">
      <input id={id} type={show ? "text" : "password"} className="input pr-10" value={value} onChange={(e) => onChange(e.target.value)} autoComplete={autoComplete} required />
      <button type="button" onClick={() => setShow(!show)} className="absolute right-2.5 top-2 text-faint hover:text-ink" aria-label={show ? "Hide password" : "Show password"}>
        {show ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
      </button>
    </div>
  );
}

const Submit = ({ busy, children }: { busy: boolean; children: ReactNode }) => (
  <button className="btn-primary h-11 w-full text-[15px]" disabled={busy}>{busy ? <Loader2 className="size-4 animate-spin" /> : children}</button>
);

function useAfterAuth() {
  const nav = useNavigate();
  const [params] = useSearchParams();
  const { setUser, refresh } = useApp();
  return async (u: Parameters<typeof setUser>[0]) => { setUser(u); await refresh(); nav(params.get("next") || "/dashboard", { replace: true }); };
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

function AppleMark() {
  return (
    <svg viewBox="0 0 24 24" className="size-[18px]" fill="currentColor" aria-hidden>
      <path d="M16.37 12.6c-.02-2.3 1.88-3.4 1.96-3.46-1.07-1.56-2.73-1.78-3.32-1.8-1.41-.14-2.76.83-3.48.83-.72 0-1.82-.81-3-.79-1.54.02-2.96.9-3.76 2.27-1.6 2.78-.41 6.9 1.15 9.15.76 1.1 1.67 2.34 2.86 2.3 1.15-.05 1.58-.74 2.97-.74 1.38 0 1.77.74 2.98.72 1.23-.02 2.01-1.12 2.76-2.23.87-1.28 1.23-2.52 1.25-2.58-.03-.01-2.4-.92-2.42-3.66zM14.1 5.86c.63-.77 1.06-1.83.94-2.89-.91.04-2.01.61-2.66 1.37-.58.67-1.09 1.75-.96 2.79 1.02.08 2.05-.52 2.68-1.27z" />
    </svg>
  );
}

/** Google, Apple and phone sign-in. Google/Apple are enabled only when this server has their credentials. */
function SocialSignIn({ onPhone }: { onPhone: () => void }) {
  const [params] = useSearchParams();
  const [prov, setProv] = useState<AuthProviders | null>(null);
  useEffect(() => { api.authProviders().then(setProv).catch(() => setProv({ google: false, apple: false, phone: { enabled: true, delivery: "outbox", dev_codes: false } })); }, []);
  const next = encodeURIComponent(params.get("next") || "/dashboard");
  const off = (p: "google" | "apple") => prov !== null && !prov[p];
  const cls = "btn-secondary h-11 w-full justify-center gap-2.5 text-[14px] font-medium";
  return (
    <div className="space-y-2.5" data-testid="social-signin">
      {off("google") ? <button type="button" className={cls} disabled title="Not configured on this server"><GoogleMark /> Continue with Google</button>
        : <a href={`/api/auth/google/start?next=${next}`} className={cls} data-testid="google-signin"><GoogleMark /> Continue with Google</a>}
      {off("apple") ? <button type="button" className={cls} disabled title="Not configured on this server"><AppleMark /> Continue with Apple</button>
        : <a href={`/api/auth/apple/start?next=${next}`} className={cls} data-testid="apple-signin"><AppleMark /> Continue with Apple</a>}
      <button type="button" className={cls} onClick={onPhone} data-testid="phone-signin"><Smartphone className="size-[18px]" strokeWidth={1.6} /> Continue with phone number</button>
      {prov && (!prov.google || !prov.apple) && (
        <p className="text-[11.5px] leading-relaxed text-faint">{[!prov.google && "Google", !prov.apple && "Apple"].filter(Boolean).join(" and ")} sign-in will switch on once this server's operator adds the credentials.</p>
      )}
      <div className="flex items-center gap-3 py-2 font-mono text-[10.5px] uppercase tracking-[0.16em] text-faint" aria-hidden><span className="h-px flex-1 bg-line-2" />or with email<span className="h-px flex-1 bg-line-2" /></div>
    </div>
  );
}

/** Two steps: send a 6-digit code to the number, then verify it. New numbers get a new account. */
function PhoneSignIn({ onBack }: { onBack: () => void }) {
  const done = useAfterAuth();
  const [phone, setPhone] = useState(""), [code, setCode] = useState(""), [name, setName] = useState("");
  const [sent, setSent] = useState<{ phone: string; masked: string; delivery: string; dev_code?: string } | null>(null);
  const [busy, setBusy] = useState(false), [err, setErr] = useState<string | null>(null), [wait, setWait] = useState(0);
  useEffect(() => { if (wait <= 0) return; const t = setTimeout(() => setWait(wait - 1), 1000); return () => clearTimeout(t); }, [wait]);
  async function send(e?: FormEvent) {
    e?.preventDefault(); setBusy(true); setErr(null);
    try { setSent(await api.phoneStart(phone)); setWait(30); } catch (x) { setErr((x as Error).message); } finally { setBusy(false); }
  }
  async function verify(e: FormEvent) {
    e.preventDefault(); setBusy(true); setErr(null);
    try { done((await api.phoneVerify(sent!.phone, code, name)).user); } catch (x) { setErr((x as Error).message); setBusy(false); }
  }
  return (
    <div data-testid="phone-flow">
      {!sent ? (
        <form onSubmit={send} className="space-y-4" noValidate>
          <label className="block"><span className="label">Mobile number</span>
            <input type="tel" inputMode="tel" className="input" placeholder="98765 43210" value={phone} onChange={(e) => setPhone(e.target.value)} autoComplete="tel" required data-testid="phone-input" /></label>
          <p className="text-xs text-faint">Indian numbers can be entered without +91. We'll text you a 6-digit code.</p>
          <ErrorNote error={err} />
          <Submit busy={busy}>Send code</Submit>
        </form>
      ) : (
        <form onSubmit={verify} className="space-y-4" noValidate>
          <p className="text-sm text-text">Enter the code sent to <span className="font-medium text-ink">{sent.masked}</span>.</p>
          {sent.dev_code && <p role="status" className="rounded-[3px] border border-review/30 bg-review-bg px-3 py-2 text-[13px] text-review">Development mode, no SMS provider configured: your code is <span className="font-mono font-semibold" data-testid="dev-code">{sent.dev_code}</span></p>}
          {!sent.dev_code && sent.delivery === "outbox" && <p className="rounded-[3px] border border-line-2 px-3 py-2 text-[12.5px] text-muted">Text messages aren't configured on this server yet, so the code was written to the server's outbox for the operator.</p>}
          <label className="block"><span className="label">6-digit code</span>
            <input inputMode="numeric" maxLength={6} className="input font-mono tracking-[0.4em]" value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} autoComplete="one-time-code" required data-testid="otp-input" /></label>
          <label className="block"><span className="label">Your name (new accounts only, optional)</span>
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" maxLength={80} /></label>
          <ErrorNote error={err} />
          <Submit busy={busy}>Verify and continue</Submit>
          <div className="flex justify-between text-sm">
            <button type="button" className="text-accent hover:underline" onClick={() => { setSent(null); setCode(""); }}>Change number</button>
            <button type="button" className="text-accent hover:underline disabled:text-faint disabled:no-underline" disabled={wait > 0 || busy} onClick={() => send()}>{wait > 0 ? `Resend in ${wait}s` : "Resend code"}</button>
          </div>
        </form>
      )}
      <button type="button" onClick={onBack} className="mt-6 inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink"><ArrowLeft className="size-4" /> Other ways to sign in</button>
    </div>
  );
}

export function Login() {
  const [params] = useSearchParams();
  const [email, setEmail] = useState(""), [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false), [err, setErr] = useState<string | null>(params.get("error"));
  const [phoneMode, setPhoneMode] = useState(false);
  const done = useAfterAuth();
  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setErr(null);
    try { done((await api.login(email, password)).user); } catch (x) { setErr((x as Error).message); setBusy(false); }
  }
  return (
    <AuthFrame title="Sign in" subtitle={<>New to Nivaaran? <Link to="/register" className="font-medium text-accent hover:underline">Create an account</Link></>}>
      {phoneMode ? <PhoneSignIn onBack={() => setPhoneMode(false)} /> : <>
      <SocialSignIn onPhone={() => setPhoneMode(true)} />
      <form onSubmit={submit} className="space-y-4" noValidate>
        <label className="block"><span className="label">Email</span><input type="email" className="input" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required data-testid="login-email" /></label>
        <label className="block"><span className="label flex justify-between">Password <Link to="/forgot-password" className="font-normal text-accent hover:underline">Forgot password?</Link></span>
          <PasswordInput id="password" value={password} onChange={setPassword} autoComplete="current-password" /></label>
        <ErrorNote error={err} />
        <Submit busy={busy}>Sign in</Submit>
      </form>
      </>}
    </AuthFrame>
  );
}

export function Register() {
  const [name, setName] = useState(""), [email, setEmail] = useState(""), [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false), [err, setErr] = useState<string | null>(null);
  const [phoneMode, setPhoneMode] = useState(false);
  const done = useAfterAuth();
  const strong = password.length >= 10 && /[A-Za-z]/.test(password) && /\d/.test(password);
  async function submit(e: FormEvent) {
    e.preventDefault(); setErr(null);
    if (!strong) { setErr("Use at least 10 characters, including a letter and a number."); return; }
    setBusy(true);
    try { done((await api.register(name, email, password)).user); } catch (x) { setErr((x as Error).message); setBusy(false); }
  }
  return (
    <AuthFrame title="Create your account" subtitle={<>Already registered? <Link to="/login" className="font-medium text-accent hover:underline">Sign in</Link></>}>
      {phoneMode ? <PhoneSignIn onBack={() => setPhoneMode(false)} /> : <>
      <SocialSignIn onPhone={() => setPhoneMode(true)} />
      <form onSubmit={submit} className="space-y-4" noValidate>
        <label className="block"><span className="label">Name</span><input className="input" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" required data-testid="register-name" /></label>
        <label className="block"><span className="label">Email</span><input type="email" className="input" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required data-testid="register-email" /></label>
        <label className="block"><span className="label">Password</span><PasswordInput id="new-password" value={password} onChange={setPassword} autoComplete="new-password" />
          <span className={`mt-1.5 block text-xs ${strong ? "text-covered" : "text-faint"}`}>{strong ? "Strong enough." : "At least 10 characters, with a letter and a number."}</span></label>
        <ErrorNote error={err} />
        <Submit busy={busy}>Create account</Submit>
        <p className="text-xs text-faint">Your documents stay on this Nivaaran server and are visible only to your account.</p>
      </form>
      </>}
    </AuthFrame>
  );
}

export function ForgotPassword() {
  const [email, setEmail] = useState(""), [busy, setBusy] = useState(false), [msg, setMsg] = useState<string | null>(null), [err, setErr] = useState<string | null>(null);
  return (
    <AuthFrame title="Reset your password" subtitle="Enter your account email and we'll issue a reset link.">
      <form className="space-y-4" onSubmit={async (e) => { e.preventDefault(); setBusy(true); setErr(null); try { setMsg((await api.resetRequest(email)).message); } catch (x) { setErr((x as Error).message); } finally { setBusy(false); } }}>
        <label className="block"><span className="label">Email</span><input type="email" className="input" value={email} onChange={(e) => setEmail(e.target.value)} required /></label>
        <ErrorNote error={err} />
        {msg ? <p role="status" className="rounded-xl border border-covered/25 bg-covered-bg px-3 py-2.5 text-sm text-covered">{msg}</p> : <Submit busy={busy}>Send reset link</Submit>}
        <p className="text-sm"><Link to="/login" className="text-accent hover:underline">Back to sign in</Link></p>
      </form>
    </AuthFrame>
  );
}

export function ResetPassword() {
  const [params] = useSearchParams();
  const nav = useNavigate();
  const [pw, setPw] = useState(""), [busy, setBusy] = useState(false), [err, setErr] = useState<string | null>(null), [ok, setOk] = useState(false);
  useEffect(() => { if (ok) setTimeout(() => nav("/login"), 1500); }, [ok, nav]);
  return (
    <AuthFrame title="Choose a new password" subtitle="Reset links work once and expire after 30 minutes.">
      <form className="space-y-4" onSubmit={async (e) => { e.preventDefault(); setBusy(true); setErr(null); try { await api.resetConfirm(params.get("token") ?? "", pw); setOk(true); } catch (x) { setErr((x as Error).message); } finally { setBusy(false); } }}>
        <label className="block"><span className="label">New password</span><PasswordInput id="reset-password" value={pw} onChange={setPw} autoComplete="new-password" /></label>
        <ErrorNote error={err} />
        {ok ? <p role="status" className="text-sm text-covered">Password updated. Taking you to sign in…</p> : <Submit busy={busy}>Update password</Submit>}
      </form>
    </AuthFrame>
  );
}
