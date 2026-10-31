import { useSyncExternalStore } from 'react';

export type RouteName = 'home' | 'privacy' | 'terms' | 'error' | 'not-found';

export function routeForPath(pathname: string): RouteName {
  const path = pathname.replace(/\/+$/, '') || '/';
  if (path === '/') return 'home';
  if (path === '/privacy') return 'privacy';
  if (path === '/terms') return 'terms';
  if (path === '/error') return 'error';
  return 'not-found';
}

function emitRouteChange() {
  window.dispatchEvent(new Event('life-sandbox:route-change'));
}

export function navigate(path: string, { replace = false } = {}) {
  if (window.location.pathname === path) return;
  window.history[replace ? 'replaceState' : 'pushState']({}, '', path);
  emitRouteChange();
  window.scrollTo({ top: 0, behavior: 'auto' });
}

function subscribe(onStoreChange: () => void) {
  window.addEventListener('popstate', onStoreChange);
  window.addEventListener('life-sandbox:route-change', onStoreChange);
  return () => {
    window.removeEventListener('popstate', onStoreChange);
    window.removeEventListener('life-sandbox:route-change', onStoreChange);
  };
}

export function useRoute(): RouteName {
  return useSyncExternalStore(subscribe, () => routeForPath(window.location.pathname), () => 'home');
}
