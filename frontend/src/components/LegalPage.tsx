import { ArrowLeft, FileText, Scale, ShieldCheck } from 'lucide-react';
import type { ReactNode } from 'react';
import { navigate } from '../router';

const LAST_UPDATED = 'October 27, 2026';
const supportEmail = import.meta.env.VITE_SUPPORT_EMAIL?.trim();

function BackToApp() {
  return (
    <button
      type="button"
      onClick={() => navigate('/')}
      className="inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold text-fg-secondary transition-colors hover:bg-surface-hover hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
    >
      <ArrowLeft size={16} /> Back to Life Sandbox
    </button>
  );
}

function ContactNotice() {
  if (supportEmail) {
    return <a className="font-semibold text-accent hover:underline" href={`mailto:${supportEmail}`}>{supportEmail}</a>;
  }
  return <>the support contact published by the deployment operator</>;
}

export function PrivacyPage() {
  return (
    <LegalShell icon={ShieldCheck} eyebrow="Legal" title="Privacy policy" summary="How Life Sandbox handles information used to provide the service.">
      <PolicySection title="Information we process">
        We process the content you submit, including chats, saved memories, projects, tasks, reminders, feedback, and files you choose to upload. If you sign in with Google, we process the identity details needed to create your session. We also process basic operational data such as request timestamps, error records, and tool-execution traces to operate and secure the service.
      </PolicySection>
      <PolicySection title="Why we use it">
        We use this information to provide responses and follow-through features, maintain your account session, store the items you ask us to save, prevent abuse, diagnose failures, and improve reliability. We do not sell personal information.
      </PolicySection>
      <PolicySection title="Service providers and integrations">
        Prompts and relevant conversation context are sent to the configured AI provider to generate a response. This deployment uses Nebius Token Factory when Nebius is configured. Optional Google integrations are used only after you connect an account and grant the requested permissions. Hosted Mem0 memory is used only when you explicitly opt in for the relevant exchange. Hosting, database, and storage providers may process data solely to operate this service.
      </PolicySection>
      <PolicySection title="Retention and your choices">
        Conversations, approved memories, tasks, and reminders remain until you delete them or the deployment operator removes them under its retention policy. You can manage saved memories and follow-through items from the Memory &amp; tasks area. Removing browser-local data does not automatically remove server-side records. To request access, correction, or deletion of account data, contact <ContactNotice />.
      </PolicySection>
      <PolicySection title="Security and limits">
        We use access controls, encrypted transport, and provider-managed infrastructure, but no internet service can guarantee absolute security. Do not submit secrets, payment credentials, or other highly sensitive information unless you are comfortable with the configured providers processing it.
      </PolicySection>
      <PolicySection title="Changes to this policy">
        We may update this policy when the service or applicable requirements change. The updated date above identifies the current version. Continued use after an update means you acknowledge the revised policy.
      </PolicySection>
    </LegalShell>
  );
}

export function TermsPage() {
  return (
    <LegalShell icon={Scale} eyebrow="Legal" title="Terms of use" summary="The rules for using Life Sandbox responsibly.">
      <PolicySection title="Acceptance and eligibility">
        By using Life Sandbox, you agree to these terms and confirm that you may legally use the service. If you use it for an organization, you confirm that you have authority to accept these terms for that organization.
      </PolicySection>
      <PolicySection title="Decision support, not professional advice">
        Life Sandbox provides AI-assisted research and planning support. Responses can be incomplete, inaccurate, or outdated and must not be treated as medical, legal, financial, safety, or other professional advice. Verify important information independently and make final decisions yourself.
      </PolicySection>
      <PolicySection title="Your content and connected accounts">
        You are responsible for the content you submit and for ensuring that you have the rights to provide it. Do not upload unlawful, harmful, infringing, or confidential material you are not authorized to share. You may disconnect optional integrations at any time; you remain responsible for actions taken through accounts you connect.
      </PolicySection>
      <PolicySection title="Acceptable use">
        Do not misuse the service, attempt to bypass security controls, interfere with other users, probe for vulnerabilities, automate abusive requests, or use the service to facilitate fraud, harm, or illegal activity. We may limit or suspend access to protect the service and its users.
      </PolicySection>
      <PolicySection title="Availability and liability">
        The service is provided on an “as available” basis. We may change, pause, or discontinue features. To the maximum extent allowed by law, the deployment operator is not liable for indirect, incidental, special, consequential, or loss-of-data damages arising from use of the service.
      </PolicySection>
      <PolicySection title="Contact and changes">
        Questions about these terms can be sent to <ContactNotice />. We may update these terms; continued use after a revision means you accept the updated version.
      </PolicySection>
    </LegalShell>
  );
}

function PolicySection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h2 className="text-base font-bold text-fg">{title}</h2>
      <p className="mt-2 text-sm leading-7 text-fg-secondary">{children}</p>
    </section>
  );
}

function LegalShell({ icon: Icon, eyebrow, title, summary, children }: { icon: typeof FileText; eyebrow: string; title: string; summary: string; children: ReactNode }) {
  return (
    <main className="min-h-dvh bg-bg px-4 py-6 sm:px-6 sm:py-10">
      <div className="mx-auto max-w-3xl">
        <BackToApp />
        <article className="mt-5 rounded-2xl border border-border bg-surface p-6 shadow-2xs sm:p-10">
          <div className="flex items-start gap-4 border-b border-border pb-6">
            <span className="grid size-11 place-items-center rounded-xl bg-accent-muted text-accent"><Icon size={21} /></span>
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-accent">{eyebrow}</p>
              <h1 className="mt-1 text-3xl font-bold tracking-tight text-fg">{title}</h1>
              <p className="mt-2 text-sm leading-6 text-fg-secondary">{summary}</p>
              <p className="mt-3 text-xs text-fg-muted">Last updated: {LAST_UPDATED}</p>
            </div>
          </div>
          <div className="mt-7 space-y-7">{children}</div>
        </article>
      </div>
    </main>
  );
}
