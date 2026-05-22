import { TestBed } from '@angular/core/testing';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { ThemeService } from './theme.service';

describe('ThemeService', () => {
  let service: ThemeService;
  let localStorageMock: Record<string, string>;

  beforeEach(() => {
    // Provide a working localStorage stand-in. The test runner's browser
    // environment may not implement the full Storage API, causing
    // `localStorage.getItem is not a function` errors.
    localStorageMock = {};
    const storageMock = {
      getItem: vi.fn((key: string) => localStorageMock[key] ?? null),
      setItem: vi.fn((key: string, value: string) => { localStorageMock[key] = value; }),
      removeItem: vi.fn((key: string) => { delete localStorageMock[key]; }),
      clear: vi.fn(() => { localStorageMock = {}; }),
    };
    Object.defineProperty(window, 'localStorage', { value: storageMock, writable: true });

    TestBed.resetTestingModule();
    TestBed.configureTestingModule({ providers: [ThemeService] });
    service = TestBed.inject(ThemeService);
  });

  afterEach(() => {
    TestBed.resetTestingModule();
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('should have theme signal', () => {
    expect(typeof service.theme()).toBe('string');
    expect(['light', 'dark']).toContain(service.theme());
  });

  it('should have preference signal', () => {
    expect(typeof service.preference()).toBe('string');
    expect(['light', 'dark', 'system']).toContain(service.preference());
  });

  it('should set dark preference', () => {
    service.setPreference('dark');
    expect(service.preference()).toBe('dark');
  });

  it('should set light preference', () => {
    service.setPreference('light');
    expect(service.preference()).toBe('light');
  });

  it('should set system preference', () => {
    service.setPreference('system');
    expect(service.preference()).toBe('system');
  });

  it('should cycle through preferences', () => {
    service.setPreference('dark');
    expect(service.preference()).toBe('dark');
    service.setPreference('light');
    expect(service.preference()).toBe('light');
    service.setPreference('system');
    expect(service.preference()).toBe('system');
  });
});