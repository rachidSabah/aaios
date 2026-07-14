import { describe, it, expect } from 'vitest';

describe('AAiOS web — Phase 2 stub', () => {
  it('Vitest is wired up correctly', () => {
    expect(1 + 1).toBe(2);
  });

  it('The HealthResponse type accepts the expected shape', () => {
    const sample = {
      status: 'ok',
      version: '0.1.0.dev0',
      python: '3.12.0',
      platform: 'Windows-11',
      timestamp: '2026-07-14T00:00:00Z',
      checks: { process: 'alive' },
    };
    expect(sample.status).toBe('ok');
    expect(sample.checks.process).toBe('alive');
  });
});
