import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { FormattedMessage } from '../components/FormattedMessage';

describe('FormattedMessage Component', () => {
  it('renders plain text content correctly', () => {
    render(<FormattedMessage content="Life Sandbox helps evaluate trade-offs." />);
    expect(screen.getByText('Life Sandbox helps evaluate trade-offs.')).toBeInTheDocument();
  });

  it('renders markdown headers', () => {
    const { container } = render(<FormattedMessage content="## Next Steps" />);
    const heading = container.querySelector('h3');
    expect(heading).toBeInTheDocument();
    expect(heading?.textContent).toBe('Next Steps');
  });

  it('renders code blocks with syntax styling', () => {
    const codeSnippet = '```json\n{"status": "ok"}\n```';
    const { container } = render(<FormattedMessage content={codeSnippet} />);
    const preElement = container.querySelector('pre');
    expect(preElement).toBeInTheDocument();
    expect(preElement?.textContent).toContain('"status": "ok"');
  });
});
