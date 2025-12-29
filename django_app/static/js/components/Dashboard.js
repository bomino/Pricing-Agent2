/**
 * Dashboard Component
 * Handles all dashboard-specific functionality
 */

import { createChart, Formatters, ChartConfigs } from '../config/charts.js';
import Theme from '../config/theme.js';
import { fetchData } from '../utils/api.js';

export class Dashboard {
  constructor() {
    this.charts = {};
    this.refreshInterval = 60000; // 1 minute
    this.refreshTimer = null;
  }
  
  /**
   * Initialize dashboard
   */
  async init() {
    // Initialize metric cards
    this.initMetricCards();
    
    // Initialize charts
    await this.initCharts();
    
    // Set up auto-refresh
    this.startAutoRefresh();
    
    // Set up event listeners
    this.setupEventListeners();
    
    // Initialize HTMX extensions
    this.initHTMX();
  }
  
  /**
   * Initialize metric cards with animations
   */
  initMetricCards() {
    const metricCards = document.querySelectorAll('[data-metric-card]');
    
    metricCards.forEach((card, index) => {
      // Add staggered animation
      card.style.animationDelay = `${index * 50}ms`;
      card.classList.add('animate-fade-in');
      
      // Animate numbers
      const valueElement = card.querySelector('[data-metric-value]');
      if (valueElement) {
        this.animateValue(valueElement);
      }
      
      // Add hover effects
      card.addEventListener('mouseenter', () => {
        card.classList.add('transform', 'scale-105');
      });
      
      card.addEventListener('mouseleave', () => {
        card.classList.remove('transform', 'scale-105');
      });
    });
  }
  
  /**
   * Initialize all charts
   */
  async initCharts() {
    // Spending Trend Chart
    const spendingCtx = document.getElementById('spendingChart');
    if (spendingCtx) {
      this.charts.spending = await this.createSpendingChart(spendingCtx);
    }
    
    // Category Breakdown Chart
    const categoryCtx = document.getElementById('categoryChart');
    if (categoryCtx) {
      this.charts.category = await this.createCategoryChart(categoryCtx);
    }
    
    // Supplier Performance Chart
    const supplierCtx = document.getElementById('supplierChart');
    if (supplierCtx) {
      this.charts.supplier = await this.createSupplierChart(supplierCtx);
    }
    
    // Price Trend Chart
    const priceCtx = document.getElementById('priceTrendChart');
    if (priceCtx) {
      this.charts.price = await this.createPriceTrendChart(priceCtx);
    }
  }
  
  /**
   * Create spending trend chart
   */
  async createSpendingChart(ctx) {
    // In production, this would fetch from API
    const data = {
      labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
      datasets: [{
        label: 'Actual Spending',
        data: [1200000, 1400000, 1100000, 1600000, 1500000, 1800000],
        borderColor: Theme.charts.categorical[0],
        backgroundColor: `${Theme.charts.categorical[0]}20`,
        tension: 0.4,
        fill: true,
        valueFormat: 'currency'
      }, {
        label: 'Budget',
        data: [1300000, 1300000, 1300000, 1500000, 1500000, 1500000],
        borderColor: Theme.charts.categorical[1],
        backgroundColor: 'transparent',
        borderDash: [5, 5],
        tension: 0,
        fill: false,
        valueFormat: 'currency'
      }]
    };
    
    return createChart(ctx, {
      type: 'line',
      data: data,
      options: {
        ...ChartConfigs.line.options,
        plugins: {
          ...ChartConfigs.line.options.plugins,
          legend: {
            display: true,
            position: 'top',
            align: 'end',
          },
          tooltip: {
            ...ChartConfigs.line.options.plugins.tooltip,
            callbacks: {
              label: function(context) {
                return `${context.dataset.label}: ${Formatters.currency(context.parsed.y)}`;
              }
            }
          }
        },
        scales: {
          ...ChartConfigs.line.options.scales,
          y: {
            ...ChartConfigs.line.options.scales.y,
            ticks: {
              callback: function(value) {
                return Formatters.abbreviated(value);
              }
            }
          }
        }
      }
    });
  }
  
  /**
   * Create category breakdown chart
   */
  async createCategoryChart(ctx) {
    const data = {
      labels: ['Steel', 'Concrete', 'Electrical', 'Plumbing', 'Hardware', 'Other'],
      datasets: [{
        data: [35, 25, 20, 10, 7, 3],
        backgroundColor: Theme.charts.categorical.slice(0, 6),
        borderWidth: 0,
      }]
    };
    
    return createChart(ctx, {
      type: 'doughnut',
      data: data,
      options: {
        ...ChartConfigs.doughnut.options,
        plugins: {
          ...ChartConfigs.doughnut.options.plugins,
          tooltip: {
            callbacks: {
              label: function(context) {
                const value = context.parsed;
                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                const percentage = ((value / total) * 100).toFixed(1);
                return `${context.label}: ${percentage}% ($${Formatters.abbreviated(value * 50000)})`;
              }
            }
          },
          datalabels: {
            display: true,
            color: '#fff',
            font: {
              weight: 'bold',
              size: 14,
            },
            formatter: (value) => `${value}%`,
          }
        }
      }
    });
  }
  
  /**
   * Create supplier performance chart
   */
  async createSupplierChart(ctx) {
    const data = {
      labels: ['Supplier A', 'Supplier B', 'Supplier C', 'Supplier D', 'Supplier E'],
      datasets: [{
        label: 'On-Time Delivery',
        data: [95, 88, 92, 85, 90],
        backgroundColor: Theme.charts.categorical[2],
        valueFormat: 'percentage'
      }, {
        label: 'Quality Score',
        data: [92, 95, 88, 90, 94],
        backgroundColor: Theme.charts.categorical[3],
        valueFormat: 'percentage'
      }, {
        label: 'Cost Competitiveness',
        data: [85, 90, 95, 88, 82],
        backgroundColor: Theme.charts.categorical[4],
        valueFormat: 'percentage'
      }]
    };
    
    return createChart(ctx, {
      type: 'bar',
      data: data,
      options: {
        ...ChartConfigs.bar.options,
        plugins: {
          ...ChartConfigs.bar.options.plugins,
          tooltip: {
            callbacks: {
              label: function(context) {
                return `${context.dataset.label}: ${context.parsed.y}%`;
              }
            }
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            max: 100,
            ticks: {
              callback: function(value) {
                return value + '%';
              }
            }
          }
        }
      }
    });
  }
  
  /**
   * Create price trend chart
   */
  async createPriceTrendChart(ctx) {
    const data = {
      labels: ['Week 1', 'Week 2', 'Week 3', 'Week 4'],
      datasets: [{
        label: 'Steel Rebar',
        data: [850, 870, 865, 890],
        borderColor: Theme.charts.categorical[0],
        backgroundColor: 'transparent',
        tension: 0.4,
      }, {
        label: 'Concrete',
        data: [120, 118, 122, 119],
        borderColor: Theme.charts.categorical[1],
        backgroundColor: 'transparent',
        tension: 0.4,
      }, {
        label: 'Copper Wire',
        data: [450, 460, 455, 470],
        borderColor: Theme.charts.categorical[2],
        backgroundColor: 'transparent',
        tension: 0.4,
      }]
    };
    
    return createChart(ctx, {
      type: 'line',
      data: data,
      options: {
        ...ChartConfigs.line.options,
        plugins: {
          ...ChartConfigs.line.options.plugins,
          tooltip: {
            callbacks: {
              label: function(context) {
                return `${context.dataset.label}: $${context.parsed.y}/unit`;
              }
            }
          }
        },
        scales: {
          y: {
            ticks: {
              callback: function(value) {
                return '$' + value;
              }
            }
          }
        }
      }
    });
  }
  
  /**
   * Animate metric values
   */
  animateValue(element) {
    const endValue = parseFloat(element.dataset.value || element.textContent.replace(/[^0-9.-]/g, ''));
    const duration = 1000;
    const startTime = performance.now();
    const startValue = 0;
    
    const updateValue = (currentTime) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      
      // Easing function
      const easeOutQuart = 1 - Math.pow(1 - progress, 4);
      const currentValue = startValue + (endValue - startValue) * easeOutQuart;
      
      // Format based on data type
      const format = element.dataset.format || 'number';
      let displayValue;
      
      switch (format) {
        case 'currency':
          displayValue = Formatters.currency(currentValue);
          break;
        case 'percentage':
          displayValue = Formatters.percentage(currentValue);
          break;
        case 'abbreviated':
          displayValue = Formatters.abbreviated(currentValue);
          break;
        default:
          displayValue = Math.round(currentValue).toLocaleString();
      }
      
      element.textContent = displayValue;
      
      if (progress < 1) {
        requestAnimationFrame(updateValue);
      }
    };
    
    requestAnimationFrame(updateValue);
  }
  
  /**
   * Set up event listeners
   */
  setupEventListeners() {
    // Period selector for charts
    document.querySelectorAll('[data-period-selector]').forEach(selector => {
      selector.addEventListener('change', (e) => {
        this.updateChartPeriod(e.target.dataset.chart, e.target.value);
      });
    });
    
    // Refresh button
    const refreshBtn = document.querySelector('[data-refresh]');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', () => {
        this.refreshDashboard();
      });
    }
    
    // Export buttons
    document.querySelectorAll('[data-export-chart]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        this.exportChart(e.target.dataset.exportChart);
      });
    });
  }
  
  /**
   * Initialize HTMX extensions
   */
  initHTMX() {
    // After HTMX swaps, reinitialize components
    document.body.addEventListener('htmx:afterSwap', (event) => {
      // Reinitialize metric cards in swapped content
      const swappedElement = event.detail.target;
      const metricCards = swappedElement.querySelectorAll('[data-metric-card]');
      metricCards.forEach(card => this.initMetricCards());
    });
    
    // Show loading state during HTMX requests
    document.body.addEventListener('htmx:beforeRequest', (event) => {
      const indicator = event.detail.target.querySelector('.htmx-indicator');
      if (indicator) {
        indicator.classList.add('opacity-100');
      }
    });
    
    document.body.addEventListener('htmx:afterRequest', (event) => {
      const indicator = event.detail.target.querySelector('.htmx-indicator');
      if (indicator) {
        indicator.classList.remove('opacity-100');
      }
    });
  }
  
  /**
   * Update chart based on period selection
   */
  async updateChartPeriod(chartName, period) {
    // Show loading state
    const chart = this.charts[chartName];
    if (!chart) return;
    
    // In production, fetch new data based on period
    // For now, we'll just update with mock data
    console.log(`Updating ${chartName} chart for period: ${period}`);
    
    // Simulate API call
    setTimeout(() => {
      // Update chart with new data
      // chart.data = newData;
      // chart.update();
    }, 500);
  }
  
  /**
   * Refresh dashboard data
   */
  async refreshDashboard() {
    console.log('Refreshing dashboard...');
    
    // Show loading state
    document.body.classList.add('loading');
    
    try {
      // In production, fetch fresh data from API
      // const data = await fetchData('/api/dashboard/');
      
      // Update metric cards
      // this.updateMetrics(data.metrics);
      
      // Update charts
      // this.updateCharts(data.charts);
      
      console.log('Dashboard refreshed');
    } catch (error) {
      console.error('Error refreshing dashboard:', error);
    } finally {
      document.body.classList.remove('loading');
    }
  }
  
  /**
   * Start auto-refresh timer
   */
  startAutoRefresh() {
    this.refreshTimer = setInterval(() => {
      this.refreshDashboard();
    }, this.refreshInterval);
  }
  
  /**
   * Stop auto-refresh timer
   */
  stopAutoRefresh() {
    if (this.refreshTimer) {
      clearInterval(this.refreshTimer);
      this.refreshTimer = null;
    }
  }
  
  /**
   * Export chart as image
   */
  exportChart(chartName) {
    const chart = this.charts[chartName];
    if (!chart) return;
    
    const url = chart.toBase64Image();
    const link = document.createElement('a');
    link.download = `${chartName}-chart-${Date.now()}.png`;
    link.href = url;
    link.click();
  }
  
  /**
   * Clean up resources
   */
  destroy() {
    // Stop auto-refresh
    this.stopAutoRefresh();
    
    // Destroy all charts
    Object.values(this.charts).forEach(chart => {
      if (chart) chart.destroy();
    });
    
    this.charts = {};
  }
}

// Auto-initialize on DOM ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new Dashboard();
    window.dashboard.init();
  });
} else {
  window.dashboard = new Dashboard();
  window.dashboard.init();
}

export default Dashboard;