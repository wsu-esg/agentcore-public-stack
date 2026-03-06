import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { AuthApiService, RuntimeEndpointResponse } from './auth-api.service';
import { ConfigService } from '../services/config.service';
import { signal } from '@angular/core';

describe('AuthApiService', () => {
  let service: AuthApiService;
  let httpMock: HttpTestingController;
  let configService: Partial<ConfigService>;

  beforeEach(() => {
    configService = {
      appApiUrl: signal('http://localhost:8000')
    };

    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [
        AuthApiService,
        { provide: ConfigService, useValue: configService }
      ]
    });

    service = TestBed.inject(AuthApiService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  describe('getRuntimeEndpoint', () => {
    it('should fetch runtime endpoint URL', async () => {
      const mockResponse: RuntimeEndpointResponse = {
        runtime_endpoint_url: 'https://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/arn:aws:bedrock-agentcore:us-east-1:123456789012:agent/abc-123/invocations',
        provider_id: 'entra-id'
      };

      const promise = new Promise<RuntimeEndpointResponse>((resolve, reject) => {
        service.getRuntimeEndpoint().subscribe({
          next: resolve,
          error: reject
        });
      });

      const req = httpMock.expectOne('http://localhost:8000/auth/runtime-endpoint');
      expect(req.request.method).toBe('GET');
      req.flush(mockResponse);

      const response = await promise;
      expect(response).toEqual(mockResponse);
      expect(response.runtime_endpoint_url).toBe(mockResponse.runtime_endpoint_url);
      expect(response.provider_id).toBe('entra-id');
    });

    it('should handle 404 error when provider not found', async () => {
      const promise = new Promise<RuntimeEndpointResponse>((resolve, reject) => {
        service.getRuntimeEndpoint().subscribe({
          next: resolve,
          error: reject
        });
      });

      const req = httpMock.expectOne('http://localhost:8000/auth/runtime-endpoint');
      req.flush('Runtime not found for provider', { status: 404, statusText: 'Not Found' });

      try {
        await promise;
        throw new Error('Should have thrown 404 error');
      } catch (error: any) {
        expect(error.status).toBe(404);
      }
    });

    it('should handle 401 error when user not authenticated', async () => {
      const promise = new Promise<RuntimeEndpointResponse>((resolve, reject) => {
        service.getRuntimeEndpoint().subscribe({
          next: resolve,
          error: reject
        });
      });

      const req = httpMock.expectOne('http://localhost:8000/auth/runtime-endpoint');
      req.flush('Unauthorized', { status: 401, statusText: 'Unauthorized' });

      try {
        await promise;
        throw new Error('Should have thrown 401 error');
      } catch (error: any) {
        expect(error.status).toBe(401);
      }
    });
  });
});
