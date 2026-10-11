import { ArrowLeft } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { LogoMark } from "../components/Shell";

const UPDATED = "11 October 2026";

function Page({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="min-h-dvh bg-paper">
      <header className="theme-forest bg-forest px-5 py-5 md:px-10">
        <div className="mx-auto flex max-w-3xl items-center gap-3">
          <Link to="/" className="flex items-center gap-2.5"><LogoMark className="size-7" /><span className="font-display text-[24px] leading-none text-ivory" translate="no">Nivaaran</span></Link>
        </div>
      </header>
      <main className="mx-auto max-w-3xl px-5 py-10 md:px-10">
        <Link to="/" className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink"><ArrowLeft className="size-4" /> Back to Nivaaran</Link>
        <h1 className="h-display mt-6 text-[40px] leading-tight">{title}</h1>
        <p className="mt-1 text-sm text-muted">Last updated {UPDATED}</p>
        <div className="legal mt-8 space-y-6 text-[15px] leading-relaxed text-text [&_h2]:mt-8 [&_h2]:text-[19px] [&_h2]:font-semibold [&_h2]:text-ink [&_li]:ml-5 [&_li]:list-disc [&_ul]:space-y-1.5">{children}</div>
      </main>
    </div>
  );
}

export function Privacy() {
  return (
    <Page title="Privacy policy">
      <p>Nivaaran helps you understand your health-insurance policy and check a hospital bill against it. This page explains what we collect, why, who else handles it, and how to delete it. It applies to the website and to the Nivaaran apps for Android and iOS, which show the same service.</p>

      <h2>What we collect</h2>
      <ul>
        <li><strong>Your account:</strong> when you sign in with Google we receive your Google account ID, your name, your email address (if Google has verified it) and your profile picture. We do not receive your Google password.</li>
        <li><strong>Documents you upload:</strong> policy wordings, endorsements, brochures and hospital bills, the text read from them, and the results Nivaaran works out (clauses, estimates, notes).</li>
        <li><strong>What you enter:</strong> claim details, corrections to bill lines, questions you ask the assistant, and your profile name.</li>
        <li><strong>Technical data:</strong> a session cookie that keeps you signed in, and standard server logs (time, address, page requested) kept for security and fixing faults.</li>
      </ul>
      <p>We do not use advertising or tracking cookies, we do not sell your data, and we do not use your documents for marketing.</p>

      <h2>Why we use it</h2>
      <ul>
        <li>To sign you in and keep your documents private to your account.</li>
        <li>To read your policy and bill and show you what is likely to be covered, with the clause behind each answer.</li>
        <li>To keep the service secure and working.</li>
      </ul>

      <h2>Who else handles it</h2>
      <ul>
        <li><strong>Google sign-in:</strong> Google confirms who you are when you choose "Continue with Google".</li>
        <li><strong>Google Gemini:</strong> when you use read-aloud or choose another language, the text being read or translated (for example a policy summary or an answer) is sent to Google's Gemini service to produce the voice or the translation. Under Google's terms for its free tier, Google may use such text to improve its products. Your uploaded files themselves are not sent.</li>
        <li><strong>Our hosting provider:</strong> stores the service and its database on our behalf.</li>
      </ul>

      <h2>How long we keep it</h2>
      <p>Your account and documents are kept until you delete them. Sign-in sessions expire after 7 days. Translations and generated audio of general text are kept to make the service faster; they do not identify you.</p>

      <h2>Your choices and rights</h2>
      <ul>
        <li><strong>Delete a document or claim</strong> at any time from the Documents or Claim pages.</li>
        <li><strong>Delete your account</strong> from Settings → Delete account. This removes your account, documents, claims, analyses, chats and reports from our database.</li>
        <li>You can sign out at any time; this ends the session on our server.</li>
      </ul>

      <h2>Children</h2>
      <p>Nivaaran is intended for adults managing health insurance. It is not directed at children under 18.</p>

      <h2>Important</h2>
      <p>Nivaaran gives decision-support estimates. It is not an insurer, a broker or a legal adviser, and its results are not a claim decision. The wording of your policy always governs.</p>

      <h2>Changes and contact</h2>
      <p>If this policy changes we will update this page and its date. For questions or requests about your data, contact us at the email address shown on Nivaaran's app-store listing.</p>
    </Page>
  );
}

export function Terms() {
  return (
    <Page title="Terms of use">
      <p>By using Nivaaran (the website or the Android/iOS apps) you agree to these terms.</p>
      <h2>What Nivaaran is</h2>
      <p>Nivaaran reads the insurance documents and bills you upload and gives estimates of what may be covered, with references to the clauses it relied on. It is a decision-support tool. It is not an insurer, broker, third-party administrator or legal adviser, and it does not guarantee that any claim will be approved or paid.</p>
      <h2>Your responsibilities</h2>
      <ul>
        <li>Upload only documents you are entitled to use, such as your own or your family's policy and bills.</li>
        <li>Check important results against the original policy wording and with your insurer.</li>
        <li>Keep your Google account secure; anyone who can sign in to it can see your Nivaaran documents.</li>
      </ul>
      <h2>Translations and read-aloud</h2>
      <p>Translations into Indian languages and the spoken explanations are produced automatically and may contain mistakes. The English policy wording governs.</p>
      <h2>Availability</h2>
      <p>We work to keep Nivaaran available and accurate, but it is provided as is, without a guarantee that it will always be error-free or uninterrupted.</p>
      <h2>Your data</h2>
      <p>How we handle your information is described in the <Link to="/privacy" className="text-accent underline">privacy policy</Link>. You can delete your account at any time from Settings.</p>
    </Page>
  );
}
