import type { ReactNode } from 'react';

export function StepLabel({ children }: { children: ReactNode }) {
  return <div className="step-label">{children}</div>;
}
