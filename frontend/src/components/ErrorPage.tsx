import { ArrowLeft, Home, RefreshCw, ShieldAlert } from 'lucide-react';
import { navigate } from '../router';

type ErrorPageProps = {
  code: '404' | '500';
  title: string;
  description: string;
  onRetry?: () => void;
};

export default function ErrorPage({ code, title, description, onRetry }: ErrorPageProps) {
  return (
    <main className="grid min-h-dvh place-items-center bg-bg px-5 py-10">
      <section className="w-full max-w-lg rounded-2xl border border-border bg-surface p-7 text-center shadow-sm sm:p-10">
        <span className="mx-auto grid size-14 place-items-center rounded-2xl bg-error/10 text-error"><ShieldAlert size={27} /></span>
        <p className="mt-6 text-sm font-bold tracking-[0.2em] text-accent">ERROR {code}</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-fg">{title}</h1>
        <p className="mx-auto mt-3 max-w-sm text-sm leading-6 text-fg-secondary">{description}</p>
        <div className="mt-7 flex flex-wrap justify-center gap-3">
          <button type="button" onClick={() => navigate('/')} className="inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-accent-fg transition-colors hover:bg-accent-hover">
            <Home size={16} /> Go to home
          </button>
          {onRetry ? (
            <button type="button" onClick={onRetry} className="inline-flex items-center gap-2 rounded-lg border border-border-strong px-4 py-2.5 text-sm font-semibold text-fg transition-colors hover:bg-surface-hover">
              <RefreshCw size={16} /> Try again
            </button>
          ) : (
            <button type="button" onClick={() => window.history.back()} className="inline-flex items-center gap-2 rounded-lg border border-border-strong px-4 py-2.5 text-sm font-semibold text-fg transition-colors hover:bg-surface-hover">
              <ArrowLeft size={16} /> Go back
            </button>
          )}
        </div>
      </section>
    </main>
  );
}
