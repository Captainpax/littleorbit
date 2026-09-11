"use client";

import { LayoutProvider, ThemeProvider } from "@once-ui-system/core";

export function Providers({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <LayoutProvider>
      <ThemeProvider
        theme="dark"
        neutral="slate"
        brand="violet"
        accent="red"
        solid="color"
        solidStyle="flat"
        border="rounded"
        surface="translucent"
        transition="micro"
        scaling="100"
      >
        {children}
      </ThemeProvider>
    </LayoutProvider>
  );
}
