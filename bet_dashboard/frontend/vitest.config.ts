import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// Vitest 5 shares Vite 8 config surface (peer range ^6||^7||^8).
// jsdom env (restored after happy-dom experiment 2026-09-24): the experiment
// did NOT fix the container-level blocker — worker spawn dies at vitest 5's
// hardcoded 60s START_TIMEOUT regardless of DOM env (14 diagnostics in
// automation-summary-issue-64.md §3; jsdom proven green 72/72 at 18:19).
// happy-dom uninstalled; jsdom 30 stays.
// DOM APIs for MUI/recharts covered by setup.ts polyfills; axios goes through
// MSW's setupServer interceptor (node-level), unaffected by the DOM env.
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
        deps: {
            // Disable vitest's in-worker dep re-optimization: after
            // user-event entered the import graph, vite's test-mode
            // re-bundling (esbuild pre-bundle of MUI/recharts/MSW/RTL)
            // exceeded the hardcoded 60s worker-start window inside this
            // container, killing every worker spawn (even zero-import
            // probes). vite-node transforms deps on demand instead.
            optimizer: {
                web: { enabled: false },
            },
        },
        // Serialize test files through the single shared worker: parallel
        // thread workers each pay ~45-60s jsdom+MSW env setup under container
        // CPU and can lose vitest's hardcoded 60s worker-start race.
        fileParallelism: false,
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
            // Coverage thresholds (cycle 14, issue #71 gates half — D32):
            // vitest 5's typed thresholds API is FLAT per-metric only
            // (Partial<Record<'lines'|'functions'|'statements'|'branches',
            // number>>, node.d.ts:255-263) — the vitest-3 per-path shape
            // ('src/glob/**': {lines: N}) is NOT supported by installed v5.
            // Per-layer gating (api ≥95, hooks ≥90, components later) is
            // therefore deferred to CI (cycle 15), where per-path checks run
            // against the coverage report. NO global threshold by design.
        },
    },
});
