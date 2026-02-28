// Полностью независимое модальное окно для пополнения баланса в админке
(function() {
    'use strict';
    
    window.topupModal = {
        show: function(profileId, username, balance) {
            // Удаляем существующее окно если есть
            const existing = document.getElementById('topup-modal-overlay');
            if (existing) {
                existing.remove();
            }
            
            // Создаем HTML модального окна
            const modalHTML = `
            <div id="topup-modal-overlay" style="
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0,0,0,0.5);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 10000;
            ">
                <div style="
                    background: white;
                    border-radius: 8px;
                    padding: 30px;
                    max-width: 400px;
                    width: 90%;
                    box-shadow: 0 4px 30px rgba(0,0,0,0.3);
                ">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                        <h2 style="margin: 0; color: #333; font-size: 20px;">💰 Пополнить баланс</h2>
                        <button type="button" onclick="window.topupModal.close();" style="
                            background: none;
                            border: none;
                            font-size: 28px;
                            cursor: pointer;
                            color: #999;
                            padding: 0;
                            width: 30px;
                            height: 30px;
                        ">×</button>
                    </div>
                    
                    <div style="background: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px;">
                        <p style="margin: 0 0 10px 0; color: #666; font-size: 14px;">
                            <strong>Менеджер:</strong> ${this.escapeHtml(username)}
                        </p>
                        <p style="margin: 0; color: #666; font-size: 14px;">
                            <strong>Текущий баланс:</strong> <span style="color: #5bc0be; font-weight: bold; font-size: 16px;">$${parseFloat(balance).toFixed(2)}</span>
                        </p>
                    </div>
                    
                    <form id="topup-form" onsubmit="return window.topupModal.submit(event, ${profileId});" style="display: flex; flex-direction: column; gap: 15px;">
                        <div>
                            <label style="display: block; margin-bottom: 8px; color: #333; font-weight: 600; font-size: 14px;">Сумма пополнения ($)</label>
                            <input type="number" id="topup-amount" name="amount" step="0.01" min="0.01" required style="
                                width: 100%;
                                padding: 10px;
                                border: 1px solid #ddd;
                                border-radius: 5px;
                                font-size: 14px;
                                box-sizing: border-box;
                                font-family: Arial;
                            " />
                        </div>
                        
                        <div>
                            <label style="display: block; margin-bottom: 8px; color: #333; font-weight: 600; font-size: 14px;">Комментарий</label>
                            <textarea id="topup-comment" name="comment" rows="3" style="
                                width: 100%;
                                padding: 10px;
                                border: 1px solid #ddd;
                                border-radius: 5px;
                                font-size: 14px;
                                box-sizing: border-box;
                                font-family: Arial;
                                resize: vertical;
                            "></textarea>
                        </div>
                        
                        <div style="display: flex; gap: 10px; justify-content: flex-end; margin-top: 10px;">
                            <button type="button" onclick="window.topupModal.close();" style="
                                padding: 10px 20px;
                                border: 1px solid #ddd;
                                background: white;
                                color: #666;
                                border-radius: 5px;
                                cursor: pointer;
                                font-weight: 600;
                                font-size: 14px;
                            ">Отмена</button>
                            <button type="submit" id="topup-submit-btn" style="
                                padding: 10px 20px;
                                background: linear-gradient(135deg, #5bc0be 0%, #4a9b98 100%);
                                color: white;
                                border: none;
                                border-radius: 5px;
                                cursor: pointer;
                                font-weight: 600;
                                font-size: 14px;
                            ">Пополнить баланс</button>
                        </div>
                    </form>
                </div>
            </div>
            `;
            
            // Вставляем в DOM
            document.body.insertAdjacentHTML('beforeend', modalHTML);
            
            // Закрытие при клике на фон
            document.getElementById('topup-modal-overlay').addEventListener('click', (e) => {
                if (e.target.id === 'topup-modal-overlay') {
                    this.close();
                }
            });
            
            // Закрытие при ESC
            const escHandler = (e) => {
                if (e.key === 'Escape') {
                    this.close();
                    document.removeEventListener('keydown', escHandler);
                }
            };
            document.addEventListener('keydown', escHandler);
            
            // Фокус на поле суммы
            setTimeout(() => {
                document.getElementById('topup-amount').focus();
            }, 100);
        },
        
        close: function() {
            const modal = document.getElementById('topup-modal-overlay');
            if (modal) {
                modal.remove();
            }
        },
        
        submit: function(event, profileId) {
            event.preventDefault();
            
            const amount = document.getElementById('topup-amount').value;
            const comment = document.getElementById('topup-comment').value;
            const submitBtn = document.getElementById('topup-submit-btn');
            
            if (!amount || parseFloat(amount) <= 0) {
                alert('Пожалуйста, введите корректную сумму');
                return false;
            }
            
            // Отключаем кнопку и показываем индикатор
            submitBtn.disabled = true;
            const originalText = submitBtn.textContent;
            submitBtn.textContent = 'Обработка...';
            
            // Формируем данные
            const formData = new FormData();
            formData.append('profile_id', profileId);
            formData.append('amount', amount);
            formData.append('comment', comment);
            formData.append('csrfmiddlewaretoken', this.getCookie('csrftoken'));
            
            // Отправляем запрос
            fetch('/tajsharatv/admin/topup-balance/', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('✅ Баланс успешно пополнен на $' + amount + '!');
                    this.close();
                    // Перезагружаем страницу после небольшой задержки
                    setTimeout(() => {
                        location.reload();
                    }, 500);
                } else {
                    alert('❌ Ошибка: ' + (data.message || 'Неизвестная ошибка'));
                    submitBtn.disabled = false;
                    submitBtn.textContent = originalText;
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('❌ Ошибка соединения. Проверьте консоль браузера (F12)');
                submitBtn.disabled = false;
                submitBtn.textContent = originalText;
            });
            
            return false;
        },
        
        getCookie: function(name) {
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
        },
        
        escapeHtml: function(text) {
            const map = {
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#039;'
            };
            return text.replace(/[&<>"']/g, (m) => map[m]);
        }
    };
})();
