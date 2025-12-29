/**
 * Material Manager Component
 * Handles material CRUD operations and UI interactions
 */

import { API } from '../utils/api.js';
import { Charts } from '../utils/charts.js';
import { Utils } from '../utils/utils.js';

export class MaterialManager {
    constructor() {
        this.api = new API();
        this.charts = new Charts();
        this.selectedMaterials = new Set();
        this.priceChart = null;
    }

    init() {
        this.bindEvents();
        this.initializeFilters();
        this.setupBulkActions();
    }

    bindEvents() {
        // Select all checkbox
        const selectAll = document.getElementById('select-all');
        if (selectAll) {
            selectAll.addEventListener('change', (e) => {
                this.toggleSelectAll(e.target.checked);
            });
        }

        // Individual checkboxes
        document.querySelectorAll('.material-checkbox').forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                this.toggleMaterial(e.target.value, e.target.checked);
            });
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey || e.metaKey) {
                switch(e.key) {
                    case 'a':
                        e.preventDefault();
                        this.selectAll();
                        break;
                    case 'n':
                        e.preventDefault();
                        this.createNew();
                        break;
                }
            }
        });
    }

    initializeFilters() {
        // Auto-submit forms on filter change
        const filters = ['#category-filter', '#status-filter'];
        filters.forEach(selector => {
            const element = document.querySelector(selector);
            if (element) {
                element.addEventListener('change', () => {
                    this.applyFilters();
                });
            }
        });
    }

    setupBulkActions() {
        const bulkActionBtn = document.getElementById('bulk-action-btn');
        if (bulkActionBtn) {
            bulkActionBtn.addEventListener('click', () => {
                this.showBulkActions();
            });
        }
    }

    async viewDetail(materialId) {
        try {
            const response = await this.api.get(`/api/pricing/materials/${materialId}/`);
            this.showDetailModal(response.data);
        } catch (error) {
            Utils.showNotification('Failed to load material details', 'error');
        }
    }

    showDetailModal(material) {
        const modal = document.getElementById('material-detail-modal');
        const content = document.getElementById('material-detail-content');
        
        content.innerHTML = `
            <div class="grid grid-cols-2 gap-6">
                <div>
                    <h3 class="text-lg font-semibold mb-4">Basic Information</h3>
                    <dl class="space-y-3">
                        <div>
                            <dt class="text-sm font-medium text-gray-500">Material Code</dt>
                            <dd class="text-gray-900">${material.code}</dd>
                        </div>
                        <div>
                            <dt class="text-sm font-medium text-gray-500">Name</dt>
                            <dd class="text-gray-900">${material.name}</dd>
                        </div>
                        <div>
                            <dt class="text-sm font-medium text-gray-500">Category</dt>
                            <dd class="text-gray-900">${material.category.name}</dd>
                        </div>
                        <div>
                            <dt class="text-sm font-medium text-gray-500">Unit of Measure</dt>
                            <dd class="text-gray-900">${material.unit}</dd>
                        </div>
                        <div>
                            <dt class="text-sm font-medium text-gray-500">Description</dt>
                            <dd class="text-gray-900">${material.description || '-'}</dd>
                        </div>
                    </dl>
                </div>
                
                <div>
                    <h3 class="text-lg font-semibold mb-4">Pricing Information</h3>
                    <dl class="space-y-3">
                        <div>
                            <dt class="text-sm font-medium text-gray-500">Current Price</dt>
                            <dd class="text-2xl font-bold text-navy-600">
                                $${material.current_price?.toFixed(2) || '-'}
                            </dd>
                        </div>
                        <div>
                            <dt class="text-sm font-medium text-gray-500">Average Price (30 days)</dt>
                            <dd class="text-gray-900">$${material.avg_price_30d?.toFixed(2) || '-'}</dd>
                        </div>
                        <div>
                            <dt class="text-sm font-medium text-gray-500">Min Price (30 days)</dt>
                            <dd class="text-gray-900">$${material.min_price_30d?.toFixed(2) || '-'}</dd>
                        </div>
                        <div>
                            <dt class="text-sm font-medium text-gray-500">Max Price (30 days)</dt>
                            <dd class="text-gray-900">$${material.max_price_30d?.toFixed(2) || '-'}</dd>
                        </div>
                        <div>
                            <dt class="text-sm font-medium text-gray-500">Price Volatility</dt>
                            <dd class="text-gray-900">${material.volatility?.toFixed(2) || '-'}%</dd>
                        </div>
                    </dl>
                </div>
            </div>
            
            <div class="mt-6 pt-6 border-t">
                <h3 class="text-lg font-semibold mb-4">Specifications</h3>
                ${this.renderSpecifications(material.specifications)}
            </div>
            
            <div class="mt-6 pt-6 border-t">
                <h3 class="text-lg font-semibold mb-4">Active Suppliers</h3>
                ${this.renderSuppliers(material.suppliers)}
            </div>
        `;
        
        modal.style.display = 'flex';
    }

    renderSpecifications(specs) {
        if (!specs || Object.keys(specs).length === 0) {
            return '<p class="text-gray-500">No specifications available</p>';
        }
        
        return `
            <table class="min-w-full">
                <thead>
                    <tr class="bg-gray-50">
                        <th class="px-4 py-2 text-left text-sm font-medium text-gray-700">Property</th>
                        <th class="px-4 py-2 text-left text-sm font-medium text-gray-700">Value</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-gray-200">
                    ${Object.entries(specs).map(([key, value]) => `
                        <tr>
                            <td class="px-4 py-2 text-sm text-gray-600">${key}</td>
                            <td class="px-4 py-2 text-sm text-gray-900">${value}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    }

    renderSuppliers(suppliers) {
        if (!suppliers || suppliers.length === 0) {
            return '<p class="text-gray-500">No suppliers assigned</p>';
        }
        
        return `
            <div class="grid grid-cols-2 gap-4">
                ${suppliers.map(supplier => `
                    <div class="border rounded-lg p-3">
                        <div class="font-medium">${supplier.name}</div>
                        <div class="text-sm text-gray-500">${supplier.contact}</div>
                        <div class="text-sm text-gray-500">Lead time: ${supplier.lead_time} days</div>
                    </div>
                `).join('')}
            </div>
        `;
    }

    async viewPriceHistory(materialId) {
        try {
            const response = await this.api.get(`/api/pricing/materials/${materialId}/price-history/`);
            this.showPriceHistoryModal(response.data);
        } catch (error) {
            Utils.showNotification('Failed to load price history', 'error');
        }
    }

    showPriceHistoryModal(data) {
        const modal = document.getElementById('price-history-modal');
        const content = document.getElementById('price-history-content');
        
        content.innerHTML = `
            <div class="mb-4">
                <h3 class="text-lg font-semibold">${data.material.name}</h3>
                <p class="text-gray-600">Material Code: ${data.material.code}</p>
            </div>
            
            <div class="grid grid-cols-4 gap-4 mb-6">
                <div class="bg-gray-50 rounded-lg p-4">
                    <div class="text-sm text-gray-600">Current Price</div>
                    <div class="text-2xl font-bold text-navy-600">$${data.current_price.toFixed(2)}</div>
                </div>
                <div class="bg-gray-50 rounded-lg p-4">
                    <div class="text-sm text-gray-600">30-Day Avg</div>
                    <div class="text-2xl font-bold">$${data.avg_30d.toFixed(2)}</div>
                </div>
                <div class="bg-gray-50 rounded-lg p-4">
                    <div class="text-sm text-gray-600">Change</div>
                    <div class="text-2xl font-bold ${data.change > 0 ? 'text-red-600' : 'text-green-600'}">
                        ${data.change > 0 ? '+' : ''}${data.change.toFixed(1)}%
                    </div>
                </div>
                <div class="bg-gray-50 rounded-lg p-4">
                    <div class="text-sm text-gray-600">Volatility</div>
                    <div class="text-2xl font-bold">${data.volatility.toFixed(1)}%</div>
                </div>
            </div>
            
            <div class="h-80">
                <canvas id="price-history-chart"></canvas>
            </div>
            
            <div class="mt-6">
                <h4 class="font-semibold mb-3">Recent Price Changes</h4>
                <table class="min-w-full">
                    <thead>
                        <tr class="bg-gray-50">
                            <th class="px-4 py-2 text-left text-sm">Date</th>
                            <th class="px-4 py-2 text-left text-sm">Supplier</th>
                            <th class="px-4 py-2 text-right text-sm">Price</th>
                            <th class="px-4 py-2 text-right text-sm">Change</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-gray-200">
                        ${data.recent_prices.map(price => `
                            <tr>
                                <td class="px-4 py-2 text-sm">${new Date(price.date).toLocaleDateString()}</td>
                                <td class="px-4 py-2 text-sm">${price.supplier}</td>
                                <td class="px-4 py-2 text-sm text-right">$${price.amount.toFixed(2)}</td>
                                <td class="px-4 py-2 text-sm text-right">
                                    <span class="${price.change > 0 ? 'text-red-600' : 'text-green-600'}">
                                        ${price.change > 0 ? '+' : ''}${price.change.toFixed(1)}%
                                    </span>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
        
        modal.style.display = 'flex';
        
        // Create price history chart
        setTimeout(() => {
            this.createPriceChart(data.price_history);
        }, 100);
    }

    createPriceChart(priceHistory) {
        const ctx = document.getElementById('price-history-chart').getContext('2d');
        
        if (this.priceChart) {
            this.priceChart.destroy();
        }
        
        this.priceChart = this.charts.createLineChart(ctx, {
            labels: priceHistory.map(p => new Date(p.date).toLocaleDateString()),
            datasets: [{
                label: 'Price',
                data: priceHistory.map(p => p.price),
                borderColor: '#1e3a8a',
                backgroundColor: 'rgba(30, 58, 138, 0.1)',
                tension: 0.1
            }]
        }, {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: (context) => `Price: $${context.parsed.y.toFixed(2)}`
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: false,
                    ticks: {
                        callback: (value) => `$${value.toFixed(2)}`
                    }
                }
            }
        });
    }

    edit(materialId) {
        window.location.href = `/pricing/materials/${materialId}/edit/`;
    }

    async delete(materialId) {
        if (!confirm('Are you sure you want to delete this material?')) {
            return;
        }
        
        try {
            await this.api.delete(`/api/pricing/materials/${materialId}/`);
            Utils.showNotification('Material deleted successfully', 'success');
            
            // Remove row from table
            const row = document.getElementById(`material-row-${materialId}`);
            if (row) {
                row.remove();
            }
        } catch (error) {
            Utils.showNotification('Failed to delete material', 'error');
        }
    }

    openBulkImport() {
        // Implement bulk import modal
        Utils.showNotification('Bulk import feature coming soon', 'info');
    }

    toggleSelectAll(checked) {
        document.querySelectorAll('.material-checkbox').forEach(checkbox => {
            checkbox.checked = checked;
            this.toggleMaterial(checkbox.value, checked);
        });
    }

    toggleMaterial(materialId, selected) {
        if (selected) {
            this.selectedMaterials.add(materialId);
        } else {
            this.selectedMaterials.delete(materialId);
        }
        
        this.updateBulkActionsVisibility();
    }

    updateBulkActionsVisibility() {
        const bulkActions = document.getElementById('bulk-actions');
        if (bulkActions) {
            bulkActions.style.display = this.selectedMaterials.size > 0 ? 'block' : 'none';
        }
    }

    selectAll() {
        const selectAll = document.getElementById('select-all');
        if (selectAll) {
            selectAll.checked = true;
            this.toggleSelectAll(true);
        }
    }

    createNew() {
        window.location.href = '/pricing/materials/create/';
    }

    applyFilters() {
        // Filters are handled by HTMX
    }

    closeModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.style.display = 'none';
        }
    }
}