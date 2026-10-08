'use client';

import { useEffect, useState, type ReactNode } from 'react';
import { ThemeProvider as Provider, useTheme } from 'next-themes';
import { Moon, Sun } from 'lucide-react';

export function ThemeProvider({ children }: { children: ReactNode }) {
  return <Provider attribute="data-theme" defaultTheme="dark" enableSystem={false} storageKey="liveblocks-theme" disableTransitionOnChange>{children}</Provider>;
}

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const light = mounted && theme === 'light';
  return <button type="button" className="icon-button theme-toggle" aria-label="Light theme" aria-pressed={light} title={light ? 'Switch to dark mode' : 'Switch to light mode'} onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}>
    <Sun size={19} className="theme-sun" aria-hidden="true" />
    <Moon size={19} className="theme-moon" aria-hidden="true" />
  </button>;
}
