import {
  Component,
  ChangeDetectionStrategy,
  input,
  computed,
  effect,
  viewChild,
  ElementRef,
  signal,
} from '@angular/core';
import { Chart, ChartConfiguration, ChartData } from 'chart.js/auto';
import { ModelUsageSummary } from '../models';

type ChartView = 'pie' | 'bar';

/**
 * Model breakdown chart component.
 * Displays cost distribution across different AI models.
 */
@Component({
  selector: 'app-model-breakdown',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div
      class="bg-white dark:bg-gray-800 rounded-lg shadow-xs border border-gray-200 dark:border-gray-700 p-6"
    >
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-semibold text-gray-900 dark:text-white">
          Model Usage Breakdown
        </h3>
        <!-- View toggle -->
        <div
          class="inline-flex rounded-lg border border-gray-200 dark:border-gray-700 p-1"
        >
          <button
            type="button"
            (click)="setChartView('pie')"
            class="px-3 py-1 text-sm font-medium rounded-md transition-colors"
            [class.bg-blue-100]="chartView() === 'pie'"
            [class.text-blue-700]="chartView() === 'pie'"
            [class.dark:bg-blue-900/30]="chartView() === 'pie'"
            [class.dark:text-blue-400]="chartView() === 'pie'"
            [class.text-gray-600]="chartView() !== 'pie'"
            [class.dark:text-gray-400]="chartView() !== 'pie'"
            [class.hover:text-gray-900]="chartView() !== 'pie'"
            [class.dark:hover:text-white]="chartView() !== 'pie'"
          >
            Pie
          </button>
          <button
            type="button"
            (click)="setChartView('bar')"
            class="px-3 py-1 text-sm font-medium rounded-md transition-colors"
            [class.bg-blue-100]="chartView() === 'bar'"
            [class.text-blue-700]="chartView() === 'bar'"
            [class.dark:bg-blue-900/30]="chartView() === 'bar'"
            [class.dark:text-blue-400]="chartView() === 'bar'"
            [class.text-gray-600]="chartView() !== 'bar'"
            [class.dark:text-gray-400]="chartView() !== 'bar'"
            [class.hover:text-gray-900]="chartView() !== 'bar'"
            [class.dark:hover:text-white]="chartView() !== 'bar'"
          >
            Bar
          </button>
        </div>
      </div>

      @if (data().length === 0) {
        <div
          class="h-64 flex items-center justify-center bg-gray-50 dark:bg-gray-900/50 rounded-lg border-2 border-dashed border-gray-200 dark:border-gray-700"
        >
          <p class="text-sm text-gray-500 dark:text-gray-400">
            No model usage data available for this period
          </p>
        </div>
      } @else {
        <div class="h-64">
          <canvas #chartCanvas></canvas>
        </div>

        <!-- Legend/Details table -->
        <div class="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
          <div class="space-y-2">
            @for (model of sortedData(); track model.modelId; let i = $index) {
              <div
                class="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
              >
                <div class="flex items-center gap-3">
                  <span
                    class="size-3 rounded-full shrink-0"
                    [style.background-color]="getColor(i)"
                  ></span>
                  <div class="min-w-0">
                    <p
                      class="text-sm font-medium text-gray-900 dark:text-white truncate"
                    >
                      {{ model.modelName }}
                    </p>
                    <p class="text-xs text-gray-500 dark:text-gray-400">
                      {{ formatNumber(model.totalRequests) }} requests •
                      {{ formatNumber(model.uniqueUsers) }} users
                    </p>
                  </div>
                </div>
                <div class="text-right shrink-0">
                  <p class="text-sm font-medium text-gray-900 dark:text-white">
                    {{ formatCurrency(model.totalCost) }}
                  </p>
                  <p class="text-xs text-gray-500 dark:text-gray-400">
                    {{ getPercentage(model.totalCost) }}%
                  </p>
                </div>
              </div>
            }
          </div>
        </div>
      }
    </div>
  `,
})
export class ModelBreakdownComponent {
  data = input.required<ModelUsageSummary[]>();

  chartView = signal<ChartView>('pie');

  private chartCanvas = viewChild<ElementRef<HTMLCanvasElement>>('chartCanvas');
  private chart: Chart | null = null;

  // Color palette for charts
  private readonly colors = [
    '#3b82f6', // blue
    '#10b981', // emerald
    '#f59e0b', // amber
    '#ef4444', // red
    '#8b5cf6', // violet
    '#ec4899', // pink
    '#06b6d4', // cyan
    '#84cc16', // lime
    '#f97316', // orange
    '#6366f1', // indigo
  ];

  // Sort data by cost descending
  sortedData = computed(() => {
    return [...this.data()].sort((a, b) => b.totalCost - a.totalCost);
  });

  // Total cost for percentage calculation
  totalCost = computed(() => {
    return this.data().reduce((sum, m) => sum + m.totalCost, 0);
  });

  constructor() {
    effect(() => {
      const canvas = this.chartCanvas();
      const models = this.sortedData();
      const view = this.chartView();

      if (canvas && models.length > 0) {
        this.renderChart(canvas.nativeElement, models, view);
      }
    });
  }

  setChartView(view: ChartView): void {
    this.chartView.set(view);
  }

  getColor(index: number): string {
    return this.colors[index % this.colors.length];
  }

  getPercentage(cost: number): string {
    const total = this.totalCost();
    if (total === 0) return '0';
    return ((cost / total) * 100).toFixed(1);
  }

  private renderChart(
    canvas: HTMLCanvasElement,
    models: ModelUsageSummary[],
    view: ChartView
  ): void {
    // Destroy existing chart if present
    if (this.chart) {
      this.chart.destroy();
    }

    const labels = models.map(m => m.modelName);
    const costData = models.map(m => m.totalCost);
    const backgroundColors = models.map((_, i) => this.getColor(i));

    const isDarkMode = document.documentElement.classList.contains('dark');
    const textColor = isDarkMode ? '#9ca3af' : '#6b7280';
    const gridColor = isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';

    if (view === 'pie') {
      this.renderPieChart(canvas, labels, costData, backgroundColors, isDarkMode);
    } else {
      this.renderBarChart(canvas, labels, costData, backgroundColors, textColor, gridColor, isDarkMode);
    }
  }

  private renderPieChart(
    canvas: HTMLCanvasElement,
    labels: string[],
    data: number[],
    colors: string[],
    isDarkMode: boolean
  ): void {
    const chartData: ChartData<'doughnut'> = {
      labels,
      datasets: [
        {
          data,
          backgroundColor: colors,
          borderColor: isDarkMode ? '#1f2937' : '#ffffff',
          borderWidth: 2,
          hoverOffset: 4,
        },
      ],
    };

    const config: ChartConfiguration<'doughnut'> = {
      type: 'doughnut',
      data: chartData,
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '60%',
        plugins: {
          legend: {
            display: false,
          },
          tooltip: {
            backgroundColor: isDarkMode ? '#1f2937' : '#ffffff',
            titleColor: isDarkMode ? '#ffffff' : '#111827',
            bodyColor: isDarkMode ? '#d1d5db' : '#4b5563',
            borderColor: isDarkMode ? '#374151' : '#e5e7eb',
            borderWidth: 1,
            padding: 12,
            callbacks: {
              label: context => {
                const value = context.parsed;
                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                const percentage = ((value / total) * 100).toFixed(1);
                return `${this.formatCurrency(value)} (${percentage}%)`;
              },
            },
          },
        },
      },
    };

    this.chart = new Chart(canvas, config);
  }

  private renderBarChart(
    canvas: HTMLCanvasElement,
    labels: string[],
    data: number[],
    colors: string[],
    textColor: string,
    gridColor: string,
    isDarkMode: boolean
  ): void {
    const chartData: ChartData<'bar'> = {
      labels,
      datasets: [
        {
          label: 'Cost',
          data,
          backgroundColor: colors,
          borderRadius: 4,
        },
      ],
    };

    const config: ChartConfiguration<'bar'> = {
      type: 'bar',
      data: chartData,
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: 'y',
        plugins: {
          legend: {
            display: false,
          },
          tooltip: {
            backgroundColor: isDarkMode ? '#1f2937' : '#ffffff',
            titleColor: isDarkMode ? '#ffffff' : '#111827',
            bodyColor: isDarkMode ? '#d1d5db' : '#4b5563',
            borderColor: isDarkMode ? '#374151' : '#e5e7eb',
            borderWidth: 1,
            padding: 12,
            callbacks: {
              label: context => {
                return this.formatCurrency(context.parsed.x ?? 0);
              },
            },
          },
        },
        scales: {
          x: {
            grid: {
              color: gridColor,
            },
            ticks: {
              color: textColor,
              callback: value => this.formatCurrencyShort(Number(value)),
            },
          },
          y: {
            grid: {
              display: false,
            },
            ticks: {
              color: textColor,
            },
          },
        },
      },
    };

    this.chart = new Chart(canvas, config);
  }

  formatCurrency(value: number): string {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  }

  private formatCurrencyShort(value: number): string {
    if (value >= 1000) {
      return `$${(value / 1000).toFixed(1)}k`;
    }
    return `$${value.toFixed(0)}`;
  }

  formatNumber(value: number): string {
    return new Intl.NumberFormat('en-US').format(value);
  }
}
