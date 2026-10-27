import { describe, expect, it } from 'vitest';
import { routeForPath } from '../router';

describe('routeForPath', () => {
  it.each([
    ['/', 'home'],
    ['/privacy', 'privacy'],
    ['/terms/', 'terms'],
    ['/error', 'error'],
    ['/does-not-exist', 'not-found'],
  ] as const)('maps %s to %s', (path, expected) => {
    expect(routeForPath(path)).toBe(expected);
  });
});
