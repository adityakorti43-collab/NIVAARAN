import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ErrorNote, PageHeader, Section } from "../components/ui";
import { api } from "../lib/api";
import { useApp } from "../lib/store";

const SIGNIN: Record<string, string> = { password: "with email and password", google: "with Google", apple: "with Apple", phone: "with a phone code", demo: "to a demo workspace" };

export default function Settings() {
  const { user, setUser, signOut } = useApp();
  const nav = useNavigate();
  const [name, setName] = useState(user?.name ?? "");
  const [cur, setCur] = useState(""), [next, setNext] = useState("");
  const [msg, setMsg] = useState<string | null>(null), [err, setErr] = useState<string | null>(null);
  const [confirm, setConfirm] = useState("");
  if (!user) return null;
  const placeholder = user.email.endsWith(".nivaaran.local");   // phone / private-relay accounts have no real email
  const noPw = !user.is_demo && user.has_password === false;
  return (
    <div>
      <PageHeader eyebrow="Settings" title="Your account" description={user.is_demo ? "You're in a demo workspace. It is deleted automatically after 24 hours. Create an account to keep your work." : `Signed in ${SIGNIN[user.provider ?? "password"]}${user.phone ? ` as ${user.phone}` : placeholder ? "" : ` as ${user.email}`}.`} />
      {msg && <p role="status" className="mb-4 rounded-xl border border-covered/25 bg-covered-bg px-3 py-2.5 text-sm text-covered">{msg}</p>}
      <ErrorNote error={err} className="mb-4" />
      <div className="grid gap-5 lg:grid-cols-2">
        <Section title="Profile">
          <form className="space-y-3" onSubmit={async (e) => { e.preventDefault(); setErr(null); try { setUser((await api.updateProfile(name)).user); setMsg("Profile saved."); } catch (x) { setErr((x as Error).message); } }}>
            <label className="block"><span className="label">Name</span><input className="input" value={name} onChange={(e) => setName(e.target.value)} required maxLength={80} /></label>
            {user.phone && <label className="block"><span className="label">Mobile number</span><input className="input" value={user.phone} disabled /></label>}
            {!placeholder && <label className="block"><span className="label">Email</span><input className="input" value={user.email} disabled /></label>}
            <button className="btn-primary">Save profile</button>
          </form>
        </Section>
        <Section title="Password" description={user.is_demo ? "Demo workspaces don't have a password." : noPw ? "You sign in without a password. You can add one as a backup; use at least 10 characters, with a letter and a number." : "Use at least 10 characters, with a letter and a number."}>
          <form className="space-y-3" onSubmit={async (e) => { e.preventDefault(); setErr(null); try { await api.changePassword(cur, next); setCur(""); setNext(""); setMsg(noPw ? "Password set." : "Password changed."); setUser((await api.me()).user); } catch (x) { setErr((x as Error).message); } }}>
            {!noPw && <label className="block"><span className="label">Current password</span><input type="password" className="input" value={cur} onChange={(e) => setCur(e.target.value)} autoComplete="current-password" disabled={user.is_demo} /></label>}
            <label className="block"><span className="label">New password</span><input type="password" className="input" value={next} onChange={(e) => setNext(e.target.value)} autoComplete="new-password" disabled={user.is_demo} /></label>
            <button className="btn-secondary" disabled={user.is_demo}>{noPw ? "Set a password" : "Change password"}</button>
          </form>
        </Section>
        <Section title="Session">
          <p className="text-sm text-muted">Signing out ends this session on the server.</p>
          <button className="btn-secondary mt-3" onClick={async () => { await signOut(); nav("/"); }}>Sign out</button>
        </Section>
        <Section title="Delete account" description="Deletes your account, documents, claims, analyses, chats, scenarios and report records. This cannot be undone.">
          <label className="block"><span className="label">Type DELETE to confirm</span><input className="input" value={confirm} onChange={(e) => setConfirm(e.target.value)} /></label>
          <button className="btn mt-3 border border-conflict/40 text-conflict hover:bg-conflict-bg" disabled={confirm !== "DELETE"}
            onClick={async () => { try { await api.deleteAccount(); setUser(null); nav("/"); } catch (x) { setErr((x as Error).message); } }}>Delete my account</button>
        </Section>
      </div>
    </div>
  );
}
