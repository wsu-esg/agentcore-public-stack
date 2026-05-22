import { TestBed } from '@angular/core/testing';
import { HttpRequest, HttpHandlerFn, HttpResponse } from '@angular/common/http';
import { signal } from '@angular/core';
import { of } from 'rxjs';
import { describe, it, expect, beforeEach, vi } from 'vitest';

import { csrfInterceptor } from './csrf.interceptor';
import { SessionService } from './session.service';
import { ConfigService } from '../services/config.service';

describe('csrfInterceptor', () => {
  let session: { csrfHeaders: ReturnType<typeof vi.fn> };

  function runInterceptor(req: HttpRequest<unknown>): HttpRequest<unknown> {
    let captured!: HttpRequest<unknown>;
    const next: HttpHandlerFn = (forwarded) => {
      captured = forwarded;
      return of(new HttpResponse({ status: 200 }));
    };
    TestBed.runInInjectionContext(() => {
      csrfInterceptor(req, next).subscribe();
    });
    return captured;
  }

  beforeEach(() => {
    TestBed.resetTestingModule();
    session = { csrfHeaders: vi.fn().mockReturnValue({}) };
    TestBed.configureTestingModule({
      providers: [
        { provide: SessionService, useValue: session },
        // Simulate the production same-origin base URL so /api/... requests
        // match the URL scope check in the interceptor.
        { provide: ConfigService, useValue: { appApiUrl: signal('/api') } },
      ],
    });
  });

  it('skips GET, HEAD, and OPTIONS without consulting SessionService', () => {
    // HttpRequest overloads accept GET/HEAD or OPTIONS/DELETE separately,
    // so build each safe-method request through its specific overload.
    const safeRequests: HttpRequest<unknown>[] = [
      new HttpRequest('GET', '/api/auth/session'),
      new HttpRequest('HEAD', '/api/auth/session'),
      new HttpRequest('OPTIONS', '/api/auth/session'),
    ];
    for (const req of safeRequests) {
      const forwarded = runInterceptor(req);
      expect(forwarded).toBe(req);
    }
    // Skipping safe methods is the perf-sensitive happy path — no signal reads.
    expect(session.csrfHeaders).not.toHaveBeenCalled();
  });

  it('passes the request through unchanged when SessionService has no token', () => {
    session.csrfHeaders.mockReturnValue({});
    const req = new HttpRequest('POST', '/api/sessions', {});
    const forwarded = runInterceptor(req);
    expect(forwarded).toBe(req);
    expect(forwarded.headers.has('X-CSRF-Token')).toBe(false);
  });

  it('attaches X-CSRF-Token from SessionService on POST', () => {
    session.csrfHeaders.mockReturnValue({ 'X-CSRF-Token': 'csrf-secret-abc' });
    const req = new HttpRequest('POST', '/api/sessions/bulk-delete', { ids: [] });
    const forwarded = runInterceptor(req);
    expect(forwarded.headers.get('X-CSRF-Token')).toBe('csrf-secret-abc');
    expect(forwarded.url).toBe('/api/sessions/bulk-delete');
    expect(forwarded.body).toEqual({ ids: [] });
  });

  it('attaches the header on PUT, PATCH, and DELETE', () => {
    session.csrfHeaders.mockReturnValue({ 'X-CSRF-Token': 'tok' });
    const requests: HttpRequest<unknown>[] = [
      new HttpRequest('PUT', '/api/x', {}),
      new HttpRequest('PATCH', '/api/x', {}),
      new HttpRequest('DELETE', '/api/x'),
    ];
    for (const req of requests) {
      const forwarded = runInterceptor(req);
      expect(forwarded.headers.get('X-CSRF-Token')).toBe('tok');
    }
  });

  it('does NOT attach the header to third-party hosts (e.g. S3 presigned PUT URLs)', () => {
    session.csrfHeaders.mockReturnValue({ 'X-CSRF-Token': 'tok' });
    const s3Url = 'https://my-bucket.s3.us-east-1.amazonaws.com/branding/logo_light/abc.png?X-Amz-Signature=xyz';
    const req = new HttpRequest('PUT', s3Url, new Blob());
    const forwarded = runInterceptor(req);
    // Request must pass through unmodified — the extra header would break the
    // AWS presigned URL signature and fail S3 CORS preflight.
    expect(forwarded).toBe(req);
    expect(forwarded.headers.has('X-CSRF-Token')).toBe(false);
  });
});