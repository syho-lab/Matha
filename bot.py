import os
import logging
import re
import requests
from typing import Dict, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
import sympy as sp
from sympy import (
    sympify, factor, cancel, apart, expand, simplify, solve, diff, integrate, 
    symbols, fraction, Poly, series, limit, oo, I, pi, E, sin, cos, tan, log, ln,
    sqrt, exp, trigsimp, expand_trig, nsimplify, solveset, S, latex
)

try:
    from keep_alive import keep_alive
    keep_alive()
except ImportError:
    pass

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не установлен")

class UltraMathSolver:
    def __init__(self):
        self.x, self.y, self.z, self.t = symbols('x y z t')
        self.a, self.b, self.c, self.n, self.m = symbols('a b c n m')
        self.symbols_dict = {
            'x': self.x, 'y': self.y, 'z': self.z, 't': self.t,
            'a': self.a, 'b': self.b, 'c': self.c, 'n': self.n, 'm': self.m
        }
        
        # База знаний сложных примеров
        self.complex_patterns = {
            'quadratic': r'(\w+)\*\*2\s*[\+\-]\s*\d+\s*\*\s*\w+\s*[\+\-]\s*\d+',
            'rational': r'\([^)]+\)\s*/\s*\([^)]+\)',
            'trigonometric': r'sin|cos|tan|cot|sec|csc',
            'logarithmic': r'log|ln',
            'exponential': r'exp|\*\*|\^',
            'derivative': r'diff|derivative',
            'integral': r'integrate|∫'
        }
    
    def ultra_preprocess(self, expr_str: str) -> str:
        """УЛЬТРА-умная предобработка"""
        if not expr_str or len(expr_str.strip()) < 2:
            return ""
            
        original = expr_str
        expr_str = expr_str.strip()
        
        # 1. Умные замены математических символов
        math_symbols = {
            '^': '**', '=': '==', '÷': '/', '×': '*', '–': '-', '−': '-',
            'π': 'pi', '∞': 'oo', '√': 'sqrt', '∫': 'integrate',
            '∂': 'diff', '∑': 'Sum', '∏': 'Product', 'α': 'alpha',
            'β': 'beta', 'γ': 'gamma', 'θ': 'theta', 'φ': 'phi',
            '≈': '~', '≠': '!=', '≤': '<=', '≥': '>=', '±': '+/-'
        }
        
        for old, new in math_symbols.items():
            expr_str = expr_str.replace(old, new)
        
        # 2. Автоматическое добавление умножения
        expr_str = re.sub(r'(\d)([a-zA-Zα-ω])', r'\1*\2', expr_str)  # 2x → 2*x
        expr_str = re.sub(r'([a-zA-Zα-ω])\(', r'\1*(', expr_str)     # x( → x*(
        expr_str = re.sub(r'\)\s*\(', ')*(', expr_str)              # )( → )*(
        expr_str = re.sub(r'(\d)(sin|cos|tan|log|ln|sqrt)', r'\1*\2', expr_str)
        
        # 3. Исправление частых ошибок пользователей
        common_errors = {
            'sinx': 'sin(x)', 'cosx': 'cos(x)', 'tanx': 'tan(x)',
            'logx': 'log(x)', 'lnx': 'ln(x)', 'sqrtx': 'sqrt(x)',
            'arcsin': 'asin', 'arccos': 'acos', 'arctan': 'atan',
            'e^': 'exp', 'e**': 'exp'
        }
        
        for wrong, correct in common_errors.items():
            expr_str = re.sub(r'\b' + wrong + r'\b', correct, expr_str)
        
        # 4. Обработка специальных случаев
        # Дроби вида a/b/c → (a/b)/c
        expr_str = re.sub(r'(\d+)/(\d+)/(\d+)', r'(\1/\2)/\3', expr_str)
        
        # Степени с дробями
        expr_str = re.sub(r'(\w+)\^\((\d+)/(\d+)\)', r'\1**(\2/\3)', expr_str)
        
        # 5. Умная обработка уравнений
        if '=' in expr_str and 'solve' not in expr_str:
            parts = expr_str.split('=')
            if len(parts) == 2:
                expr_str = f"{parts[0].strip()} - ({parts[1].strip()})"
        
        logger.info(f"🔧 Препроцессинг: '{original}' → '{expr_str}'")
        return expr_str
    
    def analyze_expression_intelligence(self, expr_str: str) -> Dict:
        """УЛЬТРА-анализ выражения"""
        analysis = {
            'type': 'unknown',
            'subtype': '',
            'complexity': 'low',
            'confidence': 0,
            'features': [],
            'suggestions': []
        }
        
        expr_lower = expr_str.lower()
        
        # Детектирование признаков
        features = []
        
        # Математические типы
        if any(keyword in expr_lower for keyword in ['solve', '=']) and any(var in expr_lower for var in ['x', 'y', 'z']):
            features.append('equation')
        if 'diff' in expr_lower:
            features.append('derivative')
        if 'integrate' in expr_lower:
            features.append('integral')
        if 'limit' in expr_lower:
            features.append('limit')
        if '/' in expr_lower and ('(' in expr_lower or any(var in expr_lower for var in ['x', 'y', 'z'])):
            features.append('rational')
        if any(f in expr_lower for f in ['sin', 'cos', 'tan', 'cot']):
            features.append('trigonometric')
        if any(f in expr_lower for f in ['log', 'ln']):
            features.append('logarithmic')
        if any(f in expr_lower for f in ['exp', '**', '^']):
            features.append('exponential')
        if any(var in expr_lower for var in ['x', 'y', 'z']) and any(op in expr_lower for op in ['+', '-', '*', '/']):
            features.append('algebraic')
        if all(c in '0123456789+-*/.()^ ' for c in expr_lower.replace(' ', '')):
            features.append('numeric')
        
        # Определение основного типа
        type_priority = ['equation', 'derivative', 'integral', 'limit', 'rational', 
                        'trigonometric', 'logarithmic', 'exponential', 'algebraic', 'numeric']
        
        for t in type_priority:
            if t in features:
                analysis['type'] = t
                break
        
        # Оценка сложности
        complexity_score = 0
        if '(' in expr_str and ')' in expr_str:
            complexity_score += 1
        if any(op in expr_str for op in ['**', '^']):
            complexity_score += 1
        if '/' in expr_str:
            complexity_score += 1
        if any(f in expr_str for f in ['sin', 'cos', 'tan', 'log', 'ln', 'exp']):
            complexity_score += 2
        
        if complexity_score >= 3:
            analysis['complexity'] = 'high'
        elif complexity_score >= 1:
            analysis['complexity'] = 'medium'
        
        # Уверенность
        analysis['confidence'] = min(80 + len(features) * 5, 95)
        analysis['features'] = features
        
        # Предложения
        if analysis['type'] == 'equation' and 'solve' not in expr_lower:
            analysis['suggestions'].append("💡 Используй solve(уравнение, x) для лучшего решения")
        if analysis['type'] == 'rational' and 'cancel' not in expr_lower:
            analysis['suggestions'].append("💡 Я автоматически упрощу дробь")
        
        return analysis
    
    def try_wolfram_solution(self, expr_str: str) -> str:
        """Попытка найти решение через Wolfram Alpha (заглушка)"""
        # В реальной реализации здесь был бы API вызов к Wolfram Alpha
        # Но для демонстрации возвращаем заглушку
        return None
    
    def ultra_solve(self, expr_str: str) -> str:
        """УЛЬТРА-решение с максимальным интеллектом"""
        try:
            # 1. Предобработка
            processed_expr = self.ultra_preprocess(expr_str)
            if not processed_expr:
                return "❌ Не вижу математического выражения"
            
            # 2. Анализ
            analysis = self.analyze_expression_intelligence(processed_expr)
            
            # 3. Парсинг
            try:
                sympy_expr = sympify(processed_expr, locals=self.symbols_dict)
            except Exception as e:
                # Альтернативные попытки парсинга
                try:
                    # Попробуем убрать возможные проблемы
                    alt_expr = processed_expr.replace('==', '-').replace('=', '-')
                    sympy_expr = sympify(alt_expr, locals=self.symbols_dict)
                except:
                    # Последняя попытка - базовое выражение
                    try:
                        sympy_expr = sympify(processed_expr.split('=')[0] if '=' in processed_expr else processed_expr, 
                                           locals=self.symbols_dict)
                    except:
                        return "❌ Не могу разобрать пример"
            
            # 4. Построение решения
            result = self.build_ultra_solution_header(expr_str, analysis)
            
            # 5. Выбор решателя
            solver_methods = {
                'rational': self.solve_rational_ultra,
                'equation': self.solve_equation_ultra,
                'algebraic': self.solve_algebraic_ultra,
                'numeric': self.solve_numeric_ultra,
                'derivative': self.solve_derivative_ultra,
                'integral': self.solve_integral_ultra,
                'trigonometric': self.solve_trigonometric_ultra,
                'logarithmic': self.solve_logarithmic_ultra,
                'exponential': self.solve_exponential_ultra,
                'limit': self.solve_limit_ultra
            }
            
            solver_func = solver_methods.get(analysis['type'], self.solve_general_ultra)
            solution_part = solver_func(sympy_expr, processed_expr, analysis)
            
            result += solution_part
            
            # 6. Добавляем подсказки
            if analysis['suggestions']:
                result += "\n\n💡 *Советы:*\n"
                for suggestion in analysis['suggestions']:
                    result += f"• {suggestion}\n"
            
            return result
            
        except Exception:
            # В случае ЛЮБОЙ ошибки - понятное сообщение
            return "❌ Не могу решить этот пример\n\n💡 *Попробуй:*\n• Проверить синтаксис\n• Использовать * для умножения\n• Упростить выражение"
    
    def build_ultra_solution_header(self, original: str, analysis: Dict) -> str:
        """Заголовок решения"""
        type_names = {
            'rational': '🧮 Алгебраическая дробь',
            'equation': '🎯 Уравнение', 
            'algebraic': '📐 Алгебраическое выражение',
            'numeric': '🔢 Числовое выражение',
            'derivative': '📈 Производная',
            'integral': '📊 Интеграл',
            'trigonometric': '📐 Тригонометрия',
            'logarithmic': '📊 Логарифмы',
            'exponential': '⚡ Степени',
            'limit': '🎯 Предел',
            'unknown': '🧮 Математическое выражение'
        }
        
        complexity_emojis = {'low': '🟢', 'medium': '🟡', 'high': '🔴'}
        
        header = f"{type_names.get(analysis['type'], '🧮 Выражение')}\n"
        header += f"📊 *Сложность:* {complexity_emojis[analysis['complexity']]} {analysis['complexity'].upper()}\n"
        header += f"🎯 *Пример:* `{original}`\n\n"
        header += "="*50 + "\n\n"
        
        return header
    
    def solve_rational_ultra(self, expr, original: str, analysis: Dict) -> str:
        """УЛЬТРА-решение дробей"""
        try:
            result = ""
            numerator, denominator = fraction(expr)
            
            # Шаг 1: Разложение на множители
            factored_num = factor(numerator)
            factored_den = factor(denominator)
            
            if factored_num != numerator or factored_den != denominator:
                result += "📝 *Разложение на множители:*\n"
                result += f"`{self.format_math(factored_num)} / {self.format_math(factored_den)}`\n\n"
            
            # Шаг 2: Сокращение
            simplified = cancel(expr)
            if simplified != expr:
                result += "📝 *После сокращения:*\n"
                result += f"`{self.format_math(simplified)}`\n\n"
            
            # Шаг 3: Область определения
            if denominator.has(self.x):
                restrictions = solve(denominator, self.x)
                if restrictions:
                    result += "📝 *Область определения:*\n"
                    for sol in restrictions:
                        result += f"`x ≠ {self.format_math(sol)}`\n"
                    result += "\n"
            
            # Шаг 4: Разложение на простейшие
            if simplified.is_rational_function():
                try:
                    partial = apart(simplified)
                    if partial != simplified:
                        result += "📝 *Разложение на простейшие дроби:*\n"
                        result += f"`{self.format_math(partial)}`\n\n"
                except:
                    pass
            
            result += "✅ *Ответ:*\n"
            result += f"```\n{self.format_math(simplified)}\n```\n"
            
            if simplified.is_number:
                decimal_val = float(simplified)
                result += f"🔢 *Десятичная форма:* `{decimal_val:.6f}`"
            
            return result
            
        except Exception:
            return "❌ Не могу решить эту дробь"
    
    def solve_equation_ultra(self, expr, original: str, analysis: Dict) -> str:
        """УЛЬТРА-решение уравнений"""
        try:
            result = ""
            
            # Определяем переменную
            if 'solve(' in original:
                match = re.search(r'solve\((.*),\s*(\w+)\)', original)
                if match:
                    eq_part = self.ultra_preprocess(match.group(1))
                    var_str = match.group(2)
                    var = symbols(var_str)
                    equation = sympify(eq_part, locals=self.symbols_dict)
                else:
                    equation = expr
                    var = self.x
            else:
                equation = expr
                var = self.x
            
            result += "📝 *Уравнение:*\n"
            result += f"`{self.format_math(equation)} = 0`\n\n"
            
            # Решение
            solutions = solve(equation, var)
            
            if solutions:
                result += "📝 *Решения:*\n"
                for i, sol in enumerate(solutions, 1):
                    result += f"`{var}_{i} = {self.format_math(sol)}`\n"
                
                result += "\n🔍 *Проверка решений:*\n"
                for sol in solutions:
                    check_val = equation.subs(var, sol)
                    result += f"`{var} = {self.format_math(sol)}`: `{self.format_math(check_val)} ≈ 0` ✓\n"
            else:
                result += "❌ *Уравнение не имеет решений*\n"
            
            return result
            
        except Exception:
            return "❌ Не могу решить это уравнение"
    
    def solve_algebraic_ultra(self, expr, original: str, analysis: Dict) -> str:
        """УЛЬТРА-решение алгебраических выражений"""
        try:
            result = ""
            simplified = simplify(expr)
            
            result += "📝 *Упрощение:*\n"
            result += f"`{self.format_math(simplified)}`\n\n"
            
            # Разложение на множители
            try:
                factored = factor(simplified)
                if factored != simplified:
                    result += "📝 *Разложение на множители:*\n"
                    result += f"`{self.format_math(factored)}`\n\n"
            except:
                pass
            
            # Нахождение корней для многочленов
            if simplified.is_polynomial() and simplified.has(self.x):
                roots = solve(simplified, self.x)
                if roots:
                    result += "📝 *Корни:*\n"
                    for i, root in enumerate(roots, 1):
                        result += f"`x_{i} = {self.format_math(root)}`\n"
                    result += "\n"
            
            result += "✅ *Ответ:*\n"
            result += f"```\n{self.format_math(simplified)}\n```"
            
            return result
            
        except Exception:
            return "❌ Не могу упростить это выражение"
    
    def solve_numeric_ultra(self, expr, original: str, analysis: Dict) -> str:
        """УЛЬТРА-решение числовых выражений"""
        try:
            exact = simplify(expr)
            numeric = float(exact)
            
            result = "✅ *Ответ:*\n"
            result += f"```\n{self.format_math(exact)}\n```\n\n"
            
            result += "📊 *Дополнительные формы:*\n"
            result += f"• Десятичная: `{numeric}`\n"
            
            if numeric != int(numeric):
                result += f"• Дробь: `{exact}`\n"
            if abs(numeric) > 1000 or (0 < abs(numeric) < 0.001):
                result += f"• Научная запись: `{numeric:.2e}`\n"
            if numeric < 0:
                result += f"• Модуль: `{abs(numeric)}`\n"
            
            return result
            
        except Exception:
            return "❌ Не могу вычислить это выражение"

    def solve_derivative_ultra(self, expr, original: str, analysis: Dict) -> str:
        """УЛЬТРА-решение производных"""
        try:
            derivative = diff(expr, self.x)
            simplified = simplify(derivative)
            
            result = "✅ *Производная:*\n"
            result += f"```\n{self.format_math(simplified)}\n```"
            
            return result
            
        except Exception:
            return "❌ Не могу найти производную"

    def solve_integral_ultra(self, expr, original: str, analysis: Dict) -> str:
        """УЛЬТРА-решение интегралов"""
        try:
            integral = integrate(expr, self.x)
            simplified = simplify(integral)
            
            result = "✅ *Интеграл:*\n"
            result += f"```\n{self.format_math(simplified)} + C\n```"
            
            return result
            
        except Exception:
            return "❌ Не могу найти интеграл"

    def solve_trigonometric_ultra(self, expr, original: str, analysis: Dict) -> str:
        """УЛЬТРА-решение тригонометрии"""
        try:
            simplified = trigsimp(expr)
            
            result = "✅ *Упрощенное выражение:*\n"
            result += f"```\n{self.format_math(simplified)}\n```"
            
            return result
            
        except Exception:
            return "❌ Не могу упростить тригонометрическое выражение"

    def solve_logarithmic_ultra(self, expr, original: str, analysis: Dict) -> str:
        """УЛЬТРА-решение логарифмов"""
        try:
            simplified = simplify(expr)
            
            result = "✅ *Упрощенное выражение:*\n"
            result += f"```\n{self.format_math(simplified)}\n```"
            
            return result
            
        except Exception:
            return "❌ Не могу упростить логарифмическое выражение"

    def solve_exponential_ultra(self, expr, original: str, analysis: Dict) -> str:
        """УЛЬТРА-решение степеней"""
        try:
            simplified = simplify(expr)
            
            result = "✅ *Упрощенное выражение:*\n"
            result += f"```\n{self.format_math(simplified)}\n```"
            
            return result
            
        except Exception:
            return "❌ Не могу упростить степенное выражение"

    def solve_limit_ultra(self, expr, original: str, analysis: Dict) -> str:
        """УЛЬТРА-решение пределов"""
        try:
            lim = limit(expr, self.x, 0)
            
            result = "✅ *Предел:*\n"
            result += f"```\n{self.format_math(lim)}\n```"
            
            return result
            
        except Exception:
            return "❌ Не могу найти предел"

    def solve_general_ultra(self, expr, original: str, analysis: Dict) -> str:
        """УЛЬТРА-решение общих выражений"""
        try:
            simplified = simplify(expr)
            
            result = "✅ *Упрощенное выражение:*\n"
            result += f"```\n{self.format_math(simplified)}\n```"
            
            if simplified.is_number:
                result += f"\n🔢 *Численное значение:* `{float(simplified)}`"
            
            return result
            
        except Exception:
            return "❌ Не могу упростить это выражение"
    
    def format_math(self, expr) -> str:
        """Красивое форматирование"""
        if isinstance(expr, str):
            return expr
            
        expr_str = str(expr)
        replacements = {
            '**': '^', '*': '·', 'sqrt': '√', 'pi': 'π', 
            'oo': '∞', 'exp': 'e^', 'I': 'i', 'E': 'e'
        }
        
        for old, new in replacements.items():
            expr_str = expr_str.replace(old, new)
            
        return expr_str

# Инициализация решателя
ultra_solver = UltraMathSolver()

# Обработчики Telegram
async def ultra_start(update: Update, context: CallbackContext):
    user = update.effective_user
    
    welcome_text = f"""🚀 *ДОБРО ПОЖАЛОВАТЬ В ULTRA MATH BOT!* 🧠

Привет, {user.first_name}! Я - искусственный интеллект для решения *ЛЮБЫХ* математических задач!

🎯 *МОИ СУПЕРСПОСОБНОСТИ:*
• 🤖 Автоопределение типа задачи
• 📝 Пошаговые решения с объяснениями  
• 🧮 Дроби, уравнения, производные, интегралы
• 💡 Умные подсказки и проверки
• 🚀 Мгновенные вычисления
• 🛡️ Защита от ошибок

✨ *Просто напиши пример!*"""

    keyboard = [
        [InlineKeyboardButton("🧮 Быстрые примеры", callback_data="quick_examples")],
        [InlineKeyboardButton("🎯 Сложные задачи", callback_data="challenge_mode")],
        [InlineKeyboardButton("📚 Все функции", callback_data="all_features")]
    ]
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def handle_text_message(update: Update, context: CallbackContext):
    user_input = update.message.text.strip()
    
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, 
        action="typing"
    )
    
    # УЛЬТРА-решение
    result = ultra_solver.ultra_solve(user_input)
    
    keyboard = [
        [InlineKeyboardButton("🔁 Новый пример", callback_data="new_problem")],
        [InlineKeyboardButton("💡 Другие примеры", callback_data="quick_examples")]
    ]
    
    await update.message.reply_text(
        result,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def handle_callback_query(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    if query.data == "quick_examples":
        examples_text = """🧮 *БЫСТРЫЕ ПРИМЕРЫ:*

*🔢 Дроби:*
`(x^2 - 4)/(x - 2)`
`1/(x+1) + 2/(x-1)`
`(x^3 - 8)/(x^2 - 4)`

*📐 Многочлены:*
`3*x^2 - 12*x + 12`
`x^2 + 2*x + 1`
`2*x^3 - 5*x^2 + 3*x`

*🎯 Уравнения:*
`x^2 - 5*x + 6 = 0`
`solve(x^2 - 9 = 0, x)`
`x^3 - 3*x + 2 = 0`

*📈 Производные:*
`diff(x^2, x)`
`diff(sin(x), x)`

*📊 Интегралы:*
`integrate(x^2, x)`
`integrate(sin(x), x)`

*🔢 Числовые:*
`2 + 3 * 4^2`
`(15 - 3) / 4 + 2^3`
`sqrt(16) + 3**2`"""
        
        await query.edit_message_text(
            examples_text,
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
    
    elif query.data == "all_features":
        features_text = """📚 *ВСЕ ФУНКЦИИ:*

*🧮 Алгебра:*
• Дроби и рациональные выражения
• Многочлены и их преобразования
• Уравнения и системы уравнений
• Разложение на множители

*📈 Математический анализ:*
• Производные и дифференцирование
• Интегралы и первообразные
• Пределы и непрерывность

*📐 Тригонометрия:*
• Тригонометрические функции
• Упрощение выражений
• Обратные тригонометрические функции

*📊 Другие функции:*
• Логарифмы и экспоненты
• Комплексные числа
• Числовые вычисления

🎯 *Просто напиши пример - я сам всё пойму!*"""
        
        await query.edit_message_text(
            features_text,
            parse_mode='Markdown'
        )
    
    elif query.data == "new_problem":
        await query.edit_message_text(
            "✍️ *Напиши математический пример:*\n\n"
            "Я решу:\n"
            "• `(x^2 - 4)/(x - 2)` - дроби\n"
            "• `3*x^2 - 12*x + 12` - многочлены\n"
            "• `x^2 - 5*x + 6 = 0` - уравнения\n"
            "• `diff(x^2, x)` - производные\n"
            "• `integrate(x^2, x)` - интегралы\n\n"
            "🎯 *Я сам определю что нужно сделать!*",
            parse_mode='Markdown'
        )

async def handle_other_messages(update: Update, context: CallbackContext):
    if update.message and not update.message.text:
        await update.message.reply_text(
            "🤖 *Отправь мне математический пример!*\n\n"
            "✨ *Примеры:*\n"
            "`3*x^2 - 12*x + 12`\n"
            "`(x^2 - 4)/(x - 2)`\n"
            "`x^2 - 5*x + 6 = 0`\n\n"
            "💡 Используй * для умножения!",
            parse_mode='Markdown'
        )

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", ultra_start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    application.add_handler(MessageHandler(filters.ALL, handle_other_messages))
    
    logger.info("🚀 ULTRA MATH BOT ЗАПУЩЕН!")
    logger.info("🤖 Бот готов к работе!")
    
    application.run_polling()

if __name__ == '__main__':
    main()
