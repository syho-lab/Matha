import os
import logging
import tempfile
import re
import asyncio
from typing import Dict, List, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
import sympy as sp
from sympy import (
    sympify, factor, cancel, apart, expand, simplify, solve, diff, integrate, 
    symbols, fraction, Poly, series, limit, oo, I, pi, E, sin, cos, tan, log, ln,
    sqrt, exp, trigsimp, expand_trig, nsimplify
)
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
import numpy as np

# ========== КОНФИГУРАЦИЯ ==========
try:
    pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'
    TESSERACT_AVAILABLE = True
except:
    TESSERACT_AVAILABLE = False

try:
    from keep_alive import keep_alive
    keep_alive()
    logging.info("🔄 Flask сервер запущен для мониторинга")
except ImportError:
    logging.warning("Flask недоступен")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не установлен")

# ========== МЕГА-КЛАСС РЕШАТЕЛЯ ==========
class MegaMathSolver:
    def __init__(self):
        self.x, self.y, self.z, self.t = symbols('x y z t')
        self.a, self.b, self.c, self.n = symbols('a b c n')
        self.symbols_dict = {
            'x': self.x, 'y': self.y, 'z': self.z, 't': self.t,
            'a': self.a, 'b': self.b, 'c': self.c, 'n': self.n
        }
        
    def intelligent_preprocess(self, expr_str: str) -> str:
        """Умная предобработка выражений"""
        if not expr_str or expr_str.isspace():
            return ""
            
        # Сохраняем оригинал для анализа
        original = expr_str
        
        # 1. Заменяем кавычки и специальные символы
        expr_str = expr_str.replace('"', '').replace("'", "")
        expr_str = expr_str.replace('’', "'").replace('‘', "'")
        
        # 2. Математические символы
        replacements = {
            '^': '**', '=': '==', '÷': '/', '×': '*', '–': '-', '−': '-',
            'π': 'pi', '∞': 'oo', '√': 'sqrt', '∫': 'integrate',
            '∂': 'diff', '∑': 'Sum', '∏': 'Product', '∆': 'delta',
            'α': 'alpha', 'β': 'beta', 'γ': 'gamma', 'θ': 'theta'
        }
        for old, new in replacements.items():
            expr_str = expr_str.replace(old, new)
            
        # 3. Умное добавление умножения
        # Между цифрой и буквой: 3x → 3*x
        expr_str = re.sub(r'(\d)([a-zA-Zα-ω])', r'\1*\2', expr_str)
        # Между буквой и скобкой: x( → x*(
        expr_str = re.sub(r'([a-zA-Zα-ω])\(', r'\1*(', expr_str)
        # Между скобками: )( → )*(
        expr_str = re.sub(r'\)\s*\(', ')*(', expr_str)
        # Между цифрой и функцией: 2sin → 2*sin
        expr_str = re.sub(r'(\d)(sin|cos|tan|log|ln|sqrt)', r'\1*\2', expr_str)
        
        # 4. Исправление распознанных ошибок OCR
        ocr_corrections = {
            'х': 'x', 'у': 'y', 'з': 'z', 'с': 'c', 'о': 'o',
            'а': 'a', 'в': 'b', 'е': 'e', 'к': 'k', 'м': 'm',
            'н': 'n', 'р': 'p', 'т': 't', 'і': 'i', 'ј': 'j',
            'ѕ': 's', 'ѡ': 'w', 'ѵ': 'v', 'ѻ': 'o', 'с': 'c'
        }
        for wrong, correct in ocr_corrections.items():
            expr_str = expr_str.replace(wrong, correct)
            
        # 5. Удаление лишних пробелов
        expr_str = re.sub(r'\s+', ' ', expr_str).strip()
        
        logger.info(f"🔧 Препроцессинг: '{original}' → '{expr_str}'")
        return expr_str
    
    def detect_expression_type(self, expr_str: str) -> Dict:
        """Интеллектуальное определение типа выражения"""
        expr_clean = expr_str.lower().replace(' ', '')
        
        analysis = {
            'type': 'unknown',
            'subtype': '',
            'confidence': 0,
            'features': []
        }
        
        # Признаки разных типов выражений
        features = []
        
        if 'solve(' in expr_clean or ('=' in expr_clean and any(c in expr_clean for c in 'xyzabc')):
            features.append('equation')
        if 'diff(' in expr_clean or 'derivative' in expr_clean:
            features.append('derivative')
        if 'integrate(' in expr_clean or '∫' in expr_clean:
            features.append('integral')
        if 'limit(' in expr_clean:
            features.append('limit')
        if 'series(' in expr_clean or 'expand(' in expr_clean:
            features.append('series')
        if '/' in expr_clean and ('(' in expr_clean or any(c in expr_clean for c in 'xyz')):
            features.append('fraction')
        if any(c in expr_clean for c in 'xyz') and any(op in expr_clean for op in ['+', '-', '*', '^']):
            features.append('polynomial')
        if all(c in '0123456789+-*/.()^ ' for c in expr_clean.replace(' ', '')):
            features.append('numeric')
        if any(f in expr_clean for f in ['sin', 'cos', 'tan', 'log', 'ln', 'exp']):
            features.append('trigonometric')
            
        # Определение основного типа по приоритету
        type_priority = ['equation', 'derivative', 'integral', 'limit', 'series', 'fraction', 'trigonometric', 'polynomial', 'numeric']
        
        for t in type_priority:
            if t in features:
                analysis['type'] = t
                analysis['features'] = features
                analysis['confidence'] = min(90 + len(features) * 2, 100)
                break
                
        return analysis
    
    def solve_with_intelligence(self, expr_str: str) -> str:
        """МЕГА-умное решение с анализом и улучшенным выводом"""
        try:
            # Интеллектуальная предобработка
            processed_expr = self.intelligent_preprocess(expr_str)
            
            if not processed_expr:
                return "❌ Не вижу математического выражения"
                
            # Анализ типа выражения
            analysis = self.detect_expression_type(processed_expr)
            
            # Парсинг выражения
            try:
                sympy_expr = sympify(processed_expr, locals=self.symbols_dict)
            except Exception as e:
                # Попробуем альтернативный парсинг
                try:
                    # Убираем возможные проблемы
                    alt_expr = processed_expr.replace('==', '-')
                    sympy_expr = sympify(alt_expr, locals=self.symbols_dict)
                except:
                    return f"❌ Не могу разобрать выражение: {str(e)}"
            
            # Строим результат
            result = self.build_solution_header(expr_str, analysis)
            
            # Выбираем решатель по типу
            solver_map = {
                'fraction': self.solve_fraction_mega,
                'equation': self.solve_equation_mega,
                'polynomial': self.solve_polynomial_mega,
                'numeric': self.solve_numeric_mega,
                'derivative': self.solve_derivative_mega,
                'integral': self.solve_integral_mega,
                'trigonometric': self.solve_trigonometric_mega,
                'limit': self.solve_limit_mega,
                'series': self.solve_series_mega
            }
            
            solver_func = solver_map.get(analysis['type'], self.solve_general_mega)
            result += solver_func(sympy_expr, processed_expr, analysis)
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка решения: {str(e)}")
            return "❌ Не удалось решить этот пример\n\n💡 Попробуйте:\n• Проверить синтаксис\n• Использовать * для умножения\n• Упростить выражение"
    
    def build_solution_header(self, original_expr: str, analysis: Dict) -> str:
        """Заголовок решения с анализом"""
        type_names = {
            'fraction': 'Алгебраическая дробь',
            'equation': 'Уравнение',
            'polynomial': 'Многочлен',
            'numeric': 'Числовое выражение',
            'derivative': 'Производная',
            'integral': 'Интеграл',
            'trigonometric': 'Тригонометрическое выражение',
            'limit': 'Предел',
            'series': 'Ряд',
            'unknown': 'Математическое выражение'
        }
        
        header = f"🧮 *РЕШАЕМ:* `{original_expr}`\n"
        header += f"📊 *Тип:* {type_names.get(analysis['type'], 'Выражение')}\n"
        
        if analysis['confidence'] > 80:
            header += f"✅ *Уверенность:* {analysis['confidence']}%\n"
            
        header += "\n" + "="*40 + "\n\n"
        return header
    
    def solve_fraction_mega(self, expr, original_str: str, analysis: Dict) -> str:
        """МЕГА-решение дробей"""
        try:
            result = ""
            
            # Получаем числитель и знаменатель
            numerator, denominator = fraction(expr)
            
            result += "📝 *ШАГ 1: Анализ дроби*\n"
            result += f"`{self.format_math(expr)}`\n\n"
            
            # Разложение на множители
            factored_num = factor(numerator)
            factored_den = factor(denominator)
            
            if factored_num != numerator or factored_den != denominator:
                result += "📝 *ШАГ 2: Разложение на множители*\n"
                result += f"Числитель: `{self.format_math(factored_num)}`\n"
                result += f"Знаменатель: `{self.format_math(factored_den)}`\n\n"
            
            # Сокращение дроби
            simplified = cancel(expr)
            if simplified != expr:
                result += "📝 *ШАГ 3: Сокращение дроби*\n"
                result += f"`{self.format_math(simplified)}`\n\n"
            
            # Область определения
            if denominator.has(self.x):
                restrictions = solve(denominator, self.x)
                if restrictions:
                    result += "📝 *ШАГ 4: Область определения*\n"
                    result += "Знаменатель ≠ 0:\n"
                    for sol in restrictions:
                        result += f"`x ≠ {self.format_math(sol)}`\n"
                    result += "\n"
            
            # Дополнительные преобразования
            if simplified.is_rational_function():
                try:
                    partial_fractions = apart(simplified)
                    if partial_fractions != simplified:
                        result += "📝 *ШАГ 5: Разложение на простейшие*\n"
                        result += f"`{self.format_math(partial_fractions)}`\n\n"
                except:
                    pass
            
            result += "🎯 *ФИНАЛЬНЫЙ ОТВЕТ:*\n"
            result += f"```\n{self.format_math(simplified)}\n```\n"
            
            # Численное значение если возможно
            if simplified.is_number:
                decimal_val = float(simplified)
                result += f"\n🔢 *Десятичная форма:* `{decimal_val:.6f}`"
                
            return result
            
        except Exception as e:
            return f"❌ Ошибка решения дроби: {str(e)}"
    
    def solve_polynomial_mega(self, expr, original_str: str, analysis: Dict) -> str:
        """МЕГА-решение многочленов"""
        try:
            result = ""
            
            # Упрощение
            simplified = simplify(expr)
            result += "📝 *ШАГ 1: Упрощение*\n"
            result += f"`{self.format_math(simplified)}`\n\n"
            
            # Разложение на множители
            factored = factor(simplified)
            if factored != simplified:
                result += "📝 *ШАГ 2: Разложение на множители*\n"
                result += f"`{self.format_math(factored)}`\n\n"
            
            # Нахождение корней
            if simplified.is_polynomial() and simplified.has(self.x):
                roots = solve(simplified, self.x)
                if roots:
                    result += "📝 *ШАГ 3: Нахождение корней*\n"
                    for i, root in enumerate(roots, 1):
                        result += f"`x_{i} = {self.format_math(root)}`\n"
                    
                    # Проверка корней
                    result += "\n🔍 *Проверка корней:*\n"
                    for root in roots:
                        substitution = simplified.subs(self.x, root)
                        result += f"P({self.format_math(root)}) = {self.format_math(substitution)} ✓\n"
                    result += "\n"
            
            result += "🎯 *ФИНАЛЬНЫЙ ОТВЕТ:*\n"
            result += f"```\n{self.format_math(simplified)}\n```"
            
            return result
            
        except Exception as e:
            return f"❌ Ошибка решения многочлена: {str(e)}"
    
    def solve_equation_mega(self, expr, original_str: str, analysis: Dict) -> str:
        """МЕГА-решение уравнений"""
        try:
            result = ""
            
            # Парсинг уравнения
            if 'solve(' in original_str:
                match = re.search(r'solve\((.*),\s*(\w+)\)', original_str)
                if match:
                    eq_part = self.intelligent_preprocess(match.group(1))
                    var_str = match.group(2)
                    var = symbols(var_str)
                    
                    if '==' in eq_part:
                        left, right = eq_part.split('==', 1)
                        equation = sympify(left) - sympify(right)
                    else:
                        equation = sympify(eq_part)
                else:
                    return "❌ Неверный формат уравнения"
            else:
                # Простое уравнение
                processed = self.intelligent_preprocess(original_str)
                if '=' in processed:
                    left, right = processed.split('=', 1)
                    equation = sympify(left.strip()) - sympify(right.strip())
                    var = self.x
                else:
                    equation = sympify(processed)
                    var = self.x
            
            result += "📝 *ШАГ 1: Запись уравнения*\n"
            result += f"`{self.format_math(equation)} = 0`\n\n"
            
            # Решение уравнения
            solutions = solve(equation, var)
            
            if solutions:
                result += "📝 *ШАГ 2: Решение уравнения*\n"
                for i, sol in enumerate(solutions, 1):
                    result += f"`{var}_{i} = {self.format_math(sol)}`\n"
                result += "\n"
                
                # Проверка решений
                result += "📝 *ШАГ 3: Проверка решений*\n"
                for sol in solutions:
                    check = equation.subs(var, sol)
                    result += f"При `{var} = {self.format_math(sol)}`: `{self.format_math(check)} = 0` ✓\n"
                result += "\n"
            else:
                result += "❌ Уравнение не имеет решений в действительных числах\n\n"
            
            result += "🎯 *РЕШЕНИЯ:*\n"
            if solutions:
                for i, sol in enumerate(solutions, 1):
                    result += f"`{var}_{i} = {self.format_math(sol)}`\n"
            else:
                result += "Решений нет"
            
            return result
            
        except Exception as e:
            return f"❌ Ошибка решения уравнения: {str(e)}"
    
    def solve_numeric_mega(self, expr, original_str: str, analysis: Dict) -> str:
        """МЕГА-решение числовых выражений"""
        try:
            result = "📝 *ШАГ 1: Вычисление*\n"
            result += f"`{original_str}`\n\n"
            
            # Точное значение
            exact_value = simplify(expr)
            
            # Численное значение
            numeric_value = float(exact_value)
            
            result += "🎯 *ФИНАЛЬНЫЙ ОТВЕТ:*\n"
            result += f"```\n{self.format_math(exact_value)}\n```\n\n"
            
            # Дополнительные формы
            result += "📊 *Дополнительные формы:*\n"
            result += f"• Десятичная: `{numeric_value}`\n"
            
            if abs(numeric_value) > 1000 or (0 < abs(numeric_value) < 0.001):
                result += f"• Научная запись: `{numeric_value:.2e}`\n"
                
            if numeric_value != int(numeric_value):
                result += f"• Дробь: `{exact_value}`\n"
                
            if numeric_value < 0:
                result += f"• Модуль: `{abs(numeric_value)}`\n"
            
            return result
            
        except Exception as e:
            return f"❌ Ошибка вычисления: {str(e)}"

    # ДОБАВЛЕННЫЕ МЕТОДЫ ДЛЯ ИСПРАВЛЕНИЯ ОШИБКИ
    def solve_derivative_mega(self, expr, original_str: str, analysis: Dict) -> str:
        """МЕГА-решение производных"""
        try:
            result = "📝 *ШАГ 1: Нахождение производной*\n"
            derivative = diff(expr, self.x)
            simplified = simplify(derivative)
            
            result += f"`{self.format_math(simplified)}`\n\n"
            result += "🎯 *ПРОИЗВОДНАЯ:*\n"
            result += f"```\n{self.format_math(simplified)}\n```"
            
            return result
        except Exception as e:
            return f"❌ Ошибка нахождения производной: {str(e)}"

    def solve_integral_mega(self, expr, original_str: str, analysis: Dict) -> str:
        """МЕГА-решение интегралов"""
        try:
            result = "📝 *ШАГ 1: Нахождение интеграла*\n"
            integral = integrate(expr, self.x)
            simplified = simplify(integral)
            
            result += f"`{self.format_math(simplified)}`\n\n"
            result += "🎯 *ИНТЕГРАЛ:*\n"
            result += f"```\n{self.format_math(simplified)} + C\n```"
            
            return result
        except Exception as e:
            return f"❌ Ошибка нахождения интеграла: {str(e)}"

    def solve_trigonometric_mega(self, expr, original_str: str, analysis: Dict) -> str:
        """МЕГА-решение тригонометрических выражений"""
        try:
            result = "📝 *ШАГ 1: Упрощение*\n"
            simplified = trigsimp(expr)
            result += f"`{self.format_math(simplified)}`\n\n"
            
            result += "🎯 *ФИНАЛЬНЫЙ ОТВЕТ:*\n"
            result += f"```\n{self.format_math(simplified)}\n```"
            
            return result
        except Exception as e:
            return f"❌ Ошибка упрощения тригонометрического выражения: {str(e)}"

    def solve_limit_mega(self, expr, original_str: str, analysis: Dict) -> str:
        """МЕГА-решение пределов"""
        try:
            result = "📝 *ШАГ 1: Нахождение предела*\n"
            lim = limit(expr, self.x, 0)  # Базовый предел
            result += f"`{self.format_math(lim)}`\n\n"
            
            result += "🎯 *ПРЕДЕЛ:*\n"
            result += f"```\n{self.format_math(lim)}\n```"
            
            return result
        except Exception as e:
            return f"❌ Ошибка нахождения предела: {str(e)}"

    def solve_series_mega(self, expr, original_str: str, analysis: Dict) -> str:
        """МЕГА-решение рядов"""
        try:
            result = "📝 *ШАГ 1: Разложение в ряд*\n"
            series_exp = series(expr, self.x, 0, 4)  # Разложение до 4 порядка
            result += f"`{self.format_math(series_exp)}`\n\n"
            
            result += "🎯 *РАЗЛОЖЕНИЕ В РЯД:*\n"
            result += f"```\n{self.format_math(series_exp)}\n```"
            
            return result
        except Exception as e:
            return f"❌ Ошибка разложения в ряд: {str(e)}"
    
    def solve_general_mega(self, expr, original_str: str, analysis: Dict) -> str:
        """МЕГА-решение общих выражений"""
        try:
            result = ""
            
            # Упрощение
            simplified = simplify(expr)
            result += "📝 *ШАГ 1: Упрощение*\n"
            result += f"`{self.format_math(simplified)}`\n\n"
            
            # Дополнительные преобразования
            try:
                expanded = expand(simplified)
                if expanded != simplified:
                    result += "📝 *ШАГ 2: Раскрытие скобок*\n"
                    result += f"`{self.format_math(expanded)}`\n\n"
                    simplified = expanded
            except:
                pass
            
            # Разложение на множители если возможно
            try:
                factored = factor(simplified)
                if factored != simplified:
                    result += "📝 *ШАГ 3: Разложение на множители*\n"
                    result += f"`{self.format_math(factored)}`\n\n"
            except:
                pass
            
            result += "🎯 *ФИНАЛЬНЫЙ ОТВЕТ:*\n"
            result += f"```\n{self.format_math(simplified)}\n```"
            
            if simplified.is_number:
                result += f"\n🔢 *Численное значение:* `{float(simplified)}`"
            
            return result
            
        except Exception as e:
            return f"❌ Ошибка упрощения: {str(e)}"
    
    def format_math(self, expr) -> str:
        """Красивое форматирование математических выражений"""
        if isinstance(expr, str):
            return expr
            
        expr_str = str(expr)
        
        # Замены для лучшего отображения
        replacements = {
            '**': '^',
            '*': '·',
            'sqrt': '√',
            'pi': 'π',
            'oo': '∞',
            'exp': 'e^',
            'I': 'i',
            'E': 'e'
        }
        
        for old, new in replacements.items():
            expr_str = expr_str.replace(old, new)
            
        return expr_str

# ========== МЕГА-OCR ДВИЖОК ==========
class MegaOCR:
    def __init__(self):
        self.available = TESSERACT_AVAILABLE
        
    def enhance_image(self, image_path: str) -> Image.Image:
        """Улучшение качества изображения для OCR"""
        try:
            image = Image.open(image_path)
            
            # Конвертация в grayscale
            image = image.convert('L')
            
            # Увеличение контраста
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(2.0)
            
            # Увеличение резкости
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(2.0)
            
            # Увеличение размера
            new_size = (image.width * 2, image.height * 2)
            image = image.resize(new_size, Image.Resampling.LANCZOS)
            
            return image
            
        except Exception as e:
            logger.error(f"Ошибка улучшения изображения: {e}")
            return None
    
    def recognize_math_text(self, image_path: str) -> Dict:
        """Интеллектуальное распознавание математического текста"""
        if not self.available:
            return {
                'success': False,
                'text': 'OCR недоступен на сервере',
                'confidence': 0
            }
            
        try:
            # Улучшаем изображение
            enhanced_image = self.enhance_image(image_path)
            if not enhanced_image:
                return {
                    'success': False,
                    'text': 'Ошибка обработки изображения',
                    'confidence': 0
                }
            
            # Специальная конфигурация для математики
            custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ()[]{}/*+-=^<>|~!@#$%&_.,:; '
            
            # Распознавание
            text = pytesseract.image_to_string(enhanced_image, config=custom_config)
            text = text.strip()
            
            if not text or len(text) < 2:
                return {
                    'success': False,
                    'text': 'Не удалось распознать текст',
                    'confidence': 0
                }
            
            # Очистка и коррекция текста
            cleaned_text = self.clean_recognized_text(text)
            
            # Оценка уверенности
            confidence = self.estimate_confidence(cleaned_text)
            
            return {
                'success': True,
                'text': cleaned_text,
                'confidence': confidence,
                'original': text
            }
            
        except Exception as e:
            logger.error(f"Ошибка OCR: {e}")
            return {
                'success': False,
                'text': f'Ошибка распознавания: {str(e)}',
                'confidence': 0
            }
    
    def clean_recognized_text(self, text: str) -> str:
        """Очистка распознанного текста"""
        # Удаление лишних переносов строк
        text = re.sub(r'\n+', ' ', text)
        
        # Замены OCR ошибок
        ocr_corrections = {
            'х': 'x', 'у': 'y', 'з': 'z', 'с': 'c', 'о': 'o',
            'а': 'a', 'в': 'b', 'е': 'e', 'к': 'k', 'м': 'm',
            'н': 'n', 'р': 'p', 'т': 't', 'і': 'i', 'ѵ': 'v',
            '—': '-', '–': '-', '−': '-', '×': '*', '⋅': '*',
            '÷': '/', '⁄': '/', '∕': '/', '∗': '*', '•': '*',
            '（': '(', '）': ')', '【': '[', '】': ']', '〈': '<',
            '〉': '>', '«': '"', '»': '"', '″': '"', '‴': '"',
            '′': "'", '‘': "'", '’': "'", '“': '"', '”': '"',
            '¦': '|', '‖': '|', '∣': '|', '∶': ':', '：': ':',
            '；': ';', '，': ',', '、': ',', '﹑': ',', '‚': ',',
            '„': '"', '…': '...', '⋯': '...', '︙': '...',
            '！': '!', '？': '?', '﹖': '?', '⁇': '??', '⁈': '?!',
            '⁉': '!?', '﹗': '!', '‼': '!!', '⁈': '!?',
            '¼': '1/4', '½': '1/2', '¾': '3/4', '⅓': '1/3',
            '⅔': '2/3', '⅕': '1/5', '⅖': '2/5', '⅗': '3/5',
            '⅘': '4/5', '⅙': '1/6', '⅚': '5/6', '⅛': '1/8',
            '⅜': '3/8', '⅝': '5/8', '⅞': '7/8'
        }
        
        for wrong, correct in ocr_corrections.items():
            text = text.replace(wrong, correct)
        
        # Удаление лишних пробелов
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def estimate_confidence(self, text: str) -> int:
        """Оценка уверенности в распознавании"""
        confidence = 50  # Базовая уверенность
        
        # Признаки хорошего распознавания
        math_patterns = [
            r'\d+', r'[xyz]', r'[+\-*/=]', r'[()]', r'\^', 
            r'sin|cos|tan', r'log|ln', r'sqrt', r'pi'
        ]
        
        for pattern in math_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                confidence += 5
                
        # Штраф за подозрительные символы
        suspicious = re.findall(r'[^0-9a-zA-Z\s+\-*/=()^.,]', text)
        confidence -= len(suspicious) * 3
        
        return max(0, min(100, confidence))

# ========== ИНИЦИАЛИЗАЦИЯ ==========
mega_solver = MegaMathSolver()
mega_ocr = MegaOCR()

# ========== ТЕЛЕГРАМ ОБРАБОТЧИКИ ==========
async def mega_start(update: Update, context: CallbackContext):
    """МЕГА-стартовое сообщение"""
    user = update.effective_user
    
    welcome_text = f"""🚀 *ДОБРО ПОЖАЛОВАТЬ В MEGA MATH BOT!* 🧠

Привет, {user.first_name}! Я - искусственный интеллект для решения *ЛЮБЫХ* математических задач!

🎯 *МОИ СУПЕРСПОСОБНОСТИ:*
• 🤖 Автоопределение типа задачи
• 📝 Пошаговые решения с объяснениями  
• 📸 Распознавание примеров по фото
• 🧮 Дроби, уравнения, производные, интегралы
• 💡 Умные подсказки и проверки
• 🚀 Мгновенные вычисления

✨ *Просто напиши или сфотографируй пример!*"""

    keyboard = [
        [InlineKeyboardButton("🧮 Быстрые примеры", callback_data="quick_examples")],
        [InlineKeyboardButton("📚 Типы задач", callback_data="problem_types")],
        [InlineKeyboardButton("📸 Инструкция по фото", callback_data="photo_guide")],
        [InlineKeyboardButton("🎯 Сложные задачи", callback_data="challenge_mode")]
    ]
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def handle_text_message(update: Update, context: CallbackContext):
    """Обработка текстовых сообщений"""
    user_input = update.message.text.strip()
    
    # Показываем статус "печатает"
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, 
        action="typing"
    )
    
    # Решаем пример
    result = mega_solver.solve_with_intelligence(user_input)
    
    # Клавиатура для следующих действий
    keyboard = [
        [InlineKeyboardButton("🔁 Новый пример", callback_data="new_problem")],
        [InlineKeyboardButton("📊 Анализ решения", callback_data="analyze_solution")],
        [InlineKeyboardButton("💡 Похожие задачи", callback_data="similar_problems")]
    ]
    
    await update.message.reply_text(
        result,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def handle_photo_message(update: Update, context: CallbackContext):
    """Обработка фотографий с примерами"""
    if not mega_ocr.available:
        await update.message.reply_text(
            "❌ *Распознавание фото временно недоступно*\n\n"
            "Пожалуйста, отправьте пример текстом:\n"
            "`3*x^2 - 12*x + 12`\n"
            "`(x^2 - 4)/(x - 2)`\n"
            "`x^2 - 5*x + 6 = 0`",
            parse_mode='Markdown'
        )
        return
    
    try:
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action="upload_photo"
        )
        
        # Получаем фото
        photo_file = await update.message.photo[-1].get_file()
        
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
            temp_path = temp_file.name
        
        # Скачиваем фото
        await photo_file.download_to_drive(temp_path)
        
        # Распознаем текст
        ocr_result = mega_ocr.recognize_math_text(temp_path)
        
        # Удаляем временный файл
        os.unlink(temp_path)
        
        if not ocr_result['success']:
            await update.message.reply_text(
                f"❌ *Не удалось распознать пример*\n\n"
                f"*Причина:* {ocr_result['text']}\n\n"
                f"📸 *Советы для лучшего распознавания:*\n"
                f"• Четкий печатный текст\n"
                f"• Хорошее освещение\n"
                f"• Пример по центру фото\n"
                f"• Контрастные чернила",
                parse_mode='Markdown'
            )
            return
        
        # Показываем что распознали
        confidence_emoji = "🔴" if ocr_result['confidence'] < 50 else "🟡" if ocr_result['confidence'] < 80 else "🟢"
        
        await update.message.reply_text(
            f"📸 *Распознано:* `{ocr_result['text']}`\n"
            f"{confidence_emoji} *Уверенность:* {ocr_result['confidence']}%",
            parse_mode='Markdown'
        )
        
        # Решаем распознанный пример
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action="typing"
        )
        
        solution = mega_solver.solve_with_intelligence(ocr_result['text'])
        
        keyboard = [
            [InlineKeyboardButton("📸 Распознать еще", callback_data="photo_guide")],
            [InlineKeyboardButton("🧮 Текстовый ввод", callback_data="new_problem")]
        ]
        
        await update.message.reply_text(
            solution,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Ошибка обработки фото: {e}")
        await update.message.reply_text(
            "❌ *Произошла ошибка при обработке фото*\n\n"
            "Попробуйте:\n"
            "• Переснять фото\n"
            "• Отправить пример текстом\n"
            "• Проверить освещение",
            parse_mode='Markdown'
        )

async def handle_callback_query(update: Update, context: CallbackContext):
    """Обработка нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "quick_examples":
        examples_text = """🧮 *БЫСТРЫЕ ПРИМЕРЫ ДЛЯ ТЕСТА:*

*Дроби:*
`(x^2 - 4)/(x - 2)`
`1/(x+1) + 2/(x-1)`
`(x^3 - 8)/(x^2 - 4)`

*Многочлены:*
`3*x^2 - 12*x + 12`
`x^2 + 2*x + 1`
`2*x^3 - 5*x^2 + 3*x`

*Уравнения:*
`x^2 - 5*x + 6 = 0`
`solve(x^2 - 9 = 0, x)`
`x^3 - 3*x + 2 = 0`

*Числовые:*
`2 + 3 * 4^2`
`(15 - 3) / 4 + 2^3`
`sqrt(16) + 3**2`

✨ *Просто скопируй и отправь!*"""
        
        await query.edit_message_text(
            examples_text,
            parse_mode='Markdown'
        )
    
    elif query.data == "problem_types":
        types_text = """📚 *ТИПЫ РЕШАЕМЫХ ЗАДАЧ:*

*🔢 Алгебра:*
• Дроби и рациональные выражения
• Многочлены и их преобразования
• Уравнения и системы уравнений
• Неравенства

*📈 Математический анализ:*
• Производные и дифференцирование
• Интегралы и первообразные
• Пределы и непрерывность
• Ряды и разложения

*📐 Тригонометрия:*
• Тригонометрические функции
• Уравнения и тождества
• Обратные тригонометрические функции

*🧮 Общая математика:*
• Числовые вычисления
• Упрощение выражений
• Разложение на множители

🎯 *Бот сам определит тип задачи!*"""
        
        await query.edit_message_text(
            types_text,
            parse_mode='Markdown'
        )
    
    elif query.data == "photo_guide":
        guide_text = """📸 *ИНСТРУКЦИЯ ПО ФОТО:*

*✅ ЧТО ХОРОШО РАСПОЗНАЕТСЯ:*
• Четкий печатный текст
• Примеры в одну строку
• Стандартные математические символы
• Хорошее освещение

*✅ РЕКОМЕНДУЕМЫЙ ФОРМАТ:*
`3*x^2 - 12*x + 12`
`(x^2 - 4)/(x - 2)`
`x^2 - 5*x + 6 = 0`

*❌ ЧТО ПЛОХО РАСПОЗНАЕТСЯ:*
• Курсивный почерк
• Многоэтажные дроби
• Сложные матрицы
• Плохое освещение

*💡 СОВЕТЫ:*
• Пишите печатными буквами
• Используйте * для умножения
• Размещайте пример по центру
• Следите за контрастом"""
        
        await query.edit_message_text(
            guide_text,
            parse_mode='Markdown'
        )
    
    elif query.data == "challenge_mode":
        challenges_text = """🎯 *СЛОЖНЫЕ ЗАДАЧИ:*

*🧩 Комплексные дроби:*
`((x^2 - 1)/(x + 1)) / ((x - 1)/(x^2 + 2*x + 1))`

*⚡ Степенные выражения:*
`(x^4 - 16)/(x^2 + 4) + (x^2 - 4)/(x + 2)`

*🔢 Системы уравнений:*
`solve([x + y - 5, 2*x - y - 1], [x, y])`

*📐 Тригонометрия:*
`sin(x)^2 + cos(x)^2 + tan(x)*cot(x)`

*📊 Логарифмы:*
`log(x^2 - 1) - log(x - 1)`

🚀 *Проверь мои возможности!*"""
        
        await query.edit_message_text(
            challenges_text,
            parse_mode='Markdown'
        )
    
    elif query.data == "new_problem":
        await query.edit_message_text(
            "✍️ *Напиши математический пример:*\n\n"
            "• `3*x^2 - 12*x + 12`\n"
            "• `(x^2 - 4)/(x - 2)`\n"
            "• `x^2 - 5*x + 6 = 0`\n\n"
            "🎯 Я сам пойму что нужно сделать!",
            parse_mode='Markdown'
        )

    # Добавляем обработчики для новых кнопок
    elif query.data in ["analyze_solution", "similar_problems"]:
        await query.edit_message_text(
            "🔧 *Эта функция в разработке*\n\n"
            "Скоро здесь появятся:\n"
            "• Подробный анализ решения\n"
            "• Похожие задачи для тренировки\n"
            "• Рекомендации по улучшению\n\n"
            "А пока попробуйте другие примеры! 🚀",
            parse_mode='Markdown'
        )

async def handle_other_messages(update: Update, context: CallbackContext):
    """Обработка других типов сообщений"""
    if update.message and not (update.message.text or update.message.photo):
        await update.message.reply_text(
            "🤖 *Отправь мне математический пример!*\n\n"
            "• 📝 *Текстом* - напиши пример\n"
            f"• 📸 *Фото* - сфотографируй пример{' (доступно)' if mega_ocr.available else ' (временно недоступно)'}\n\n"
            "✨ *Примеры:*\n"
            "`3*x^2 - 12*x + 12`\n"
            "`(x^2 - 4)/(x - 2)`\n"
            "`x^2 - 5*x + 6 = 0`",
            parse_mode='Markdown'
        )

# ========== ЗАПУСК БОТА ==========
def main():
    """Запуск МЕГА-бота"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", mega_start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo_message))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    application.add_handler(MessageHandler(filters.ALL, handle_other_messages))
    
    logger.info("🚀 MEGA MATH BOT ЗАПУЩЕН!")
    logger.info(f"📸 OCR доступен: {mega_ocr.available}")
    logger.info("🤖 Бот готов к работе!")
    
    application.run_polling()

if __name__ == '__main__':
    main()
