import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { provideRouter, ActivatedRoute } from '@angular/router';
import { signal } from '@angular/core';
import { InferenceJobDetailPage } from './inference-job-detail.page';
import { FineTuningStateService } from '../../services/fine-tuning-state.service';
import type { InferenceJobResponse, DownloadResponse } from '../../models/fine-tuning.models';

const mockJob: InferenceJobResponse = {
  job_id: 'ij-1',
  user_id: 'u1',
  email: 'test@example.com',
  job_type: 'BATCH_TRANSFORM',
  training_job_id: 'tj-1',
  model_name: 'Test Model',
  model_s3_path: 's3://bucket/model',
  status: 'TRANSFORMING',
  input_s3_key: 's3://bucket/input.jsonl',
  output_s3_prefix: null,
  result_s3_key: null,
  instance_type: 'ml.g5.xlarge',
  transform_job_name: 'transform-job-1',
  transform_start_time: '2026-03-01T01:00:00Z',
  transform_end_time: null,
  billable_seconds: 120,
  estimated_cost_usd: 5.0,
  created_at: '2026-03-02T00:00:00Z',
  updated_at: '2026-03-02T01:00:00Z',
  error_message: null,
  max_runtime_seconds: 3600,
};

function createMockState() {
  return {
    currentInferenceJob: signal<InferenceJobResponse | null>(mockJob),
    currentLogs: signal<string[]>(['inference log 1']),
    loading: signal(false),
    error: signal<string | null>(null),
    loadInferenceJobDetail: vi.fn().mockResolvedValue(undefined),
    loadInferenceJobLogs: vi.fn().mockResolvedValue(undefined),
    getInferenceDownloadUrl: vi.fn().mockResolvedValue({
      download_url: 'https://s3.example.com/results',
      expires_at: '2026-03-02T02:00:00Z',
      result_s3_key: 'results/output.jsonl',
    } as DownloadResponse),
    stopInferenceJob: vi.fn().mockResolvedValue(undefined),
    clearError: vi.fn(),
  };
}

describe('InferenceJobDetailPage', () => {
  let mockState: ReturnType<typeof createMockState>;

  beforeEach(() => {
    mockState = createMockState();
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        { provide: FineTuningStateService, useValue: mockState },
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: { paramMap: { get: (key: string) => key === 'jobId' ? 'ij-1' : null } },
          },
        },
      ],
    });
    TestBed.overrideComponent(InferenceJobDetailPage, {
      set: { template: '<div></div>' },
    });
  });

  afterEach(() => {
    TestBed.resetTestingModule();
  });

  function createComponent() {
    const fixture = TestBed.createComponent(InferenceJobDetailPage);
    fixture.detectChanges();
    return fixture.componentInstance;
  }

  it('should load job detail and logs on init', () => {
    createComponent();
    expect(mockState.loadInferenceJobDetail).toHaveBeenCalledWith('ij-1');
    expect(mockState.loadInferenceJobLogs).toHaveBeenCalledWith('ij-1');
  });

  it('should refresh job detail and logs together', async () => {
    const component = createComponent();
    mockState.loadInferenceJobDetail.mockClear();
    mockState.loadInferenceJobLogs.mockClear();
    await component.refreshJob();
    expect(mockState.loadInferenceJobDetail).toHaveBeenCalledWith('ij-1');
    expect(mockState.loadInferenceJobLogs).toHaveBeenCalledWith('ij-1');
  });

  it('should refresh only logs', async () => {
    const component = createComponent();
    mockState.loadInferenceJobLogs.mockClear();
    await component.refreshLogs();
    expect(mockState.loadInferenceJobLogs).toHaveBeenCalledWith('ij-1');
  });

  it('should show stop confirmation', () => {
    const component = createComponent();
    expect(component.confirmingStop()).toBe(false);
    component.confirmStop();
    expect(component.confirmingStop()).toBe(true);
  });

  it('should cancel stop confirmation', () => {
    const component = createComponent();
    component.confirmStop();
    component.cancelStop();
    expect(component.confirmingStop()).toBe(false);
  });

  it('should execute stop and reload detail', async () => {
    const component = createComponent();
    component.confirmStop();
    mockState.loadInferenceJobDetail.mockClear();
    await component.executeStop();
    expect(component.confirmingStop()).toBe(false);
    expect(mockState.stopInferenceJob).toHaveBeenCalledWith('ij-1');
    expect(mockState.loadInferenceJobDetail).toHaveBeenCalledWith('ij-1');
  });

  it('should download results and open URL', async () => {
    const component = createComponent();
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null);
    await component.downloadResults();
    expect(mockState.getInferenceDownloadUrl).toHaveBeenCalledWith('ij-1');
    expect(openSpy).toHaveBeenCalledWith('https://s3.example.com/results', '_blank');
    expect(component.loadingDownload()).toBe(false);
    openSpy.mockRestore();
  });

  it('should set download error on failure', async () => {
    const component = createComponent();
    mockState.getInferenceDownloadUrl.mockRejectedValueOnce(new Error('Download failed'));
    await component.downloadResults();
    expect(component.downloadError()).toBe('Download failed');
    expect(component.loadingDownload()).toBe(false);
  });

  it('should set generic download error for non-Error throws', async () => {
    const component = createComponent();
    mockState.getInferenceDownloadUrl.mockRejectedValueOnce('unknown');
    await component.downloadResults();
    expect(component.downloadError()).toBe('Failed to get download URL');
  });

  it('should identify stoppable statuses', () => {
    const component = createComponent();
    expect(component.canStop('PENDING')).toBe(true);
    expect(component.canStop('TRANSFORMING')).toBe(true);
    expect(component.canStop('COMPLETED')).toBe(false);
    expect(component.canStop('FAILED')).toBe(false);
    expect(component.canStop('STOPPED')).toBe(false);
  });

  it('should format duration with hours, minutes, seconds', () => {
    const component = createComponent();
    expect(component.formatDuration(7261)).toBe('2h 1m 1s');
    expect(component.formatDuration(120)).toBe('2m 0s');
    expect(component.formatDuration(45)).toBe('45s');
    expect(component.formatDuration(0)).toBe('0s');
  });

  it('should return dash for null duration', () => {
    const component = createComponent();
    expect(component.formatDuration(null)).toBe('-');
  });

  it('should format cost as USD', () => {
    const component = createComponent();
    expect(component.formatCost(5.0)).toBe('$5.00');
    expect(component.formatCost(0)).toBe('$0.00');
  });

  it('should return dash for null cost', () => {
    const component = createComponent();
    expect(component.formatCost(null)).toBe('-');
  });

  // ── Elapsed timer ─────────────────────────────────────────────────

  it('should initialize now signal with current timestamp', () => {
    const before = Date.now();
    const component = createComponent();
    const after = Date.now();
    expect(component.now()).toBeGreaterThanOrEqual(before);
    expect(component.now()).toBeLessThanOrEqual(after);
  });

  it('should compute elapsed for active inference job', () => {
    const component = createComponent();
    // mockJob has status TRANSFORMING and transform_start_time set
    const elapsed = component.elapsed();
    expect(elapsed).not.toBeNull();
    expect(elapsed).toMatch(/\d+/);
  });

  it('should return null elapsed for completed job', () => {
    mockState.currentInferenceJob.set({ ...mockJob, status: 'COMPLETED' });
    const component = createComponent();
    expect(component.elapsed()).toBeNull();
  });

  it('should use created_at when transform_start_time is null', () => {
    mockState.currentInferenceJob.set({
      ...mockJob,
      status: 'PENDING',
      transform_start_time: null,
      created_at: new Date(Date.now() - 60_000).toISOString(),
    });
    const component = createComponent();
    const elapsed = component.elapsed();
    expect(elapsed).not.toBeNull();
    expect(elapsed).toMatch(/\d+/);
  });

  // ── Polling ───────────────────────────────────────────────────────

  it('should start polling on init for active jobs', () => {
    vi.useFakeTimers();
    try {
      const component = createComponent();
      mockState.loadInferenceJobDetail.mockClear();
      mockState.loadInferenceJobLogs.mockClear();

      vi.advanceTimersByTime(10_000);

      expect(mockState.loadInferenceJobDetail).toHaveBeenCalledWith('ij-1');
      expect(mockState.loadInferenceJobLogs).toHaveBeenCalledWith('ij-1');
    } finally {
      vi.useRealTimers();
    }
  });

  it('should stop polling when job reaches terminal status', () => {
    vi.useFakeTimers();
    try {
      const component = createComponent();
      // Simulate job completing
      mockState.currentInferenceJob.set({ ...mockJob, status: 'COMPLETED' });
      mockState.loadInferenceJobDetail.mockClear();

      vi.advanceTimersByTime(10_000);
      // Polling should have stopped — no new calls
      vi.advanceTimersByTime(10_000);

      expect(mockState.loadInferenceJobDetail).not.toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });
});
