import { Component, type ErrorInfo, type ReactNode } from 'react';
import App from './App';
import ErrorPage from './components/ErrorPage';
import { PrivacyPage, TermsPage } from './components/LegalPage';
import { useRoute } from './router';

class AppErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Unexpected application error', error, info);
  }

  render() {
    if (this.state.failed) {
      return <ErrorPage code="500" title="Something went wrong" description="The page could not be displayed. Try again, or return to the start of the app." onRetry={() => this.setState({ failed: false })} />;
    }
    return this.props.children;
  }
}

function RouteView() {
  const route = useRoute();
  if (route === 'privacy') return <PrivacyPage />;
  if (route === 'terms') return <TermsPage />;
  if (route === 'error') return <ErrorPage code="500" title="Service unavailable" description="We could not complete that request right now. Please try again in a moment." onRetry={() => window.location.reload()} />;
  if (route === 'not-found') return <ErrorPage code="404" title="Page not found" description="The address may be incorrect, or the page may have moved." />;
  return <App />;
}

export default function AppRouter() {
  return <AppErrorBoundary><RouteView /></AppErrorBoundary>;
}
