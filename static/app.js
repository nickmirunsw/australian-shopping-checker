// Shopping List Price Checker JavaScript

class ShoppingListApp {
    constructor() {
        this.items = [];
        this.results = null;
        this.previousModal = null; // Track which modal was open before
        this.adminSessionToken = localStorage.getItem('adminSessionToken'); // Admin authentication
        this.initializeEventListeners();
        this.initializeKeyboardShortcuts();
        this.refreshDatabaseStats(); // Load initial database stats
        this.checkAdminStatus(); // Check if admin is logged in
    }

    initializeEventListeners() {
        // Add item button
        document.getElementById('addItemBtn').addEventListener('click', () => {
            this.addItem();
        });

        // Enter key on new item input
        document.getElementById('newItem').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.addItem();
            }
        });

        // Quick add buttons
        document.querySelectorAll('.quick-add').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const item = e.target.getAttribute('data-item');
                this.addItemToList(item);
            });
        });

        // Check prices button
        document.getElementById('checkPricesBtn').addEventListener('click', () => {
            this.checkPrices();
        });

        // Clear list button
        document.getElementById('clearListBtn').addEventListener('click', () => {
            this.clearList();
        });

        // Postcode validation
        document.getElementById('postcode').addEventListener('input', (e) => {
            this.validatePostcode(e.target);
        });

        // Database management buttons
        document.getElementById('refreshStatsBtn').addEventListener('click', () => {
            this.refreshDatabaseStats();
        });

        document.getElementById('clearDatabaseBtn').addEventListener('click', () => {
            this.clearDatabase();
        });

        document.getElementById('generateDummyBtn').addEventListener('click', () => {
            this.generateDummyData();
        });

        document.getElementById('dailyUpdateBtn').addEventListener('click', () => {
            this.runDailyUpdate();
        });

        document.getElementById('viewProductsBtn').addEventListener('click', () => {
            this.viewTrackedProducts();
        });

        // Admin authentication
        document.getElementById('adminToggleBtn').addEventListener('click', () => {
            this.toggleAdminLogin();
        });

        document.getElementById('adminLoginForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.performAdminLogin();
        });

        // Add modal event listeners
        this.initializeModalEventListeners();
    }

    initializeKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + Enter to check prices
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && this.items.length > 0) {
                e.preventDefault();
                this.checkPrices();
            }
            
            // Ctrl/Cmd + Delete to clear list
            if ((e.ctrlKey || e.metaKey) && e.key === 'Delete') {
                e.preventDefault();
                this.clearList();
            }

            // Escape to clear current input
            if (e.key === 'Escape') {
                const input = document.getElementById('newItem');
                input.value = '';
                input.blur();
            }
        });

        // Show keyboard shortcuts hint
        this.showKeyboardHints();
    }

    initializeModalEventListeners() {
        // Listen for when price history modal is hidden
        const priceHistoryModal = document.getElementById('priceHistoryModal');
        priceHistoryModal.addEventListener('hidden.bs.modal', () => {
            // If we came from the tracked products modal, reopen it
            if (this.previousModal === 'trackedProducts') {
                setTimeout(() => {
                    const trackedProductsModal = new bootstrap.Modal(document.getElementById('trackedProductsModal'));
                    trackedProductsModal.show();
                }, 300); // Small delay to ensure smooth transition
                this.previousModal = null; // Reset
            }
        });

        // Listen for when tracked products modal is hidden (to clear previous modal tracking)
        const trackedProductsModal = document.getElementById('trackedProductsModal');
        trackedProductsModal.addEventListener('hidden.bs.modal', () => {
            this.previousModal = null;
        });
    }

    showKeyboardHints() {
        const hints = document.createElement('div');
        hints.className = 'keyboard-hints';
        hints.innerHTML = `
            <div class="hints-content">
                <h6><i class="bi bi-keyboard"></i> Keyboard Shortcuts</h6>
                <div class="hint-item"><kbd>Ctrl/⌘ + Enter</kbd> Check Prices</div>
                <div class="hint-item"><kbd>Ctrl/⌘ + Del</kbd> Clear List</div>
                <div class="hint-item"><kbd>Esc</kbd> Clear Input</div>
            </div>
        `;

        // Add styles for hints
        if (!document.querySelector('.hints-styles')) {
            const styles = document.createElement('style');
            styles.className = 'hints-styles';
            styles.textContent = `
                .keyboard-hints {
                    position: fixed;
                    bottom: 20px;
                    left: 20px;
                    background: rgba(255, 255, 255, 0.95);
                    backdrop-filter: blur(10px);
                    padding: 12px 16px;
                    border-radius: 8px;
                    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
                    border-left: 4px solid var(--primary-color);
                    font-size: 0.8rem;
                    z-index: 1000;
                    opacity: 0;
                    transform: translateY(20px);
                    transition: all 0.3s ease;
                }
                .keyboard-hints.show {
                    opacity: 1;
                    transform: translateY(0);
                }
                .keyboard-hints h6 {
                    margin: 0 0 8px 0;
                    color: var(--primary-color);
                    font-weight: 600;
                }
                .hint-item {
                    margin: 4px 0;
                    color: var(--text-secondary);
                }
                .hint-item kbd {
                    background: var(--primary-color);
                    color: white;
                    padding: 2px 6px;
                    border-radius: 3px;
                    font-size: 0.7rem;
                    margin-right: 8px;
                }
                @media (max-width: 768px) {
                    .keyboard-hints {
                        display: none;
                    }
                }
            `;
            document.head.appendChild(styles);
        }

        document.body.appendChild(hints);
        
        setTimeout(() => hints.classList.add('show'), 1000);
        
        // Auto-hide after 8 seconds
        setTimeout(() => {
            hints.classList.remove('show');
            setTimeout(() => hints.remove(), 300);
        }, 8000);
    }

    addItem() {
        const input = document.getElementById('newItem');
        const itemText = input.value.trim();
        
        if (!itemText) {
            this.showError('Please enter an item name');
            return;
        }

        // Split by commas for multiple items
        const itemsToAdd = itemText.split(',').map(item => item.trim()).filter(item => item);
        
        itemsToAdd.forEach(item => {
            this.addItemToList(item);
        });

        input.value = '';
        input.focus();
    }

    addItemToList(itemText) {
        if (this.items.includes(itemText)) {
            this.showError(`"${itemText}" is already in your list`);
            return;
        }

        this.items.push(itemText);
        this.updateShoppingListDisplay();
        this.updateCheckButton();
        this.clearError();
        this.showToast(`Added "${itemText}" to your list`, 'success');
    }

    removeItem(itemText) {
        this.items = this.items.filter(item => item !== itemText);
        this.updateShoppingListDisplay();
        this.updateCheckButton();
        
        // Clear results since the item list has changed
        this.results = null;
        this.hideResults();
        
        this.showToast(`Removed "${itemText}" from your list`, 'info');
    }

    updateShoppingListDisplay() {
        const container = document.getElementById('shoppingList');

        if (this.items.length === 0) {
            // Clear any existing items and show empty state
            container.innerHTML = `
                <div class="text-muted text-center" id="emptyState">
                    <i class="bi bi-cart-x fs-1"></i>
                    <p>No items yet. Add some items to get started!</p>
                </div>
            `;
            return;
        }

        // Hide empty state and show items
        const itemsHtml = this.items.map((item, index) => `
            <div class="shopping-item new-item">
                <span class="item-text">${this.escapeHtml(item)}</span>
                <button class="remove-btn" data-item-index="${index}" title="Remove item">
                    <i class="bi bi-x"></i>
                </button>
            </div>
        `).join('');

        container.innerHTML = itemsHtml;

        // Add event listeners for remove buttons
        container.querySelectorAll('.remove-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const index = parseInt(e.currentTarget.getAttribute('data-item-index'));
                const itemText = this.items[index];
                this.removeItem(itemText);
            });
        });
    }

    updateCheckButton() {
        const btn = document.getElementById('checkPricesBtn');
        btn.disabled = this.items.length === 0;
    }

    clearList() {
        this.items = [];
        this.results = null;
        this.updateShoppingListDisplay();
        this.updateCheckButton();
        this.hideResults();
    }

    validatePostcode(input) {
        const postcode = input.value;
        const isValid = /^[1-9]\d{3}$/.test(postcode);
        
        if (postcode && !isValid) {
            input.classList.add('is-invalid');
        } else {
            input.classList.remove('is-invalid');
        }
    }

    async checkPrices() {
        if (this.items.length === 0) return;

        const postcode = document.getElementById('postcode').value.trim();
        if (!/^[1-9]\d{3}$/.test(postcode)) {
            this.showError('Please enter a valid Australian postcode (1000-9999)');
            return;
        }

        this.showLoading(true);
        this.clearError();
        this.showToast(`Checking prices for ${this.items.length} items...`, 'info');

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

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            this.results = data;
            this.displayResults(data);
            this.showToast(`Found prices for ${data.results.length} items!`, 'success');

        } catch (error) {
            console.error('Error checking prices:', error);
            this.showError('Failed to check prices. Please try again.');
        } finally {
            this.showLoading(false);
        }
    }

    showLoading(show) {
        const loadingState = document.getElementById('loadingState');
        const resultsContainer = document.getElementById('resultsContainer');
        const emptyState = document.getElementById('resultsEmptyState');

        if (show) {
            loadingState.classList.remove('d-none');
            resultsContainer.classList.add('d-none');
            emptyState.classList.add('d-none');
        } else {
            loadingState.classList.add('d-none');
        }
    }

    displayResults(data) {
        this.showResultsSummary(data);
        this.showResultsTable(data);
    }

    showResultsSummary(data) {
        const summary = document.getElementById('resultsSummary');
        const totalItems = data.results.length;
        const onSaleCount = data.results.filter(r => r.onSale).length;
        
        let totalPrice = 0;
        let totalSavings = 0;

        data.results.forEach(result => {
            if (result.price) {
                totalPrice += result.price;
            }
            if (result.was && result.price) {
                totalSavings += (result.was - result.price);
            }
            // Add potential savings from alternatives
            if (result.potentialSavings && result.potentialSavings.length > 0) {
                const topSaving = Math.max(...result.potentialSavings.map(s => s.savings || 0));
                totalSavings += topSaving;
            }
        });

        document.getElementById('totalItems').textContent = totalItems;
        document.getElementById('totalPrice').textContent = `$${totalPrice.toFixed(2)}`;
        document.getElementById('totalSavings').textContent = `$${totalSavings.toFixed(2)}`;
        document.getElementById('onSaleCount').textContent = onSaleCount;

        summary.classList.remove('d-none');
    }

    showResultsTable(data) {
        const container = document.getElementById('resultsContainer');
        const tbody = document.getElementById('resultsTableBody');
        const emptyState = document.getElementById('resultsEmptyState');

        emptyState.classList.add('d-none');

        tbody.innerHTML = data.results.map(result => {
            const priceDisplay = result.price ? `$${result.price.toFixed(2)}` : 'N/A';
            const wasDisplay = result.was ? `$${result.was.toFixed(2)}` : '';
            const priceClass = result.onSale ? 'price-on-sale' : 'price-regular';
            
            const statusHtml = this.getStatusHtml(result);
            const alternativesCount = result.alternatives ? result.alternatives.length : 0;
            const alternativesBtn = alternativesCount > 0 ? 
                `<button class="btn btn-outline-info btn-sm alternatives-btn" 
                         onclick="app.showAlternatives('${this.escapeHtml(result.input)}')">
                    <i class="bi bi-list-ul"></i> ${alternativesCount} alternatives
                 </button>` : '';

            const priceHistoryBtn = result.bestMatch ?
                `<button class="btn btn-outline-primary btn-sm alternatives-btn mt-1" 
                         onclick="app.showPriceHistory('${this.escapeHtml(result.bestMatch)}', '${result.retailer}')">
                    <i class="bi bi-graph-up"></i> Price History
                 </button>` : '';

            return `
                <tr>
                    <td><strong>${this.escapeHtml(result.input)}</strong></td>
                    <td>${result.bestMatch ? this.escapeHtml(result.bestMatch) : 'No match found'}</td>
                    <td class="price-cell ${priceClass}">
                        ${priceDisplay}
                        ${wasDisplay ? `<br><span class="was-price">${wasDisplay}</span>` : ''}
                    </td>
                    <td>${wasDisplay}</td>
                    <td>${statusHtml}</td>
                    <td>
                        ${alternativesBtn}
                        ${priceHistoryBtn}
                    </td>
                </tr>
            `;
        }).join('');

        container.classList.remove('d-none');
    }

    getStatusHtml(result) {
        let statusHtml = '';
        
        if (result.onSale) {
            statusHtml += '<span class="status-indicator status-on-sale"><i class="bi bi-fire"></i> On Sale</span><br>';
        }
        
        if (result.inStock === true) {
            statusHtml += '<span class="status-indicator status-in-stock"><i class="bi bi-check-circle"></i> In Stock</span>';
        } else if (result.inStock === false) {
            statusHtml += '<span class="status-indicator status-regular"><i class="bi bi-x-circle"></i> Out of Stock</span>';
        } else {
            statusHtml += '<span class="status-indicator status-regular"><i class="bi bi-question-circle"></i> Unknown</span>';
        }

        return statusHtml;
    }

    showAlternatives(itemName) {
        const result = this.results.results.find(r => r.input === itemName);
        if (!result || !result.alternatives) return;

        const modal = new bootstrap.Modal(document.getElementById('alternativesModal'));
        const content = document.getElementById('alternativesContent');

        let alternativesHtml = `
            <h6>Showing alternatives for: <strong>${this.escapeHtml(itemName)}</strong></h6>
            <div class="mb-3">
                <strong>Best Match:</strong> ${this.escapeHtml(result.bestMatch)} - 
                <span class="text-success">$${result.price ? result.price.toFixed(2) : 'N/A'}</span>
            </div>
            <hr>
        `;

        result.alternatives.forEach((alt, index) => {
            const savings = result.price && alt.price ? (result.price - alt.price) : 0;
            const savingsPercent = savings > 0 && result.price ? ((savings / result.price) * 100).toFixed(1) : 0;
            
            alternativesHtml += `
                <div class="alternative-item">
                    <div class="d-flex justify-content-between align-items-start">
                        <div class="flex-grow-1">
                            <div class="product-name">${this.escapeHtml(alt.name)}</div>
                            ${alt.matchScore ? `<div class="match-score">Match: ${(alt.matchScore * 100).toFixed(0)}%</div>` : ''}
                            ${alt.onSale ? '<span class="sale-badge">ON SALE</span>' : ''}
                        </div>
                        <div class="text-end">
                            <div class="product-price">$${alt.price ? alt.price.toFixed(2) : 'N/A'}</div>
                            ${alt.was ? `<div class="was-price">Was: $${alt.was.toFixed(2)}</div>` : ''}
                            ${savings > 0 ? `<div class="product-savings">Save $${savings.toFixed(2)} (${savingsPercent}%)</div>` : ''}
                        </div>
                    </div>
                </div>
            `;
        });

        // Add potential savings if available
        if (result.potentialSavings && result.potentialSavings.length > 0) {
            alternativesHtml += `
                <hr>
                <h6><i class="bi bi-lightbulb"></i> Top Savings Opportunities:</h6>
            `;
            
            result.potentialSavings.slice(0, 3).forEach(saving => {
                alternativesHtml += `
                    <div class="alert alert-success">
                        <strong>${this.escapeHtml(saving.alternative)}</strong><br>
                        Save $${saving.savings.toFixed(2)} (${saving.percentage}%) 
                        - Only $${saving.alternativePrice.toFixed(2)} vs $${saving.currentPrice.toFixed(2)}
                    </div>
                `;
            });
        }

        content.innerHTML = alternativesHtml;
        modal.show();
    }

    async showPriceHistory(productName, retailer = 'woolworths') {
        // Check if we're coming from the tracked products modal
        const trackedProductsModal = bootstrap.Modal.getInstance(document.getElementById('trackedProductsModal'));
        if (trackedProductsModal) {
            this.previousModal = 'trackedProducts';
            trackedProductsModal.hide();
        }
        
        const modal = new bootstrap.Modal(document.getElementById('priceHistoryModal'));
        const content = document.getElementById('priceHistoryContent');

        // Show loading state
        content.innerHTML = `
            <div class="text-center">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <p class="mt-2">Loading price history...</p>
            </div>
        `;
        
        modal.show();

        try {
            // Fetch price history and prediction in parallel
            const [historyResponse, predictionResponse] = await Promise.all([
                fetch(`/price-history/${encodeURIComponent(productName)}?retailer=${retailer}&days_back=60`),
                fetch(`/sale-prediction/${encodeURIComponent(productName)}?retailer=${retailer}`)
            ]);

            const historyData = await historyResponse.json();
            const predictionData = await predictionResponse.json();

            // Create chart and prediction display
            this.displayPriceHistoryChart(historyData, predictionData, content);

        } catch (error) {
            console.error('Error fetching price history:', error);
            content.innerHTML = `
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-triangle"></i>
                    Error loading price history: ${error.message}
                </div>
            `;
        }
    }

    displayPriceHistoryChart(historyData, predictionData, container) {
        // Prepare chart data
        const history = historyData.history || [];
        const chartData = {
            labels: history.map(record => {
                const date = new Date(record.date_recorded);
                return date.toLocaleDateString('en-AU', { month: 'short', day: 'numeric' });
            }),
            datasets: [{
                label: 'Price ($)',
                data: history.map(record => record.price),
                borderColor: 'rgb(37, 99, 235)',
                backgroundColor: history.map(record => 
                    record.on_sale ? 'rgba(220, 38, 38, 0.2)' : 'rgba(37, 99, 235, 0.1)'
                ),
                pointBackgroundColor: history.map(record => 
                    record.on_sale ? 'rgb(220, 38, 38)' : 'rgb(37, 99, 235)'
                ),
                pointBorderColor: history.map(record => 
                    record.on_sale ? 'rgb(220, 38, 38)' : 'rgb(37, 99, 235)'
                ),
                pointRadius: history.map(record => record.on_sale ? 6 : 4),
                fill: false,
                tension: 0.1
            }]
        };

        const chartOptions = {
            responsive: true,
            plugins: {
                title: {
                    display: true,
                    text: `Price History: ${historyData.product_name}`
                },
                legend: {
                    display: true
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const record = history[context.dataIndex];
                            let label = `Price: $${context.parsed.y.toFixed(2)}`;
                            if (record.on_sale && record.was_price) {
                                label += ` (Was: $${record.was_price.toFixed(2)})`;
                            }
                            return label;
                        },
                        afterLabel: function(context) {
                            const record = history[context.dataIndex];
                            return record.on_sale ? '🔥 ON SALE' : '';
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: false,
                    title: {
                        display: true,
                        text: 'Price ($)'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Date'
                    }
                }
            }
        };

        // Generate prediction info
        let predictionHtml = '';
        if (predictionData.has_prediction) {
            const predictionDate = new Date(predictionData.predicted_sale_date);
            const daysUntil = predictionData.days_until_sale;
            
            predictionHtml = `
                <div class="row mt-4">
                    <div class="col-12">
                        <div class="alert alert-info">
                            <h6><i class="bi bi-crystal-ball"></i> Sale Prediction</h6>
                            <div class="row">
                                <div class="col-md-3">
                                    <strong>Next Sale:</strong><br>
                                    ${predictionDate.toLocaleDateString('en-AU')}
                                    <br><small class="text-muted">${daysUntil > 0 ? `in ${daysUntil} days` : daysUntil < 0 ? `${Math.abs(daysUntil)} days ago` : 'today'}</small>
                                </div>
                                <div class="col-md-3">
                                    <strong>Confidence:</strong><br>
                                    <div class="progress" style="height: 20px;">
                                        <div class="progress-bar" role="progressbar" 
                                             style="width: ${(predictionData.confidence * 100)}%"
                                             aria-valuenow="${(predictionData.confidence * 100)}" 
                                             aria-valuemin="0" aria-valuemax="100">
                                            ${Math.round(predictionData.confidence * 100)}%
                                        </div>
                                    </div>
                                </div>
                                ${predictionData.predicted_sale_price ? `
                                <div class="col-md-3">
                                    <strong>Expected Sale Price:</strong><br>
                                    $${predictionData.predicted_sale_price}
                                    ${predictionData.estimated_savings ? `<br><small class="text-success">Save ~$${predictionData.estimated_savings}</small>` : ''}
                                </div>
                                ` : ''}
                                <div class="col-md-3">
                                    <strong>Pattern:</strong><br>
                                    Sale every ~${Math.round(predictionData.analysis.avg_interval_days)} days
                                    <br><small class="text-muted">${predictionData.analysis.sale_count} sales detected</small>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        } else {
            predictionHtml = `
                <div class="alert alert-warning mt-4">
                    <h6><i class="bi bi-info-circle"></i> No Prediction Available</h6>
                    <p>${predictionData.reason || 'Not enough historical data to predict sales.'}</p>
                </div>
            `;
        }

        // Create chart container and render
        container.innerHTML = `
            <div class="row">
                <div class="col-12">
                    <canvas id="priceChart" width="800" height="400"></canvas>
                </div>
            </div>
            ${predictionHtml}
        `;

        // Render the chart
        const ctx = document.getElementById('priceChart').getContext('2d');
        new Chart(ctx, {
            type: 'line',
            data: chartData,
            options: chartOptions
        });
    }

    hideResults() {
        document.getElementById('resultsSummary').classList.add('d-none');
        document.getElementById('resultsContainer').classList.add('d-none');
        document.getElementById('resultsEmptyState').classList.remove('d-none');
    }

    showError(message) {
        const errorState = document.getElementById('errorState');
        const errorMessage = document.getElementById('errorMessage');
        
        errorMessage.textContent = message;
        errorState.classList.remove('d-none');
        errorState.style.animation = 'slideIn 0.3s ease-out';

        // Auto-hide error after 5 seconds
        setTimeout(() => {
            this.clearError();
        }, 5000);
    }

    showToast(message, type = 'success') {
        // Create toast element
        const toast = document.createElement('div');
        toast.className = `toast-notification toast-${type}`;
        toast.innerHTML = `
            <div class="toast-content">
                <i class="bi bi-${type === 'success' ? 'check-circle' : type === 'error' ? 'x-circle' : 'info-circle'}"></i>
                <span>${message}</span>
            </div>
        `;

        // Add toast styles if not already added
        if (!document.querySelector('.toast-styles')) {
            const styles = document.createElement('style');
            styles.className = 'toast-styles';
            styles.textContent = `
                .toast-notification {
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    background: white;
                    padding: 12px 16px;
                    border-radius: 8px;
                    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
                    z-index: 9999;
                    transform: translateX(400px);
                    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                    border-left: 4px solid var(--success-color);
                }
                .toast-notification.toast-error {
                    border-left-color: var(--warning-color);
                }
                .toast-notification.show {
                    transform: translateX(0);
                }
                .toast-content {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }
                .toast-content i {
                    font-size: 1.1em;
                    color: var(--success-color);
                }
                .toast-notification.toast-error .toast-content i {
                    color: var(--warning-color);
                }
            `;
            document.head.appendChild(styles);
        }

        // Add to DOM
        document.body.appendChild(toast);

        // Trigger animation
        setTimeout(() => toast.classList.add('show'), 10);

        // Auto-remove
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    clearError() {
        document.getElementById('errorState').classList.add('d-none');
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    async refreshDatabaseStats() {
        try {
            const response = await fetch('/database/stats');
            const data = await response.json();
            const stats = data.stats;
            
            const totalRecords = stats.price_history ? stats.price_history.total_records || 0 : 0;
            const uniqueProducts = stats.price_history ? stats.price_history.unique_products || 0 : 0;
            
            const statsText = `${totalRecords} records, ${uniqueProducts} products`;
            document.getElementById('dbStats').textContent = statsText;
            
            // Show/hide buttons based on database state AND admin status
            const dummyBtn = document.getElementById('generateDummyBtn');
            const dailyUpdateBtn = document.getElementById('dailyUpdateBtn');
            const viewProductsBtn = document.getElementById('viewProductsBtn');
            
            // Only show admin-only buttons if user is logged in as admin
            if (this.adminSessionToken) {
                // Admin is logged in - show buttons based on database state
                
                // Always show dummy data button for admins
                dummyBtn.classList.remove('d-none');
                
                if (totalRecords === 0) {
                    // Empty database: hide daily update and view products
                    dailyUpdateBtn.classList.add('d-none');
                    viewProductsBtn.classList.add('d-none');
                } else {
                    // Database has data: show daily update and view products
                    dailyUpdateBtn.classList.remove('d-none');
                    viewProductsBtn.classList.remove('d-none');
                }
            } else {
                // Not admin - hide all admin-only buttons
                dummyBtn.classList.add('d-none');
                dailyUpdateBtn.classList.add('d-none');
                viewProductsBtn.classList.add('d-none');
            }
            
        } catch (error) {
            console.error('Error fetching database stats:', error);
            document.getElementById('dbStats').textContent = 'Error loading stats';
        }
    }

    async clearDatabase() {
        // Show confirmation dialog
        const confirmMessage = `⚠️ WARNING: This will permanently delete ALL price history data!\n\nThis includes:\n• All tracked product prices\n• Historical sale data\n• Dummy test data\n\nThis action cannot be undone.\n\nAre you sure you want to continue?`;
        
        if (!confirm(confirmMessage)) {
            return; // User cancelled
        }

        // Double confirmation for safety
        const doubleConfirm = prompt(`To confirm, please type "DELETE ALL DATA" (without quotes):`);
        if (doubleConfirm !== "DELETE ALL DATA") {
            this.showToast('Database clear cancelled', 'info');
            return;
        }

        try {
            const response = await this.makeAuthenticatedRequest('/admin/clear-database', {
                method: 'POST'
            });

            const result = await response.json();

            if (result.success) {
                this.showToast('Database cleared successfully', 'success');
                await this.refreshDatabaseStats(); // Refresh stats to show 0 records
            } else {
                this.showToast('Failed to clear database', 'error');
            }

        } catch (error) {
            console.error('Error clearing database:', error);
            this.showToast(error.message || 'Error clearing database', 'error');
        }
    }

    async generateDummyData() {
        try {
            this.showToast('Generating dummy data...', 'info');
            
            const response = await this.makeAuthenticatedRequest('/admin/generate-dummy-data', {
                method: 'POST'
            });

            const result = await response.json();

            if (result.success) {
                this.showToast(result.message || 'Dummy data generated successfully!', 'success');
                await this.refreshDatabaseStats(); // Refresh stats 
            } else {
                this.showToast(result.message || 'Failed to generate dummy data', 'error');
            }

        } catch (error) {
            console.error('Error generating dummy data:', error);
            this.showToast(error.message || 'Error generating dummy data', 'error');
        }
    }

    async runDailyUpdate() {
        try {
            // Show initial progress
            this.showToast('Starting daily price update...', 'info');
            
            // Disable the button to prevent multiple clicks
            const updateBtn = document.getElementById('dailyUpdateBtn');
            const originalText = updateBtn.innerHTML;
            updateBtn.disabled = true;
            updateBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Updating...';

            const response = await this.makeAuthenticatedRequest('/daily-price-update', {
                method: 'POST'
            });

            const result = await response.json();

            if (result.success) {
                const stats = result.stats;
                const processedInfo = stats.batches_processed ? 
                    `(${stats.batches_processed} batches of ${stats.batch_size})` : '';
                
                this.showToast(
                    `Daily update completed! Updated ${stats.successful_updates}/${stats.products_processed} products ${processedInfo} (${stats.success_rate}% success)`, 
                    'success'
                );
                
                // Refresh database stats to show new record count
                await this.refreshDatabaseStats();
            } else {
                this.showToast(result.message || 'Daily update failed', 'error');
            }

        } catch (error) {
            console.error('Error running daily update:', error);
            this.showToast('Error running daily update', 'error');
        } finally {
            // Re-enable the button
            const updateBtn = document.getElementById('dailyUpdateBtn');
            updateBtn.disabled = false;
            updateBtn.innerHTML = '<i class="bi bi-calendar-check"></i> Daily Price Update';
        }
    }

    async viewTrackedProducts() {
        const modal = new bootstrap.Modal(document.getElementById('trackedProductsModal'));
        const content = document.getElementById('trackedProductsContent');

        // Show loading state
        content.innerHTML = `
            <div class="text-center">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <p class="mt-2">Loading tracked products...</p>
            </div>
        `;
        
        modal.show();

        try {
            const response = await this.makeAuthenticatedRequest('/admin/tracked-products');
            const data = await response.json();

            if (data.products && data.products.length > 0) {
                this.displayTrackedProducts(data, content);
            } else {
                content.innerHTML = `
                    <div class="alert alert-info text-center">
                        <i class="bi bi-info-circle fs-1"></i>
                        <h5>No Products Found</h5>
                        <p>No products are currently being tracked in the database.</p>
                    </div>
                `;
            }

        } catch (error) {
            console.error('Error fetching tracked products:', error);
            content.innerHTML = `
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-triangle"></i>
                    Error loading tracked products: ${error.message}
                </div>
            `;
        }
    }

    displayTrackedProducts(data, container) {
        const products = data.products;
        
        let productsHtml = `
            <div class="mb-3">
                <h6>Tracking ${data.count} products across different retailers:</h6>
            </div>
            <div class="mb-3">
                <div class="input-group">
                    <span class="input-group-text">
                        <i class="bi bi-search"></i>
                    </span>
                    <input type="text" class="form-control" id="productSearchInput" 
                           placeholder="Search products or retailers..." 
                           onkeyup="app.filterTrackedProducts()">
                    <button class="btn btn-outline-secondary" type="button" onclick="app.clearProductSearch()">
                        <i class="bi bi-x"></i> Clear
                    </button>
                </div>
            </div>
            <div class="table-responsive">
                <table class="table table-hover" id="trackedProductsTable">
                    <thead class="table-dark">
                        <tr>
                            <th>Product Name</th>
                            <th>Retailer</th>
                            <th>Records</th>
                            <th>First Seen</th>
                            <th>Last Updated</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        products.forEach(product => {
            const firstSeen = new Date(product.first_seen).toLocaleDateString('en-AU');
            const lastSeen = new Date(product.last_seen).toLocaleDateString('en-AU');
            
            productsHtml += `
                <tr>
                    <td><strong>${this.escapeHtml(product.product_name)}</strong></td>
                    <td>
                        <span class="badge bg-${product.retailer === 'woolworths' ? 'success' : 'primary'}">
                            ${product.retailer}
                        </span>
                    </td>
                    <td>
                        <span class="badge bg-info">${product.record_count} records</span>
                    </td>
                    <td><small class="text-muted">${firstSeen}</small></td>
                    <td><small class="text-muted">${lastSeen}</small></td>
                    <td>
                        <button class="btn btn-outline-primary btn-sm me-1" 
                                onclick="app.showPriceHistory('${this.escapeHtml(product.product_name)}', '${product.retailer}')">
                            <i class="bi bi-graph-up"></i> History
                        </button>
                        <button class="btn btn-outline-danger btn-sm" 
                                onclick="app.deleteProduct('${this.escapeHtml(product.product_name)}', '${product.retailer}')">
                            <i class="bi bi-trash"></i> Delete
                        </button>
                    </td>
                </tr>
            `;
        });

        productsHtml += `
                    </tbody>
                </table>
            </div>
        `;

        container.innerHTML = productsHtml;
    }

    async deleteProduct(productName, retailer) {
        // Show confirmation dialog
        const confirmMessage = `⚠️ Delete Product: ${productName} (${retailer})\n\nThis will permanently delete ALL price history data for this product at this retailer.\n\nThis action cannot be undone.\n\nAre you sure you want to continue?`;
        
        if (!confirm(confirmMessage)) {
            return; // User cancelled
        }

        try {
            this.showToast('Deleting product...', 'info');
            
            const response = await this.makeAuthenticatedRequest(`/admin/product/${encodeURIComponent(productName)}/${encodeURIComponent(retailer)}`, {
                method: 'DELETE'
            });

            const result = await response.json();

            if (result.success) {
                this.showToast(`Deleted ${result.records_deleted} records for "${productName}" at ${retailer}`, 'success');
                
                // Refresh the product list
                await this.viewTrackedProducts();
                
                // Refresh database stats
                await this.refreshDatabaseStats();
            } else {
                this.showToast('Failed to delete product', 'error');
            }

        } catch (error) {
            console.error('Error deleting product:', error);
            this.showToast(error.message || 'Error deleting product', 'error');
        }
    }

    filterTrackedProducts() {
        const searchInput = document.getElementById('productSearchInput');
        const searchTerm = searchInput.value.toLowerCase();
        const table = document.getElementById('trackedProductsTable');
        const rows = table.getElementsByTagName('tbody')[0].getElementsByTagName('tr');

        for (let i = 0; i < rows.length; i++) {
            const productName = rows[i].cells[0].textContent.toLowerCase();
            const retailer = rows[i].cells[1].textContent.toLowerCase();
            
            if (productName.includes(searchTerm) || retailer.includes(searchTerm)) {
                rows[i].style.display = '';
            } else {
                rows[i].style.display = 'none';
            }
        }
    }

    clearProductSearch() {
        const searchInput = document.getElementById('productSearchInput');
        searchInput.value = '';
        this.filterTrackedProducts(); // Show all products again
        searchInput.focus();
    }

    // Admin Authentication Methods
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
                // Session expired
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

    updateAdminUI(isAdmin) {
        const toggleBtn = document.getElementById('adminToggleBtn');
        const adminButtons = document.querySelectorAll('.admin-only');
        
        if (isAdmin) {
            toggleBtn.innerHTML = '<i class="bi bi-shield-check"></i> Admin Logout';
            toggleBtn.className = 'btn btn-success btn-sm';
            adminButtons.forEach(btn => btn.classList.remove('d-none'));
        } else {
            toggleBtn.innerHTML = '<i class="bi bi-shield-lock"></i> Admin Login';
            toggleBtn.className = 'btn btn-outline-secondary btn-sm';
            adminButtons.forEach(btn => btn.classList.add('d-none'));
        }
        
        // Refresh database stats to update button visibility based on admin status and data state
        this.refreshDatabaseStats();
    }

    toggleAdminLogin() {
        if (this.adminSessionToken) {
            this.performAdminLogout();
        } else {
            this.showAdminLogin();
        }
    }

    showAdminLogin() {
        // Clear previous form data
        document.getElementById('adminUsername').value = '';
        document.getElementById('adminPassword').value = '';
        document.getElementById('adminLoginError').classList.add('d-none');
        
        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('adminLoginModal'));
        modal.show();
    }

    async performAdminLogin() {
        const username = document.getElementById('adminUsername').value;
        const password = document.getElementById('adminPassword').value;
        const errorDiv = document.getElementById('adminLoginError');
        const loginBtn = document.getElementById('adminLoginBtn');
        
        // Disable button and show loading
        loginBtn.disabled = true;
        loginBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> Logging in...';
        
        try {
            const response = await fetch('/admin/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ username, password })
            });
            
            const data = await response.json();
            
            if (response.ok && data.success) {
                this.adminSessionToken = data.session_token;
                localStorage.setItem('adminSessionToken', data.session_token);
                this.updateAdminUI(true);
                
                // Close modal
                const modal = bootstrap.Modal.getInstance(document.getElementById('adminLoginModal'));
                modal.hide();
                
                this.showToast('Admin login successful', 'success');
            } else {
                errorDiv.textContent = data.message || 'Login failed';
                errorDiv.classList.remove('d-none');
            }
        } catch (error) {
            console.error('Login error:', error);
            errorDiv.textContent = 'Login failed due to network error: ' + error.message;
            errorDiv.classList.remove('d-none');
        } finally {
            // Re-enable button
            loginBtn.disabled = false;
            loginBtn.innerHTML = '<i class="bi bi-box-arrow-in-right"></i> Login';
        }
    }

    async performAdminLogout() {
        try {
            await fetch('/admin/logout', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${this.adminSessionToken}`
                }
            });
        } catch (error) {
            console.error('Logout error:', error);
        }
        
        // Clear session regardless of server response
        this.adminSessionToken = null;
        localStorage.removeItem('adminSessionToken');
        this.updateAdminUI(false);
        this.showToast('Admin logged out', 'info');
    }

    // Update existing admin-only methods to check authentication
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
            // Session expired
            this.adminSessionToken = null;
            localStorage.removeItem('adminSessionToken');
            this.updateAdminUI(false);
            throw new Error('Admin session expired. Please log in again.');
        }
        
        return response;
    }
}

// Initialize the app when the page loads
document.addEventListener('DOMContentLoaded', () => {
    window.app = new ShoppingListApp();
});

