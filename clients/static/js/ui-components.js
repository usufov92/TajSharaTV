// ===================================
// UI COMPONENTS - JAVASCRIPT
// Professional Interactive Components
// ===================================

document.addEventListener('DOMContentLoaded', function() {
    // Initialize all components
    initTableSearch();
    initFormatting();
    initClipboard();
    initConfirmDialogs();
    initTooltips();
});

// Table Search Functionality
function initTableSearch() {
    const searchInputs = document.querySelectorAll('[data-table-search]');
    
    searchInputs.forEach(input => {
        const tableId = input.getAttribute('data-table-search');
        const table = document.getElementById(tableId);
        
        if (!table) return;
        
        input.addEventListener('keyup', function() {
            const filter = this.value.toLowerCase();
            const rows = table.querySelectorAll('tbody tr');
            
            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(filter) ? '' : 'none';
            });
        });
    });
}

// Format Currency
function formatCurrency(amount, currency = 'TJS') {
    const formatted = new Intl.NumberFormat('tg-TJ', {
        style: 'currency',
        currency: currency,
        minimumFractionDigits: 2
    }).format(amount);
    
    return formatted;
}

// Format Date
function formatDate(dateString, format = 'full') {
    const date = new Date(dateString);
    
    const options = {
        full: { year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' },
        short: { year: 'numeric', month: 'short', day: 'numeric' },
        time: { hour: '2-digit', minute: '2-digit' }
    };
    
    return new Intl.DateTimeFormat('ru-RU', options[format] || options.full).format(date);
}

// Apply formatting to elements
function initFormatting() {
    // Format currency elements
    document.querySelectorAll('[data-currency]').forEach(el => {
        const amount = parseFloat(el.textContent);
        const currency = el.getAttribute('data-currency') || 'TJS';
        el.textContent = formatCurrency(amount, currency);
    });
    
    // Format date elements
    document.querySelectorAll('[data-date]').forEach(el => {
        const dateStr = el.getAttribute('data-date');
        const format = el.getAttribute('data-date-format') || 'full';
        el.textContent = formatDate(dateStr, format);
    });
}

// Clipboard Functionality
function initClipboard() {
    document.querySelectorAll('[data-clipboard]').forEach(btn => {
        btn.addEventListener('click', function() {
            const text = this.getAttribute('data-clipboard');
            
            navigator.clipboard.writeText(text).then(() => {
                showToast('Скопировано!', 'success');
                
                // Visual feedback
                const originalText = this.innerHTML;
                this.innerHTML = '<i class="fas fa-check"></i> Скопировано';
                
                setTimeout(() => {
                    this.innerHTML = originalText;
                }, 2000);
            }).catch(err => {
                showToast('Ошибка копирования', 'error');
            });
        });
    });
}

// Confirm Dialogs
function initConfirmDialogs() {
    document.querySelectorAll('[data-confirm]').forEach(btn => {
        btn.addEventListener('click', function(e) {
            const message = this.getAttribute('data-confirm');
            
            if (!confirm(message)) {
                e.preventDefault();
                return false;
            }
        });
    });
}

// Tooltips
function initTooltips() {
    const tooltips = document.querySelectorAll('[data-tooltip]');
    
    tooltips.forEach(el => {
        el.classList.add('tooltip-custom');
    });
}

// Show Toast Notification
function showToast(message, type = 'info', duration = 3000) {
    const container = getOrCreateToastContainer();
    
    const toast = document.createElement('div');
    toast.className = `toast-custom toast-${type}`;
    
    const iconMap = {
        success: 'fas fa-check-circle',
        error: 'fas fa-exclamation-circle',
        warning: 'fas fa-exclamation-triangle',
        info: 'fas fa-info-circle'
    };
    
    toast.innerHTML = `
        <div style="display: flex; align-items: center; gap: 1rem;">
            <i class="${iconMap[type]}" style="font-size: 1.5rem;"></i>
            <div>
                <div class="toast-title">${type === 'success' ? 'Успешно' : type === 'error' ? 'Ошибка' : 'Уведомление'}</div>
                <div class="toast-message">${message}</div>
            </div>
        </div>
    `;
    
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

function getOrCreateToastContainer() {
    let container = document.querySelector('.toast-container');
    
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
    }
    
    return container;
}

// Loading Overlay
function showLoading(message = 'Загрузка...') {
    const overlay = document.createElement('div');
    overlay.className = 'loading-overlay';
    overlay.id = 'loadingOverlay';
    
    overlay.innerHTML = `
        <div class="loading-content">
            <div class="spinner-custom"></div>
            <div style="margin-top: 1rem; font-weight: 600; color: var(--text-primary);">${message}</div>
        </div>
    `;
    
    document.body.appendChild(overlay);
}

function hideLoading() {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) {
        overlay.remove();
    }
}

// Export functions for use in other scripts
window.UIComponents = {
    formatCurrency,
    formatDate,
    showToast,
    showLoading,
    hideLoading
};

// Add slideOut animation
const style = document.createElement('style');
style.textContent = `
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);
