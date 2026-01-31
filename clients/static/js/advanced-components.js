/* ============================================================
   РАСШИРЕННЫЕ UI КОМПОНЕНТЫ - ADVANCED
   ============================================================ */

// ============================================================
// DARK MODE
// ============================================================

class ThemeManager {
  constructor() {
    this.currentTheme = localStorage.getItem('theme') || 'light';
    this.init();
  }

  init() {
    this.setTheme(this.currentTheme);
    this.createToggle();
  }

  setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
    this.currentTheme = theme;
    this.updateIcon();
  }

  createToggle() {
    const toggle = document.createElement('button');
    toggle.id = 'theme-toggle-btn';
    toggle.className = 'theme-toggle';
    toggle.innerHTML = '<span id="theme-icon">🌙</span>';
    toggle.title = 'Переключить тему';
    
    toggle.addEventListener('click', () => {
      const newTheme = this.currentTheme === 'dark' ? 'light' : 'dark';
      this.setTheme(newTheme);
    });

    const nav = document.querySelector('.navbar-nav');
    if (nav) {
      const li = document.createElement('li');
      li.className = 'nav-item';
      li.appendChild(toggle);
      nav.appendChild(li);
    }
  }

  updateIcon() {
    const icon = document.getElementById('theme-icon');
    if (icon) {
      icon.textContent = this.currentTheme === 'dark' ? '☀️' : '🌙';
    }
  }
}

// ============================================================
// NOTIFICATION SYSTEM
// ============================================================

class NotificationSystem {
  constructor() {
    this.container = this.createContainer();
  }

  createContainer() {
    let container = document.querySelector('.notification-container');
    if (!container) {
      container = document.createElement('div');
      container.className = 'notification-container';
      container.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 9999;
        display: flex;
        flex-direction: column;
        gap: 12px;
        max-width: 400px;
      `;
      document.body.appendChild(container);
    }
    return container;
  }

  show(message, type = 'info', duration = 5000) {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    
    const icons = {
      success: '✅',
      error: '❌',
      warning: '⚠️',
      info: 'ℹ️',
    };

    notification.innerHTML = `
      <div style="display: flex; align-items: flex-start; gap: 12px;">
        <span style="font-size: 20px; flex-shrink: 0;">${icons[type]}</span>
        <div style="flex: 1;">
          <div style="font-weight: 700; margin-bottom: 4px;">${this.getTitle(type)}</div>
          <div style="font-size: 13px; color: #6c757d;">${message}</div>
        </div>
        <button class="notification-close" style="background: none; border: none; font-size: 18px; color: #6c757d; cursor: pointer; padding: 0; flex-shrink: 0;">×</button>
      </div>
    `;

    notification.style.cssText = `
      background: #ffffff;
      border-radius: 10px;
      padding: 16px 20px;
      box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
      border-left: 4px solid ${this.getColor(type)};
      animation: slideInRight 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    `;

    const closeBtn = notification.querySelector('.notification-close');
    closeBtn.addEventListener('click', () => {
      notification.style.animation = 'slideOutRight 0.3s ease';
      setTimeout(() => notification.remove(), 300);
    });

    this.container.appendChild(notification);

    if (duration > 0) {
      setTimeout(() => {
        notification.style.animation = 'slideOutRight 0.3s ease';
        setTimeout(() => notification.remove(), 300);
      }, duration);
    }
  }

  getTitle(type) {
    const titles = {
      success: 'Успешно',
      error: 'Ошибка',
      warning: 'Предупреждение',
      info: 'Информация',
    };
    return titles[type] || 'Уведомление';
  }

  getColor(type) {
    const colors = {
      success: '#28a745',
      error: '#dc3545',
      warning: '#ffc107',
      info: '#17a2b8',
    };
    return colors[type] || '#5bc0be';
  }
}

// ============================================================
// LOADING OVERLAY
// ============================================================

class LoadingOverlay {
  constructor() {
    this.overlay = null;
  }

  show(message = 'Загрузка...') {
    this.hide(); // Remove existing if any
    
    this.overlay = document.createElement('div');
    this.overlay.className = 'loading-overlay';
    this.overlay.innerHTML = `
      <div class="loading-spinner">
        <div class="spinner"></div>
        <div class="loading-text">${message}</div>
      </div>
    `;

    this.overlay.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(0, 0, 0, 0.7);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 10000;
      backdrop-filter: blur(4px);
      animation: fadeIn 0.3s ease;
    `;

    document.body.appendChild(this.overlay);
  }

  hide() {
    if (this.overlay) {
      this.overlay.style.animation = 'fadeOut 0.3s ease';
      setTimeout(() => {
        if (this.overlay && this.overlay.parentNode) {
          this.overlay.parentNode.removeChild(this.overlay);
        }
        this.overlay = null;
      }, 300);
    }
  }
}

// ============================================================
// CONFIRM DIALOG
// ============================================================

class ConfirmDialog {
  static show(message, onConfirm, onCancel = null) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay active';
    
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.innerHTML = `
      <div class="modal-header">
        <h2>Подтверждение</h2>
      </div>
      <div class="modal-body">
        <p>${message}</p>
      </div>
      <div class="modal-footer">
        <button class="btn btn-secondary" id="cancel-btn">Отмена</button>
        <button class="btn btn-danger" id="confirm-btn">Подтвердить</button>
      </div>
    `;

    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    const confirmBtn = overlay.querySelector('#confirm-btn');
    const cancelBtn = overlay.querySelector('#cancel-btn');

    const cleanup = () => {
      overlay.classList.remove('active');
      setTimeout(() => overlay.remove(), 300);
    };

    confirmBtn.addEventListener('click', () => {
      if (onConfirm) onConfirm();
      cleanup();
    });

    cancelBtn.addEventListener('click', () => {
      if (onCancel) onCancel();
      cleanup();
    });

    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) {
        if (onCancel) onCancel();
        cleanup();
      }
    });
  }
}

// ============================================================
// TABLE ENHANCEMENTS
// ============================================================

class TableEnhancements {
  constructor(tableSelector) {
    this.table = document.querySelector(tableSelector);
    if (!this.table) return;
    this.init();
  }

  init() {
    this.addSorting();
    this.addRowAnimations();
    this.addRowSelection();
  }

  addSorting() {
    const headers = this.table.querySelectorAll('thead th');
    headers.forEach((header, index) => {
      if (header.querySelector('a')) return; // Skip if already has link
      
      header.style.cursor = 'pointer';
      header.addEventListener('click', () => {
        this.sortTable(index);
      });
    });
  }

  sortTable(columnIndex) {
    const tbody = this.table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    
    rows.sort((a, b) => {
      const aText = a.cells[columnIndex].textContent.trim();
      const bText = b.cells[columnIndex].textContent.trim();
      return aText.localeCompare(bText, 'ru', { numeric: true });
    });

    rows.forEach(row => tbody.appendChild(row));
  }

  addRowAnimations() {
    const rows = this.table.querySelectorAll('tbody tr');
    rows.forEach((row, index) => {
      row.style.animation = `fadeInUp 0.3s ease ${index * 0.05}s both`;
    });
  }

  addRowSelection() {
    const rows = this.table.querySelectorAll('tbody tr');
    rows.forEach(row => {
      row.addEventListener('click', function(e) {
        if (e.target.tagName === 'A' || e.target.tagName === 'BUTTON') return;
        this.classList.toggle('selected');
      });
    });
  }
}

// ============================================================
// FORM VALIDATION
// ============================================================

class FormValidation {
  constructor(formSelector) {
    this.form = document.querySelector(formSelector);
    if (!this.form) return;
    this.init();
  }

  init() {
    this.form.addEventListener('submit', (e) => {
      if (!this.validate()) {
        e.preventDefault();
      }
    });

    const inputs = this.form.querySelectorAll('input, select, textarea');
    inputs.forEach(input => {
      input.addEventListener('blur', () => {
        this.validateField(input);
      });
      
      input.addEventListener('input', () => {
        if (input.classList.contains('error')) {
          this.validateField(input);
        }
      });
    });
  }

  validate() {
    let isValid = true;
    const inputs = this.form.querySelectorAll('[required]');

    inputs.forEach(input => {
      if (!this.validateField(input)) {
        isValid = false;
      }
    });

    return isValid;
  }

  validateField(field) {
    let isValid = true;
    let errorMessage = '';

    if (field.hasAttribute('required') && !field.value.trim()) {
      isValid = false;
      errorMessage = 'Это поле обязательно';
    }

    if (field.type === 'email' && field.value.trim()) {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(field.value)) {
        isValid = false;
        errorMessage = 'Введите корректный email';
      }
    }

    if (field.type === 'tel' && field.value.trim()) {
      const phoneRegex = /^[\d\s\-\+\(\)]+$/;
      if (!phoneRegex.test(field.value)) {
        isValid = false;
        errorMessage = 'Введите корректный телефон';
      }
    }

    if (field.hasAttribute('minlength')) {
      const minLength = parseInt(field.getAttribute('minlength'));
      if (field.value.length < minLength) {
        isValid = false;
        errorMessage = `Минимум ${minLength} символов`;
      }
    }

    this.showFieldError(field, isValid, errorMessage);
    return isValid;
  }

  showFieldError(field, isValid, message) {
    const formGroup = field.closest('.form-group');
    if (!formGroup) return;

    let errorElement = formGroup.querySelector('.form-error');
    if (!errorElement) {
      errorElement = document.createElement('span');
      errorElement.className = 'form-error';
      field.parentNode.insertBefore(errorElement, field.nextSibling);
    }

    if (!isValid) {
      field.classList.add('error');
      errorElement.textContent = message;
      errorElement.style.display = 'block';
    } else {
      field.classList.remove('error');
      errorElement.textContent = '';
      errorElement.style.display = 'none';
    }
  }
}

// ============================================================
// ИНИЦИАЛИЗАЦИЯ
// ============================================================

document.addEventListener('DOMContentLoaded', function() {
  // Инициализация темы
  window.themeManager = new ThemeManager();
  
  // Инициализация уведомлений
  window.notifications = new NotificationSystem();
  
  // Инициализация загрузки
  window.loading = new LoadingOverlay();
  
  // Улучшение таблиц
  const tables = document.querySelectorAll('.list-table table, #result_list, .results');
  tables.forEach(table => {
    new TableEnhancements(table);
  });
  
  // Валидация форм
  const forms = document.querySelectorAll('form');
  forms.forEach(form => {
    if (!form.classList.contains('no-validation')) {
      new FormValidation(form);
    }
  });
  
  // Подтверждение удаления
  document.querySelectorAll('.delete-btn, .deletelink, a[href*="delete"]').forEach(link => {
    link.addEventListener('click', function(e) {
      e.preventDefault();
      ConfirmDialog.show(
        'Вы уверены, что хотите удалить этот объект? Это действие нельзя отменить.',
        () => {
          window.location.href = this.href || this.dataset.href;
        }
      );
    });
  });
  
  // Анимация при скролле
  const animateOnScroll = () => {
    const elements = document.querySelectorAll('.balance-card, .card, .module');
    elements.forEach(el => {
      const rect = el.getBoundingClientRect();
      if (rect.top < window.innerHeight - 100) {
        el.style.animation = 'fadeInUp 0.6s ease both';
      }
    });
  };
  
  window.addEventListener('scroll', animateOnScroll);
  animateOnScroll(); // Initial call
  
  // Автоматическое скрытие алертов
  const alerts = document.querySelectorAll('.alert');
  alerts.forEach(alert => {
    setTimeout(() => {
      alert.style.animation = 'fadeOut 0.5s ease';
      setTimeout(() => alert.remove(), 500);
    }, 5000);
  });
});

// ============================================================
// GLOBAL UTILITIES
// ============================================================

// Глобальные функции
window.showNotification = (message, type = 'info') => {
  if (window.notifications) {
    window.notifications.show(message, type);
  }
};

window.showLoading = (message) => {
  if (window.loading) {
    window.loading.show(message);
  }
};

window.hideLoading = () => {
  if (window.loading) {
    window.loading.hide();
  }
};

window.confirmAction = (message, onConfirm, onCancel) => {
  ConfirmDialog.show(message, onConfirm, onCancel);
};

// Экспорт классов
window.ThemeManager = ThemeManager;
window.NotificationSystem = NotificationSystem;
window.LoadingOverlay = LoadingOverlay;
window.ConfirmDialog = ConfirmDialog;
window.TableEnhancements = TableEnhancements;
window.FormValidation = FormValidation;
