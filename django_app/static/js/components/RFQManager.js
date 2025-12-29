/**
 * RFQ Manager Component
 * Handles RFQ listing, creation, and management operations
 */

export class RFQManager {
    constructor() {
        this.selectedRFQs = new Set();
        this.csrfToken = this.getCookie('csrftoken');
    }

    init() {
        this.setupEventListeners();
        this.setupCheckboxes();
        this.setupSearch();
    }

    setupEventListeners() {
        // Select all checkbox
        const selectAll = document.getElementById('select-all');
        if (selectAll) {
            selectAll.addEventListener('change', (e) => {
                const checkboxes = document.querySelectorAll('.rfq-checkbox');
                checkboxes.forEach(cb => {
                    cb.checked = e.target.checked;
                    if (e.target.checked) {
                        this.selectedRFQs.add(cb.value);
                    } else {
                        this.selectedRFQs.delete(cb.value);
                    }
                });
                this.updateBulkActions();
            });
        }

        // Individual checkboxes
        document.querySelectorAll('.rfq-checkbox').forEach(cb => {
            cb.addEventListener('change', (e) => {
                if (e.target.checked) {
                    this.selectedRFQs.add(e.target.value);
                } else {
                    this.selectedRFQs.delete(e.target.value);
                }
                this.updateBulkActions();
            });
        });
    }

    setupCheckboxes() {
        // Initialize checkbox states
        this.updateBulkActions();
    }

    setupSearch() {
        const searchInput = document.getElementById('rfq-search');
        if (searchInput) {
            // Search is handled by HTMX, but we can add additional features here
            searchInput.addEventListener('input', (e) => {
                // Could add local filtering or debouncing here if needed
            });
        }
    }

    updateBulkActions() {
        const bulkActions = document.getElementById('bulk-actions');
        const selectedCount = document.getElementById('selected-count');
        
        if (bulkActions) {
            if (this.selectedRFQs.size > 0) {
                bulkActions.classList.remove('hidden');
                if (selectedCount) {
                    selectedCount.textContent = this.selectedRFQs.size;
                }
            } else {
                bulkActions.classList.add('hidden');
            }
        }
    }

    async viewResponses(rfqId) {
        try {
            const response = await fetch(`/procurement/quotes/?rfq_id=${rfqId}`, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            
            if (response.ok) {
                const html = await response.text();
                const modal = document.getElementById('response-modal');
                const content = document.getElementById('response-content');
                
                if (modal && content) {
                    content.innerHTML = html;
                    modal.style.display = 'block';
                }
            }
        } catch (error) {
            console.error('Error loading responses:', error);
            this.showNotification('Error loading responses', 'error');
        }
    }

    async duplicate(rfqId) {
        if (!confirm('Are you sure you want to duplicate this RFQ?')) {
            return;
        }

        try {
            const response = await fetch(`/procurement/api/rfqs/${rfqId}/duplicate/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrfToken,
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                this.showNotification('RFQ duplicated successfully', 'success');
                setTimeout(() => location.reload(), 1000);
            } else {
                throw new Error('Failed to duplicate RFQ');
            }
        } catch (error) {
            console.error('Error duplicating RFQ:', error);
            this.showNotification('Error duplicating RFQ', 'error');
        }
    }

    async delete(rfqId) {
        if (!confirm('Are you sure you want to delete this RFQ? This action cannot be undone.')) {
            return;
        }

        try {
            const response = await fetch(`/procurement/api/rfqs/${rfqId}/`, {
                method: 'DELETE',
                headers: {
                    'X-CSRFToken': this.csrfToken
                }
            });

            if (response.ok) {
                const row = document.getElementById(`rfq-row-${rfqId}`);
                if (row) {
                    row.remove();
                }
                this.showNotification('RFQ deleted successfully', 'success');
            } else {
                throw new Error('Failed to delete RFQ');
            }
        } catch (error) {
            console.error('Error deleting RFQ:', error);
            this.showNotification('Error deleting RFQ', 'error');
        }
    }

    async bulkPublish() {
        if (this.selectedRFQs.size === 0) {
            this.showNotification('Please select RFQs to publish', 'warning');
            return;
        }

        if (!confirm(`Are you sure you want to publish ${this.selectedRFQs.size} RFQ(s)?`)) {
            return;
        }

        try {
            const response = await fetch('/procurement/api/rfqs/bulk-publish/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrfToken,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    rfq_ids: Array.from(this.selectedRFQs)
                })
            });

            if (response.ok) {
                this.showNotification('RFQs published successfully', 'success');
                setTimeout(() => location.reload(), 1000);
            } else {
                throw new Error('Failed to publish RFQs');
            }
        } catch (error) {
            console.error('Error publishing RFQs:', error);
            this.showNotification('Error publishing RFQs', 'error');
        }
    }

    async bulkCancel() {
        if (this.selectedRFQs.size === 0) {
            this.showNotification('Please select RFQs to cancel', 'warning');
            return;
        }

        if (!confirm(`Are you sure you want to cancel ${this.selectedRFQs.size} RFQ(s)?`)) {
            return;
        }

        try {
            const response = await fetch('/procurement/api/rfqs/bulk-cancel/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrfToken,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    rfq_ids: Array.from(this.selectedRFQs)
                })
            });

            if (response.ok) {
                this.showNotification('RFQs cancelled successfully', 'success');
                setTimeout(() => location.reload(), 1000);
            } else {
                throw new Error('Failed to cancel RFQs');
            }
        } catch (error) {
            console.error('Error cancelling RFQs:', error);
            this.showNotification('Error cancelling RFQs', 'error');
        }
    }

    async bulkExport() {
        if (this.selectedRFQs.size === 0) {
            this.showNotification('Please select RFQs to export', 'warning');
            return;
        }

        try {
            const params = new URLSearchParams({
                rfq_ids: Array.from(this.selectedRFQs).join(',')
            });
            
            window.location.href = `/procurement/api/rfqs/export/?${params}`;
        } catch (error) {
            console.error('Error exporting RFQs:', error);
            this.showNotification('Error exporting RFQs', 'error');
        }
    }

    closeModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.style.display = 'none';
        }
    }

    openBulkImport() {
        // Implementation for bulk import modal
        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h2 class="text-xl font-bold">Import RFQs</h2>
                    <button onclick="this.parentElement.parentElement.parentElement.remove()" 
                            class="text-gray-400 hover:text-gray-600">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="modal-body">
                    <div class="text-center py-8">
                        <i class="fas fa-file-upload text-6xl text-gray-400 mb-4"></i>
                        <p class="text-gray-600 mb-4">Drag and drop your CSV or Excel file here</p>
                        <input type="file" id="import-file" accept=".csv,.xlsx,.xls" class="hidden">
                        <button onclick="document.getElementById('import-file').click()" 
                                class="btn btn-primary">
                            Select File
                        </button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        modal.style.display = 'block';
    }

    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `fixed top-4 right-4 px-6 py-4 rounded-lg shadow-lg z-50 ${
            type === 'success' ? 'bg-green-500' :
            type === 'error' ? 'bg-red-500' :
            type === 'warning' ? 'bg-yellow-500' :
            'bg-blue-500'
        } text-white`;
        
        notification.innerHTML = `
            <div class="flex items-center">
                <i class="fas fa-${
                    type === 'success' ? 'check-circle' :
                    type === 'error' ? 'exclamation-circle' :
                    type === 'warning' ? 'exclamation-triangle' :
                    'info-circle'
                } mr-3"></i>
                <span>${message}</span>
            </div>
        `;
        
        document.body.appendChild(notification);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            notification.style.opacity = '0';
            notification.style.transition = 'opacity 0.5s';
            setTimeout(() => notification.remove(), 500);
        }, 5000);
    }

    getCookie(name) {
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
}