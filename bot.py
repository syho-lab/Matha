import os
import logging
import tempfile
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
import sympy as sp
from sympy import sympify, factor, cancel, apart, expand, simplify, solve, diff, integrate, limit, series, symbols, latex, fraction, Poly
from PIL import Image
import pytesseract
import re

# Настройка pytesseract для Render
pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'

try:
    from keep_alive import keep_alive
    keep_alive()
    logging.info("Flask server started for monitoring")
except ImportError as e:
    logging.warning(f"Flask not available: {e}")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не установлен")

class SmartMathSolver:
    def __init__(self):
        self.x, self.y, self.z = symbols('x y z')
        self.a, self.b, self.c = symbols('a b c')
    
    def format_expression(self, expr):
        """Умное форматирование выражений"""
        expr_str = str(expr)
        replacements = {
            '**': '^',
            '*': '⋅',
            'sqrt': '√',
            'pi': 'π',
            'oo': '∞',
            'exp': 'e^',
            'I': 'i'
        }
        for old, new in replacements.items():
            expr_str = expr_str.replace(old, new)
        return expr_str
    
    def detect_expression_type(self, expr_str, sympy_expr):
        """Определяет тип математического выражения"""
        expr_str_lower = expr_str.lower()
        
        if 'solve' in expr_str_lower:
            return 'equation'
        elif 'diff' in expr_str_lower or 'derivative' in expr_str_lower:
            return 'derivative'
        elif 'integrate' in expr_str_lower or '∫' in expr_str_lower:
            return 'integral'
        elif 'limit' in expr_str_lower:
            return 'limit'
        elif 'series' in expr_str_lower:
            return 'series'
        elif sympy_expr.is_rational_function():
            return 'rational'
        elif sympy_expr.is_polynomial():
            return 'polynomial'
        elif sympy_expr.is_number:
            return 'numeric'
        else:
            return 'general'
    
    def solve_expression(self, expression: str) -> str:
        """Умный решатель с определением типа выражения"""
        try:
            # Очистка и подготовка выражения
            expr = expression.strip()
            expr = expr.replace('^', '**').replace('=', '==')
            expr = expr.replace('÷', '/').replace('×', '*')
            
            # Парсим выражение
            sympy_expr = sympify(expr, locals={
                'x': self.x, 'y': self.y, 'z': self.z,
                'a': self.a, 'b': self.b, 'c': self.c
            })
            
            # Определяем тип выражения
            expr_type = self.detect_expression_type(expression, sympy_expr)
            
            result = f"🧮 **РЕШЕНИЕ ПРИМЕРА**\n\n"
            result += f"**Дано:** `{self.format_expression(expression)}`\n"
            result += f"**Тип:** {self.get_type_description(expr_type)}\n\n"
            
            # Выбираем соответствующий решатель
            if expr_type == 'rational':
                return result + self.solve_rational(sympy_expr, expression)
            elif expr_type == 'equation':
                return result + self.solve_equation(expression)
            elif expr_type == 'derivative':
                return result + self.solve_derivative(expression)
            elif expr_type == 'integral':
                return result + self.solve_integral(expression)
            elif expr_type == 'limit':
                return result + self.solve_limit(expression)
            elif expr_type == 'series':
                return result + self.solve_series(expression)
            elif expr_type == 'polynomial':
                return result + self.solve_polynomial(sympy_expr, expression)
            elif expr_type == 'numeric':
                return result + self.solve_numeric(sympy_expr, expression)
            else:
                return result + self.solve_general(sympy_expr, expression)
                
        except Exception as e:
            return f"❌ **Ошибка анализа:** `{str(e)}`\n\nПроверьте правильность написания примера."
    
    def get_type_description(self, expr_type):
        """Описание типа выражения"""
        descriptions = {
            'rational': 'Алгебраическая дробь',
            'equation': 'Уравнение',
            'derivative': 'Производная',
            'integral': 'Интеграл',
            'limit': 'Предел',
            'series': 'Ряд',
            'polynomial': 'Многочлен',
            'numeric': 'Числовое выражение',
            'general': 'Общее выражение'
        }
        return descriptions.get(expr_type, 'Неизвестный тип')
    
    def solve_rational(self, expr, original_str):
        """Умное решение рациональных выражений"""
        result = ""
        steps_added = False
        
        try:
            # Шаг 1: Анализ структуры
            num, den = fraction(expr)
            result += "**📝 Шаг 1: Анализ дроби**\n"
            result += f"Дробь: `{self.format_expression(original_str)}`\n\n"
            
            # Шаг 2: Разложение на множители (только если возможно)
            num_factored = factor(num)
            den_factored = factor(den)
            
            if num_factored != num or den_factored != den:
                result += "**📝 Шаг 2: Разложение на множители**\n"
                result += f"Числитель: `{self.format_expression(num)}` = `{self.format_expression(num_factored)}`\n"
                result += f"Знаменатель: `{self.format_expression(den)}` = `{self.format_expression(den_factored)}`\n\n"
                steps_added = True
            
            # Шаг 3: Сокращение (только если есть что сокращать)
            simplified = cancel(expr)
            if simplified != expr:
                result += "**📝 Шаг 3: Сокращение дроби**\n"
                result += f"После сокращения: `{self.format_expression(simplified)}`\n\n"
                steps_added = True
            
            # Шаг 4: Область определения (только для знаменателей с переменными)
            if den.has(self.x) or den.has(self.y) or den.has(self.z):
                domain_solutions = solve(den, self.x)
                if domain_solutions:
                    result += "**📝 Шаг 4: Область определения**\n"
                    result += "Знаменатель ≠ 0:\n"
                    for sol in domain_solutions:
                        result += f"`x ≠ {self.format_expression(sol)}`\n"
                    result += "\n"
                    steps_added = True
            
            # Шаг 5: Дополнительные преобразования
            if simplified.is_rational_function() and simplified != expr:
                try:
                    partial = apart(simplified)
                    if partial != simplified:
                        result += "**📝 Шаг 5: Разложение на простейшие дроби**\n"
                        result += f"`{self.format_expression(partial)}`\n\n"
                        steps_added = True
                except:
                    pass
            
            # Если не было промежуточных шагов, покажем только упрощение
            if not steps_added:
                result += "**📝 Упрощение выражения**\n"
                result += f"`{self.format_expression(simplified)}`\n\n"
            
            # Финальный ответ
            result += "**✅ ОКОНЧАТЕЛЬНЫЙ ОТВЕТ:**\n"
            result += f"`{self.format_expression(simplified)}`\n\n"
            
            # Дополнительная информация
            if simplified.is_number:
                decimal_val = float(simplified)
                result += f"**🔢 Десятичная форма:** `{decimal_val}`\n"
                if abs(decimal_val) > 1000 or abs(decimal_val) < 0.001:
                    result += f"**📊 Научная запись:** `{decimal_val:.2e}`\n"
            
            return result
            
        except Exception as e:
            return f"❌ Ошибка при решении дроби: {str(e)}"
    
    def solve_polynomial(self, expr, original_str):
        """Решение многочленов"""
        result = ""
        
        try:
            # Упрощение
            simplified = simplify(expr)
            result += "**📝 Шаг 1: Упрощение**\n"
            result += f"`{self.format_expression(simplified)}`\n\n"
            
            # Разложение на множители
            factored = factor(simplified)
            if factored != simplified:
                result += "**📝 Шаг 2: Разложение на множители**\n"
                result += f"`{self.format_expression(factored)}`\n\n"
            
            # Нахождение корней для полиномов
            if simplified.is_polynomial() and simplified.has(self.x):
                roots = solve(simplified, self.x)
                if roots:
                    result += "**📝 Шаг 3: Нахождение корней**\n"
                    for i, root in enumerate(roots, 1):
                        result += f"`x_{i} = {self.format_expression(root)}`\n"
                    result += "\n"
            
            result += "**✅ ОТВЕТ:**\n"
            result += f"`{self.format_expression(simplified)}`\n"
            
            return result
            
        except Exception as e:
            return f"❌ Ошибка при решении многочлена: {str(e)}"
    
    def solve_equation(self, expr_str):
        """Решение уравнений"""
        try:
            # Извлекаем уравнение из строки
            if 'solve' in expr_str.lower():
                # Формат: solve(уравнение, переменная)
                match = re.search(r'solve\((.*),\s*(\w+)\)', expr_str)
                if match:
                    eq_str = match.group(1).strip()
                    var_str = match.group(2).strip()
                    var = symbols(var_str)
                    
                    # Парсим уравнение
                    if '==' in eq_str:
                        left, right = eq_str.split('==', 1)
                        equation = sympify(left) - sympify(right)
                    else:
                        equation = sympify(eq_str)
                else:
                    return "❌ Неверный формат уравнения. Используйте: solve(уравнение, переменная)"
            else:
                # Прямое уравнение
                if '=' in expr_str:
                    left, right = expr_str.split('=', 1)
                    equation = sympify(left) - sympify(right)
                    var = self.x
                else:
                    equation = sympify(expr_str)
                    var = self.x
            
            result = "**📝 Шаг 1: Записываем уравнение**\n"
            result += f"`{self.format_expression(equation)} = 0`\n\n"
            
            # Решаем уравнение
            solutions = solve(equation, var)
            
            if solutions:
                result += "**📝 Шаг 2: Находим решения**\n"
                for i, sol in enumerate(solutions, 1):
                    result += f"`{var}_{i} = {self.format_expression(sol)}`\n"
                result += "\n"
                
                # Проверка решений
                result += "**📝 Шаг 3: Проверка решений**\n"
                for sol in solutions:
                    check = equation.subs(var, sol)
                    result += f"При `{var} = {self.format_expression(sol)}`: `{self.format_expression(check)} = 0` ✓\n"
                result += "\n"
            else:
                result += "**❌ Уравнение не имеет решений**\n\n"
            
            result += "**✅ РЕШЕНИЯ:**\n"
            if solutions:
                for i, sol in enumerate(solutions, 1):
                    result += f"`{var}_{i} = {self.format_expression(sol)}`\n"
            else:
                result += "Решений нет"
            
            return result
            
        except Exception as e:
            return f"❌ Ошибка при решении уравнения: {str(e)}"
    
    def solve_numeric(self, expr, original_str):
        """Решение числовых выражений"""
        try:
            result = "**📝 Шаг 1: Вычисление**\n"
            result += f"`{self.format_expression(original_str)}`\n\n"
            
            value = float(expr)
            
            result += "**✅ ОТВЕТ:**\n"
            result += f"`{value}`\n\n"
            
            # Дополнительные формы
            if value != int(value):
                result += f"**🔢 Дробная форма:** `{expr}`\n"
            
            if abs(value) > 1000 or (abs(value) < 0.001 and value != 0):
                result += f"**📊 Научная запись:** `{value:.2e}`\n"
            
            return result
            
        except Exception as e:
            return f"❌ Ошибка при вычислении: {str(e)}"
    
    def solve_general(self, expr, original_str):
        """Решение общих выражений"""
        try:
            result = "**📝 Шаг 1: Упрощение выражения**\n"
            result += f"Исходное: `{self.format_expression(original_str)}`\n\n"
            
            simplified = simplify(expr)
            
            result += "**📝 Шаг 2: Упрощенная форма**\n"
            result += f"`{self.format_expression(simplified)}`\n\n"
            
            # Дополнительные преобразования
            try:
                expanded = expand(simplified)
                if expanded != simplified:
                    result += "**📝 Шаг 3: Раскрытие скобок**\n"
                    result += f"`{self.format_expression(expanded)}`\n\n"
            except:
                pass
            
            result += "**✅ ОТВЕТ:**\n"
            result += f"`{self.format_expression(simplified)}`\n"
            
            if simplified.is_number:
                result += f"\n**🔢 Численное значение:** `{float(simplified)}`"
            
            return result
            
        except Exception as e:
            return f"❌ Ошибка при упрощении: {str(e)}"
    
    def solve_derivative(self, expr_str):
        """Решение производных"""
        try:
            # Парсим выражение для производной
            if 'diff' in expr_str:
                match = re.search(r'diff\((.*),\s*(\w+)\)', expr_str)
                if match:
                    func_str = match.group(1).strip()
                    var_str = match.group(2).strip()
                    func = sympify(func_str)
                    var = symbols(var_str)
                else:
                    return "❌ Неверный формат. Используйте: diff(функция, переменная)"
            else:
                func = sympify(expr_str.replace('diff', '').strip('()'))
                var = self.x
            
            result = "**📝 Шаг 1: Исходная функция**\n"
            result += f"`f({var}) = {self.format_expression(func)}`\n\n"
            
            # Находим производную
            derivative = diff(func, var)
            
            result += "**📝 Шаг 2: Нахождение производной**\n"
            result += f"`f'({var}) = {self.format_expression(derivative)}`\n\n"
            
            # Упрощаем производную
            simplified_deriv = simplify(derivative)
            if simplified_deriv != derivative:
                result += "**📝 Шаг 3: Упрощение производной**\n"
                result += f"`f'({var}) = {self.format_expression(simplified_deriv)}`\n\n"
            
            result += "**✅ ПРОИЗВОДНАЯ:**\n"
            result += f"`{self.format_expression(simplified_deriv)}`"
            
            return result
            
        except Exception as e:
            return f"❌ Ошибка при нахождении производной: {str(e)}"

# Глобальный экземпляр решателя
solver = SmartMathSolver()

async def start(update: Update, context: CallbackContext):
    user = update.effective_user
    welcome_text = f"""
👋 Привет, {user.first_name}!

Я - **СУПЕР-УМНЫЙ** математический бот! 🧠✨

🎯 **Мои способности:**
• 🤖 Автоматически определяю тип примера
• 📝 Показываю ТОЛЬКО нужные шаги решения
• 📸 Распознаю примеры по фото
• 🧮 Решаю ЛЮБУЮ математику
• 💡 Объясняю каждый шаг понятно

**Просто отправь мне пример текстом или фото!**
    """
    
    keyboard = [
        [InlineKeyboardButton("🧮 Примеры", callback_data="smart_examples")],
        [InlineKeyboardButton("📸 Фото-инструкция", callback_data="photo_help")],
        [InlineKeyboardButton("🎯 Сложные примеры", callback_data="hard_examples")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def handle_text(update: Update, context: CallbackContext):
    """Обработка текстовых сообщений"""
    user_input = update.message.text.strip()
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    result_text = solver.solve_expression(user_input)
    
    keyboard = [
        [InlineKeyboardButton("🧮 Новый пример", callback_data="new_example")],
        [InlineKeyboardButton("🎯 Сложный пример", callback_data="hard_examples")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(result_text, reply_markup=reply_markup, parse_mode='Markdown')

def recognize_text_from_image(image_path: str) -> str:
    """Распознает текст с изображения"""
    try:
        image = Image.open(image_path)
        image = image.convert('L')  # Grayscale
        
        # Настройки для лучшего распознавания математики
        custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ()[]{}/*+-=^𝑥𝑦𝑧π∞αβγθ'
        text = pytesseract.image_to_string(image, config=custom_config)
        
        text = text.strip()
        
        # Заменяем распознанные символы
        replacements = {
            'х': 'x', 'у': 'y', 'з': 'z', 'с': 'c',
            '—': '-', '–': '-', '−': '-', '×': '*',
            '÷': '/', '∗': '*', '⋅': '*', 'а': 'a',
            'в': 'b', 'е': 'e', 'к': 'k', 'м': 'm',
            'н': 'h', 'о': 'o', 'р': 'p', 'т': 't'
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
            
        return text if text else "Не удалось распознать текст"
        
    except Exception as e:
        return f"Ошибка распознавания: {str(e)}"

async def handle_photo(update: Update, context: CallbackContext):
    """Обработка фотографий"""
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        
        photo_file = await update.message.photo[-1].get_file()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
            temp_path = temp_file.name
        
        await photo_file.download_to_drive(temp_path)
        
        recognized_text = recognize_text_from_image(temp_path)
        
        os.unlink(temp_path)
        
        if "Не удалось распознать" in recognized_text or not recognized_text:
            await update.message.reply_text(
                "❌ Не удалось распознать пример.\n\n"
                "📸 **Советы:**\n"
                "• Четкий почерк/шрифт\n"
                "• Хорошее освещение\n"
                "• Пример по центру\n"
                "• Контрастные цвета"
            )
            return
        
        await update.message.reply_text(f"📸 **Распознано:** `{recognized_text}`")
        
        result_text = solver.solve_expression(recognized_text)
        
        keyboard = [
            [InlineKeyboardButton("📸 Еще фото", callback_data="photo_help")],
            [InlineKeyboardButton("🧮 Текстовый пример", callback_data="new_example")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(result_text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка обработки фото: {str(e)}")

async def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    if query.data == "smart_examples":
        examples_text = """
🧮 **Умные примеры для теста:**

**Дроби:**
`(x^2 - 4)/(x - 2)`
`(x^3 - 8)/(x^2 - 4)`
`1/(x+1) + 2/(x-1)`

**Уравнения:**
`solve(x^2 - 5x + 6 = 0, x)`
`solve(x^3 - 3x + 2 = 0, x)`

**Производные:**
`diff(x^3 + 2x^2 - x, x)`
`diff(sin(x) * cos(x), x)`

**Числовые:**
`2 + 3 * 4^2`
`(15 - 3) / 4 + 2^3`
        """
        await query.edit_message_text(examples_text, parse_mode='Markdown')
        
    elif query.data == "hard_examples":
        examples_text = """
🎯 **Сложные примеры:**

**Комплексные дроби:**
`((x^2 - 1)/(x + 1)) / ((x - 1)/(x^2 + 2x + 1))`

**Системы уравнений:**
`solve([x + y - 5, 2x - y - 1], [x, y])`

**Степенные выражения:**
`(x^4 - 16)/(x^2 + 4) + (x^2 - 4)/(x + 2)`

**Тригонометрия:**
`sin(x)^2 + cos(x)^2 + tan(x)*cot(x)`

**Логарифмы:**
`log(x^2 - 1) - log(x - 1)`
        """
        await query.edit_message_text(examples_text, parse_mode='Markdown')
        
    elif query.data == "photo_help":
        help_text = """
📸 **Идеальное фото для распознавания:**

✅ **ХОРОШО:**
• `(x^2 - 4)/(x - 2)`
• `2 + 3 * 4`
• `solve(x^2 - 9 = 0, x)`

❌ **ПЛОХО:**
• Многоэтажные дроби
• Сложные матрицы
• Курсивный почерк

**Советы:**
1. Пишите печатными буквами
2. Используйте стандартные символы
3. Один пример = одна строка
4. Хорошее освещение
        """
        await query.edit_message_text(help_text, parse_mode='Markdown')
        
    elif query.data == "new_example":
        await query.edit_message_text("✍️ Введите ЛЮБОЙ математический пример или отправьте фото:")

async def handle_any_message(update: Update, context: CallbackContext):
    if update.message and not (update.message.text or update.message.photo):
        await update.message.reply_text(
            "🎯 Отправьте мне ЛЮБОЙ математический пример!\n\n"
            "• **Текстом** - любой пример\n"
            "• **Фото** - сфотографируйте пример\n\n"
            "Я сам определю тип и решу оптимальным способом! 🤖"
        )

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.ALL, handle_any_message))
    
    logger.info("🤖 УМНЫЙ бот запущен!")
    application.run_polling()

if __name__ == '__main__':
    main()
