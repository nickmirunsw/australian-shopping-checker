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
        // Remove auto-login on page load for security
        this.updateAdminUI(false); // Start with logged out state
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

        document.getElementById('adminLogoutBtn')?.addEventListener('click', () => {
            this.performAdminLogout();
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

        document.getElementById('viewFavoritesBtn')?.addEventListener('click', () => {
            this.viewFavorites();
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
        
        // Re-initialize lucide icons for the new content
        if (window.lucide) {
            lucide.createIcons();
        }
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
                    <button onclick="app.showPriceHistory('${bestMatch.name}', '${bestMatch.retailer || 'woolworths'}')" 
                            class="btn btn-ghost btn-sm" title="Price History">
                        <i data-lucide="trending-up"></i>
                    </button>
                </div>
            </div>
            <div class="product-body">
                <div class="alternatives-grid">
                    ${result.alternatives.map(alt => this.createAlternativeItem(alt, result.input, !!this.adminSessionToken)).join('')}
                </div>
            </div>
        `;
        
        return card;
    }

    createAlternativeItem(alt, inputName, isAdmin = false) {
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
                    <div class="alternative-actions">
                        <button onclick="app.showPriceHistory('${alt.name}', '${alt.retailer || 'woolworths'}')" 
                                class="btn btn-ghost btn-sm" title="Price History">
                            <i data-lucide="trending-up"></i>
                        </button>
                        ${isAdmin ? `
                            <button onclick="app.addToFavorites('${alt.name}', '${alt.retailer || 'woolworths'}')" 
                                    class="btn btn-ghost btn-sm" title="Add to Favorites">
                                <i data-lucide="heart"></i>
                            </button>
                        ` : ''}
                    </div>
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
            console.log('Admin panel opened');
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
                
                // Re-setup event listeners for logout button
                this.setupAdminEventListeners();
                
                // Refresh results to show admin features like favorites buttons
                if (this.results) {
                    this.displayResults(this.results);
                }
            } else {
                this.showToast('Login failed. Check your credentials.', 'error');
            }
        } catch (error) {
            console.error('Admin login error:', error);
            this.showToast('Login error. Please try again.', 'error');
        }
    }

    performAdminLogout() {
        this.adminSessionToken = null;
        localStorage.removeItem('adminSessionToken');
        this.updateAdminUI(false);
        this.showToast('Logged out successfully', 'success');
        
        // Refresh results to hide admin features
        if (this.results) {
            this.displayResults(this.results);
        }
    }

    setupAdminEventListeners() {
        // Note: Admin button event listeners are already set up in main setupEventListeners()
        // This function is kept for any future admin-specific event handling
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
        // Store original products for search
        this.allProducts = products;
        
        const modal = document.getElementById('modalContent');
        modal.innerHTML = `
            <div style="padding: 2rem; max-width: 900px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem;">
                    <h2 style="margin: 0; color: var(--text-primary);">Tracked Products (${products.length})</h2>
                    <button onclick="app.hideModal()" style="background: none; border: none; font-size: 1.5rem; cursor: pointer; color: var(--text-primary);">&times;</button>
                </div>
                
                <!-- Search Bar -->
                <div style="margin-bottom: 1.5rem;">
                    <input 
                        type="text" 
                        id="productSearch" 
                        placeholder="Search tracked products..." 
                        class="input"
                        style="width: 100%; padding: 0.75rem; border: 1.5px solid var(--color-gray-300); border-radius: 0.5rem; font-size: 0.9rem;"
                        oninput="app.filterProducts(this.value)"
                    >
                </div>
                
                <div id="productsContainer" style="max-height: 60vh; overflow-y: auto;"></div>
            </div>
        `;
        
        this.showModal();
        this.renderProducts(products);
        
        // Focus search input
        setTimeout(() => {
            const searchInput = document.getElementById('productSearch');
            if (searchInput) {
                searchInput.focus();
            }
        }, 100);
    }

    filterProducts(searchTerm) {
        if (!this.allProducts) return;
        
        const filtered = this.allProducts.filter(product => 
            product.product_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
            product.retailer.toLowerCase().includes(searchTerm.toLowerCase())
        );
        
        this.renderProducts(filtered);
    }

    renderProducts(products) {
        const container = document.getElementById('productsContainer');
        if (!container) return;
        
        // Categorize products
        const categories = this.categorizeProducts(products);
        
        container.innerHTML = products.length > 0 ? `
            ${Object.entries(categories).map(([category, items]) => `
                <div style="margin-bottom: 2rem;">
                    <h3 style="margin-bottom: 1rem; color: var(--color-primary); font-size: 1rem; text-transform: uppercase; letter-spacing: 0.5px;">
                        ${category} (${items.length})
                    </h3>
                    <div style="display: grid; gap: 0.5rem;">
                        ${items.map(product => `
                            <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.75rem 1rem; background: var(--bg-secondary); border-radius: 0.5rem; border: 1px solid var(--color-gray-200);">
                                <div style="flex: 1;">
                                    <div style="font-weight: 500; color: var(--text-primary); font-size: 0.9rem;">${product.product_name}</div>
                                    <div style="font-size: 0.75rem; color: var(--text-secondary);">
                                        ${product.retailer} • ${product.record_count} records • 
                                        ${product.first_seen} to ${product.last_seen}
                                    </div>
                                </div>
                                <div style="display: flex; gap: 0.5rem; margin-left: 1rem;">
                                    <button onclick="app.showPriceHistory('${product.product_name}', '${product.retailer}')" 
                                            style="padding: 0.4rem 0.6rem; background: var(--color-primary); color: white; border: none; border-radius: 0.25rem; cursor: pointer; font-size: 0.75rem;">
                                        History
                                    </button>
                                    <button onclick="app.addToFavorites('${product.product_name}', '${product.retailer}')" 
                                            style="padding: 0.4rem 0.6rem; background: var(--color-secondary); color: white; border: none; border-radius: 0.25rem; cursor: pointer; font-size: 0.75rem;">
                                        ♥ Fav
                                    </button>
                                    <button onclick="app.deleteProduct('${product.product_name}', '${product.retailer}')" 
                                            style="padding: 0.4rem 0.6rem; background: var(--color-error); color: white; border: none; border-radius: 0.25rem; cursor: pointer; font-size: 0.75rem;">
                                        Delete
                                    </button>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `).join('')}
        ` : `
            <div style="text-align: center; padding: 2rem; color: var(--text-secondary);">
                ${this.allProducts && this.allProducts.length > 0 ? 
                    'No products match your search.' : 
                    'No products being tracked yet. Use the search feature to start tracking prices!'
                }
            </div>
        `;
    }

    categorizeProducts(products) {
        const categories = {
            'Dairy & Eggs': [],
            'Meat & Poultry': [],
            'Bakery': [],
            'Fruits & Vegetables': [],
            'Pantry & Dry Goods': [],
            'Snacks & Confectionery': [],
            'Beverages': [],
            'Frozen Foods': [],
            'Health & Beauty': [],
            'Household': [],
            'Other': []
        };

        products.forEach(product => {
            const name = product.product_name.toLowerCase();
            let categorized = false;

            // Dairy & Eggs
            if (/milk|cheese|yoghurt|yogurt|butter|cream|egg|dairy/.test(name)) {
                categories['Dairy & Eggs'].push(product);
                categorized = true;
            }
            // Meat & Poultry  
            else if (/chicken|beef|pork|lamb|fish|salmon|tuna|meat|sausage|bacon|ham/.test(name)) {
                categories['Meat & Poultry'].push(product);
                categorized = true;
            }
            // Bakery
            else if (/bread|roll|bagel|muffin|cake|pastry|biscuit|cookie/.test(name)) {
                categories['Bakery'].push(product);
                categorized = true;
            }
            // Fruits & Vegetables
            else if (/banana|apple|orange|tomato|lettuce|carrot|potato|onion|fruit|vegetable|salad/.test(name)) {
                categories['Fruits & Vegetables'].push(product);
                categorized = true;
            }
            // Pantry & Dry Goods
            else if (/rice|pasta|cereal|flour|sugar|salt|oil|sauce|spice|tin|can/.test(name)) {
                categories['Pantry & Dry Goods'].push(product);
                categorized = true;
            }
            // Snacks & Confectionery
            else if (/chocolate|lolly|candy|chips|crisp|biscuit|cookie|snack|nuts|cheezels/.test(name)) {
                categories['Snacks & Confectionery'].push(product);
                categorized = true;
            }
            // Beverages
            else if (/juice|water|soft drink|coke|pepsi|tea|coffee|beer|wine|milk/.test(name)) {
                categories['Beverages'].push(product);
                categorized = true;
            }
            // Frozen Foods
            else if (/frozen|ice cream|pizza/.test(name)) {
                categories['Frozen Foods'].push(product);
                categorized = true;
            }
            // Health & Beauty
            else if (/shampoo|soap|toothpaste|vitamin|medicine/.test(name)) {
                categories['Health & Beauty'].push(product);
                categorized = true;
            }
            // Household
            else if (/detergent|cleaner|paper|tissue|toilet/.test(name)) {
                categories['Household'].push(product);
                categorized = true;
            }

            if (!categorized) {
                categories['Other'].push(product);
            }
        });

        // Remove empty categories
        Object.keys(categories).forEach(key => {
            if (categories[key].length === 0) {
                delete categories[key];
            }
        });

        return categories;
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
            // Ask user for update type
            const useQuickMode = confirm(
                'Choose update mode:\n\n' +
                'OK = Quick Update (up to 100 products, ~2-3 minutes)\n' +
                'Cancel = Full Update (all products, may take 10+ minutes)\n\n' +
                'Recommendation: Use Quick Update during business hours.'
            );
            
            const updateType = useQuickMode ? 'Quick' : 'Full';
            this.showToast(`Starting ${updateType} price update...`, 'success');
            
            const response = await this.makeAuthenticatedRequest('/daily-price-update', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    quick_mode: useQuickMode,
                    batch_size: useQuickMode ? 20 : 25  // Slightly larger batches for full updates
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                const stats = result.stats;
                const message = `${updateType} update completed: ${stats.successful_updates}/${stats.products_processed} products updated (${stats.success_rate}% success)`;
                this.showToast(message, 'success');
                this.refreshDatabaseStats();
                
                // Show detailed results
                if (stats.failed_updates > 0) {
                    this.showToast(`Note: ${stats.failed_updates} products failed to update`, 'warning');
                }
            } else {
                this.showToast(`${updateType} update failed: ${result.message}`, 'error');
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

    async showPriceHistory(productName, retailer) {
        try {
            // Always use public endpoint to avoid auth issues
            const response = await fetch(`/price-history/${encodeURIComponent(productName)}?retailer=${encodeURIComponent(retailer)}&days_back=365`);
            const data = await response.json();
            
            if (response.ok && data.history && data.history.length > 0) {
                this.showPriceHistoryModal(data.history, productName, retailer);
            } else {
                this.showToast('No price history available for this product', 'warning');
            }
        } catch (error) {
            console.error('Error loading price history:', error);
            this.showToast('Error loading price history', 'error');
        }
    }

    showPriceHistoryModal(history, productName, retailer) {
        const modal = document.getElementById('modalContent');
        const isDarkMode = document.documentElement.getAttribute('data-theme') === 'dark';
        
        modal.innerHTML = `
            <div style="padding: 2rem; max-width: 1000px; width: 90vw;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem;">
                    <h2 style="margin: 0; color: var(--text-primary);">Price History: ${productName}</h2>
                    <button onclick="app.hideModal()" style="background: none; border: none; font-size: 1.5rem; cursor: pointer; color: var(--text-primary);">&times;</button>
                </div>
                
                <div style="margin-bottom: 1.5rem; height: 300px; position: relative; overflow: hidden;">
                    <canvas id="priceChart" style="width: 100%; height: 100%;"></canvas>
                </div>
                
                <div id="salePrediction" style="margin-bottom: 1.5rem; padding: 1rem; background: var(--bg-secondary); border-radius: 0.5rem; border: 1px solid var(--color-gray-200);">
                    <h3 style="margin: 0 0 0.5rem 0; color: var(--text-primary); font-size: 1rem;">Sale Prediction</h3>
                    <div id="predictionContent">Loading prediction...</div>
                </div>
                
                <div style="max-height: 300px; overflow-y: auto;">
                    <table style="width: 100%; border-collapse: collapse;">
                        <thead>
                            <tr style="border-bottom: 1px solid var(--color-gray-200);">
                                <th style="text-align: left; padding: 0.5rem; color: var(--text-primary);">Date</th>
                                <th style="text-align: left; padding: 0.5rem; color: var(--text-primary);">Price</th>
                                <th style="text-align: left; padding: 0.5rem; color: var(--text-primary);">Was</th>
                                <th style="text-align: left; padding: 0.5rem; color: var(--text-primary);">Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${history.map(record => `
                                <tr style="border-bottom: 1px solid var(--color-gray-100);">
                                    <td style="padding: 0.5rem; color: var(--text-primary);">${new Date(record.date_recorded).toLocaleDateString()}</td>
                                    <td style="padding: 0.5rem; color: var(--text-primary);">$${record.price}</td>
                                    <td style="padding: 0.5rem; color: var(--text-primary);">${record.was_price ? '$' + record.was_price : '-'}</td>
                                    <td style="padding: 0.5rem; color: var(--text-primary);">${record.on_sale ? 'ON SALE' : 'Regular'}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
        
        this.showModal();
        
        // Load sale prediction
        this.loadSalePrediction(productName, retailer);
        
        // Create price chart
        setTimeout(() => {
            const ctx = document.getElementById('priceChart').getContext('2d');
            
            // Get current CSS custom properties for theming
            const primaryColor = isDarkMode ? '#2d8f47' : '#1e7b32';
            const textColor = isDarkMode ? '#f0f6fc' : '#111827';
            const gridColor = isDarkMode ? '#374151' : '#e5e7eb';
            
            new Chart(ctx, {
                type: 'line',
                data: {
                    labels: history.map(record => new Date(record.date_recorded).toLocaleDateString()),
                    datasets: [{
                        label: 'Price ($)',
                        data: history.map(record => parseFloat(record.price)),
                        borderColor: primaryColor,
                        backgroundColor: isDarkMode ? 'rgba(45, 143, 71, 0.1)' : 'rgba(30, 123, 50, 0.1)',
                        tension: 0.1,
                        fill: true
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        intersect: false,
                        mode: 'index'
                    },
                    plugins: {
                        title: {
                            display: true,
                            text: `${productName} - Price Trend`,
                            color: textColor,
                            font: {
                                size: 16,
                                weight: 'bold'
                            }
                        },
                        legend: {
                            labels: {
                                color: textColor
                            }
                        }
                    },
                    scales: {
                        x: {
                            ticks: {
                                color: textColor,
                                maxRotation: 45,
                                maxTicksLimit: 8
                            },
                            grid: {
                                color: gridColor
                            }
                        },
                        y: {
                            beginAtZero: false,
                            ticks: {
                                color: textColor,
                                maxTicksLimit: 6,
                                callback: function(value) {
                                    return '$' + value.toFixed(2);
                                }
                            },
                            grid: {
                                color: gridColor
                            }
                        }
                    }
                }
            });
        }, 100);
    }
    
    async loadSalePrediction(productName, retailer) {
        try {
            const response = await fetch(`/sale-prediction/${encodeURIComponent(productName)}?retailer=${encodeURIComponent(retailer)}`);
            const data = await response.json();
            
            const predictionContent = document.getElementById('predictionContent');
            if (response.ok && data.prediction) {
                const pred = data.prediction;
                predictionContent.innerHTML = `
                    <div style="display: flex; align-items: center; gap: 1rem; flex-wrap: wrap;">
                        <div>
                            <strong style="color: var(--color-primary);">Next Sale Estimate:</strong> 
                            ${pred.estimated_next_sale || 'No prediction available'}
                        </div>
                        <div>
                            <strong style="color: var(--color-secondary);">Confidence:</strong> 
                            ${pred.confidence ? Math.round(pred.confidence * 100) + '%' : 'Low'}
                        </div>
                        <div>
                            <strong>Avg Sale Cycle:</strong> 
                            ${pred.average_sale_cycle || 'N/A'} days
                        </div>
                    </div>
                    ${pred.reasoning ? `<p style="margin-top: 0.5rem; font-size: 0.875rem; color: var(--text-secondary);">${pred.reasoning}</p>` : ''}
                `;
            } else {
                predictionContent.innerHTML = '<p style="color: var(--text-muted);">No prediction data available yet. More price history needed.</p>';
            }
        } catch (error) {
            console.error('Error loading sale prediction:', error);
            const predictionContent = document.getElementById('predictionContent');
            predictionContent.innerHTML = '<p style="color: var(--color-error);">Failed to load prediction</p>';
        }
    }

    async addToFavorites(productName, retailer) {
        if (!this.adminSessionToken) {
            this.showToast('Please login as admin first', 'warning');
            return;
        }
        
        try {
            const response = await fetch('/admin/favorites', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${this.adminSessionToken}`
                },
                body: JSON.stringify({ product_name: productName, retailer: retailer })
            });
            
            if (response.status === 401) {
                this.adminSessionToken = null;
                localStorage.removeItem('adminSessionToken');
                this.updateAdminUI(false);
                this.showToast('Admin session expired. Please log in again.', 'error');
                return;
            }
            
            const result = await response.json();
            
            if (result.success) {
                this.showToast(`Added "${productName}" to favorites`, 'success');
            } else {
                this.showToast(result.message || 'Failed to add to favorites', 'error');
            }
        } catch (error) {
            console.error('Error adding to favorites:', error);
            this.showToast('Error adding to favorites', 'error');
        }
    }

    async viewFavorites() {
        if (!this.adminSessionToken) {
            this.showToast('Please login as admin first', 'warning');
            return;
        }

        try {
            const response = await fetch('/admin/favorites', {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${this.adminSessionToken}`
                }
            });

            if (response.status === 401) {
                this.adminSessionToken = null;
                localStorage.removeItem('adminSessionToken');
                this.updateAdminUI(false);
                this.showToast('Admin session expired. Please log in again.', 'error');
                return;
            }

            const data = await response.json();
            
            if (response.ok && data.success) {
                this.showFavoritesModal(data.favorites);
            } else {
                this.showToast('Failed to load favorites', 'error');
            }
        } catch (error) {
            console.error('Error loading favorites:', error);
            this.showToast('Error loading favorites', 'error');
        }
    }

    showFavoritesModal(favorites) {
        const modal = document.getElementById('modalContent');
        modal.innerHTML = `
            <div style="padding: 2rem; max-width: 800px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem;">
                    <h2 style="margin: 0;">My Favorites (${favorites.length})</h2>
                    <button onclick="app.hideModal()" style="background: none; border: none; font-size: 1.5rem; cursor: pointer;">&times;</button>
                </div>
                
                <div style="max-height: 60vh; overflow-y: auto;">
                    ${favorites.length > 0 ? `
                        <div style="display: grid; gap: 0.75rem;">
                            ${favorites.map(fav => `
                                <div style="display: flex; justify-content: space-between; align-items: center; padding: 1rem; background: var(--bg-secondary); border-radius: 0.5rem; border: 1px solid var(--color-gray-200);">
                                    <div>
                                        <div style="font-weight: 500; color: var(--text-primary);">${fav.product_name}</div>
                                        <div style="font-size: 0.875rem; color: var(--text-secondary);">
                                            ${fav.retailer} • Added ${new Date(fav.created_at).toLocaleDateString()}
                                        </div>
                                    </div>
                                    <div style="display: flex; gap: 0.5rem;">
                                        <button onclick="app.showPriceHistory('${fav.product_name}', '${fav.retailer}')" 
                                                style="padding: 0.5rem; background: var(--color-primary); color: white; border: none; border-radius: 0.25rem; cursor: pointer;">
                                            History
                                        </button>
                                        <button onclick="app.removeFavorite(${fav.id})" 
                                                style="padding: 0.5rem; background: var(--color-error); color: white; border: none; border-radius: 0.25rem; cursor: pointer;">
                                            Remove
                                        </button>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    ` : `
                        <div style="text-align: center; padding: 2rem; color: var(--text-secondary);">
                            No favorites added yet. Add products to your favorites from the search results!
                        </div>
                    `}
                </div>
            </div>
        `;
        
        this.showModal();
    }

    async removeFavorite(favoriteId) {
        if (!confirm('Remove this product from your favorites?')) {
            return;
        }

        try {
            const response = await this.makeAuthenticatedRequest(`/admin/favorites/${favoriteId}`, {
                method: 'DELETE'
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showToast('Removed from favorites', 'success');
                this.viewFavorites(); // Refresh the modal
            } else {
                this.showToast('Failed to remove favorite', 'error');
            }
        } catch (error) {
            console.error('Error removing favorite:', error);
            this.showToast('Error removing favorite', 'error');
        }
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