/**
 * API Client Utilities
 * Handles all API communications
 */

// API configuration
const API_BASE_URL = '/api/v1';
const API_TIMEOUT = 30000; // 30 seconds

// Request headers
const getHeaders = () => ({
  'Content-Type': 'application/json',
  'X-CSRFToken': getCookie('csrftoken'),
  'X-Requested-With': 'XMLHttpRequest',
});

/**
 * Get CSRF token from cookies
 */
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

/**
 * Handle API response
 */
async function handleResponse(response) {
  if (!response.ok) {
    const error = await response.json().catch(() => ({
      message: `HTTP error! status: ${response.status}`,
    }));
    throw new Error(error.message || `Request failed with status ${response.status}`);
  }
  
  // Check if response has content
  const contentType = response.headers.get('content-type');
  if (contentType && contentType.includes('application/json')) {
    return response.json();
  }
  
  return response.text();
}

/**
 * Fetch with timeout
 */
function fetchWithTimeout(url, options, timeout = API_TIMEOUT) {
  return Promise.race([
    fetch(url, options),
    new Promise((_, reject) =>
      setTimeout(() => reject(new Error('Request timeout')), timeout)
    )
  ]);
}

/**
 * Generic fetch wrapper
 */
export async function fetchData(endpoint, options = {}) {
  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE_URL}${endpoint}`;
  
  const defaultOptions = {
    method: 'GET',
    headers: getHeaders(),
    credentials: 'same-origin',
  };
  
  const mergedOptions = {
    ...defaultOptions,
    ...options,
    headers: {
      ...defaultOptions.headers,
      ...(options.headers || {}),
    },
  };
  
  try {
    const response = await fetchWithTimeout(url, mergedOptions);
    return handleResponse(response);
  } catch (error) {
    console.error('API request failed:', error);
    throw error;
  }
}

/**
 * GET request
 */
export async function get(endpoint, params = {}) {
  const queryString = new URLSearchParams(params).toString();
  const url = queryString ? `${endpoint}?${queryString}` : endpoint;
  
  return fetchData(url, {
    method: 'GET',
  });
}

/**
 * POST request
 */
export async function post(endpoint, data = {}) {
  return fetchData(endpoint, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * PUT request
 */
export async function put(endpoint, data = {}) {
  return fetchData(endpoint, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

/**
 * PATCH request
 */
export async function patch(endpoint, data = {}) {
  return fetchData(endpoint, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

/**
 * DELETE request
 */
export async function deleteRequest(endpoint) {
  return fetchData(endpoint, {
    method: 'DELETE',
  });
}

/**
 * Upload file
 */
export async function uploadFile(endpoint, file, additionalData = {}) {
  const formData = new FormData();
  formData.append('file', file);
  
  // Add additional data to form
  Object.keys(additionalData).forEach(key => {
    formData.append(key, additionalData[key]);
  });
  
  return fetchData(endpoint, {
    method: 'POST',
    body: formData,
    headers: {
      'X-CSRFToken': getCookie('csrftoken'),
      'X-Requested-With': 'XMLHttpRequest',
      // Don't set Content-Type, let browser set it with boundary
    },
  });
}

/**
 * Batch requests
 */
export async function batchRequests(requests) {
  return Promise.all(requests.map(req => 
    fetchData(req.endpoint, req.options).catch(error => ({
      error: true,
      message: error.message,
      endpoint: req.endpoint,
    }))
  ));
}

/**
 * API endpoints
 */
export const API = {
  // Dashboard
  dashboard: {
    metrics: () => get('/dashboard/metrics/'),
    charts: (period) => get('/dashboard/charts/', { period }),
    activities: () => get('/dashboard/activities/'),
  },
  
  // Materials
  materials: {
    list: (params) => get('/materials/', params),
    get: (id) => get(`/materials/${id}/`),
    create: (data) => post('/materials/', data),
    update: (id, data) => put(`/materials/${id}/`, data),
    delete: (id) => deleteRequest(`/materials/${id}/`),
    prices: (id, params) => get(`/materials/${id}/prices/`, params),
    predict: (id, data) => post(`/materials/${id}/predict/`, data),
  },
  
  // Suppliers
  suppliers: {
    list: (params) => get('/suppliers/', params),
    get: (id) => get(`/suppliers/${id}/`),
    create: (data) => post('/suppliers/', data),
    update: (id, data) => put(`/suppliers/${id}/`, data),
    delete: (id) => deleteRequest(`/suppliers/${id}/`),
    performance: (id) => get(`/suppliers/${id}/performance/`),
  },
  
  // RFQs
  rfqs: {
    list: (params) => get('/rfqs/', params),
    get: (id) => get(`/rfqs/${id}/`),
    create: (data) => post('/rfqs/', data),
    update: (id, data) => put(`/rfqs/${id}/`, data),
    delete: (id) => deleteRequest(`/rfqs/${id}/`),
    publish: (id) => post(`/rfqs/${id}/publish/`),
    close: (id) => post(`/rfqs/${id}/close/`),
    award: (id, data) => post(`/rfqs/${id}/award/`, data),
  },
  
  // Quotes
  quotes: {
    list: (params) => get('/quotes/', params),
    get: (id) => get(`/quotes/${id}/`),
    create: (data) => post('/quotes/', data),
    update: (id, data) => put(`/quotes/${id}/`, data),
    delete: (id) => deleteRequest(`/quotes/${id}/`),
    compare: (ids) => post('/quotes/compare/', { ids }),
  },
  
  // Analytics
  analytics: {
    reports: (params) => get('/reports/', params),
    generateReport: (type, params) => post('/reports/generate/', { type, ...params }),
    exportReport: (id, format) => get(`/reports/${id}/export/`, { format }),
  },
  
  // Prices
  prices: {
    list: (params) => get('/prices/', params),
    trends: (params) => get('/prices/trends/', params),
    alerts: (params) => get('/price-alerts/', params),
    createAlert: (data) => post('/price-alerts/', data),
  },
};

// WebSocket connection for real-time updates
export class WebSocketClient {
  constructor(url) {
    this.url = url;
    this.ws = null;
    this.reconnectInterval = 5000;
    this.shouldReconnect = true;
    this.listeners = {};
  }
  
  connect() {
    this.ws = new WebSocket(this.url);
    
    this.ws.onopen = () => {
      console.log('WebSocket connected');
      this.emit('open');
    };
    
    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      this.emit('message', data);
      
      // Emit specific event based on message type
      if (data.type) {
        this.emit(data.type, data);
      }
    };
    
    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      this.emit('error', error);
    };
    
    this.ws.onclose = () => {
      console.log('WebSocket disconnected');
      this.emit('close');
      
      if (this.shouldReconnect) {
        setTimeout(() => this.connect(), this.reconnectInterval);
      }
    };
  }
  
  send(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }
  
  on(event, callback) {
    if (!this.listeners[event]) {
      this.listeners[event] = [];
    }
    this.listeners[event].push(callback);
  }
  
  off(event, callback) {
    if (this.listeners[event]) {
      this.listeners[event] = this.listeners[event].filter(cb => cb !== callback);
    }
  }
  
  emit(event, data) {
    if (this.listeners[event]) {
      this.listeners[event].forEach(callback => callback(data));
    }
  }
  
  disconnect() {
    this.shouldReconnect = false;
    if (this.ws) {
      this.ws.close();
    }
  }
}

export default {
  fetchData,
  get,
  post,
  put,
  patch,
  deleteRequest,
  uploadFile,
  batchRequests,
  API,
  WebSocketClient,
};