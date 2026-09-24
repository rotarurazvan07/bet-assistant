// client.ts tests (issue #67). SPEC DIVERGENCE: the issue describes
// interceptors (401 redirect, 500 toast, network retry) — client.ts is a
// 9-line axios.create with ZERO interceptors. Tests pin actual behavior:
// baseURL '/api', JSON content-type header, and raw pass-through of
// 4xx/5xx (no retry, no transformation).

import { describe, it, expect } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '../../test/handlers';
import client from '../client';

describe('api client', () => {
    it('has baseURL /api', () => {
        expect(client.defaults.baseURL).toBe('/api');
    });

    it('sends JSON content-type header', () => {
        expect(client.defaults.headers['Content-Type']).toBe('application/json');
    });

    it('has no response interceptors (divergence pin: no 401/500 handling)', () => {
        expect(client.interceptors.response.handlers?.length ?? 0).toBe(0);
        expect(client.interceptors.request.handlers?.length ?? 0).toBe(0);
    });

    it('4xx rejects with axios error carrying status', async () => {
        server.use(http.get('/api/status', () => HttpResponse.json({ detail: 'nope' }, { status: 404 })));
        await expect(client.get('/status')).rejects.toMatchObject({
            response: { status: 404, data: { detail: 'nope' } },
        });
    });

    it('5xx rejects raw (no toast/retry interceptor exists)', async () => {
        server.use(http.get('/api/status', () => HttpResponse.json({ detail: 'boom' }, { status: 500 })));
        await expect(client.get('/status')).rejects.toMatchObject({
            response: { status: 500 },
        });
    });

    it('network error rejects without response object', async () => {
        server.use(http.get('/api/status', () => Response.error()));
        await expect(client.get('/status')).rejects.toMatchObject({ isAxiosError: true });
    });
});
