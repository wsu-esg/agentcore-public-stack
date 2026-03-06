/**
 * TypeScript models for admin user management.
 * Mirrors backend Pydantic models from apis/app_api/admin/users/models.py
 */

// ========== User Status ==========

export type UserStatus = 'active' | 'inactive' | 'suspended';

// ========== User List Item ==========

export interface UserListItem {
  userId: string;
  email: string;
  name: string;
  status: UserStatus;
  lastLoginAt: string;
  emailDomain?: string;
  currentMonthCost?: number;
  quotaUsagePercentage?: number;
}

// ========== User List Response ==========

export interface UserListResponse {
  users: UserListItem[];
  nextCursor?: string;
  totalCount?: number;
}

// ========== Quota Status ==========

export interface QuotaStatus {
  tierId?: string;
  tierName?: string;
  matchedBy?: string;
  monthlyLimit?: number;
  currentUsage: number;
  usagePercentage: number;
  remaining?: number;
  hasActiveOverride: boolean;
  overrideReason?: string;
}

// ========== Cost Summary ==========

export interface CostSummary {
  totalCost: number;
  totalRequests: number;
  totalInputTokens: number;
  totalOutputTokens: number;
  cacheSavings: number;
  primaryModel?: string;
}

// ========== Quota Event Summary ==========

export interface QuotaEventSummary {
  eventId: string;
  eventType: 'warning' | 'block' | 'reset' | 'override_applied';
  timestamp: string;
  percentageUsed: number;
}

// ========== User Profile ==========

export interface UserProfile {
  userId: string;
  email: string;
  name: string;
  roles: string[];
  picture?: string;
  emailDomain: string;
  createdAt: string;
  lastLoginAt: string;
  status: UserStatus;
}

// ========== User Detail Response ==========

export interface UserDetailResponse {
  profile: UserProfile;
  costSummary: CostSummary;
  quotaStatus: QuotaStatus;
  recentEvents: QuotaEventSummary[];
}

// ========== Request Options ==========

export interface UserListRequestOptions {
  status?: UserStatus;
  domain?: string;
  limit?: number;
  cursor?: string;
}

export interface UserSearchOptions {
  email: string;
}
 