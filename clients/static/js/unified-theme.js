/* ============================================================
   ЕДИНАЯ ТЕМА - БЕЗ ПЕРЕКЛЮЧАТЕЛЯ
   ============================================================ */

// Очищаем старые настройки темы из localStorage
if (localStorage.getItem('unified-theme')) {
  localStorage.removeItem('unified-theme');
}

// Удаляем атрибут темы если он был установлен
if (document.documentElement.hasAttribute('data-theme')) {
  document.documentElement.removeAttribute('data-theme');
}
if (document.body.hasAttribute('data-theme')) {
  document.body.removeAttribute('data-theme');
}

console.log('✅ Unified Theme System loaded (theme switcher disabled)');

