/**
 * Chart.js Configuration
 * Centralized chart configurations and utilities
 */

import Theme from './theme.js';

// Default Chart.js configuration
export const ChartDefaults = {
  // Global font settings
  font: {
    family: Theme.fonts.sans,
    size: 12,
    weight: 400,
  },
  
  // Default colors
  colors: Theme.charts.categorical,
  
  // Common chart options
  options: {
    responsive: true,
    maintainAspectRatio: false,
    
    plugins: {
      legend: {
        display: true,
        position: 'bottom',
        labels: {
          padding: 15,
          usePointStyle: true,
          font: {
            size: 12,
            family: Theme.fonts.sans,
          }
        }
      },
      
      tooltip: {
        backgroundColor: 'rgba(16, 42, 67, 0.95)',
        titleColor: '#ffffff',
        bodyColor: '#ffffff',
        borderColor: '#243b53',
        borderWidth: 1,
        padding: 12,
        cornerRadius: 4,
        displayColors: true,
        mode: 'index',
        intersect: false,
        callbacks: {
          // Default formatters
          label: function(context) {
            let label = context.dataset.label || '';
            if (label) {
              label += ': ';
            }
            if (context.parsed.y !== null) {
              label += formatValue(context.parsed.y, context.dataset.valueFormat);
            }
            return label;
          }
        }
      }
    },
    
    scales: {
      x: {
        grid: {
          display: false,
          drawBorder: false,
        },
        ticks: {
          font: {
            size: 11,
            family: Theme.fonts.sans,
          }
        }
      },
      y: {
        grid: {
          borderDash: [2, 4],
          color: 'rgba(156, 163, 175, 0.2)',
          drawBorder: false,
        },
        ticks: {
          font: {
            size: 11,
            family: Theme.fonts.sans,
          }
        }
      }
    },
    
    animation: {
      duration: Theme.animation.duration.chart,
      easing: 'easeInOutQuart',
    }
  }
};

// Chart type specific configurations
export const ChartConfigs = {
  // Line chart configuration
  line: {
    type: 'line',
    options: {
      ...ChartDefaults.options,
      elements: {
        line: {
          tension: 0.4,
          borderWidth: 2,
        },
        point: {
          radius: 0,
          hitRadius: 30,
          hoverRadius: 4,
        }
      },
      interaction: {
        mode: 'index',
        intersect: false,
      },
    }
  },
  
  // Bar chart configuration
  bar: {
    type: 'bar',
    options: {
      ...ChartDefaults.options,
      barPercentage: 0.7,
      categoryPercentage: 0.8,
    }
  },
  
  // Doughnut/Pie chart configuration
  doughnut: {
    type: 'doughnut',
    options: {
      ...ChartDefaults.options,
      cutout: '65%',
      plugins: {
        ...ChartDefaults.options.plugins,
        legend: {
          ...ChartDefaults.options.plugins.legend,
          position: 'right',
        }
      },
      scales: {} // Remove scales for doughnut charts
    }
  },
  
  // Area chart configuration
  area: {
    type: 'line',
    options: {
      ...ChartDefaults.options,
      elements: {
        line: {
          tension: 0.4,
          borderWidth: 2,
          fill: true,
        },
        point: {
          radius: 0,
          hitRadius: 30,
          hoverRadius: 4,
        }
      },
    }
  },
  
  // Mixed chart configuration
  mixed: {
    type: 'bar',
    options: {
      ...ChartDefaults.options,
      interaction: {
        mode: 'index',
        intersect: false,
      },
    }
  }
};

// Value formatters
export const Formatters = {
  // Currency formatter
  currency: (value, currency = 'USD') => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency,
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  },
  
  // Percentage formatter
  percentage: (value, decimals = 1) => {
    return `${value.toFixed(decimals)}%`;
  },
  
  // Number formatter with abbreviation
  abbreviated: (value) => {
    if (value >= 1000000) {
      return `${(value / 1000000).toFixed(1)}M`;
    } else if (value >= 1000) {
      return `${(value / 1000).toFixed(1)}K`;
    }
    return value.toString();
  },
  
  // Compact number formatter
  compact: (value) => {
    return new Intl.NumberFormat('en-US', {
      notation: 'compact',
      compactDisplay: 'short',
    }).format(value);
  },
  
  // Date formatter
  date: (value, format = 'short') => {
    const date = new Date(value);
    if (format === 'short') {
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    } else if (format === 'long') {
      return date.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
    }
    return date.toLocaleDateString();
  }
};

// Helper function to format values based on type
function formatValue(value, format) {
  if (!format) return value;
  
  switch (format) {
    case 'currency':
      return Formatters.currency(value);
    case 'percentage':
      return Formatters.percentage(value);
    case 'abbreviated':
      return Formatters.abbreviated(value);
    case 'compact':
      return Formatters.compact(value);
    default:
      return value;
  }
}

// Chart factory function
export function createChart(ctx, config) {
  // Merge with defaults based on chart type
  const chartType = config.type || 'line';
  const baseConfig = ChartConfigs[chartType] || ChartDefaults;
  
  const mergedConfig = {
    ...baseConfig,
    ...config,
    options: {
      ...baseConfig.options,
      ...(config.options || {}),
    }
  };
  
  return new Chart(ctx, mergedConfig);
}

// Update chart data with animation
export function updateChartData(chart, newData, animate = true) {
  chart.data = newData;
  chart.update(animate ? 'active' : 'none');
}

// Destroy chart safely
export function destroyChart(chart) {
  if (chart) {
    chart.destroy();
  }
}

// Generate gradient for charts
export function createGradient(ctx, colorStart, colorEnd, opacity = 0.1) {
  const gradient = ctx.createLinearGradient(0, 0, 0, 400);
  gradient.addColorStop(0, colorStart + Math.round(opacity * 255).toString(16));
  gradient.addColorStop(1, colorEnd + '00');
  return gradient;
}

// Export all utilities
export default {
  ChartDefaults,
  ChartConfigs,
  Formatters,
  createChart,
  updateChartData,
  destroyChart,
  createGradient,
};