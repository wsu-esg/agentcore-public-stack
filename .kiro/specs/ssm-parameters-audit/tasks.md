# Implementation Plan: SSM Parameters Audit

## Overview

This implementation plan adds missing SSM parameters to CDK stacks to ensure the runtime-provisioner Lambda function can successfully fetch all required configuration values. The work is organized into discrete tasks that build incrementally, with testing integrated throughout.

## Tasks

- [x] 1. Add missing SSM parameter to InferenceApiStack
  - Add ECR repository URI parameter export
  - Verify existing parameters are still present
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

- [ ]* 1.1 Write unit test for ECR repository URI parameter export
  - **Property 1: Parameter Naming Convention Compliance**
  - **Validates: Requirements 2.1, 8.1**

- [x] 2. Add missing SSM parameter to InfrastructureStack
  - Add OAuth callback URL parameter export
  - Implement conditional logic for custom domain vs ALB URL
  - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [ ]* 2.1 Write unit test for OAuth callback URL with custom domain
  - Test that callback URL uses custom domain when configured
  - **Validates: Requirements 7.2, 7.4**

- [ ]* 2.2 Write unit test for OAuth callback URL with ALB URL
  - Test that callback URL uses ALB URL when no custom domain
  - **Validates: Requirements 7.3, 7.4**

- [ ]* 2.3 Write property test for OAuth callback URL format
  - **Property 2: OAuth Callback URL Format**
  - **Validates: Requirements 7.4**

- [x] 3. Add missing SSM parameter to FrontendStack
  - Add CORS origins parameter export
  - Implement conditional logic for custom domain vs CloudFront domain
  - _Requirements: 5.2, 5.3, 5.4_

- [ ]* 3.1 Write unit test for CORS origins parameter export
  - Test that CORS origins parameter is created
  - **Validates: Requirements 5.2**

- [ ]* 3.2 Write unit test for CORS origins with custom domain
  - Test that CORS origins uses custom domain when configured
  - **Validates: Requirements 5.3**

- [ ]* 3.3 Write unit test for CORS origins with CloudFront domain
  - Test that CORS origins uses CloudFront domain when no custom domain
  - **Validates: Requirements 5.4**

- [x] 4. Update runtime-provisioner Lambda error handling
  - Implement get_optional_parameter function for optional API keys
  - Implement get_required_parameter function for required parameters
  - Add parameter value validation
  - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [ ]* 4.1 Write unit test for optional parameter handling
  - Test that get_optional_parameter returns None for missing parameters
  - **Validates: Requirements 6.2, 6.4**

- [ ]* 4.2 Write unit test for required parameter handling
  - Test that get_required_parameter raises exception for missing parameters
  - **Validates: Requirements 6.1, 6.3**

- [ ]* 4.3 Write unit test for parameter value validation
  - Test URL validation logic
  - **Validates: Requirements 7.4**

- [x] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Create parameter dependency documentation
  - Update design document with complete parameter dependency matrix
  - Document which stacks export each parameter
  - Document which stacks/Lambda functions import each parameter
  - Mark parameters as required or optional
  - _Requirements: 9.1, 9.2, 9.3, 9.4_

- [ ]* 6.1 Write integration test for parameter naming convention
  - Test that all deployed parameters follow naming convention
  - **Property 1: Parameter Naming Convention Compliance**
  - **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7**

- [ ]* 6.2 Write integration test for runtime provisioner parameter fetching
  - Test that runtime provisioner can fetch all required parameters
  - **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 3.1, 3.2, 4.1, 5.1, 5.2, 7.1**

- [ ]* 6.3 Write property test for parameter naming convention
  - **Property 1: Parameter Naming Convention Compliance**
  - **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7**

- [x] 7. Update CDK deployment scripts
  - Verify deployment order is correct (Infrastructure → Inference → Gateway → App → Frontend)
  - Update any deployment documentation
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [x] 8. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- Integration tests validate end-to-end parameter flow after deployment
- The deployment order must be maintained: InfrastructureStack → InferenceApiStack → GatewayStack → AppApiStack → FrontendStack
- Optional API key parameters (/api-keys/*) are NOT created by CDK - they must be manually created by administrators when needed
