import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import InstallBanner from '../components/InstallBanner';

beforeEach(() => {
  localStorage.clear();
  jest.clearAllMocks();
});

function fireInstallPrompt(overrides = {}) {
  const event = new Event('beforeinstallprompt');
  event.preventDefault = jest.fn();
  event.prompt = jest.fn();
  event.userChoice = Promise.resolve({ outcome: 'accepted', ...overrides });
  act(() => {
    window.dispatchEvent(event);
  });
  return event;
}

describe('InstallBanner', () => {
  test('renders nothing initially (before install prompt)', () => {
    render(<InstallBanner />);
    expect(screen.queryByRole('banner', { name: /install app banner/i })).not.toBeInTheDocument();
  });

  test('appears when beforeinstallprompt fires and not dismissed before', () => {
    render(<InstallBanner />);
    fireInstallPrompt();
    expect(screen.getByRole('banner', { name: /install app banner/i })).toBeInTheDocument();
    expect(screen.getByText('Install Son of Mervan')).toBeInTheDocument();
  });

  test('does not appear if previously dismissed (localStorage flag set)', () => {
    localStorage.setItem('pwa-install-dismissed', '1');
    render(<InstallBanner />);
    fireInstallPrompt();
    expect(screen.queryByRole('banner', { name: /install app banner/i })).not.toBeInTheDocument();
  });

  test('"Not now" button hides the banner and sets localStorage flag', () => {
    render(<InstallBanner />);
    fireInstallPrompt();
    fireEvent.click(screen.getByRole('button', { name: /not now/i }));
    expect(screen.queryByRole('banner', { name: /install app banner/i })).not.toBeInTheDocument();
    expect(localStorage.getItem('pwa-install-dismissed')).toBe('1');
  });

  test('close (X) button hides the banner and sets localStorage flag', () => {
    render(<InstallBanner />);
    fireInstallPrompt();
    fireEvent.click(screen.getByRole('button', { name: /close install banner/i }));
    expect(screen.queryByRole('banner', { name: /install app banner/i })).not.toBeInTheDocument();
    expect(localStorage.getItem('pwa-install-dismissed')).toBe('1');
  });

  test('"Install" button calls prompt() on the deferred event', async () => {
    render(<InstallBanner />);
    const promptEvent = fireInstallPrompt();
    fireEvent.click(screen.getByRole('button', { name: /^install$/i }));
    await promptEvent.userChoice;
    expect(promptEvent.prompt).toHaveBeenCalledTimes(1);
  });

  test('"Install" button hides banner after accepted outcome', async () => {
    render(<InstallBanner />);
    const promptEvent = fireInstallPrompt({ outcome: 'accepted' });
    fireEvent.click(screen.getByRole('button', { name: /^install$/i }));
    await promptEvent.userChoice;
    await waitFor(() => {
      expect(screen.queryByRole('banner', { name: /install app banner/i })).not.toBeInTheDocument();
    });
  });
});
