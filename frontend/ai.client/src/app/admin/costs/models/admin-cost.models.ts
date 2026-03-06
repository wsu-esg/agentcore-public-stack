/**
 * TypeScript models for admin cost dashboard.
 * Mirrors backend Pydantic models from apis/app_api/admin/costs/models.py
 */

// ========== Model Breakdown ==========

export interface ModelBreakdownItem {
  cost: number;
  requests: number;
}

// ========== Top User Cost ==========

export interface TopUserCost {
  userId: string;
  totalCost: number;
  totalRequests: number;
  lastUpdated: string;

  // Optional enrichment fields
  email?: string;
  tierName?: string;
  quotaLimit?: number;
  quotaPercentage?: number;
}

// ========== System Cost Summary ==========

export interface SystemCostSummary {
  period: string; // "2025-01" or "2025-01-15"
  periodType: 'daily' | 'monthly';

  totalCost: number;
  totalRequests: number;
  activeUsers: number;

  totalInputTokens: number;
  totalOutputTokens: number;
  totalCacheSavings: number;

  modelBreakdown?: Record<string, ModelBreakdownItem>;
  lastUpdated: string;
}

// ========== Model Usage Summary ==========

export interface ModelUsageSummary {
  modelId: string;
  modelName: string;
  provider: string;

  totalCost: number;
  totalRequests: number;
  uniqueUsers: number;
  avgCostPerRequest: number;

  totalInputTokens: number;
  totalOutputTokens: number;
}

// ========== Tier Usage Summary ==========

export interface TierUsageSummary {
  tierId: string;
  tierName: string;

  totalCost: number;
  totalUsers: number;
  usersAtLimit: number;
  usersWarned: number;
  avgUtilization: number;
}

// ========== Cost Trend ==========

export interface CostTrend {
  date: string;
  totalCost: number;
  totalRequests: number;
  activeUsers: number;
}

// ========== Admin Cost Dashboard ==========

export interface AdminCostDashboard {
  currentPeriod: SystemCostSummary;
  topUsers: TopUserCost[];
  modelUsage: ModelUsageSummary[];
  tierUsage?: TierUsageSummary[];
  dailyTrends?: CostTrend[];
}

// ========== API Request Options ==========

export interface DashboardRequestOptions {
  period?: string;
  topUsersLimit?: number;
  includeTrends?: boolean;
}

export interface TopUsersRequestOptions {
  period?: string;
  limit?: number;
  minCost?: number;
  tierId?: string;
}

export interface TrendsRequestOptions {
  startDate: string;
  endDate: string;
}

export interface ExportRequestOptions {
  period?: string;
  format: 'csv' | 'json';
}
