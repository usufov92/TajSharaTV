from django import template

register = template.Library()

@register.filter
def abs_value(value):
    """Возвращает абсолютное значение числа"""
    try:
        return abs(float(value))
    except (ValueError, TypeError):
        return value
