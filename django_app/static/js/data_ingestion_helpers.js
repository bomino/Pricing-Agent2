/**
 * Helper functions for Data Ingestion module
 * Makes the process smooth and provides better error handling
 */

// Get CSRF token
function getCSRFToken() {
    let token = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
    if (!token) {
        // Try to get from cookie
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'csrftoken') {
                token = decodeURIComponent(value);
                break;
            }
        }
    }
    return token;
}

// Show toast notification
function showToast(message, type = 'info', duration = 3000) {
    // Remove existing toasts
    document.querySelectorAll('.toast-notification').forEach(t => t.remove());
    
    const toast = document.createElement('div');
    toast.className = 'toast-notification fixed top-4 right-4 px-6 py-3 rounded-lg shadow-lg z-50 transition-all duration-300';
    
    // Set color based on type
    const colors = {
        'success': 'bg-green-500 text-white',
        'error': 'bg-red-500 text-white',
        'warning': 'bg-yellow-500 text-white',
        'info': 'bg-blue-500 text-white'
    };
    
    toast.className += ' ' + (colors[type] || colors.info);
    
    toast.innerHTML = `
        <div class="flex items-center">
            <i class="fas ${
                type === 'success' ? 'fa-check-circle' :
                type === 'error' ? 'fa-exclamation-circle' :
                type === 'warning' ? 'fa-exclamation-triangle' :
                'fa-info-circle'
            } mr-2"></i>
            <span>${message}</span>
        </div>
    `;
    
    document.body.appendChild(toast);
    
    // Animate in
    setTimeout(() => {
        toast.style.opacity = '1';
        toast.style.transform = 'translateX(0)';
    }, 10);
    
    // Remove after duration
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

// Save column mappings with better error handling
async function saveColumnMappings(uploadId, mappings) {
    try {
        console.log('Saving mappings:', mappings);
        
        const response = await fetch(`/data-ingestion/mapping/${uploadId}/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify(mappings)
        });
        
        // Try to parse response
        let data;
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
            data = await response.json();
        } else {
            // If not JSON, try to parse response text
            const text = await response.text();
            console.error('Non-JSON response:', text);
            data = { success: false, error: 'Invalid response format' };
        }
        
        if (data.success) {
            showToast(data.message || 'Mappings saved successfully!', 'success');
            
            // Redirect if provided
            if (data.redirect) {
                setTimeout(() => {
                    window.location.href = data.redirect;
                }, 1500);
            }
            
            return true;
        } else {
            showToast(data.error || 'Failed to save mappings', 'error');
            return false;
        }
        
    } catch (error) {
        console.error('Error saving mappings:', error);
        showToast(`Network error: ${error.message}`, 'error');
        return false;
    }
}

// Auto-map columns intelligently
function autoMapColumns(sourceColumns, targetFields) {
    const mappings = {};
    
    // Common mapping patterns
    const patterns = {
        'po_number': ['po', 'purchase_order', 'order_number', 'po_num', 'ponumber'],
        'supplier_name': ['supplier', 'vendor', 'supplier_name', 'vendor_name', 'vendorname'],
        'material_description': ['material', 'item', 'product', 'description', 'item_desc', 'material_desc'],
        'quantity': ['qty', 'quantity', 'amount', 'volume', 'units'],
        'unit_price': ['price', 'unit_price', 'cost', 'rate', 'unit_cost'],
        'total_price': ['total', 'total_price', 'amount', 'total_amount', 'line_total'],
        'purchase_date': ['date', 'order_date', 'po_date', 'purchase_date', 'created']
    };
    
    targetFields.forEach(field => {
        const fieldName = field.name || field;
        const fieldLower = fieldName.toLowerCase();
        
        // Try to find best matching column
        let bestMatch = null;
        let bestScore = 0;
        
        sourceColumns.forEach(col => {
            const colLower = col.toLowerCase();
            let score = 0;
            
            // Exact match
            if (colLower === fieldLower) {
                score = 100;
            }
            // Check against patterns
            else if (patterns[fieldName]) {
                patterns[fieldName].forEach(pattern => {
                    if (colLower.includes(pattern) || pattern.includes(colLower)) {
                        score = Math.max(score, 80);
                    }
                });
            }
            // Partial match
            else if (colLower.includes(fieldLower) || fieldLower.includes(colLower)) {
                score = 60;
            }
            
            if (score > bestScore) {
                bestScore = score;
                bestMatch = col;
            }
        });
        
        if (bestMatch && bestScore > 50) {
            mappings[fieldName] = bestMatch;
        }
    });
    
    return mappings;
}

// Validate required fields are mapped
function validateMappings(mappings, requiredFields) {
    const missing = [];
    
    requiredFields.forEach(field => {
        const fieldName = field.name || field;
        if (!mappings[fieldName]) {
            missing.push(fieldName);
        }
    });
    
    if (missing.length > 0) {
        showToast(`Missing required fields: ${missing.join(', ')}`, 'warning');
        return false;
    }
    
    return true;
}

// Export functions for use in templates
window.DataIngestionHelpers = {
    getCSRFToken,
    showToast,
    saveColumnMappings,
    autoMapColumns,
    validateMappings
};