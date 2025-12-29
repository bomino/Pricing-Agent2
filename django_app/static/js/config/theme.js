/**
 * Theme Configuration
 * Central configuration for all UI components
 */

export const Theme = {
  // Chart Color Palettes
  charts: {
    // Primary palette for categorical data
    categorical: [
      '#1e3a8a', // Deep Blue
      '#0891b2', // Cyan
      '#0d9488', // Teal
      '#059669', // Emerald
      '#84cc16', // Lime
      '#eab308', // Yellow
      '#f97316', // Orange
      '#ef4444', // Red
    ],
    
    // Sequential palette for continuous data
    sequential: [
      '#f0f4f8',
      '#d9e2ec',
      '#9fb3c8',
      '#627d98',
      '#334e68',
      '#243b53',
      '#102a43',
    ],
    
    // Diverging palette for data with midpoint
    diverging: [
      '#ef4444', // Red (negative)
      '#f87171',
      '#fca5a5',
      '#fecaca',
      '#f3f4f6', // Gray (neutral)
      '#bfdbfe',
      '#93c5fd',
      '#60a5fa',
      '#3b82f6', // Blue (positive)
    ],
    
    // Semantic colors for specific metrics
    semantic: {
      revenue: '#059669',    // Green for positive financial
      expenses: '#ef4444',   // Red for costs
      profit: '#1e3a8a',     // Navy for profit
      pending: '#eab308',    // Yellow for pending
      completed: '#10b981',  // Green for completed
      cancelled: '#6b7280',  // Gray for cancelled
    }
  },
  
  // Status colors for badges and indicators
  status: {
    active: { bg: '#d1fae5', text: '#065f46', border: '#10b981' },
    inactive: { bg: '#f3f4f6', text: '#374151', border: '#9ca3af' },
    pending: { bg: '#fed7aa', text: '#92400e', border: '#f59e0b' },
    success: { bg: '#d1fae5', text: '#065f46', border: '#10b981' },
    warning: { bg: '#fed7aa', text: '#92400e', border: '#f59e0b' },
    danger: { bg: '#fee2e2', text: '#991b1b', border: '#ef4444' },
    info: { bg: '#dbeafe', text: '#1e40af', border: '#3b82f6' },
  },
  
  // Metric card color schemes
  metrics: {
    primary: {
      icon: '#243b53',
      iconBg: '#d9e2ec',
      trend: {
        up: '#10b981',
        down: '#ef4444',
        neutral: '#6b7280'
      }
    },
    alternating: [
      { icon: '#243b53', bg: '#f0f4f8', border: '#9fb3c8' },
      { icon: '#0891b2', bg: '#ecfeff', border: '#67e8f9' },
      { icon: '#0d9488', bg: '#f0fdfa', border: '#5eead4' },
      { icon: '#059669', bg: '#f0fdf4', border: '#86efac' },
    ]
  },
  
  // Animation and transition settings
  animation: {
    duration: {
      fast: 150,
      base: 200,
      slow: 300,
      chart: 750,
    },
    easing: {
      default: 'ease-in-out',
      smooth: 'cubic-bezier(0.4, 0, 0.2, 1)',
      bounce: 'cubic-bezier(0.68, -0.55, 0.265, 1.55)',
    }
  },
  
  // Breakpoints for responsive design
  breakpoints: {
    sm: 640,
    md: 768,
    lg: 1024,
    xl: 1280,
    '2xl': 1536,
  },
  
  // Font configurations
  fonts: {
    sans: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    mono: "'Fira Code', 'Courier New', monospace",
    display: "'Inter', sans-serif",
  }
};

// Utility function to get CSS variable value
export function getCSSVariable(name) {
  return getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim();
}

// Utility function to set CSS variable
export function setCSSVariable(name, value) {
  document.documentElement.style.setProperty(name, value);
}

// Dark mode toggle (if needed in future)
export function toggleDarkMode() {
  document.documentElement.classList.toggle('dark');
  localStorage.setItem('darkMode', 
    document.documentElement.classList.contains('dark')
  );
}

// Initialize theme
export function initTheme() {
  // Check for saved theme preference or default to light
  const darkMode = localStorage.getItem('darkMode') === 'true';
  if (darkMode) {
    document.documentElement.classList.add('dark');
  }
  
  // Add custom fonts
  const fontLink = document.createElement('link');
  fontLink.href = 'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap';
  fontLink.rel = 'stylesheet';
  document.head.appendChild(fontLink);
}

export default Theme;