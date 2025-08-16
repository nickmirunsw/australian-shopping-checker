// Modern Shopping List App JavaScript
class ModernShoppingApp {
    constructor() {
        this.items = [];
        this.results = null;
        this.adminSessionToken = localStorage.getItem('adminSessionToken');
        this.theme = localStorage.getItem('theme') || 'light';
        this.modalStack = []; // Track modal history for proper navigation
        this.isClosingModal = false; // Prevent rapid modal close/open cycles
        this.statsRefreshInterval = null; // Auto-refresh stats timer
        
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
        // Prevent duplicate event listeners
        if (this.eventListenersSetup) return;
        this.eventListenersSetup = true;
        
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

        document.getElementById('viewFavoritesBtn')?.addEventListener('click', () => {
            this.viewFavorites();
        });

        document.getElementById('quickUpdateBtn')?.addEventListener('click', () => {
            this.quickUpdate();
        });

        document.getElementById('forceUpdateBtn')?.addEventListener('click', () => {
            this.forceUpdate();
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
            this.results = null; // Clear stored results
            this.updateItemsList();
            this.updateItemCount();
            this.updateCheckButton();
            this.showEmptyState(); // This will hide results and show empty state
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
        
        // Handle case where no match found (check both bestMatch and alternatives)
        if (!result.bestMatch && (!result.alternatives || result.alternatives.length === 0)) {
            card.innerHTML = `
                <div class="product-header" style="background: linear-gradient(135deg, var(--color-gray-500), var(--color-gray-600));">
                    <div class="product-name">${this.capitalizeFirst(result.input)}</div>
                    <div class="product-summary">
                        <span>No matches found</span>
                        <span style="font-size: 0.8rem; opacity: 0.8;">Try a different search term</span>
                    </div>
                </div>
                <div class="product-body">
                    <div class="empty-alternatives">
                        <i data-lucide="search-x" style="width: 48px; height: 48px; color: var(--color-gray-400); margin-bottom: 1rem;"></i>
                        <p style="color: var(--text-secondary); text-align: center; margin: 0;">
                            Sorry, we couldn't find "${result.input}" at ${result.retailer || 'Woolworths'}. 
                            Try searching for a more generic term like "milk" instead of "Dairy Farmers milk 2L".
                        </p>
                    </div>
                </div>
            `;
            return card;
        }
        
        // Create best match object from the result data
        const bestMatch = result.bestMatch ? {
            name: result.bestMatch,
            price: result.price,
            was: result.was,
            onSale: result.onSale,
            promoText: result.promoText,
            url: result.url,
            inStock: result.inStock,
            retailer: result.retailer
        } : (result.alternatives && result.alternatives.length > 0 ? result.alternatives[0] : null);
        
        if (!bestMatch) {
            // This shouldn't happen but let's handle it gracefully
            return this.createProductCard({...result, bestMatch: null, alternatives: []});
        }
        
        const onSaleCount = (result.alternatives ? result.alternatives.filter(alt => alt.onSale).length : 0) + (result.onSale ? 1 : 0);
        
        card.innerHTML = `
            <div class="product-header">
                <div class="product-name">${this.capitalizeFirst(result.input)}</div>
                <div class="product-summary">
                    <span>Best: ${bestMatch.display_name || bestMatch.name}</span>
                    <span>$${bestMatch.price}</span>
                    ${onSaleCount > 0 ? `<span>${onSaleCount} on sale</span>` : ''}
                    <button onclick="app.showPriceHistory('${bestMatch.name}', '${bestMatch.retailer || 'woolworths'}', event)" 
                            ontouchstart="this.style.background='var(--color-primary)'" 
                            ontouchend="this.style.background=''"
                            class="btn btn-ghost btn-sm mobile-friendly" title="Price History">
                        <i data-lucide="trending-up"></i>
                    </button>
                </div>
            </div>
            <div class="product-body">
                <div class="alternatives-grid">
                    ${(result.alternatives || []).map(alt => this.createAlternativeItem(alt, result.input, !!this.adminSessionToken)).join('')}
                </div>
            </div>
        `;
        
        return card;
    }

    createAlternativeItem(alt, inputName, isAdmin = false) {
        // Use display_name if available, fallback to name
        const displayName = alt.display_name || alt.name;
        const internalName = alt.name; // Keep internal name for database operations
        
        return `
            <div class="alternative-item">
                <div class="alternative-info">
                    <div class="alternative-name">${displayName}</div>
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
                        <button onclick="app.showPriceHistory('${internalName}', '${alt.retailer || 'woolworths'}', event)" 
                                ontouchstart="this.style.background='var(--color-primary)'" 
                                ontouchend="this.style.background=''"
                                class="btn btn-ghost btn-sm mobile-friendly" title="Price History">
                            <i data-lucide="trending-up"></i>
                        </button>
                        ${isAdmin ? `
                            <button onclick="app.addToFavorites('${internalName}', '${alt.retailer || 'woolworths'}', this)" 
                                    ontouchstart="this.style.background='var(--color-secondary)'" 
                                    ontouchend="this.style.background=''"
                                    class="btn btn-ghost btn-sm mobile-friendly" title="Add to Favorites">
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
            
            // Start auto-refreshing stats every 10 seconds when admin is logged in
            if (!this.statsRefreshInterval) {
                this.statsRefreshInterval = setInterval(() => {
                    this.refreshDatabaseStats();
                }, 10000); // 10 seconds
                console.log('✅ Started auto-refresh stats every 10 seconds');
            }
        } else {
            loginForm.classList.remove('hidden');
            controls.classList.add('hidden');
            
            // Stop auto-refreshing when not logged in
            if (this.statsRefreshInterval) {
                clearInterval(this.statsRefreshInterval);
                this.statsRefreshInterval = null;
                console.log('🛑 Stopped auto-refresh stats');
            }
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
            // Use authenticated endpoint if admin is logged in, otherwise use public endpoint
            let response;
            if (this.adminSessionToken) {
                response = await this.makeAuthenticatedRequest('/admin/database-stats');
            } else {
                response = await fetch('/database/stats');
            }
            
            const data = await response.json();
            
            if (response.ok) {
                // Handle different response formats from admin vs public endpoints
                const stats = data.stats || data;
                this.updateDatabaseStats(stats);
            }
        } catch (error) {
            console.error('Failed to refresh database stats:', error);
            // Fallback to public endpoint if authenticated fails
            try {
                const fallbackResponse = await fetch('/database/stats');
                const fallbackData = await fallbackResponse.json();
                if (fallbackResponse.ok) {
                    const stats = fallbackData.stats || fallbackData;
                    this.updateDatabaseStats(stats);
                }
            } catch (fallbackError) {
                console.error('Fallback stats refresh also failed:', fallbackError);
            }
        }
    }

    updateDatabaseStats(stats) {
        const statsContainer = document.getElementById('databaseStats');
        if (!statsContainer) return;
        
        const priceHistory = stats.price_history || {};
        
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
                <div class="stat-value" style="color: ${(priceHistory.todays_updates || 0) > 0 ? 'var(--color-success)' : 'var(--color-warning)'};">${priceHistory.todays_updates || 0}</div>
                <div class="stat-label">Updated Today</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${priceHistory.on_sale_count || 0}</div>
                <div class="stat-label">Items on Sale</div>
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
                    <button id="closeModalBtn" style="background: none; border: none; font-size: 1.5rem; cursor: pointer; color: var(--text-primary);">&times;</button>
                </div>
                
                <!-- Search Bar -->
                <div style="margin-bottom: 1.5rem;">
                    <input 
                        type="text" 
                        id="productSearch" 
                        placeholder="Search tracked products..." 
                        class="input"
                        style="width: 100%; padding: 0.75rem; border: 1.5px solid var(--color-gray-300); border-radius: 0.5rem; font-size: 0.9rem;"
                    >
                </div>
                
                <div id="productsContainer" style="max-height: 60vh; overflow-y: auto;"></div>
            </div>
        `;
        
        // Show modal and set up event listeners
        this.showModal('tracked-products', { products });
        this.renderProducts(products);
        
        // Set up modal-specific event listeners
        setTimeout(() => {
            // Close button - remove any existing listeners first
            const closeBtn = document.getElementById('closeModalBtn');
            if (closeBtn) {
                // Remove any existing listeners by cloning the node
                const newCloseBtn = closeBtn.cloneNode(true);
                closeBtn.parentNode.replaceChild(newCloseBtn, closeBtn);
                
                // Make the close button VERY obvious and impossible to miss
                newCloseBtn.style.background = '#e74c3c';
                newCloseBtn.style.color = 'white';
                newCloseBtn.style.padding = '15px 25px';
                newCloseBtn.style.fontSize = '18px';
                newCloseBtn.style.fontWeight = 'bold';
                newCloseBtn.style.border = '3px solid #c0392b';
                newCloseBtn.style.borderRadius = '8px';
                newCloseBtn.style.cursor = 'pointer';
                newCloseBtn.style.boxShadow = '0 4px 8px rgba(0,0,0,0.3)';
                newCloseBtn.textContent = 'CLOSE';
                
                // Add multiple event listeners for maximum reliability
                newCloseBtn.addEventListener('click', (e) => {
                    console.log('🔴 CLOSE BUTTON CLICKED!');
                    e.preventDefault();
                    e.stopPropagation();
                    e.stopImmediatePropagation();
                    
                    // Disable the button temporarily to prevent double clicks
                    newCloseBtn.disabled = true;
                    newCloseBtn.textContent = 'CLOSING...';
                    
                    this.hideModal();
                    this.showToast('✅ Modal closed successfully!', 'success');
                    
                    // Re-enable after delay
                    setTimeout(() => {
                        newCloseBtn.disabled = false;
                        newCloseBtn.textContent = 'CLOSE';
                    }, 1000);
                });
                
                // Add backup listeners for touch devices
                newCloseBtn.addEventListener('touchstart', (e) => {
                    console.log('🔴 CLOSE BUTTON TOUCHED!');
                    e.preventDefault();
                    this.hideModal();
                    this.showToast('✅ Modal closed (touch)!', 'success');
                });
                
                // Add backup listener for keyboard
                newCloseBtn.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                        console.log('🔴 CLOSE BUTTON KEYBOARD!');
                        e.preventDefault();
                        this.hideModal();
                        this.showToast('✅ Modal closed (keyboard)!', 'success');
                    }
                });
                
                console.log('✅ Enhanced close button set up successfully');
            } else {
                console.error('❌ Close button not found!');
                // Create emergency close button if none exists
                const emergencyClose = document.createElement('button');
                emergencyClose.textContent = '✕ EMERGENCY CLOSE ✕';
                emergencyClose.style.position = 'fixed';
                emergencyClose.style.top = '20px';
                emergencyClose.style.right = '20px';
                emergencyClose.style.background = '#e74c3c';
                emergencyClose.style.color = 'white';
                emergencyClose.style.padding = '15px';
                emergencyClose.style.fontSize = '16px';
                emergencyClose.style.border = 'none';
                emergencyClose.style.borderRadius = '8px';
                emergencyClose.style.zIndex = '10000';
                emergencyClose.addEventListener('click', () => {
                    this.hideModal();
                    this.showToast('Emergency close activated!', 'success');
                });
                document.body.appendChild(emergencyClose);
                
                // Remove emergency button after 30 seconds
                setTimeout(() => {
                    if (document.body.contains(emergencyClose)) {
                        document.body.removeChild(emergencyClose);
                    }
                }, 30000);
            }
            
            // Search input
            const searchInput = document.getElementById('productSearch');
            if (searchInput) {
                searchInput.addEventListener('input', (e) => this.filterProducts(e.target.value));
                searchInput.focus();
            }
        }, 50);
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
                                    <button onclick="app.addToFavorites('${product.product_name}', '${product.retailer}', this)" 
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


    showProgressModal(title, status) {
        console.log('📋 Showing progress modal:', title, status);
        
        // Make sure modal elements exist
        const progressOverlay = document.getElementById('progressOverlay');
        if (!progressOverlay) {
            console.error('❌ Progress overlay not found!');
            alert('Progress modal not found! Check browser console.');
            return;
        }
        
        document.getElementById('progressTitle').textContent = title;
        document.getElementById('progressStatus').textContent = status;
        document.getElementById('progressText').textContent = '0%';
        document.getElementById('progressBar').style.width = '0%';
        document.getElementById('progressLogs').innerHTML = '';
        document.getElementById('progressSummary').classList.add('hidden');
        document.getElementById('progressCloseBtn').style.display = 'none';
        
        // Force modal to be visible with high z-index
        progressOverlay.style.zIndex = '9999';
        progressOverlay.style.display = 'flex';
        progressOverlay.classList.remove('hidden');
        
        // Add a bright border for testing
        const modal = document.getElementById('progressModal');
        modal.style.border = '3px solid var(--color-primary)';
        modal.style.boxShadow = '0 0 20px rgba(30, 123, 50, 0.3)';
        
        console.log('✅ Progress modal should be visible now');
        this.addProgressLog('Starting update process...', 'info');
    }

    updateProgress(percent, status, logMessage = null, logType = 'info') {
        document.getElementById('progressText').textContent = `${Math.round(percent)}%`;
        document.getElementById('progressBar').style.width = `${percent}%`;
        document.getElementById('progressStatus').textContent = status;
        
        if (logMessage) {
            this.addProgressLog(logMessage, logType);
        }
    }

    addProgressLog(message, type = 'info') {
        const logsContainer = document.getElementById('progressLogs');
        const logEntry = document.createElement('div');
        logEntry.className = `progress-log-entry ${type}`;
        
        const timestamp = new Date().toLocaleTimeString();
        logEntry.innerHTML = `<span style="color: var(--text-muted);">[${timestamp}]</span> ${message}`;
        
        logsContainer.appendChild(logEntry);
        logsContainer.scrollTop = logsContainer.scrollHeight;
    }

    updateProgressComplete(stats, updateType) {
        this.updateProgress(100, 'Update completed!', `${updateType} update finished`, 'success');
        
        // Show summary
        const summaryContainer = document.getElementById('progressSummary');
        summaryContainer.innerHTML = `
            <h4>Update Summary</h4>
            <div class="progress-stats">
                <div class="progress-stat">
                    <div class="progress-stat-value">${stats.products_processed}</div>
                    <div class="progress-stat-label">Processed</div>
                </div>
                <div class="progress-stat">
                    <div class="progress-stat-value">${stats.successful_updates}</div>
                    <div class="progress-stat-label">Successful</div>
                </div>
                <div class="progress-stat">
                    <div class="progress-stat-value">${stats.failed_updates}</div>
                    <div class="progress-stat-label">Failed</div>
                </div>
                <div class="progress-stat">
                    <div class="progress-stat-value">${stats.success_rate}%</div>
                    <div class="progress-stat-label">Success Rate</div>
                </div>
            </div>
            <p><strong>Batches:</strong> ${stats.batches_processed} batches of ${stats.batch_size} products each</p>
            <p><strong>New Records:</strong> ${stats.new_records} price records added to database</p>
            ${stats.failed_updates > 0 ? `<p style="color: var(--color-warning);"><strong>Note:</strong> ${stats.failed_updates} products could not be updated (search/matching issues)</p>` : ''}
        `;
        summaryContainer.classList.remove('hidden');
        
        // Show close button
        document.getElementById('progressCloseBtn').style.display = 'block';
        document.getElementById('progressCloseBtn').onclick = () => this.hideProgressModal();
        
        this.showToast(`Update completed: ${stats.successful_updates}/${stats.products_processed} products updated`, 'success');
        
        // Force refresh database stats after successful update
        setTimeout(() => {
            this.refreshDatabaseStats();
        }, 1000);
    }

    updateProgressError(errorMessage) {
        this.updateProgress(0, 'Update failed', errorMessage, 'error');
        document.getElementById('progressCloseBtn').style.display = 'block';
        document.getElementById('progressCloseBtn').onclick = () => this.hideProgressModal();
        this.showToast('Update failed', 'error');
    }

    updateProgressCircuitBreaker(result, updateType) {
        const stats = result.stats;
        this.updateProgress(50, 'Update partially completed (Circuit breaker triggered)', 'API rate limiting detected - update stopped for safety', 'warning');
        
        // Show partial results summary
        const summaryContainer = document.getElementById('progressSummary');
        summaryContainer.innerHTML = `
            <h4>⚠️ Update Partially Completed</h4>
            <div class="progress-stats">
                <div class="progress-stat">
                    <div class="progress-stat-value">${stats.products_processed}</div>
                    <div class="progress-stat-label">Processed</div>
                </div>
                <div class="progress-stat">
                    <div class="progress-stat-value">${stats.successful_updates}</div>
                    <div class="progress-stat-label">Successful</div>
                </div>
                <div class="progress-stat">
                    <div class="progress-stat-value">${stats.failed_updates}</div>
                    <div class="progress-stat-label">Failed</div>
                </div>
                <div class="progress-stat">
                    <div class="progress-stat-value">${stats.success_rate}%</div>
                    <div class="progress-stat-label">Success Rate</div>
                </div>
            </div>
            <div style="margin-top: 1rem; padding: 1rem; background: var(--color-warning); color: white; border-radius: 0.5rem;">
                <h5 style="margin: 0 0 0.5rem 0;">🛡️ Circuit Breaker Activated</h5>
                <p style="margin: 0; font-size: 0.9rem;">
                    The update was stopped after detecting API rate limiting or service issues. 
                    This protects your account from being blocked. Try again later with Quick Mode, 
                    or contact support if the issue persists.
                </p>
            </div>
            <p><strong>Recommendation:</strong> Use Quick Mode (100 products max) for now, or wait 30 minutes before trying a full update.</p>
        `;
        summaryContainer.classList.remove('hidden');
        
        // Show close button
        document.getElementById('progressCloseBtn').style.display = 'block';
        document.getElementById('progressCloseBtn').onclick = () => this.hideProgressModal();
        
        this.showToast(`Update stopped: API rate limiting detected after ${stats.products_processed} products`, 'warning');
    }

    hideProgressModal() {
        document.getElementById('progressOverlay').classList.add('hidden');
    }


    showModal(modalType = 'generic', modalData = null) {
        // Store previous modal state if any
        const currentModal = document.getElementById('modalContent').innerHTML;
        if (currentModal.trim() && this.modalStack.length === 0) {
            this.modalStack.push({
                type: 'previous',
                content: currentModal
            });
        }
        
        // Add current modal to stack
        this.modalStack.push({
            type: modalType,
            data: modalData
        });
        
        document.getElementById('modalOverlay').classList.remove('hidden');
    }

    hideModal() {
        console.log('🔴 hideModal() called');
        
        // Prevent multiple rapid calls
        if (this.isClosingModal) {
            console.log('🔴 Modal already closing, ignoring');
            return;
        }
        
        this.isClosingModal = true;
        
        // Add a small delay to prevent event conflicts
        setTimeout(() => {
            const modalOverlay = document.getElementById('modalOverlay');
            if (modalOverlay) {
                modalOverlay.classList.add('hidden');
                console.log('🔴 Modal hidden successfully');
            }
            
            this.modalStack = []; // Clear stack completely
            this.isClosingModal = false;
            
            console.log('🔴 Modal close complete');
        }, 50);
    }

    async showPriceHistory(productName, retailer, event = null) {
        try {
            // Prevent default behavior and stop propagation for mobile
            if (event) {
                event.preventDefault();
                event.stopPropagation();
            }
            
            // Add visual feedback for mobile users
            const button = event?.target?.closest('button');
            if (button) {
                button.style.background = 'var(--color-primary)';
                button.style.transform = 'scale(0.95)';
                setTimeout(() => {
                    button.style.background = '';
                    button.style.transform = '';
                }, 200);
            }
            
            this.showToast('Loading price history...', 'info');
            
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
        // Use proper modal stack management
        this.showModal('price-history', { history, productName, retailer });
        
        const modal = document.getElementById('modalContent');
        const isDarkMode = document.documentElement.getAttribute('data-theme') === 'dark';
        
        modal.innerHTML = `
            <div style="padding: 2rem; max-width: 1000px; width: 90vw;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem;">
                    <h2 style="margin: 0; color: var(--text-primary);">Price History: ${productName}</h2>
                    <button id="closePriceHistoryBtn" style="background: none; border: none; font-size: 1.5rem; cursor: pointer; color: var(--text-primary);">&times;</button>
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
        
        this.showModal('price-history', { productName, retailer, history });
        
        // Set up close button event listener
        setTimeout(() => {
            const closeBtn = document.getElementById('closePriceHistoryBtn');
            if (closeBtn) {
                closeBtn.addEventListener('click', () => this.hideModal());
            }
        }, 50);
        
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

    async addToFavorites(productName, retailer, buttonElement = null) {
        if (!this.adminSessionToken) {
            this.showToast('Please login as admin first', 'warning');
            return;
        }
        
        // Find the button element if not provided
        if (!buttonElement) {
            buttonElement = event.target.closest('button');
        }
        
        // Prevent double-clicking/tapping
        if (buttonElement && buttonElement.disabled) {
            return;
        }
        
        // Immediate visual feedback for mobile responsiveness
        const originalHTML = buttonElement?.innerHTML || '';
        const originalBackground = buttonElement?.style.background || '';
        const originalColor = buttonElement?.style.color || '';
        
        if (buttonElement) {
            // Immediate feedback
            buttonElement.innerHTML = '<i data-lucide="loader-2" style="animation: spin 1s linear infinite;"></i>';
            buttonElement.style.background = 'var(--color-warning)';
            buttonElement.style.color = 'white';
            buttonElement.disabled = true;
            lucide.createIcons();
            
            // Add haptic feedback for mobile
            if (navigator.vibrate) {
                navigator.vibrate(50);
            }
        }
        
        // Show immediate toast for better UX
        this.showToast('Adding to favorites...', 'info');
        
        try {
            // Add timeout for mobile networks
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout
            
            const response = await fetch('/admin/favorites', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${this.adminSessionToken}`
                },
                body: JSON.stringify({ product_name: productName, retailer: retailer }),
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);
            
            if (response.status === 401) {
                this.adminSessionToken = null;
                localStorage.removeItem('adminSessionToken');
                this.updateAdminUI(false);
                this.showToast('Admin session expired. Please log in again.', 'error');
                return;
            }
            
            const result = await response.json();
            
            if (result.success) {
                // Visual feedback - success state
                if (buttonElement) {
                    buttonElement.innerHTML = '<i data-lucide="heart" style="fill: currentColor;"></i>';
                    buttonElement.style.background = 'var(--color-error)'; // Red for favorited
                    buttonElement.style.color = 'white';
                    buttonElement.title = 'Added to favorites';
                    lucide.createIcons();
                }
                this.showToast(`Added "${productName}" to favorites`, 'success');
            } else {
                // Visual feedback - error state
                if (buttonElement) {
                    buttonElement.innerHTML = '<i data-lucide="heart"></i>';
                    buttonElement.style.background = 'var(--color-gray-400)';
                    buttonElement.disabled = false;
                }
                this.showToast(result.message || 'Failed to add to favorites', 'error');
            }
        } catch (error) {
            console.error('Error adding to favorites:', error);
            
            // Better error handling for different scenarios
            let errorMessage = 'Error adding to favorites';
            if (error.name === 'AbortError') {
                errorMessage = 'Request timed out - please try again';
            } else if (!navigator.onLine) {
                errorMessage = 'No internet connection';
            }
            
            // Visual feedback - error state with recovery option
            if (buttonElement) {
                buttonElement.innerHTML = '<i data-lucide="heart"></i>';
                buttonElement.style.background = originalBackground;
                buttonElement.style.color = originalColor;
                buttonElement.disabled = false;
                lucide.createIcons();
                
                // Add retry functionality for mobile users
                buttonElement.onclick = () => {
                    this.addToFavorites(productName, retailer, buttonElement);
                };
            }
            
            this.showToast(errorMessage, 'error');
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
                    <button id="closeFavoritesBtn" style="background: none; border: none; font-size: 1.5rem; cursor: pointer;">&times;</button>
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
        
        this.showModal('favorites', favorites);
        
        // Set up close button event listener
        setTimeout(() => {
            const closeBtn = document.getElementById('closeFavoritesBtn');
            if (closeBtn) {
                closeBtn.addEventListener('click', () => this.hideModal());
            }
        }, 50);
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

    goToHomepage() {
        // Navigate to homepage without logging out admin
        this.closeAdminPanel();
        this.hideModal();
        
        // Clear any active search results but keep admin session
        this.results = null;
        this.updateResultsDisplay();
        
        // Reset to empty state without reloading page
        document.getElementById('resultsContainer').classList.add('hidden');
        document.getElementById('emptyState').classList.remove('hidden');
        document.getElementById('resultsSummary').textContent = '';
    }

    async quickUpdate() {
        // Quick update: 10 random products missing today's price data
        const confirmed = confirm('⚡ Quick Update\n\nThis will update 10 random products missing today\'s price data.\n\nPerfect for quick price checks without overwhelming the API.\n\nContinue?');
        if (!confirmed) return;
        
        try {
            // Show progress modal with NO close button initially
            this.showProgressModal('Quick Update (10)', 'Starting update...');
            document.getElementById('progressCloseBtn').style.display = 'none';
            document.getElementById('progressCloseBtn').textContent = 'Please Wait...';
            
            // Simulate progress steps
            this.updateProgress(10, '⚡ Starting Quick Update...');
            this.addProgressLog('⚡ Starting Quick Update...', 'info');
            
            this.updateProgress(25, 'Selecting 10 products missing today\'s price data...');
            this.addProgressLog('🔍 Selecting 10 products missing today\'s price data...', 'info');
            
            this.updateProgress(50, 'Sending request to server...');
            this.addProgressLog('📡 Sending request to server...', 'info');
            
            const response = await this.makeAuthenticatedRequest('/quick-update', {
                method: 'POST'
            });
            
            this.updateProgress(75, 'Processing response...');
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to start quick update');
            }
            
            const result = await response.json();
            
            this.updateProgress(100, 'Complete!');
            
            // Clear existing logs and show final results
            document.getElementById('progressLogs').innerHTML = '';
            
            if (result.success) {
                // Show BIG SUCCESS message
                this.addProgressLog(`🎉 SUCCESS! ${result.message}`, 'success');
                this.addProgressLog('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', 'info');
                
                // Show detailed stats
                const stats = result.stats;
                if (stats.products_processed > 0) {
                    this.addProgressLog(`📊 PRODUCTS PROCESSED: ${stats.products_processed}`, 'info');
                    this.addProgressLog(`✅ SUCCESSFUL UPDATES: ${stats.successful_updates}`, 'success');
                    this.addProgressLog(`❌ FAILED UPDATES: ${stats.failed_updates}`, stats.failed_updates > 0 ? 'warning' : 'info');
                    this.addProgressLog(`📈 SUCCESS RATE: ${stats.success_rate}%`, 'info');
                    
                    if (stats.new_records > 0) {
                        this.addProgressLog(`💾 NEW RECORDS ADDED: ${stats.new_records}`, 'success');
                    }
                } else {
                    this.addProgressLog(`ℹ️ NO UPDATES NEEDED - All products have today's data!`, 'info');
                }
                
                this.addProgressLog('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', 'info');
                this.addProgressLog(`🎯 Update type: ${stats.update_type}`, 'info');
                this.addProgressLog(`📅 Data stored in PostgreSQL price_history table`, 'info');
                
                document.getElementById('progressTitle').textContent = '🎉 QUICK UPDATE SUCCESSFUL!';
                document.getElementById('progressCloseBtn').textContent = 'GOT IT! ✅';
            } else {
                // Show BIG FAILURE message
                this.addProgressLog(`💥 FAILED! ${result.message}`, 'error');
                this.addProgressLog('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', 'error');
                this.addProgressLog(`❌ The Quick Update did not complete successfully`, 'error');
                this.addProgressLog(`❌ Please try again or contact support`, 'error');
                
                document.getElementById('progressTitle').textContent = '💥 QUICK UPDATE FAILED!';
                document.getElementById('progressCloseBtn').textContent = 'GOT IT! ❌';
            }
            
            // Force user to acknowledge by showing prominent button
            const progressCloseBtn = document.getElementById('progressCloseBtn');
            progressCloseBtn.style.display = 'block';
            progressCloseBtn.style.background = '#e74c3c';
            progressCloseBtn.style.color = 'white';
            progressCloseBtn.style.padding = '12px 24px';
            progressCloseBtn.style.fontSize = '16px';
            progressCloseBtn.style.fontWeight = 'bold';
            
            // CRITICAL: Add click event listener to close the progress modal
            progressCloseBtn.onclick = () => {
                console.log('🔴 Progress modal GOT IT button clicked!');
                this.hideProgressModal();
                this.showToast('Quick Update results acknowledged!', 'success');
            };
            
            this.refreshDatabaseStats();
            
        } catch (error) {
            console.error('Quick update error:', error);
            
            // Clear logs and show error
            document.getElementById('progressLogs').innerHTML = '';
            this.updateProgress(100, 'Error occurred');
            
            this.addProgressLog(`💥 CRITICAL ERROR!`, 'error');
            this.addProgressLog('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', 'error');
            this.addProgressLog(`❌ Error: ${error.message}`, 'error');
            this.addProgressLog(`❌ The Quick Update could not complete`, 'error');
            this.addProgressLog(`❌ Please check your internet connection and try again`, 'error');
            
            document.getElementById('progressTitle').textContent = '💥 ERROR OCCURRED!';
            
            const errorCloseBtn = document.getElementById('progressCloseBtn');
            errorCloseBtn.style.display = 'block';
            errorCloseBtn.textContent = 'GOT IT! ❌';
            errorCloseBtn.style.background = '#e74c3c';
            errorCloseBtn.style.color = 'white';
            errorCloseBtn.style.padding = '12px 24px';
            errorCloseBtn.style.fontSize = '16px';
            errorCloseBtn.style.fontWeight = 'bold';
            
            // CRITICAL: Add click event listener for error case too
            errorCloseBtn.onclick = () => {
                console.log('🔴 Progress modal ERROR button clicked!');
                this.hideProgressModal();
                this.showToast('Error acknowledged!', 'error');
            };
        }
    }

    async forceUpdate() {
        // Force update: Update 5 random products even if they have today's data (for testing)
        const confirmed = confirm('🔥 Force Update Today\n\nThis will FORCE update 5 random products even if they already have today\'s price data.\n\nPerfect for testing the update logic immediately!\n\nContinue?');
        if (!confirmed) return;
        
        try {
            // Show progress modal with NO close button initially
            this.showProgressModal('Force Update (5)', 'Starting force update...');
            document.getElementById('progressCloseBtn').style.display = 'none';
            document.getElementById('progressCloseBtn').textContent = 'Please Wait...';
            
            // Simulate progress steps
            this.updateProgress(10, '🔥 Starting Force Update...');
            this.addProgressLog('🔥 Starting Force Update...', 'info');
            
            this.updateProgress(25, 'Selecting 5 random products for force update...');
            this.addProgressLog('🎯 Selecting 5 random products (ignoring today\'s data)...', 'info');
            
            this.updateProgress(50, 'Sending request to server...');
            this.addProgressLog('📡 Sending force update request...', 'info');
            
            const response = await this.makeAuthenticatedRequest('/force-update', {
                method: 'POST'
            });
            
            this.updateProgress(75, 'Processing response...');
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to start force update');
            }
            
            const result = await response.json();
            
            this.updateProgress(100, 'Complete!');
            
            // Clear existing logs and show final results
            document.getElementById('progressLogs').innerHTML = '';
            
            if (result.success) {
                // Show BIG SUCCESS message
                this.addProgressLog(`🎉 SUCCESS! ${result.message}`, 'success');
                this.addProgressLog('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', 'info');
                
                // Show detailed stats
                const stats = result.stats;
                this.addProgressLog(`📊 PRODUCTS PROCESSED: ${stats.products_processed}`, 'info');
                this.addProgressLog(`✅ SUCCESSFUL UPDATES: ${stats.successful_updates}`, 'success');
                this.addProgressLog(`❌ FAILED UPDATES: ${stats.failed_updates}`, stats.failed_updates > 0 ? 'warning' : 'info');
                this.addProgressLog(`📈 SUCCESS RATE: ${stats.success_rate}%`, 'info');
                
                if (stats.new_records > 0) {
                    this.addProgressLog(`💾 NEW RECORDS ADDED: ${stats.new_records}`, 'success');
                }
                
                this.addProgressLog('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', 'info');
                this.addProgressLog(`🎯 Update type: FORCE UPDATE (for testing)`, 'info');
                this.addProgressLog(`📅 Data stored in PostgreSQL price_history table`, 'info');
                
                document.getElementById('progressTitle').textContent = '🎉 FORCE UPDATE SUCCESSFUL!';
                document.getElementById('progressCloseBtn').textContent = 'GOT IT! ✅';
            } else {
                // Show BIG FAILURE message
                this.addProgressLog(`💥 FAILED! ${result.message}`, 'error');
                this.addProgressLog('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', 'error');
                this.addProgressLog(`❌ The Force Update did not complete successfully`, 'error');
                this.addProgressLog(`❌ Please try again or contact support`, 'error');
                
                document.getElementById('progressTitle').textContent = '💥 FORCE UPDATE FAILED!';
                document.getElementById('progressCloseBtn').textContent = 'GOT IT! ❌';
            }
            
            // Force user to acknowledge by showing prominent button
            const progressCloseBtn = document.getElementById('progressCloseBtn');
            progressCloseBtn.style.display = 'block';
            progressCloseBtn.style.background = '#f39c12';
            progressCloseBtn.style.color = 'white';
            progressCloseBtn.style.padding = '12px 24px';
            progressCloseBtn.style.fontSize = '16px';
            progressCloseBtn.style.fontWeight = 'bold';
            
            // CRITICAL: Add click event listener to close the progress modal
            progressCloseBtn.onclick = () => {
                console.log('🔴 Force update GOT IT button clicked!');
                this.hideProgressModal();
                this.showToast('Force Update results acknowledged!', 'success');
            };
            
            this.refreshDatabaseStats();
            
        } catch (error) {
            console.error('Force update error:', error);
            
            // Clear logs and show error
            document.getElementById('progressLogs').innerHTML = '';
            this.updateProgress(100, 'Error occurred');
            
            this.addProgressLog(`💥 CRITICAL ERROR!`, 'error');
            this.addProgressLog('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', 'error');
            this.addProgressLog(`❌ Error: ${error.message}`, 'error');
            this.addProgressLog(`❌ The Force Update could not complete`, 'error');
            this.addProgressLog(`❌ Please check your internet connection and try again`, 'error');
            
            document.getElementById('progressTitle').textContent = '💥 ERROR OCCURRED!';
            
            const errorCloseBtn = document.getElementById('progressCloseBtn');
            errorCloseBtn.style.display = 'block';
            errorCloseBtn.textContent = 'GOT IT! ❌';
            errorCloseBtn.style.background = '#e74c3c';
            errorCloseBtn.style.color = 'white';
            errorCloseBtn.style.padding = '12px 24px';
            errorCloseBtn.style.fontSize = '16px';
            errorCloseBtn.style.fontWeight = 'bold';
            
            // CRITICAL: Add click event listener for error case too
            errorCloseBtn.onclick = () => {
                console.log('🔴 Force update ERROR button clicked!');
                this.hideProgressModal();
                this.showToast('Force update error acknowledged!', 'error');
            };
        }
    }
}

// Initialize the app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.app = new ModernShoppingApp();
});