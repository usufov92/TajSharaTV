// Предотвращаем отправку формы админки при клике по кнопке пополнения
// Флаг для отслеживания клика по кнопке пополнения
window.topupBalanceClicked = false;

// Перехватываем submit формы админки если был клик по кнопке пополнения
if (typeof django !== 'undefined' && typeof django.jQuery !== 'undefined') {
    django.jQuery(document).on('submit', 'form', function(e) {
        if (window.topupBalanceClicked) {
            e.preventDefault();
            e.stopPropagation();
            window.topupBalanceClicked = false;
            return false;
        }
    });
}

// Функция открытия модального окна пополнения баланса
function openTopupModal(profileId, username, currentBalance) {
    // Создаём модальное окно
    let modalHtml = `
        <div id="topup-modal-backdrop" style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); z-index: 999; display: flex; align-items: center; justify-content: center;">
            <div style="background: white; border-radius: 8px; padding: 30px; max-width: 400px; width: 90%; box-shadow: 0 4px 20px rgba(0,0,0,0.3);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                    <h3 style="margin: 0; color: #333;">💰 Пополнить баланс</h3>
                    <button onclick="closeTopupModal()" style="background: none; border: none; font-size: 24px; cursor: pointer; color: #999;">×</button>
                </div>
                
                <div style="margin-bottom: 20px; padding: 15px; background: #f5f5f5; border-radius: 5px;">
                    <p style="margin: 5px 0; color: #666;"><strong>Менеджер:</strong> ${escapeHtml(username)}</p>
                    <p style="margin: 5px 0; color: #666;"><strong>Текущий баланс:</strong> <span style="color: #5bc0be; font-weight: bold;">$${currentBalance.toFixed(2)}</span></p>
                </div>
                
                <form id="topup-form" style="display: flex; flex-direction: column; gap: 15px;">
                    <div>
                        <label for="topup-amount" style="display: block; margin-bottom: 5px; color: #333; font-weight: 600;">Сумма пополнения ($)</label>
                        <input type="number" id="topup-amount" name="amount" step="0.01" min="0" required 
                               style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; font-size: 14px; box-sizing: border-box;">
                    </div>
                    
                    <div>
                        <label for="topup-comment" style="display: block; margin-bottom: 5px; color: #333; font-weight: 600;">Комментарий (опционально)</label>
                        <textarea id="topup-comment" name="comment" rows="3" 
                                  style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; font-size: 14px; box-sizing: border-box; font-family: Arial, sans-serif; resize: vertical;"></textarea>
                    </div>
                    
                    <div style="display: flex; gap: 10px; justify-content: flex-end; margin-top: 10px;">
                        <button type="button" onclick="closeTopupModal()" 
                                style="padding: 10px 20px; border: 1px solid #ddd; background: white; color: #666; border-radius: 5px; cursor: pointer; font-weight: 600;">
                            Отмена
                        </button>
                        <button type="submit" 
                                style="padding: 10px 20px; background: linear-gradient(135deg, #5bc0be 0%, #4a9b98 100%); color: white; border: none; border-radius: 5px; cursor: pointer; font-weight: 600;">
                            Пополнить баланс
                        </button>
                    </div>
                </form>
            </div>
        </div>
    `;
    
    // Удаляем старое модальное окно если оно есть
    let oldBackdrop = document.getElementById('topup-modal-backdrop');
    if (oldBackdrop) {
        oldBackdrop.remove();
    }
    
    // Вставляем новое модальное окно
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    
    // Обработчик подправки формы
    document.getElementById('topup-form').addEventListener('submit', function(e) {
        e.preventDefault();
        
        let amount = parseFloat(document.getElementById('topup-amount').value);
        let comment = document.getElementById('topup-comment').value || '';
        
        if (!amount || amount <= 0) {
            alert('Пожалуйста, введите корректную сумму');
            return;
        }
        
        // Отправляем данные на сервер
        let formData = new FormData();
        formData.append('profile_id', profileId);
        formData.append('amount', amount);
        formData.append('comment', comment);
        formData.append('csrfmiddlewaretoken', getCookie('csrftoken'));
        
        // Показываем индикатор загрузки
        let submitButton = document.querySelector('#topup-form button[type="submit"]');
        let originalText = submitButton.textContent;
        submitButton.disabled = true;
        submitButton.textContent = 'Обработка...';
        
        fetch('/tajsharatv/admin/topup-balance/', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (response.ok) {
                return response.json();
            } else {
                throw new Error('Ошибка сервера');
            }
        })
        .then(data => {
            if (data.success) {
                alert('✅ Баланс успешно пополнен!');
                closeTopupModal();
                // Перезагружаем страницу для обновления данных
                setTimeout(() => {
                    window.location.reload();
                }, 500);
            } else {
                alert('❌ Ошибка: ' + (data.message || 'Неизвестная ошибка'));
                submitButton.disabled = false;
                submitButton.textContent = originalText;
            }
        })
        .catch(error => {
            console.error('Ошибка:', error);
            alert('❌ Ошибка соединения: ' + error);
            submitButton.disabled = false;
            submitButton.textContent = originalText;
        });
    });
    
    // Закрытие модального окна при клике на фон
    document.getElementById('topup-modal-backdrop').addEventListener('click', function(e) {
        if (e.target === this) {
            closeTopupModal();
        }
    });

    return false;
}

// Функция закрытия модального окна
function closeTopupModal() {
    let backdrop = document.getElementById('topup-modal-backdrop');
    if (backdrop) {
        backdrop.remove();
    }
}

// Функция для получения CSRF токена из cookies
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

// Функция для экранирования HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Закрытие модального окна при нажатии на ESC
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeTopupModal();
    }
});
