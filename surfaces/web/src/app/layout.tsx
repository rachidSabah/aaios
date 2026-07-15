import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'AAiOS — Agentic AI Operating System',
  description:
    'Windows-first, modular runtime for orchestrating generic AI agents.',
  applicationName: 'AAiOS',
  authors: [{ name: 'AAiOS Contributors' }],
  robots: { index: false, follow: false },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
