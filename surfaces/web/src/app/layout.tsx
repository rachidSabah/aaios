import type { Metadata } from 'next';
import Link from 'next/link';
import './globals.css';

export const metadata: Metadata = {
  title: 'AAiOS — Agentic AI Operating System',
  description:
    'Windows-first, modular runtime for orchestrating generic AI agents.',
  applicationName: 'AAiOS',
  authors: [{ name: 'AAiOS Contributors' }],
  robots: { index: false, follow: false },
};

const navItems = [
  { href: '/', label: 'Overview' },
  { href: '/ai-brain', label: 'AI Brain' },
  { href: '/intelligence', label: 'Intelligence' },
  { href: '/missions', label: 'Missions' },
  { href: '/execution', label: 'Execution' },
  { href: '/workflows', label: 'Workflows' },
  { href: '/monitoring', label: 'Monitoring' },
  { href: '/analytics', label: 'Analytics' },
  { href: '/experience', label: 'Experience' },
  { href: '/learning', label: 'Learning' },
  { href: '/engineering', label: 'Engineering' },
  { href: '/research', label: 'Research' },
  { href: '/repository', label: 'Repository' },
  { href: '/architecture', label: 'Architecture' },
  { href: '/reviews', label: 'Reviews' },
  { href: '/test-intelligence', label: 'Test Intel' },
  { href: '/release-readiness', label: 'Release' },
  { href: '/repository-health', label: 'Health' },
];

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <div
          style={{
            minHeight: '100vh',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <header
            style={{
              borderBottom: '1px solid var(--color-border)',
              padding: '0.75rem 1.5rem',
              display: 'flex',
              alignItems: 'center',
              gap: '2rem',
              backgroundColor: 'var(--color-card)',
            }}
          >
            <Link
              href="/"
              style={{
                fontWeight: 700,
                fontSize: '1rem',
                color: 'var(--color-fg)',
                textDecoration: 'none',
              }}
            >
              AAiOS
            </Link>
            <nav style={{ display: 'flex', gap: '1.25rem' }}>
              {navItems.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  style={{
                    color: 'var(--color-muted)',
                    textDecoration: 'none',
                    fontSize: '0.875rem',
                    fontWeight: 500,
                  }}
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          </header>
          <main style={{ flex: 1 }}>{children}</main>
        </div>
      </body>
    </html>
  );
}
