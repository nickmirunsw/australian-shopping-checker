// Modern Shopping List App JavaScript
class ModernShoppingApp {
    constructor() {
        this.items = [];
        this.results = null;
        this.adminSessionToken = localStorage.getItem('adminSessionToken');
        this.theme = localStorage.getItem('theme') || 'light';
        
        this.initializeApp();
        this.setupEventListeners();
        this.initializeTheme();
        this.refreshDatabaseStats();
        this.checkAdminStatus();
    }

    initializeApp() {
        this.updateItemCount();
        this.updateCheckButton();
        this.showEmptyState();
    }

    initializeTheme() {
        document.documentElement.setAttribute('data-theme', this.theme);
        this.updateThemeIcon();
    }

    updateThemeIcon() {
        const themeIcon = document.querySelector('#themeToggle i');
        if (themeIcon) {
            themeIcon.setAttribute('data-lucide', this.theme === 'dark' ? 'moon' : 'sun');
            lucide.createIcons();
        }
    }

    setupEventListeners() {
        // Theme toggle
        document.getElementById('themeToggle')?.addEventListener('click', () => {
            this.toggleTheme();
        });

        // Add item functionality
        document.getElementById('addItemBtn')?.addEventListener('click', () => {
            this.addItem();
        });

        document.getElementById('newItem')?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.addItem();
            }
        });

        // Quick add buttons
        document.querySelectorAll('.quick-add-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const item = e.currentTarget.getAttribute('data-item');
                this.addItemToList(item);
            });
        });

        // Clear list
        document.getElementById('clearListBtn')?.addEventListener('click', () => {
            this.clearList();
        });

        // Check prices
        document.getElementById('checkPricesBtn')?.addEventListener('click', () => {
            this.checkPrices();
        });

        // Postcode validation
        document.getElementById('postcode')?.addEventListener('input', (e) => {
            this.validatePostcode(e.target);
        });

        // Admin functionality
        document.getElementById('adminToggleBtn')?.addEventListener('click', () => {
            this.toggleAdminPanel();
        });

        document.getElementById('adminCloseBtn')?.addEventListener('click', () => {
            this.closeAdminPanel();
        });

        document.getElementById('adminLoginBtn')?.addEventListener('click', () => {
            this.performAdminLogin();
        });

        // Admin controls
        document.getElementById('viewProductsBtn')?.addEventListener('click', () => {
            this.viewTrackedProducts();
        });

        document.getElementById('generateDummyBtn')?.addEventListener('click', () => {
            this.generateDummyData();
        });

        document.getElementById('clearDatabaseBtn')?.addEventListener('click', () => {
            this.clearDatabase();
        });

        document.getElementById('dailyUpdateBtn')?.addEventListener('click', () => {
            this.runDailyUpdate();
        });

        // Modal close on overlay click
        document.getElementById('modalOverlay')?.addEventListener('click', (e) => {
            if (e.target.id === 'modalOverlay') {
                this.hideModal();
            }
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeAdminPanel();
                this.hideModal();
            }
        });
    }

    toggleTheme() {
        this.theme = this.theme === 'light' ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', this.theme);
        localStorage.setItem('theme', this.theme);
        this.updateThemeIcon();
        this.showToast(`Switched to ${this.theme} mode`, 'success');
    }

    addItem() {
        const input = document.getElementById('newItem');
        const item = input.value.trim();
        
        if (item) {
            this.addItemToList(item);
            input.value = '';
        }
    }

    addItemToList(item) {
        if (!this.items.includes(item.toLowerCase())) {
            this.items.push(item.toLowerCase());
            this.updateItemsList();
            this.updateItemCount();
            this.updateCheckButton();
            this.showToast(`Added "${item}" to your list`, 'success');
        } else {
            this.showToast(`"${item}" is already in your list`, 'warning');
        }
    }

    removeItem(item) {
        const index = this.items.indexOf(item);
        if (index > -1) {
            this.items.splice(index, 1);
            this.updateItemsList();
            this.updateItemCount();
            this.updateCheckButton();
            this.showToast(`Removed "${item}" from your list`, 'success');
        }
    }

    clearList() {
        if (this.items.length === 0) {
            this.showToast('Your list is already empty', 'warning');
            return;
        }

        if (confirm('Clear all items from your shopping list?')) {
            this.items = [];
            this.updateItemsList();
            this.updateItemCount();
            this.updateCheckButton();
            this.showEmptyState();
            this.showToast('Shopping list cleared', 'success');
        }
    }

    updateItemsList() {
        const itemsList = document.getElementById('itemsList');
        if (!itemsList) return;

        itemsList.innerHTML = '';
        
        this.items.forEach(item => {
            const li = document.createElement('li');
            li.className = 'item';
            li.innerHTML = `
                <span class="item-text">${this.capitalizeFirst(item)}</span>
                <button class="item-remove" onclick="app.removeItem('${item}')" aria-label="Remove ${item}">
                    <i data-lucide="x"></i>
                </button>
            `;
            itemsList.appendChild(li);
        });

        // Re-initialize lucide icons
        lucide.createIcons();
    }

    updateItemCount() {
        const countElement = document.getElementById('itemCount');
        if (countElement) {
            countElement.textContent = this.items.length;
        }
    }

    updateCheckButton() {
        const button = document.getElementById('checkPricesBtn');
        if (button) {
            button.disabled = this.items.length === 0;
        }
    }

    capitalizeFirst(str) {
        return str.charAt(0).toUpperCase() + str.slice(1);
    }

    validatePostcode(input) {
        const value = input.value.replace(/\D/g, ''); // Only digits
        input.value = value.slice(0, 4); // Max 4 digits
        
        if (value.length === 4) {
            input.classList.remove('error');
        }
    }

    async checkPrices() {
        if (this.items.length === 0) {
            this.showToast('Add items to your list first', 'warning');
            return;
        }

        const postcode = document.getElementById('postcode').value.trim();
        if (!postcode || postcode.length !== 4) {
            this.showToast('Please enter a valid 4-digit postcode', 'error');
            document.getElementById('postcode').focus();
            return;
        }

        this.showLoadingState();

        try {
            const response = await fetch('/check', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    items: this.items.join(', '),
                    postcode: postcode
                })
            });

            const data = await response.json();
            
            if (response.ok) {
                this.results = data;
                this.displayResults(data);
                this.showToast(`Found prices for ${data.results.length} items`, 'success');
            } else {
                this.showError('Failed to check prices. Please try again.');
                this.showToast('Failed to check prices', 'error');
            }
        } catch (error) {
            console.error('Price check error:', error);
            this.showError('Network error. Please check your connection.');
            this.showToast('Connection error', 'error');
        }
    }

    showLoadingState() {
        document.getElementById('emptyState').classList.add('hidden');
        document.getElementById('resultsContainer').classList.add('hidden');
        document.getElementById('loadingState').classList.remove('hidden');
        
        this.updateResultsSummary('Searching for prices...');
    }

    showEmptyState() {
        document.getElementById('loadingState').classList.add('hidden');
        document.getElementById('resultsContainer').classList.add('hidden');
        document.getElementById('emptyState').classList.remove('hidden');
        
        this.updateResultsSummary('');
    }

    showError(message) {
        document.getElementById('loadingState').classList.add('hidden');
        document.getElementById('resultsContainer').classList.add('hidden');
        
        const emptyState = document.getElementById('emptyState');
        emptyState.classList.remove('hidden');
        emptyState.innerHTML = `
            <i data-lucide="alert-circle"></i>
            <h3>Oops! Something went wrong</h3>
            <p>${message}</p>
        `;
        
        lucide.createIcons();
    }

    updateResultsSummary(text) {
        const summary = document.getElementById('resultsSummary');
        if (summary) {
            summary.textContent = text;
        }
    }

    displayResults(data) {
        document.getElementById('loadingState').classList.add('hidden');
        document.getElementById('emptyState').classList.add('hidden');
        document.getElementById('resultsContainer').classList.remove('hidden');
        
        this.updateResultsSummary(`Found ${data.results.length} items • Postcode: ${data.postcode}`);
        
        const container = document.getElementById('resultsContainer');
        container.innerHTML = '';
        
        data.results.forEach(result => {
            const productCard = this.createProductCard(result);
            container.appendChild(productCard);
        });
    }

    createProductCard(result) {
        const card = document.createElement('div');
        card.className = 'product-card';
        
        const bestMatch = result.alternatives[0];
        const onSaleCount = result.alternatives.filter(alt => alt.onSale).length;
        
        card.innerHTML = `
            <div class="product-header">
                <div class="product-name">${this.capitalizeFirst(result.input)}</div>
                <div class="product-summary">
                    <span>Best: ${bestMatch.name}</span>
                    <span>$${bestMatch.price}</span>
                    ${onSaleCount > 0 ? `<span>${onSaleCount} on sale</span>` : ''}
                </div>
            </div>
            <div class="product-body">
                <div class="alternatives-grid">
                    ${result.alternatives.map(alt => this.createAlternativeItem(alt)).join('')}
                </div>
            </div>
        `;
        
        return card;
    }

    createAlternativeItem(alt) {
        return `
            <div class="alternative-item">
                <div class="alternative-info">
                    <div class="alternative-name">${alt.name}</div>
                    <div class="alternative-details">
                        Match: ${Math.round((alt.matchScore || 0.8) * 100)}%
                        ${alt.promoText ? `• ${alt.promoText}` : ''}
                    </div>
                </div>
                <div class="alternative-price">
                    <div class="current-price">$${alt.price || 'N/A'}</div>
                    ${alt.was ? `<div class="was-price">was $${alt.was}</div>` : ''}
                    ${alt.onSale ? '<div class="sale-badge">ON SALE</div>' : ''}
                </div>
            </div>
        `;
    }

    // Admin functionality
    toggleAdminPanel() {
        const panel = document.querySelector('.admin-panel');
        const button = document.getElementById('adminToggleBtn');
        
        if (panel.classList.contains('active')) {
            this.closeAdminPanel();
        } else {
            panel.classList.add('active');
            button.classList.add('active');
        }
    }

    closeAdminPanel() {
        const panel = document.querySelector('.admin-panel');
        const button = document.getElementById('adminToggleBtn');
        
        panel.classList.remove('active');
        button.classList.remove('active');
    }

    async checkAdminStatus() {
        if (!this.adminSessionToken) {
            this.updateAdminUI(false);
            return;
        }

        try {
            const response = await fetch('/admin/status', {
                headers: {
                    'Authorization': `Bearer ${this.adminSessionToken}`
                }
            });
            
            const data = await response.json();
            this.updateAdminUI(data.authenticated);
            
            if (!data.authenticated) {
                this.adminSessionToken = null;
                localStorage.removeItem('adminSessionToken');
            }
        } catch (error) {
            console.error('Admin status check failed:', error);
            this.updateAdminUI(false);
            this.adminSessionToken = null;
            localStorage.removeItem('adminSessionToken');
        }
    }

    updateAdminUI(isAuthenticated) {
        const loginForm = document.getElementById('adminLoginForm');
        const controls = document.getElementById('adminControls');
        
        if (isAuthenticated) {
            loginForm.classList.add('hidden');
            controls.classList.remove('hidden');
        } else {
            loginForm.classList.remove('hidden');
            controls.classList.add('hidden');
        }
    }

    async performAdminLogin() {
        const username = document.getElementById('adminUsername').value.trim();
        const password = document.getElementById('adminPassword').value.trim();
        
        if (!username || !password) {
            this.showToast('Please enter username and password', 'error');
            return;
        }

        try {
            const response = await fetch('/admin/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ username, password })
            });

            const data = await response.json();
            
            if (response.ok && data.success) {
                this.adminSessionToken = data.session_token;
                localStorage.setItem('adminSessionToken', data.session_token);
                this.updateAdminUI(true);
                this.refreshDatabaseStats();
                this.showToast('Admin login successful', 'success');
            } else {
                this.showToast('Login failed. Check your credentials.', 'error');
            }
        } catch (error) {
            console.error('Admin login error:', error);
            this.showToast('Login error. Please try again.', 'error');
        }
    }

    async makeAuthenticatedRequest(url, options = {}) {
        if (!this.adminSessionToken) {
            throw new Error('Admin authentication required');
        }
        
        const headers = {
            ...options.headers,
            'Authorization': `Bearer ${this.adminSessionToken}`
        };
        
        const response = await fetch(url, { ...options, headers });
        
        if (response.status === 401) {
            this.adminSessionToken = null;
            localStorage.removeItem('adminSessionToken');
            this.updateAdminUI(false);
            throw new Error('Admin session expired. Please log in again.');
        }
        
        return response;
    }

    async refreshDatabaseStats() {
        try {
            const response = await fetch('/database/stats');
            const data = await response.json();
            
            if (response.ok) {
                this.updateDatabaseStats(data.stats);
            }
        } catch (error) {
            console.error('Failed to refresh database stats:', error);
        }
    }

    updateDatabaseStats(stats) {
        const statsContainer = document.getElementById('databaseStats');
        if (!statsContainer) return;
        
        const priceHistory = stats.price_history || {};
        const alternatives = stats.alternatives || {};
        
        statsContainer.innerHTML = `
            <div class="stat-card">
                <div class="stat-value">${priceHistory.unique_products || 0}</div>
                <div class="stat-label">Products Tracked</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${priceHistory.total_records || 0}</div>
                <div class="stat-label">Price Records</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${this.calculateDaysBetween(priceHistory.oldest_record, priceHistory.newest_record)}</div>
                <div class="stat-label">Days of Data</div>
            </div>
        `;
    }

    calculateDaysBetween(start, end) {
        if (!start || !end) return 0;
        const startDate = new Date(start);
        const endDate = new Date(end);
        const diffTime = Math.abs(endDate - startDate);
        return Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1;
    }

    async viewTrackedProducts() {
        try {
            const response = await this.makeAuthenticatedRequest('/admin/tracked-products');
            const data = await response.json();
            
            if (data.success) {
                this.showProductsModal(data.products);
            } else {
                this.showToast('Failed to load tracked products', 'error');
            }
        } catch (error) {
            console.error('Error viewing tracked products:', error);
            this.showToast(error.message || 'Error loading products', 'error');
        }
    }

    showProductsModal(products) {
        const modal = document.getElementById('modalContent');
        modal.innerHTML = `
            <div style="padding: 2rem; max-width: 800px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem;">
                    <h2 style="margin: 0;">Tracked Products (${products.length})</h2>
                    <button onclick="app.hideModal()" style="background: none; border: none; font-size: 1.5rem; cursor: pointer;">&times;</button>
                </div>
                
                <div style="max-height: 60vh; overflow-y: auto;">
                    ${products.length > 0 ? `
                        <div style="display: grid; gap: 0.75rem;">
                            ${products.map(product => `
                                <div style="display: flex; justify-content: space-between; align-items: center; padding: 1rem; background: var(--bg-secondary); border-radius: 0.5rem; border: 1px solid var(--color-gray-200);">
                                    <div>
                                        <div style="font-weight: 500; color: var(--text-primary);">${product.product_name}</div>
                                        <div style="font-size: 0.875rem; color: var(--text-secondary);">
                                            ${product.retailer} • ${product.record_count} records • 
                                            ${product.first_seen} to ${product.last_seen}
                                        </div>
                                    </div>
                                    <button onclick="app.deleteProduct('${product.product_name}', '${product.retailer}')" 
                                            style="padding: 0.5rem; background: var(--color-error); color: white; border: none; border-radius: 0.25rem; cursor: pointer;">
                                        Delete
                                    </button>
                                </div>
                            `).join('')}
                        </div>
                    ` : `
                        <div style="text-align: center; padding: 2rem; color: var(--text-secondary);">
                            No products being tracked yet. Use the search feature to start tracking prices!
                        </div>
                    `}
                </div>
            </div>
        `;
        
        this.showModal();
    }

    async deleteProduct(productName, retailer) {
        if (!confirm(`Delete all price history for "${productName}" at ${retailer}?`)) {
            return;
        }

        try {
            const response = await this.makeAuthenticatedRequest(
                `/admin/product/${encodeURIComponent(productName)}/${encodeURIComponent(retailer)}`,
                { method: 'DELETE' }
            );
            
            const result = await response.json();
            
            if (result.success) {
                this.showToast(`Deleted ${result.records_deleted} records`, 'success');
                this.viewTrackedProducts(); // Refresh the modal
                this.refreshDatabaseStats();
            } else {
                this.showToast('Failed to delete product', 'error');
            }
        } catch (error) {
            console.error('Error deleting product:', error);
            this.showToast(error.message || 'Error deleting product', 'error');
        }
    }

    async generateDummyData() {
        try {
            this.showToast('Generating test data...', 'success');
            
            const response = await this.makeAuthenticatedRequest('/admin/generate-dummy-data', {
                method: 'POST'
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showToast('Test data generated successfully', 'success');
                this.refreshDatabaseStats();
            } else {
                this.showToast('Failed to generate test data', 'error');
            }
        } catch (error) {
            console.error('Error generating dummy data:', error);
            this.showToast(error.message || 'Error generating data', 'error');
        }
    }

    async clearDatabase() {
        if (!confirm('Are you sure you want to clear ALL database records? This cannot be undone!')) {
            return;
        }

        try {
            const response = await this.makeAuthenticatedRequest('/admin/clear-database', {
                method: 'POST'
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showToast('Database cleared successfully', 'success');
                this.refreshDatabaseStats();
            } else {
                this.showToast('Failed to clear database', 'error');
            }
        } catch (error) {
            console.error('Error clearing database:', error);
            this.showToast(error.message || 'Error clearing database', 'error');
        }
    }

    async runDailyUpdate() {
        try {
            this.showToast('Running daily price update...', 'success');
            
            const response = await this.makeAuthenticatedRequest('/daily-price-update', {
                method: 'POST'
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showToast('Daily update completed successfully', 'success');
                this.refreshDatabaseStats();
            } else {
                this.showToast('Daily update failed', 'error');
            }
        } catch (error) {
            console.error('Error running daily update:', error);
            this.showToast(error.message || 'Error running update', 'error');
        }
    }

    showModal() {
        document.getElementById('modalOverlay').classList.remove('hidden');
    }

    hideModal() {
        document.getElementById('modalOverlay').classList.add('hidden');
    }

    showToast(message, type = 'success') {
        const container = document.getElementById('toastContainer');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        
        container.appendChild(toast);
        
        // Auto remove after 3 seconds
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 3000);
    }
}

// Initialize the app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.app = new ModernShoppingApp();
});