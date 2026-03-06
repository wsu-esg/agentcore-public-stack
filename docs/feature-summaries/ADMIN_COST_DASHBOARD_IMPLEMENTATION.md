# Admin Cost Dashboard - Implementation Summary

This document provides a comprehensive overview of the Admin Cost Dashboard implementation, serving as a reference for future development and maintenance.

## Overview

The Admin Cost Dashboard enables administrators to view system-wide usage metrics, top users by cost, model usage breakdowns, and cost trends. The implementation follows the specification in `docs/ADMIN_COST_DASHBOARD_SPEC.md`.

**Key Capabilities:**
- View system-wide cost summaries (total cost, requests, active users, cache savings)
- Browse top users sorted by cost with pagination
- Visualize cost trends over time (line chart)
- Analyze model usage distribution (pie/bar chart)
- Export data to CSV or JSON

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Frontend (Angular)                             │
├─────────────────────────────────────────────────────────────────────────┤
│  admin-costs.page.ts                                                     │
│  ├── PeriodSelectorComponent                                             │
│  ├── SystemSummaryCardComponent (x4)                                     │
│  ├── CostTrendsChartComponent (Chart.js)                                 │
│  ├── ModelBreakdownComponent (Chart.js)                                  │
│  └── TopUsersTableComponent                                              │
├─────────────────────────────────────────────────────────────────────────┤
│  Services                                                                │
│  ├── AdminCostStateService (signals-based state management)             │
│  └── AdminCostHttpService (API communication)                           │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           Backend (FastAPI)                              │
├─────────────────────────────────────────────────────────────────────────┤
│  /admin/costs/                                                           │
│  ├── GET /dashboard      → Full dashboard data                          │
│  ├── GET /top-users      → Paginated top users by cost                  │
│  ├── GET /system-summary → Aggregated system metrics                    │
│  ├── GET /by-model       → Model usage breakdown                        │
│  ├── GET /by-tier        → Tier usage breakdown (placeholder)           │
│  ├── GET /trends         → Daily cost trends                            │
│  └── GET /export         → CSV/JSON export                              │
├─────────────────────────────────────────────────────────────────────────┤
│  AdminCostService                                                        │
│  └── Queries DynamoDB via repository layer                              │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           DynamoDB Tables                                │
├─────────────────────────────────────────────────────────────────────────┤
│  UserCostSummary                                                         │
│  ├── PK: USER#<user_id>                                                  │
│  ├── SK: PERIOD#<YYYY-MM>                                                │
│  └── GSI: PeriodCostIndex (GSI2PK, GSI2SK) for top-N queries            │
├─────────────────────────────────────────────────────────────────────────┤
│  SystemCostRollup                                                        │
│  ├── PK: ROLLUP#<type> (DAILY, MONTHLY, MODEL, TIER)                    │
│  └── SK: <identifier> (date, model_id, tier_id)                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## File Structure

### Frontend

```
frontend/ai.client/src/app/admin/costs/
├── admin-costs.page.ts              # Main dashboard page component
├── models/
│   ├── admin-cost.models.ts         # TypeScript interfaces
│   └── index.ts                     # Barrel export
├── services/
│   ├── admin-cost-http.service.ts   # HTTP client for API calls
│   ├── admin-cost-state.service.ts  # Signals-based state management
│   └── index.ts                     # Barrel export
└── components/
    ├── period-selector.component.ts      # Month/year selector dropdown
    ├── system-summary-card.component.ts  # Metric card with icon
    ├── top-users-table.component.ts      # Sortable, paginated user table
    ├── cost-trends-chart.component.ts    # Line chart (Chart.js)
    ├── model-breakdown.component.ts      # Pie/bar chart toggle (Chart.js)
    └── index.ts                          # Barrel export
```

### Backend

```
backend/src/apis/app_api/admin/costs/
├── __init__.py
├── models.py      # Pydantic models for request/response
├── routes.py      # FastAPI router with endpoints
└── service.py     # Business logic and DynamoDB queries
```

---

## API Endpoints

| Endpoint | Method | Description | Response |
|----------|--------|-------------|----------|
| `/admin/costs/dashboard` | GET | Full dashboard data | `AdminCostDashboard` |
| `/admin/costs/top-users` | GET | Top N users by cost | `List[TopUserCost]` |
| `/admin/costs/system-summary` | GET | System-wide metrics | `SystemCostSummary` |
| `/admin/costs/by-model` | GET | Cost by model | `List[ModelUsageSummary]` |
| `/admin/costs/by-tier` | GET | Cost by tier | `List[TierUsageSummary]` |
| `/admin/costs/trends` | GET | Daily trends | `List[CostTrend]` |
| `/admin/costs/export` | GET | CSV/JSON export | `StreamingResponse` |

### Query Parameters

**`/dashboard`**
- `period` (optional): YYYY-MM format, defaults to current month
- `topUsersLimit` (optional): 1-1000, default 100
- `includeTrends` (optional): boolean, default true

**`/top-users`**
- `period` (optional): YYYY-MM format
- `limit` (optional): 1-1000, default 100
- `minCost` (optional): minimum cost threshold
- `tierId` (optional): filter by tier (placeholder)

**`/trends`**
- `startDate` (required): YYYY-MM-DD format
- `endDate` (required): YYYY-MM-DD format
- Max range: 90 days

**`/export`**
- `period` (optional): YYYY-MM format
- `format` (optional): 'csv' or 'json', default 'csv'

---

## Data Models

### Frontend (TypeScript)

```typescript
interface AdminCostDashboard {
  currentPeriod: SystemCostSummary;
  topUsers: TopUserCost[];
  modelUsage: ModelUsageSummary[];
  tierUsage?: TierUsageSummary[];
  dailyTrends?: CostTrend[];
}

interface TopUserCost {
  userId: string;
  email?: string;
  totalCost: number;
  totalRequests: number;
  tierName?: string;
  quotaLimit?: number;
  quotaPercentage?: number;
  lastUpdated: string;
}

interface SystemCostSummary {
  period: string;
  periodType: 'daily' | 'monthly';
  totalCost: number;
  totalRequests: number;
  activeUsers: number;
  totalInputTokens: number;
  totalOutputTokens: number;
  totalCacheSavings: number;
  modelBreakdown?: Record<string, ModelBreakdown>;
  lastUpdated: string;
}

interface CostTrend {
  date: string;
  totalCost: number;
  totalRequests: number;
  activeUsers: number;
}

interface ModelUsageSummary {
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
```

### Backend (Pydantic)

See `backend/src/apis/app_api/admin/costs/models.py` for complete definitions.

---

## Components

### PeriodSelectorComponent

Dropdown for selecting billing period (month/year).

**Inputs:**
- `selectedPeriod: string` - Current period in YYYY-MM format

**Outputs:**
- `periodChange: EventEmitter<string>` - Emits new period on selection

### SystemSummaryCardComponent

Displays a single metric with icon and optional trend indicator.

**Inputs:**
- `title: string` - Card title
- `value: string` - Formatted value to display
- `trend: number | null` - Percentage change (positive/negative)
- `icon: SummaryCardIcon` - Icon name from Heroicons

### TopUsersTableComponent

Sortable, paginated table of top users by cost.

**Inputs:**
- `users: TopUserCost[]` - User data array
- `loading: boolean` - Loading state for pagination
- `hasMore: boolean` - Whether more users can be loaded

**Outputs:**
- `userClick: EventEmitter<string>` - User ID on row click
- `loadMore: EventEmitter<void>` - Request more users

**Features:**
- Sortable columns (rank, user, cost, requests, tier, quota)
- User avatars with initials
- Tier badges with color coding
- Quota progress bars (green/yellow/red based on usage)
- Pagination via "Load more" button

### CostTrendsChartComponent

Line chart showing cost and request trends over time.

**Inputs:**
- `data: CostTrend[]` - Daily trend data

**Features:**
- Dual Y-axes (cost on left, requests on right)
- Dark mode support
- Interactive tooltips
- Summary statistics (total cost, avg daily, peak day)
- Responsive sizing

**Dependencies:** chart.js, ng2-charts

### ModelBreakdownComponent

Pie or bar chart showing cost distribution by model.

**Inputs:**
- `data: ModelUsageSummary[]` - Model usage data

**Features:**
- Toggle between pie and bar views
- Color-coded legend
- Percentage breakdown
- Dark mode support
- Click to toggle models on/off

**Dependencies:** chart.js, ng2-charts

---

## State Management

The `AdminCostStateService` uses Angular signals for reactive state:

```typescript
// State signals
dashboard = signal<AdminCostDashboard | null>(null);
topUsers = signal<TopUserCost[]>([]);
systemSummary = signal<SystemCostSummary | null>(null);
trends = signal<CostTrend[]>([]);
modelUsage = signal<ModelUsageSummary[]>([]);
selectedPeriod = signal<string>(this.getCurrentPeriod());
loading = signal(false);
error = signal<string | null>(null);

// Computed signals
totalCost = computed(() => this.systemSummary()?.totalCost ?? 0);
totalRequests = computed(() => this.systemSummary()?.totalRequests ?? 0);
activeUsers = computed(() => this.systemSummary()?.activeUsers ?? 0);
cacheSavings = computed(() => this.systemSummary()?.totalCacheSavings ?? 0);
```

**Methods:**
- `loadDashboard(options)` - Load full dashboard data
- `loadTopUsers(options)` - Load/refresh top users
- `loadSystemSummary(period)` - Load system summary only
- `loadTrends(options)` - Load trend data for date range
- `exportData(format)` - Trigger CSV/JSON download
- `setPeriod(period)` - Update selected period
- `reset()` - Clear all state

---

## DynamoDB Schema

### UserCostSummary Table

**Primary Key:**
- PK: `USER#<user_id>`
- SK: `PERIOD#<YYYY-MM>`

**GSI: PeriodCostIndex**
- GSI2PK: `PERIOD#<YYYY-MM>`
- GSI2SK: `COST#<15-digit-zero-padded-cents>`

Enables efficient "top N users by cost" queries without table scans.

### SystemCostRollup Table

**Primary Key:**
- PK: `ROLLUP#<type>` (DAILY, MONTHLY, MODEL, TIER)
- SK: `<identifier>` (date, period#model_id, period#tier_id)

Pre-aggregated metrics for fast dashboard loading.

---

## Routing

The dashboard is accessible at `/admin/costs` and linked from the admin hub.

```typescript
// In admin routing module
{
  path: 'costs',
  loadComponent: () => import('./costs/admin-costs.page')
    .then(m => m.AdminCostsPage)
}
```

---

## Dependencies

### Frontend
- `chart.js` (^4.x) - Charting library
- `ng2-charts` (^6.x) - Angular wrapper for Chart.js
- `@ng-icons/heroicons` - Icon library

### Backend
- `fastapi` - Web framework
- `pydantic` - Data validation
- `boto3` - AWS SDK for DynamoDB

---

## Performance Considerations

1. **No Table Scans**: All queries use GSI or pre-aggregated rollups
2. **Target Latencies**:
   - Dashboard load: <500ms
   - Top N users: <200ms
   - System summary: <50ms
3. **Pagination**: Top users loaded in batches of 20
4. **Caching**: 30-second cache on system rollups (backend)

---

## Future Enhancements

1. **Tier Usage Analytics**: Currently returns empty array; needs implementation
2. **User Detail View**: Navigate to detailed user cost breakdown on row click
3. **Trend Comparisons**: Compare current period to previous period
4. **Real-time Updates**: WebSocket for live cost updates
5. **Alerts**: Configure cost threshold alerts
6. **Date Range Picker**: Custom date ranges beyond monthly periods

---

## Testing

### Backend
```bash
cd backend/src
python -m pytest tests/test_admin_costs.py -v
```

### Frontend
```bash
cd frontend/ai.client
ng test --include="**/admin/costs/**"
```

---

## Troubleshooting

### Common Issues

1. **Empty dashboard data**
   - Check that SystemCostRollup table has data
   - Verify GSI2PK/GSI2SK attributes exist on UserCostSummary records
   - Run backfill script if needed

2. **Charts not rendering**
   - Verify chart.js and ng2-charts are installed
   - Check browser console for Chart.js errors
   - Ensure data arrays are not empty

3. **Export fails**
   - Check network tab for API errors
   - Verify admin authentication token is valid
   - Check backend logs for exceptions

4. **Slow dashboard load**
   - Monitor DynamoDB ConsumedReadCapacity
   - Check for table scans in CloudWatch
   - Verify GSI projections include needed attributes

---

## Related Documentation

- [Admin Cost Dashboard Specification](./ADMIN_COST_DASHBOARD_SPEC.md)
- [Cost Tracking System](./COST_TRACKING.md) (if exists)
- [Quota Management](./QUOTA_MANAGEMENT.md) (if exists)
