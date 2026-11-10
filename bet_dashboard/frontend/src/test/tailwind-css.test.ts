import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import postcss from 'postcss';
import tailwind from '@tailwindcss/postcss';
import { describe, expect, it } from 'vitest';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..');

async function buildCss(): Promise<string> {
  const css = readFileSync(resolve(root, 'src/index.css'), 'utf8');
  const result = await postcss([tailwind]).process(css, { from: resolve(root, 'src/index.css') });
  return result.css;
}

describe('tailwind css build', () => {
  it('emits utilities and the custom theme so layout cannot silently regress', async () => {
    const css = await buildCss();

    // Utilities from the theme: a config-loading failure drops every utility rule.
    expect(css).toContain('.font-medium');
    expect(css).toContain('.px-4');
    expect(css).toContain('.rounded-lg');

    // Custom theme values referenced by app code (originally a JS config).
    expect(css).toMatch(/--color-accent:\s*#3d7bff/i);
    expect(css).toMatch(/--font-sans:/);

    // A silent config/pipeline failure removes the whole utilities layer,
    // which is exactly the production UI regression this guards.
  });
});
