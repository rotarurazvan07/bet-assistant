import { execFileSync } from 'node:child_process';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

function getCommitSha() {
    if (process.env.VITE_COMMIT_SHA) return process.env.VITE_COMMIT_SHA;
    try {
        return execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim();
    } catch {
        return 'unknown';
    }
}

export default defineConfig({
    plugins: [react()],
    define: {
        'import.meta.env.VITE_COMMIT_SHA': JSON.stringify(getCommitSha()),
    },
    server: {
        proxy: {
            '/api': { target: 'http://localhost:8000', changeOrigin: true },
            '/ws': { target: 'ws://localhost:8000', changeOrigin: true, ws: true },
        },
    },
});
