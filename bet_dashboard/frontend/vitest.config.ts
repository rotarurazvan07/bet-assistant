import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// Vitest 5 shares Vite 8 config surface (peer range ^6||^7||^8).
// jsdom env: MUI + recharts need real DOM APIs; axios goes through MSW's
// setupServer interceptor (node-level), unaffected by jsdom.
export default defineConfig({
    plugins: [react()],
    test: {
        environment: 'jsdom',
        include: ['src/**/*.{test,spec}.{ts,tsx}'],
        setupFiles: ['./src/test/setup.ts'],
        globals: false,
        css: false,
        restoreMocks: true,
        // Threads pool: worker_threads spawn beats vitest 5's hardcoded 60s
        // fork-start constant (START_TIMEOUT=6e4, no config override) — fork
        // workers with jsdom+MSW setup took ~45-60s under container CPU and
        // lost the start race. isolate:false reuses one worker across files;
        // vitest 5 removed `poolOptions` from the config schema — defaults apply.
        pool: 'threads',
        isolate: false,
        coverage: {
            provider: 'v8',
            reporter: ['text', 'html', 'lcov'],
            reportsDirectory: './coverage',
            include: ['src/**/*.{ts,tsx}'],
            exclude: [
                'src/test/**',
                'src/main.tsx',
                'src/**/*.d.ts',
            ],
            // Thresholds intentionally unset here — issue #63 defers them to
            // cycle 14 (coverage-tuning cycle) per testing-suite-57-plan.
        },
    },
});
