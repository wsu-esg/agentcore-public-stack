# Admin Aggregate User Cost Dashboard Specification

## Executive Summary

This specification outlines a performant admin dashboard for viewing aggregate user costs across 10,000+ users. The design avoids table scans by leveraging new GSIs and pre-aggregated data structures, ensuring sub-second response times even at scale.

**Target Performance:**
- Dashboard load: <500ms for 10,000+ users
- Top N queries: <200ms
- Time-series aggregations: <300ms
- Zero table scans

**Prerequisites:** User cost tracking and quota management (already implemented)

---

## Table of Contents

1. [Current State Analysis](#current-state-analysis)
2. [Performance Challenge](#performance-challenge)
3. [Solution Architecture](#solution-architecture)
4. [New Infrastructure Requirements](#new-infrastructure-requirements)
5. [Data Models](#data-models)
6. [API Design](#api-design)
7. [Frontend Design](#frontend-design)
8. [Implementation Plan](#implementation-plan)
9. [Appendix: DynamoDB Schema Updates](#appendix-dynamodb-schema-updates)

---

## Current State Analysis

### What We Have

| Component | Status | Notes |
|-----------|--------|-------|
| **SessionsMetadata Table** | Implemented | Message-level cost tracking |
| **UserCostSummary Table** | Implemented | Pre-aggregated monthly costs per user |
| **Cost Aggregator Service** | Implemented | 30-second cache, single-user queries |
| **Quota System** | Implemented | Tier management, enforcement |
| **Admin Quota API** | Implemented | CRUD for tiers, assignments, overrides |
| **User Cost Endpoints** | Implemented | `/costs/summary`, `/costs/detailed-report` |

### Current Table Schemas

**UserCostSummary Table:**
```
PK: USER#<user_id>
SK: PERIOD#<YYYY-MM>

Attributes:
- totalCost, totalRequests, totalInputTokens, totalOutputTokens
- totalCacheReadTokens, totalCacheWriteTokens, cacheSavings
- modelBreakdown: { model_id: { cost, requests, tokens... } }
- lastUpdated, periodStart, periodEnd
```

**Key Limitation:** No way to query "all users sorted by cost" without a table scan.

---

## Performance Challenge

### The Problem

Querying "top 100 users by cost this month" requires:

1. **With current schema:** Table scan of all user records (O(n) - 10,000+ items)
2. **At scale:** 10,000 users × ~1KB per record = 10MB scan
3. **Performance:** 5-10 seconds, expensive, doesn't scale

### DynamoDB Anti-Patterns to Avoid

| Anti-Pattern | Why It's Bad | Our Solution |
|--------------|--------------|--------------|
| Table scan | O(n), slow, expensive | GSI with sorted partition |
| Filter expressions | Scans first, filters after | Query on sort key |
| Large result sets | Memory/network overhead | Pre-aggregated rollups |
| Single hot partition | Throughput limits | Time-bucketed partitions |

---

## Solution Architecture

### Strategy: Pre-Aggregated Rollups + Sorted GSIs

We introduce two new data structures:

1. **PeriodCostIndex GSI** - Enables "top N users by cost for period"
2. **SystemCostRollup Table** - Pre-aggregated system-wide metrics

### Architecture Diagram

```
                                       ┌─────────────────────────────┐
                                       │    Admin Dashboard API      │
                                       └─────────────┬───────────────┘
                                                     │
                      ┌──────────────────────────────┼──────────────────────────────┐
                      │                              │                              │
                      ▼                              ▼                              ▼
         ┌────────────────────┐       ┌────────────────────┐       ┌────────────────────┐
         │  PeriodCostIndex   │       │ SystemCostRollup   │       │ UserCostSummary    │
         │      (GSI)         │       │     (Table)        │       │    (existing)      │
         └────────────────────┘       └────────────────────┘       └────────────────────┘
                  │                            │                            │
                  │                            │                            │
                  ▼                            ▼                            ▼
         ┌────────────────────┐       ┌────────────────────┐       ┌────────────────────┐
         │ Top N users by     │       │ System totals:     │       │ Individual user    │
         │ cost (sorted)      │       │ - Total cost       │       │ cost details       │
         │                    │       │ - Total users      │       │                    │
         │ O(1) query         │       │ - Model breakdown  │       │ O(1) query         │
         └────────────────────┘       └────────────────────┘       └────────────────────┘
```

---

## New Infrastructure Requirements

### 1. PeriodCostIndex (GSI on UserCostSummary)

**Purpose:** Query top users by cost for a given period

**GSI Schema:**
```
GSI Name: PeriodCostIndex
PK: PERIOD#<YYYY-MM>          (all users in this period)
SK: COST#<zero-padded-cost>   (sorted by cost descending)

Projected Attributes: userId, totalCost, totalRequests, lastUpdated
```

**Key Design:**
- **Sort key format:** `COST#<15-digit-zero-padded>`
- Example: $125.50 → `COST#000000000012550` (cents, 15 digits)
- **Descending sort:** Use `ScanIndexForward=False`
- **Limit support:** `Limit=100` for top 100

**Query Patterns:**
```python
# Top 100 users by cost this month
response = table.query(
    IndexName="PeriodCostIndex",
    KeyConditionExpression="GSI2PK = :period",
    ExpressionAttributeValues={":period": "PERIOD#2025-01"},
    ScanIndexForward=False,  # Descending (highest cost first)
    Limit=100
)

# Users with cost > $50 this month
response = table.query(
    IndexName="PeriodCostIndex",
    KeyConditionExpression="GSI2PK = :period AND GSI2SK >= :min_cost",
    ExpressionAttributeValues={
        ":period": "PERIOD#2025-01",
        ":min_cost": "COST#000000000005000"  # $50.00 in cents
    },
    ScanIndexForward=False
)
```

### 2. SystemCostRollup Table

**Purpose:** Pre-aggregated system-wide metrics (no per-user queries needed)

**Schema:**
```
Table: SystemCostRollup

PK: ROLLUP#<type>              (DAILY, MONTHLY, MODEL, TIER)
SK: <identifier>               (date, model_id, tier_id)

Attributes (vary by type):
- totalCost, totalRequests, totalUsers
- totalInputTokens, totalOutputTokens
- totalCacheSavings
- modelBreakdown (for period rollups)
- lastUpdated
```

**Item Types:**

```python
# Daily rollup
{
    "PK": "ROLLUP#DAILY",
    "SK": "2025-01-15",
    "totalCost": Decimal("1250.50"),
    "totalRequests": 45000,
    "activeUsers": 850,
    "newUsers": 12,
    "totalInputTokens": 50000000,
    "totalOutputTokens": 25000000,
    "totalCacheSavings": Decimal("125.00"),
    "lastUpdated": "2025-01-15T23:59:59Z"
}

# Monthly rollup
{
    "PK": "ROLLUP#MONTHLY",
    "SK": "2025-01",
    "totalCost": Decimal("15250.75"),
    "totalRequests": 450000,
    "activeUsers": 2500,
    "totalUsers": 5000,  # All users with any historical activity
    "modelBreakdown": {
        "claude_sonnet_4": {"cost": 10000, "requests": 300000},
        "claude_opus_4": {"cost": 5000, "requests": 50000}
    },
    "topModels": ["claude_sonnet_4", "claude_opus_4", "claude_haiku"],
    "lastUpdated": "2025-01-31T23:59:59Z"
}

# Per-model rollup (for model analytics)
{
    "PK": "ROLLUP#MODEL",
    "SK": "2025-01#claude_sonnet_4",
    "totalCost": Decimal("10000.00"),
    "totalRequests": 300000,
    "uniqueUsers": 2000,
    "avgCostPerRequest": Decimal("0.033"),
    "totalInputTokens": 30000000,
    "totalOutputTokens": 15000000,
    "lastUpdated": "2025-01-31T23:59:59Z"
}

# Per-tier rollup (for quota tier analytics)
{
    "PK": "ROLLUP#TIER",
    "SK": "2025-01#basic",
    "tierId": "basic",
    "tierName": "Basic",
    "totalCost": Decimal("5000.00"),
    "totalUsers": 3000,
    "usersAtLimit": 150,
    "usersWarned": 500,
    "avgUtilization": Decimal("0.45"),  # 45% of quota used on average
    "lastUpdated": "2025-01-31T23:59:59Z"
}
```

### 3. Update Trigger for Rollups

**When a user's cost is updated:**
1. Update `UserCostSummary` (existing behavior)
2. Update `PeriodCostIndex` GSI attributes (automatic with GSI)
3. Update `SystemCostRollup` (async, can be slightly delayed)

**Implementation Options:**

| Option | Pros | Cons |
|--------|------|------|
| **A) Synchronous update** | Always consistent | Adds latency to every request |
| **B) DynamoDB Streams + Lambda** | Decoupled, scalable | Additional infrastructure |
| **C) Async task (in-process)** | Simple, no extra infra | Slight delay in rollup accuracy |
| **D) Scheduled batch job** | Very simple | Stale data between runs |

**Recommendation:** Option C (Async in-process) for Phase 1, Option B for Phase 2.

```python
# In stream_coordinator.py after storing message metadata
async def _update_system_rollups(
    self,
    user_id: str,
    cost: float,
    usage: Dict[str, int],
    model_id: str,
    timestamp: str
):
    """Update system-wide rollups asynchronously"""
    # Fire and forget - don't block the response
    asyncio.create_task(
        self._do_rollup_update(user_id, cost, usage, model_id, timestamp)
    )
```

---

## Data Models

### Backend Models

**File:** `backend/src/apis/app_api/admin/costs/models.py`

```python
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict
from decimal import Decimal


class TopUserCost(BaseModel):
    """User cost summary for admin dashboard"""
    model_config = ConfigDict(populate_by_name=True)

    user_id: str = Field(..., alias="userId")
    total_cost: float = Field(..., alias="totalCost")
    total_requests: int = Field(..., alias="totalRequests")
    last_updated: str = Field(..., alias="lastUpdated")

    # Optional enrichment
    email: Optional[str] = None
    tier_name: Optional[str] = Field(None, alias="tierName")
    quota_limit: Optional[float] = Field(None, alias="quotaLimit")
    quota_percentage: Optional[float] = Field(None, alias="quotaPercentage")


class SystemCostSummary(BaseModel):
    """System-wide cost summary"""
    model_config = ConfigDict(populate_by_name=True)

    period: str  # "2025-01" or "2025-01-15"
    period_type: str = Field(..., alias="periodType")  # "daily" or "monthly"

    total_cost: float = Field(..., alias="totalCost")
    total_requests: int = Field(..., alias="totalRequests")
    active_users: int = Field(..., alias="activeUsers")

    total_input_tokens: int = Field(..., alias="totalInputTokens")
    total_output_tokens: int = Field(..., alias="totalOutputTokens")
    total_cache_savings: float = Field(..., alias="totalCacheSavings")

    model_breakdown: Optional[Dict[str, Dict]] = Field(None, alias="modelBreakdown")
    last_updated: str = Field(..., alias="lastUpdated")


class ModelUsageSummary(BaseModel):
    """Per-model usage summary"""
    model_config = ConfigDict(populate_by_name=True)

    model_id: str = Field(..., alias="modelId")
    model_name: str = Field(..., alias="modelName")
    provider: str

    total_cost: float = Field(..., alias="totalCost")
    total_requests: int = Field(..., alias="totalRequests")
    unique_users: int = Field(..., alias="uniqueUsers")
    avg_cost_per_request: float = Field(..., alias="avgCostPerRequest")

    total_input_tokens: int = Field(..., alias="totalInputTokens")
    total_output_tokens: int = Field(..., alias="totalOutputTokens")


class TierUsageSummary(BaseModel):
    """Per-tier usage summary"""
    model_config = ConfigDict(populate_by_name=True)

    tier_id: str = Field(..., alias="tierId")
    tier_name: str = Field(..., alias="tierName")

    total_cost: float = Field(..., alias="totalCost")
    total_users: int = Field(..., alias="totalUsers")
    users_at_limit: int = Field(..., alias="usersAtLimit")
    users_warned: int = Field(..., alias="usersWarned")
    avg_utilization: float = Field(..., alias="avgUtilization")


class CostTrend(BaseModel):
    """Cost trend data point"""
    model_config = ConfigDict(populate_by_name=True)

    date: str
    total_cost: float = Field(..., alias="totalCost")
    total_requests: int = Field(..., alias="totalRequests")
    active_users: int = Field(..., alias="activeUsers")


class AdminCostDashboard(BaseModel):
    """Complete admin cost dashboard response"""
    model_config = ConfigDict(populate_by_name=True)

    # Current period summary
    current_period: SystemCostSummary = Field(..., alias="currentPeriod")

    # Top users (configurable limit)
    top_users: List[TopUserCost] = Field(..., alias="topUsers")

    # Model breakdown
    model_usage: List[ModelUsageSummary] = Field(..., alias="modelUsage")

    # Tier breakdown (if quota system enabled)
    tier_usage: Optional[List[TierUsageSummary]] = Field(None, alias="tierUsage")

    # Historical trends
    daily_trends: Optional[List[CostTrend]] = Field(None, alias="dailyTrends")
```

---

## API Design

### Admin Cost Endpoints

**File:** `backend/src/apis/app_api/admin/costs/routes.py`

```python
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional, List
from datetime import datetime

from apis.shared.auth.dependencies import get_current_user, require_admin
from apis.shared.auth.models import User
from .models import (
    TopUserCost, SystemCostSummary, ModelUsageSummary,
    TierUsageSummary, AdminCostDashboard, CostTrend
)
from .service import AdminCostService

router = APIRouter(prefix="/admin/costs", tags=["admin-costs"])


@router.get("/dashboard", response_model=AdminCostDashboard)
async def get_cost_dashboard(
    period: Optional[str] = Query(
        None,
        description="Period (YYYY-MM), defaults to current month"
    ),
    top_users_limit: int = Query(
        100,
        ge=1,
        le=1000,
        alias="topUsersLimit",
        description="Number of top users to return"
    ),
    include_trends: bool = Query(
        True,
        alias="includeTrends",
        description="Include daily trends for the period"
    ),
    current_user: User = Depends(require_admin)
):
    """
    Get comprehensive admin cost dashboard

    Returns:
    - System-wide cost summary for the period
    - Top N users by cost (sorted descending)
    - Model usage breakdown
    - Tier usage breakdown (if quota system enabled)
    - Daily trends (optional)

    Performance: <500ms for 10,000+ users (no table scans)
    """
    service = AdminCostService()
    return await service.get_dashboard(
        period=period,
        top_users_limit=top_users_limit,
        include_trends=include_trends
    )


@router.get("/top-users", response_model=List[TopUserCost])
async def get_top_users(
    period: Optional[str] = Query(None, description="Period (YYYY-MM)"),
    limit: int = Query(100, ge=1, le=1000),
    min_cost: Optional[float] = Query(
        None,
        alias="minCost",
        description="Minimum cost threshold"
    ),
    tier_id: Optional[str] = Query(
        None,
        alias="tierId",
        description="Filter by quota tier"
    ),
    current_user: User = Depends(require_admin)
):
    """
    Get top users by cost for a period

    Supports:
    - Pagination via limit
    - Minimum cost threshold
    - Filter by quota tier

    Performance: <200ms via GSI query
    """
    service = AdminCostService()
    return await service.get_top_users(
        period=period,
        limit=limit,
        min_cost=min_cost,
        tier_id=tier_id
    )


@router.get("/system-summary", response_model=SystemCostSummary)
async def get_system_summary(
    period: Optional[str] = Query(None, description="Period (YYYY-MM or YYYY-MM-DD)"),
    period_type: str = Query("monthly", enum=["daily", "monthly"]),
    current_user: User = Depends(require_admin)
):
    """
    Get system-wide cost summary

    Uses pre-aggregated rollups for <50ms response.
    """
    service = AdminCostService()
    return await service.get_system_summary(
        period=period,
        period_type=period_type
    )


@router.get("/by-model", response_model=List[ModelUsageSummary])
async def get_usage_by_model(
    period: Optional[str] = Query(None, description="Period (YYYY-MM)"),
    current_user: User = Depends(require_admin)
):
    """
    Get cost breakdown by model

    Returns all models with usage in the period, sorted by cost descending.
    """
    service = AdminCostService()
    return await service.get_usage_by_model(period=period)


@router.get("/by-tier", response_model=List[TierUsageSummary])
async def get_usage_by_tier(
    period: Optional[str] = Query(None, description="Period (YYYY-MM)"),
    current_user: User = Depends(require_admin)
):
    """
    Get cost breakdown by quota tier

    Returns usage statistics per tier, including users at limit.
    """
    service = AdminCostService()
    return await service.get_usage_by_tier(period=period)


@router.get("/trends", response_model=List[CostTrend])
async def get_cost_trends(
    start_date: str = Query(..., alias="startDate", description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., alias="endDate", description="End date (YYYY-MM-DD)"),
    current_user: User = Depends(require_admin)
):
    """
    Get daily cost trends for a date range

    Returns daily aggregates for charting.
    Max range: 90 days.
    """
    service = AdminCostService()
    return await service.get_trends(
        start_date=start_date,
        end_date=end_date
    )


@router.get("/export", response_class=StreamingResponse)
async def export_cost_data(
    period: Optional[str] = Query(None, description="Period (YYYY-MM)"),
    format: str = Query("csv", enum=["csv", "json"]),
    current_user: User = Depends(require_admin)
):
    """
    Export cost data for a period

    Returns all user costs for the period as CSV or JSON.
    Uses streaming to handle large datasets efficiently.
    """
    service = AdminCostService()
    return await service.export_data(period=period, format=format)
```

---

## Frontend Design

### Dashboard Components

#### 1. Main Dashboard Page

**File:** `frontend/ai.client/src/app/admin/costs/admin-costs.page.ts`

```typescript
import { Component, ChangeDetectionStrategy, inject, signal, computed, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AdminCostService } from './services/admin-cost.service';
import { TopUsersTableComponent } from './components/top-users-table.component';
import { CostTrendsChartComponent } from './components/cost-trends-chart.component';
import { ModelBreakdownComponent } from './components/model-breakdown.component';
import { TierBreakdownComponent } from './components/tier-breakdown.component';
import { SystemSummaryCardComponent } from './components/system-summary-card.component';
import { PeriodSelectorComponent } from './components/period-selector.component';

@Component({
  selector: 'app-admin-costs',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    CommonModule,
    FormsModule,
    TopUsersTableComponent,
    CostTrendsChartComponent,
    ModelBreakdownComponent,
    TierBreakdownComponent,
    SystemSummaryCardComponent,
    PeriodSelectorComponent
  ],
  template: `
    <div class="min-h-dvh bg-gray-50 dark:bg-gray-900 p-6">
      <!-- Header -->
      <div class="flex items-center justify-between mb-6">
        <h1 class="text-2xl font-bold text-gray-900 dark:text-white">
          Cost Analytics Dashboard
        </h1>
        <app-period-selector
          [selectedPeriod]="selectedPeriod()"
          (periodChange)="onPeriodChange($event)"
        />
      </div>

      <!-- Loading State -->
      @if (loading()) {
        <div class="flex items-center justify-center h-64">
          <div class="animate-spin rounded-full size-12 border-b-2 border-blue-600"></div>
        </div>
      } @else if (error()) {
        <div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
          <p class="text-red-600 dark:text-red-400">{{ error() }}</p>
        </div>
      } @else {
        <!-- Summary Cards -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <app-system-summary-card
            title="Total Cost"
            [value]="formatCurrency(dashboard()?.currentPeriod?.totalCost)"
            [trend]="costTrend()"
            icon="heroCurrencyDollar"
          />
          <app-system-summary-card
            title="Total Requests"
            [value]="formatNumber(dashboard()?.currentPeriod?.totalRequests)"
            [trend]="requestsTrend()"
            icon="heroChartBar"
          />
          <app-system-summary-card
            title="Active Users"
            [value]="formatNumber(dashboard()?.currentPeriod?.activeUsers)"
            [trend]="usersTrend()"
            icon="heroUsers"
          />
          <app-system-summary-card
            title="Cache Savings"
            [value]="formatCurrency(dashboard()?.currentPeriod?.totalCacheSavings)"
            [trend]="null"
            icon="heroBolt"
          />
        </div>

        <!-- Charts Row -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <app-cost-trends-chart
            [data]="dashboard()?.dailyTrends || []"
          />
          <app-model-breakdown
            [data]="dashboard()?.modelUsage || []"
          />
        </div>

        <!-- Top Users Table -->
        <app-top-users-table
          [users]="dashboard()?.topUsers || []"
          [loading]="loadingMore()"
          (loadMore)="onLoadMore()"
          (userClick)="onUserClick($event)"
        />

        <!-- Tier Breakdown (if available) -->
        @if (dashboard()?.tierUsage?.length) {
          <app-tier-breakdown
            [data]="dashboard()!.tierUsage!"
            class="mt-6"
          />
        }
      }
    </div>
  `
})
export class AdminCostsPage implements OnInit {
  private costService = inject(AdminCostService);

  // State
  selectedPeriod = signal<string>(this.getCurrentPeriod());
  dashboard = signal<AdminCostDashboard | null>(null);
  loading = signal(true);
  loadingMore = signal(false);
  error = signal<string | null>(null);

  // Computed trends (compare to previous period)
  costTrend = computed(() => this.calculateTrend('cost'));
  requestsTrend = computed(() => this.calculateTrend('requests'));
  usersTrend = computed(() => this.calculateTrend('users'));

  ngOnInit() {
    this.loadDashboard();
  }

  async loadDashboard() {
    this.loading.set(true);
    this.error.set(null);

    try {
      const data = await this.costService.getDashboard({
        period: this.selectedPeriod(),
        topUsersLimit: 100,
        includeTrends: true
      });
      this.dashboard.set(data);
    } catch (err) {
      this.error.set('Failed to load dashboard data');
      console.error(err);
    } finally {
      this.loading.set(false);
    }
  }

  onPeriodChange(period: string) {
    this.selectedPeriod.set(period);
    this.loadDashboard();
  }

  async onLoadMore() {
    // Load more users via pagination
    this.loadingMore.set(true);
    // Implementation details...
    this.loadingMore.set(false);
  }

  onUserClick(userId: string) {
    // Navigate to user detail view
  }

  formatCurrency(value: number | undefined): string {
    return value !== undefined
      ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value)
      : '$0.00';
  }

  formatNumber(value: number | undefined): string {
    return value !== undefined
      ? new Intl.NumberFormat('en-US').format(value)
      : '0';
  }

  private getCurrentPeriod(): string {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  }

  private calculateTrend(metric: string): number | null {
    // Compare current period to previous period
    // Return percentage change
    return null; // Placeholder
  }
}
```

#### 2. Top Users Table Component

```typescript
@Component({
  selector: 'app-top-users-table',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
      <div class="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
        <h3 class="text-lg font-semibold text-gray-900 dark:text-white">
          Top Users by Cost
        </h3>
      </div>

      <div class="overflow-x-auto">
        <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
          <thead class="bg-gray-50 dark:bg-gray-900">
            <tr>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                Rank
              </th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                User
              </th>
              <th class="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                Total Cost
              </th>
              <th class="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                Requests
              </th>
              <th class="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                Avg/Request
              </th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                Tier
              </th>
              <th class="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                Quota Used
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-200 dark:divide-gray-700">
            @for (user of users(); track user.userId; let i = $index) {
              <tr
                class="hover:bg-gray-50 dark:hover:bg-gray-700/50 cursor-pointer transition-colors"
                (click)="userClick.emit(user.userId)"
              >
                <td class="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
                  {{ i + 1 }}
                </td>
                <td class="px-4 py-3">
                  <div class="flex items-center gap-3">
                    <div class="size-8 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
                      <span class="text-sm font-medium text-blue-600 dark:text-blue-400">
                        {{ user.email?.charAt(0)?.toUpperCase() || user.userId.charAt(0).toUpperCase() }}
                      </span>
                    </div>
                    <div>
                      <p class="text-sm font-medium text-gray-900 dark:text-white">
                        {{ user.email || user.userId }}
                      </p>
                      @if (user.email) {
                        <p class="text-xs text-gray-500 dark:text-gray-400">
                          {{ user.userId }}
                        </p>
                      }
                    </div>
                  </div>
                </td>
                <td class="px-4 py-3 text-sm text-right font-medium text-gray-900 dark:text-white">
                  {{ formatCurrency(user.totalCost) }}
                </td>
                <td class="px-4 py-3 text-sm text-right text-gray-500 dark:text-gray-400">
                  {{ formatNumber(user.totalRequests) }}
                </td>
                <td class="px-4 py-3 text-sm text-right text-gray-500 dark:text-gray-400">
                  {{ formatCurrency(user.totalCost / (user.totalRequests || 1)) }}
                </td>
                <td class="px-4 py-3">
                  @if (user.tierName) {
                    <span class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400">
                      {{ user.tierName }}
                    </span>
                  }
                </td>
                <td class="px-4 py-3 text-right">
                  @if (user.quotaPercentage !== null && user.quotaPercentage !== undefined) {
                    <div class="flex items-center justify-end gap-2">
                      <div class="w-24 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                        <div
                          class="h-full rounded-full transition-all"
                          [class]="getQuotaBarClass(user.quotaPercentage)"
                          [style.width.%]="Math.min(user.quotaPercentage, 100)"
                        ></div>
                      </div>
                      <span class="text-xs text-gray-500 dark:text-gray-400 w-12 text-right">
                        {{ user.quotaPercentage | number:'1.0-0' }}%
                      </span>
                    </div>
                  }
                </td>
              </tr>
            }
          </tbody>
        </table>
      </div>

      @if (loading()) {
        <div class="px-4 py-3 text-center">
          <span class="text-sm text-gray-500">Loading more...</span>
        </div>
      } @else {
        <div class="px-4 py-3 border-t border-gray-200 dark:border-gray-700">
          <button
            class="text-sm text-blue-600 dark:text-blue-400 hover:underline"
            (click)="loadMore.emit()"
          >
            Load more users
          </button>
        </div>
      }
    </div>
  `
})
export class TopUsersTableComponent {
  users = input.required<TopUserCost[]>();
  loading = input(false);

  userClick = output<string>();
  loadMore = output<void>();

  Math = Math;

  formatCurrency(value: number): string {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(value);
  }

  formatNumber(value: number): string {
    return new Intl.NumberFormat('en-US').format(value);
  }

  getQuotaBarClass(percentage: number): string {
    if (percentage >= 100) return 'bg-red-500';
    if (percentage >= 80) return 'bg-yellow-500';
    return 'bg-green-500';
  }
}
```

### Dashboard Metrics Beyond Cost

The dashboard supports multiple metric types:

| Metric | Description | Use Case |
|--------|-------------|----------|
| **Total Cost** | Sum of all user costs | Budget tracking |
| **Total Requests** | Count of inference requests | Usage volume |
| **Active Users** | Users with activity in period | Adoption tracking |
| **Cache Savings** | Money saved via caching | Optimization ROI |
| **Avg Cost/Request** | Cost efficiency metric | Model selection |
| **Tokens Processed** | Input + output tokens | Capacity planning |
| **Quota Utilization** | % of quota used per tier | Tier pricing |
| **Users at Limit** | Users blocked by quota | Upsell opportunities |

---

## Implementation Plan

### Phase 1: Infrastructure (Week 1)

1. **Add PeriodCostIndex GSI to UserCostSummary table**
   - Create GSI with PK=`PERIOD#<YYYY-MM>`, SK=`COST#<padded>`
   - Update cost aggregator to maintain GSI attributes
   - Test query performance

2. **Create SystemCostRollup table**
   - Define table schema via CDK
   - Implement rollup update logic
   - Add async update to stream coordinator

3. **Backfill existing data** (if needed)
   - Script to populate GSI attributes for existing records
   - Script to generate initial rollup data

### Phase 2: Backend API (Week 2)

1. **Create admin costs service**
   - Implement `get_dashboard()` method
   - Implement `get_top_users()` with GSI query
   - Implement `get_system_summary()` from rollups
   - Implement `get_usage_by_model()` and `get_usage_by_tier()`

2. **Create admin costs routes**
   - Add endpoints to FastAPI router
   - Add admin authentication middleware
   - Add request validation

3. **Testing**
   - Unit tests for service methods
   - Integration tests for API endpoints
   - Performance tests (verify <500ms at scale)

### Phase 3: Frontend (Week 3)

1. **Create dashboard page**
   - Main page layout with period selector
   - Summary cards with trend indicators
   - Loading and error states

2. **Create visualization components**
   - Top users table with sorting
   - Cost trends chart (line chart)
   - Model breakdown (pie/bar chart)
   - Tier usage table

3. **Create admin cost service**
   - HTTP service for API calls
   - Response caching for performance
   - Error handling

### Phase 4: Polish & Optimization (Week 4)

1. **Performance tuning**
   - Verify no table scans in CloudWatch
   - Optimize GSI projections if needed
   - Add server-side caching for rollups

2. **Export functionality**
   - CSV export for compliance/reporting
   - Streaming response for large datasets

3. **Documentation**
   - API documentation
   - Admin user guide
   - Runbook for common operations

---

## Appendix: DynamoDB Schema Updates

### GSI Addition: PeriodCostIndex

**CDK Update for UserCostSummary table:**

```typescript
// In cdk/lib/stacks/cost-tracking-stack.ts

const userCostSummaryTable = new dynamodb.Table(this, 'UserCostSummary', {
  tableName: `UserCostSummary-${stage}`,
  partitionKey: { name: 'PK', type: dynamodb.AttributeType.STRING },
  sortKey: { name: 'SK', type: dynamodb.AttributeType.STRING },
  billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
  pointInTimeRecovery: true,
});

// Add GSI for period-based queries (top users by cost)
userCostSummaryTable.addGlobalSecondaryIndex({
  indexName: 'PeriodCostIndex',
  partitionKey: { name: 'GSI2PK', type: dynamodb.AttributeType.STRING },
  sortKey: { name: 'GSI2SK', type: dynamodb.AttributeType.STRING },
  projectionType: dynamodb.ProjectionType.INCLUDE,
  nonKeyAttributes: ['userId', 'totalCost', 'totalRequests', 'lastUpdated'],
});
```

### Update to DynamoDB Storage

**Update `dynamodb_storage.py` to maintain GSI attributes:**

```python
async def update_user_cost_summary(
    self,
    user_id: str,
    period: str,
    cost_delta: float,
    usage_delta: Dict[str, int],
    timestamp: str,
    model_id: Optional[str] = None,
    model_name: Optional[str] = None,
    cache_savings_delta: float = 0.0
) -> None:
    """Update pre-aggregated cost summary with GSI attributes"""

    # First, get current total to calculate new GSI sort key
    current = await self.get_user_cost_summary(user_id, period)
    current_cost = float(current.get("totalCost", 0)) if current else 0
    new_total_cost = current_cost + cost_delta

    # Format cost for GSI sort key (zero-padded cents for proper sorting)
    # Convert to cents and pad to 15 digits for costs up to $999,999,999,999.99
    cost_cents = int(new_total_cost * 100)
    gsi2_sk = f"COST#{cost_cents:015d}"

    # Update with GSI attributes
    update_expression = """
        ADD totalCost :cost,
            totalRequests :one,
            totalInputTokens :input,
            totalOutputTokens :output,
            totalCacheReadTokens :cacheRead,
            totalCacheWriteTokens :cacheWrite,
            cacheSavings :savings
        SET lastUpdated = :now,
            periodStart = if_not_exists(periodStart, :periodStart),
            periodEnd = if_not_exists(periodEnd, :periodEnd),
            userId = :userId,
            GSI2PK = :gsi2pk,
            GSI2SK = :gsi2sk
    """

    expression_values = {
        ":cost": Decimal(str(cost_delta)),
        ":one": 1,
        ":input": usage_delta.get("inputTokens", 0),
        ":output": usage_delta.get("outputTokens", 0),
        ":cacheRead": usage_delta.get("cacheReadInputTokens", 0),
        ":cacheWrite": usage_delta.get("cacheWriteInputTokens", 0),
        ":savings": Decimal(str(cache_savings_delta)),
        ":now": timestamp,
        ":periodStart": f"{period}-01T00:00:00Z",
        ":periodEnd": f"{period}-31T23:59:59Z",
        ":userId": user_id,
        ":gsi2pk": f"PERIOD#{period}",
        ":gsi2sk": gsi2_sk
    }

    self.cost_summary_table.update_item(
        Key={
            "PK": f"USER#{user_id}",
            "SK": f"PERIOD#{period}"
        },
        UpdateExpression=update_expression,
        ExpressionAttributeValues=expression_values
    )
```

### SystemCostRollup Table

**CDK definition:**

```typescript
const systemCostRollupTable = new dynamodb.Table(this, 'SystemCostRollup', {
  tableName: `SystemCostRollup-${stage}`,
  partitionKey: { name: 'PK', type: dynamodb.AttributeType.STRING },
  sortKey: { name: 'SK', type: dynamodb.AttributeType.STRING },
  billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
  pointInTimeRecovery: true,
});

// GSI for time-range queries on rollups
systemCostRollupTable.addGlobalSecondaryIndex({
  indexName: 'DateRangeIndex',
  partitionKey: { name: 'GSI1PK', type: dynamodb.AttributeType.STRING },
  sortKey: { name: 'GSI1SK', type: dynamodb.AttributeType.STRING },
  projectionType: dynamodb.ProjectionType.ALL,
});
```

---

## Success Criteria

| Criterion | Target | Measurement |
|-----------|--------|-------------|
| Dashboard load time | <500ms | P95 latency |
| Top N users query | <200ms | P95 latency |
| Table scans | 0 | CloudWatch ConsumedReadCapacity |
| User scale | 10,000+ | Load test |
| Cache hit rate | >80% | Custom metric |
| Rollup freshness | <1 minute | LastUpdated delta |

---

## Conclusion

This specification provides a scalable, performant admin cost dashboard that:

1. **Avoids table scans** via GSI-based queries and pre-aggregated rollups
2. **Scales to 10,000+ users** with consistent sub-second response times
3. **Provides rich analytics** beyond just cost (requests, users, models, tiers)
4. **Builds on existing infrastructure** (UserCostSummary table, quota system)
5. **Follows established patterns** (Pydantic models, FastAPI routes, Angular components)

The phased implementation approach allows incremental delivery while maintaining the performance and scalability requirements from day one.
