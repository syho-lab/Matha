import os
import logging
import re
from typing import Dict, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
import sympy as sp
from sympy import (
    sympify, factor, cancel, apart, expand, simplify, solve, diff, integrate, 
    symbols, fraction, Poly, series, limit, oo, pi, E, sin, cos, tan, log, ln,
    sqrt, exp, trigsimp, expand_trig, nsimplify, latex, Rational
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

BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не установлен")

class UltraMathSolver:
    def __init__(self):
        self.x, self.y, self.z, self.t = symbols('x y z t')
        self.a, self.b, self.c, self.n = symbols('a b c n')
        self.symbols_dict = {
            'x': self.x, 'y': self.y, 'z': self.z, 't': self.t,
            'a': self.a, 'b': self.b, 'c': self.c, 'n': self.n
        }
    
    def ultra_preprocess(self, expr_str: str) -> str:
        """Максимально умная предобработка"""
        if not expr_str or len(expr_str.strip()) < 1:
            return ""
            
        original = expr_str
        expr_str = expr_str.strip()
        
        # Математические символы
        math_symbols = {
            '^': '**', '=': '==', '÷': '/', '×': '*', '–': '-', '−': '-',
            'π': 'pi', '∞': 'oo', '√': 'sqrt', '∫': 'integrate',
            '∂': 'diff', '∑': 'Sum', '∏': 'Product', 'α': 'alpha',
            'β': 'beta', 'γ': 'gamma', 'θ': 'theta', 'φ': 'phi',
            '≈': '~', '≠': '!=', '≤': '<=', '≥': '>=', '±': '+/-',
            ':': '/', '÷': '/', '\\frac': '', '⇒': '=>', '→': '->'
        }
        
        for old, new in math_symbols.items():
            expr_str = expr_str.replace(old, new)
        
        # Умное умножение
        expr_str = re.sub(r'(\d)([a-zA-Zα-ω])', r'\1*\2', expr_str)
        expr_str = re.sub(r'([a-zA-Zα-ω])\(', r'\1*(', expr_str)
        expr_str = re.sub(r'\)\s*\(', ')*(', expr_str)
        expr_str = re.sub(r'(\d)(sin|cos|tan|log|ln|sqrt)', r'\1*\2', expr_str)
        
        # Исправление ошибок
        common_errors = {
            'sinx': 'sin(x)', 'cosx': 'cos(x)', 'tanx': 'tan(x)',
            'logx': 'log(x)', 'lnx': 'ln(x)', 'sqrtx': 'sqrt(x)',
            'arcsin': 'asin', 'arccos': 'acos', 'arctan': 'atan',
        }
        
        for wrong, correct in common_errors.items():
            expr_str = re.sub(r'\b' + wrong + r'\b', correct, expr_str)
        
        return expr_str
    
    def format_fraction(self, numerator, denominator) -> str:
        """Красивое форматирование дроби"""
        num_str = str(numerator)
        den_str = str(denominator)
        
        # Определяем максимальную длину для выравнивания
        max_len = max(len(num_str), len(den_str))
        
        # Центрируем числитель и знаменатель
        num_centered = num_str.center(max_len)
        den_centered = den_str.center(max_len)
        
        return f"{num_centered}\n{'─' * max_len}\n{den_centered}"
    
    def format_expression(self, expr) -> str:
        """Профессиональное форматирование выражений"""
        if isinstance(expr, (int, float)):
            return str(expr)
        
        expr_str = str(expr)
        
        # Замены для красоты
        replacements = {
            '**': '^', 
            '*': '⋅',
            'sqrt': '√',
            'pi': 'π',
            'oo': '∞',
            'exp': 'e^',
            'I': 'i',
            'E': 'e'
        }
        
        for old, new in replacements.items():
            expr_str = expr_str.replace(old, new)
        
        # Форматирование дробей
        if '/' in expr_str and expr_str.count('/') == 1:
            parts = expr_str.split('/')
            if len(parts) == 2:
                try:
                    num = sympify(parts[0])
                    den = sympify(parts[1])
                    if den != 1:
                        return self.format_fraction(num, den)
                except:
                    pass
        
        return expr_str
    
    def ultra_solve(self, expr_str: str) -> str:
        """Максимально умное решение"""
        try:
            # Предобработка
            processed_expr = self.ultra_preprocess(expr_str)
            if not processed_expr:
                return "❌ Не вижу математического выражения"
            
            # Парсинг
            try:
                sympy_expr = sympify(processed_expr, locals=self.symbols_dict)
            except Exception as e:
                # Альтернативные попытки
                try:
                    alt_expr = processed_expr.replace('==', '-').replace('=', '-')
                    sympy_expr = sympify(alt_expr, locals=self.symbols_dict)
                except:
                    try:
                        sympy_expr = sympify(processed_expr.split('=')[0] if '=' in processed_expr else processed_expr, 
                                           locals=self.symbols_dict)
                    except:
                        return "🎯 *Анализ примера*\n\n❌ Не могу разобрать математическое выражение\n\n💡 *Проверь:*\n• Синтаксис\n• Используй * для умножения\n• Правильность скобок"
            
            # Определение типа и решение
            result = self.build_beautiful_header(expr_str)
            
            if sympy_expr.is_rational_function():
                solution = self.solve_rational_beautiful(sympy_expr, expr_str)
            elif 'solve' in expr_str.lower() or '=' in expr_str:
                solution = self.solve_equation_beautiful(sympy_expr, expr_str)
            elif sympy_expr.is_number:
                solution = self.solve_numeric_beautiful(sympy_expr, expr_str)
            elif 'diff' in expr_str.lower():
                solution = self.solve_derivative_beautiful(sympy_expr, expr_str)
            elif 'integrate' in expr_str.lower():
                solution = self.solve_integral_beautiful(sympy_expr, expr_str)
            else:
                solution = self.solve_general_beautiful(sympy_expr, expr_str)
            
            return result + solution
            
        except Exception:
            return "🎯 *Анализ примера*\n\n❌ Не могу решить этот пример\n\n💡 *Рекомендации:*\n• Проверь синтаксис\n• Используй * для умножения\n• Упрости выражение"
    
    def build_beautiful_header(self, original: str) -> str:
        """Красивый заголовок"""
        header = "🎯 *МАТЕМАТИЧЕСКИЙ АНАЛИЗ*\n\n"
        header += f"📝 *Исходный пример:*\n`{original}`\n\n"
        header += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        return header
    
    def solve_rational_beautiful(self, expr, original: str) -> str:
        """Красивое решение дробей"""
        try:
            result = ""
            numerator, denominator = fraction(expr)
            
            result += "🧮 *Алгебраическая дробь*\n\n"
            
            # Разложение на множители
            factored_num = factor(numerator)
            factored_den = factor(denominator)
            
            if factored_num != numerator or factored_den != denominator:
                result += "📊 *Разложение на множители:*\n"
                result += f"`{self.format_expression(factored_num)} / {self.format_expression(factored_den)}`\n\n"
            
            # Сокращение
            simplified = cancel(expr)
            if simplified != expr:
                result += "✨ *После сокращения:*\n"
                
                # Красивое отображение дроби если возможно
                if simplified.is_rational_function():
                    simp_num, simp_den = fraction(simplified)
                    if simp_den != 1:
                        result += f"```\n{self.format_fraction(simp_num, simp_den)}\n```\n\n"
                    else:
                        result += f"`{self.format_expression(simp_num)}`\n\n"
                else:
                    result += f"`{self.format_expression(simplified)}`\n\n"
            
            # Область определения
            if denominator.has(self.x):
                restrictions = solve(denominator, self.x)
                if restrictions:
                    result += "📌 *Область определения:*\n"
                    for sol in restrictions:
                        result += f"`x ≠ {self.format_expression(sol)}`\n"
                    result += "\n"
            
            result += "✅ *Финальный ответ:*\n"
            
            # Красивое отображение финального ответа
            if simplified.is_rational_function():
                final_num, final_den = fraction(simplified)
                if final_den != 1:
                    result += f"```\n{self.format_fraction(final_num, final_den)}\n```"
                else:
                    result += f"`{self.format_expression(final_num)}`"
            else:
                result += f"`{self.format_expression(simplified)}`"
            
            # Численное значение
            if simplified.is_number:
                decimal_val = float(simplified)
                result += f"\n\n🔢 *Десятичная форма:* `{decimal_val:.6f}`"
            
            return result
            
        except Exception:
            return "❌ Не удалось решить дробное выражение"
    
    def solve_equation_beautiful(self, expr, original: str) -> str:
        """Красивое решение уравнений"""
        try:
            result = "🎯 *Решение уравнения*\n\n"
            
            # Определение переменной
            if 'solve(' in original:
                match = re.search(r'solve\((.*),\s*(\w+)\)', original)
                if match:
                    eq_part = self.ultra_preprocess(match.group(1))
                    var_str = match.group(2)
                    var = symbols(var_str)
                    
                    if '==' in eq_part:
                        left, right = eq_part.split('==', 1)
                        equation = sympify(left) - sympify(right)
                    else:
                        equation = sympify(eq_part)
                else:
                    equation = expr
                    var = self.x
            else:
                equation = expr
                var = self.x
            
            result += f"📝 *Уравнение:* `{self.format_expression(equation)} = 0`\n\n"
            
            # Решение
            solutions = solve(equation, var)
            
            if solutions:
                result += "✨ *Найденные решения:*\n"
                for i, sol in enumerate(solutions, 1):
                    result += f"`{var}₍{i}₎ = {self.format_expression(sol)}`\n"
                
                result += "\n🔍 *Проверка решений:*\n"
                for sol in solutions:
                    check_val = equation.subs(var, sol)
                    result += f"`{var} = {self.format_expression(sol)}` → `{self.format_expression(check_val)} ≈ 0` ✅\n"
            else:
                result += "❌ Уравнение не имеет действительных решений"
            
            return result
            
        except Exception:
            return "❌ Не удалось решить уравнение"
    
    def solve_numeric_beautiful(self, expr, original: str) -> str:
        """Красивое решение числовых выражений"""
        try:
            exact = simplify(expr)
            numeric = float(exact)
            
            result = "🔢 *Числовое выражение*\n\n"
            result += f"✅ *Точный ответ:*\n"
            
            # Красивое отображение дроби если это дробь
            if exact.is_rational and exact != int(exact):
                num, den = fraction(exact)
                result += f"```\n{self.format_fraction(num, den)}\n```\n\n"
            else:
                result += f"`{self.format_expression(exact)}`\n\n"
            
            result += "📊 *Дополнительные формы:*\n"
            result += f"• Десятичная: `{numeric}`\n"
            
            if numeric != int(numeric) and not exact.is_rational:
                result += f"• Дробь: `{exact}`\n"
                
            if abs(numeric) > 1000 or (0 < abs(numeric) < 0.001 and numeric != 0):
                result += f"• Научная запись: `{numeric:.2e}`\n"
                
            if numeric < 0:
                result += f"• Модуль: `{abs(numeric)}`\n"
            
            return result
            
        except Exception:
            return "❌ Не удалось вычислить выражение"
    
    def solve_derivative_beautiful(self, expr, original: str) -> str:
        """Красивое решение производных"""
        try:
            derivative = diff(expr, self.x)
            simplified = simplify(derivative)
            
            result = "📈 *Производная*\n\n"
            result += f"✅ *Результат:*\n`{self.format_expression(simplified)}`"
            
            return result
            
        except Exception:
            return "❌ Не удалось найти производную"
    
    def solve_integral_beautiful(self, expr, original: str) -> str:
        """Красивое решение интегралов"""
        try:
            integral = integrate(expr, self.x)
            simplified = simplify(integral)
            
            result = "📊 *Интеграл*\n\n"
            result += f"✅ *Результат:*\n`{self.format_expression(simplified)} + C`"
            
            return result
            
        except Exception:
            return "❌ Не удалось найти интеграл"
    
    def solve_general_beautiful(self, expr, original: str) -> str:
        """Красивое решение общих выражений"""
        try:
            simplified = simplify(expr)
            
            result = "📐 *Упрощение выражения*\n\n"
            result += f"✨ *Упрощенная форма:*\n`{self.format_expression(simplified)}`"
            
            if simplified.is_number:
                result += f"\n\n🔢 *Численное значение:* `{float(simplified)}`"
            
            return result
            
        except Exception:
            return "❌ Не удалось упростить выражение"

ultra_solver = UltraMathSolver()

async def start(update: Update, context: CallbackContext):
    user = update.effective_user
    
    welcome_text = f"""🎓 *ДОБРО ПОЖАЛОВАТЬ В ULTRA MATH BOT!*

Привет, {user.first_name}! Я — профессиональный математический ассистент с *премиальным форматированием*!

✨ *МОИ ВОЗМОЖНОСТИ:*
• 🧮 Алгебраические дроби с красивым отображением
• 🎯 Уравнения с проверкой решений  
• 📈 Производные и интегралы
• 📊 Числовые выражения в multiple форматах
• 💫 Профессиональное математическое форматирование

🚀 *Просто напиши любой пример — я сделаю всё красиво!*"""

    keyboard = [
        [InlineKeyboardButton("🧮 Примеры дробей", callback_data="fractions")],
        [InlineKeyboardButton("🎯 Примеры уравнений", callback_data="equations")],
        [InlineKeyboardButton("🔢 Числовые примеры", callback_data="numeric")],
        [InlineKeyboardButton("🚀 Сложные задачи", callback_data="challenges")]
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
    
    result = ultra_solver.ultra_solve(user_input)
    
    keyboard = [
        [InlineKeyboardButton("🔄 Новый пример", callback_data="new")],
        [InlineKeyboardButton("📚 Другие примеры", callback_data="examples")]
    ]
    
    await update.message.reply_text(
        result,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def handle_callback_query(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    if query.data == "fractions":
        examples_text = """🧮 *ПРИМЕРЫ ДРОБЕЙ:*

`(x² - 4)/(x - 2)`
`1/(x+1) + 2/(x-1)`
`(x³ - 8)/(x² - 4)`
`(2x + 4)/2`
`49/7`
`15/4`

✨ *Бот покажет дроби в красивом формате!*"""
        
        await query.edit_message_text(
            examples_text,
            parse_mode='Markdown'
        )
    
    elif query.data == "equations":
        examples_text = """🎯 *ПРИМЕРЫ УРАВНЕНИЙ:*

`x² - 5x + 6 = 0`
`solve(x² - 9 = 0, x)`
`x³ - 3x + 2 = 0`
`2x + 5 = 13`
`solve([x + y - 5, 2x - y - 1], [x, y])`

✨ *Бот найдет все решения и проверит их!*"""
        
        await query.edit_message_text(
            examples_text,
            parse_mode='Markdown'
        )
    
    elif query.data == "numeric":
        examples_text = """🔢 *ЧИСЛОВЫЕ ПРИМЕРЫ:*

`49:7` или `49/7`
`15 + 3 × 4`
`(20 - 5) ÷ 3`
`2³ + 3²`
`√16 + 4²`
`π × 2²`

✨ *Бот покажет ответ в разных форматах!*"""
        
        await query.edit_message_text(
            examples_text,
            parse_mode='Markdown'
        )
    
    elif query.data == "challenges":
        examples_text = """🚀 *СЛОЖНЫЕ ЗАДАЧИ:*

`((x² - 1)/(x + 1)) / ((x - 1)/(x² + 2x + 1))`
`(x⁴ - 16)/(x² + 4) + (x² - 4)/(x + 2)`
`diff(x³ + 2x² - x, x)`
`integrate(x² + 3x + 2, x)`
`sin(x)² + cos(x)² + tan(x)⋅cot(x)`

🎯 *Проверь возможности бота на полную!*"""
        
        await query.edit_message_text(
            examples_text,
            parse_mode='Markdown'
        )
    
    elif query.data == "new":
        await query.edit_message_text(
            "✍️ *Напиши математический пример:*\n\n"
            "Я решу его с *профессиональным форматированием*! 🎓",
            parse_mode='Markdown'
        )
    
    elif query.data == "examples":
        await query.edit_message_text(
            "📚 *Выбери тип примеров:*",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🧮 Дроби", callback_data="fractions")],
                [InlineKeyboardButton("🎯 Уравнения", callback_data="equations")],
                [InlineKeyboardButton("🔢 Числовые", callback_data="numeric")],
                [InlineKeyboardButton("🚀 Сложные", callback_data="challenges")]
            ]),
            parse_mode='Markdown'
        )

async def handle_other_messages(update: Update, context: CallbackContext):
    if update.message and not update.message.text:
        await update.message.reply_text(
            "🎓 *Отправь мне математический пример!*\n\n"
            "✨ *Примеры:*\n"
            "`49:7` - деление\n"
            "`(x² - 4)/(x - 2)` - дробь\n"
            "`x² - 5x + 6 = 0` - уравнение\n"
            "`diff(x², x)` - производная\n\n"
            "💫 *Я оформлю решение профессионально!*",
            parse_mode='Markdown'
        )

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    application.add_handler(MessageHandler(filters.ALL, handle_other_messages))
    
    application.run_polling()

if __name__ == '__main__':
    main()
