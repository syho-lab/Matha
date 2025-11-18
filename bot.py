import os
import logging
import tempfile
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
import sympy as sp
from sympy import sympify, factor, cancel, apart, expand, simplify, solve, diff, integrate, symbols
from PIL import Image
import pytesseract

# Безопасная настройка pytesseract
try:
    pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'
    TESSERACT_AVAILABLE = True
except Exception as e:
    logging.warning(f"Tesseract not available: {e}")
    TESSERACT_AVAILABLE = False

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
        if isinstance(expr, str):
            expr_str = expr
        else:
            expr_str = str(expr)
            
        replacements = {
            '**': '^',
            '*': '⋅',
            'sqrt': '√',
            'pi': 'π',
            'oo': '∞',
            'exp': 'e^'
        }
        for old, new in replacements.items():
            expr_str = expr_str.replace(old, new)
        return expr_str
    
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
            
            result = f"🧮 **РЕШЕНИЕ ПРИМЕРА**\n\n"
            result += f"**Дано:** `{self.format_expression(expression)}`\n\n"
            
            # Определяем тип и решаем
            if sympy_expr.is_rational_function():
                return result + self.solve_rational(sympy_expr, expression)
            elif 'solve' in expression.lower():
                return result + self.solve_equation(expression)
            elif 'diff' in expression.lower():
                return result + self.solve_derivative(expression)
            elif sympy_expr.is_polynomial():
                return result + self.solve_polynomial(sympy_expr, expression)
            elif sympy_expr.is_number:
                return result + self.solve_numeric(sympy_expr, expression)
            else:
                return result + self.solve_general(sympy_expr, expression)
                
        except Exception as e:
            return f"❌ **Ошибка:** Не могу решить этот пример\n`{str(e)}`\n\nПопробуйте другой пример или используйте /help"
    
    def solve_rational(self, expr, original_str):
        """Умное решение рациональных выражений"""
        result = ""
        
        try:
            # Получаем числитель и знаменатель
            num, den = expr.as_numer_denom()
            
            result += "**📝 Шаг 1: Анализ дроби**\n"
            result += f"`{self.format_expression(original_str)}`\n\n"
            
            # Разложение на множители
            num_factored = factor(num)
            den_factored = factor(den)
            
            if num_factored != num or den_factored != den:
                result += "**📝 Шаг 2: Разложение на множители**\n"
                result += f"Числитель: `{self.format_expression(num)}` = `{self.format_expression(num_factored)}`\n"
                result += f"Знаменатель: `{self.format_expression(den)}` = `{self.format_expression(den_factored)}`\n\n"
            
            # Сокращение
            simplified = cancel(expr)
            if simplified != expr:
                result += "**📝 Шаг 3: Сокращение дроби**\n"
                result += f"После сокращения: `{self.format_expression(simplified)}`\n\n"
            
            # Область определения
            if den.has(self.x):
                domain_solutions = solve(den, self.x)
                if domain_solutions:
                    result += "**📝 Шаг 4: Область определения**\n"
                    result += "Знаменатель ≠ 0:\n"
                    for sol in domain_solutions:
                        result += f"`x ≠ {self.format_expression(sol)}`\n"
                    result += "\n"
            
            # Финальный ответ
            result += "**✅ ОТВЕТ:**\n"
            result += f"`{self.format_expression(simplified)}`\n"
            
            if simplified.is_number:
                result += f"\n**🔢 Численное значение:** `{float(simplified)}`"
            
            return result
            
        except Exception as e:
            return f"❌ Ошибка при решении дроби: {str(e)}"
    
    def solve_polynomial(self, expr, original_str):
        """Решение многочленов"""
        result = ""
        
        try:
            simplified = simplify(expr)
            result += "**📝 Шаг 1: Упрощение**\n"
            result += f"`{self.format_expression(simplified)}`\n\n"
            
            # Разложение на множители
            factored = factor(simplified)
            if factored != simplified:
                result += "**📝 Шаг 2: Разложение на множители**\n"
                result += f"`{self.format_expression(factored)}`\n\n"
            
            result += "**✅ ОТВЕТ:**\n"
            result += f"`{self.format_expression(simplified)}`\n"
            
            return result
            
        except Exception as e:
            return f"❌ Ошибка при решении многочлена: {str(e)}"
    
    def solve_equation(self, expr_str):
        """Решение уравнений"""
        try:
            # Упрощенный парсинг уравнений
            if '=' in expr_str:
                if 'solve' in expr_str.lower():
                    # Убираем solve и обрабатываем
                    eq_part = expr_str.lower().replace('solve', '').strip('() ')
                    if '=' in eq_part:
                        left, right = eq_part.split('=', 1)
                        equation = sympify(left.strip()) - sympify(right.strip())
                    else:
                        equation = sympify(eq_part)
                else:
                    # Простое уравнение
                    left, right = expr_str.split('=', 1)
                    equation = sympify(left.strip()) - sympify(right.strip())
            else:
                equation = sympify(expr_str)
            
            result = "**📝 Шаг 1: Записываем уравнение**\n"
            result += f"`{self.format_expression(equation)} = 0`\n\n"
            
            # Решаем уравнение
            solutions = solve(equation, self.x)
            
            if solutions:
                result += "**📝 Шаг 2: Находим решения**\n"
                for i, sol in enumerate(solutions, 1):
                    result += f"`x_{i} = {self.format_expression(sol)}`\n"
                result += "\n"
            else:
                result += "**❌ Уравнение не имеет решений**\n\n"
            
            result += "**✅ РЕШЕНИЯ:**\n"
            if solutions:
                for i, sol in enumerate(solutions, 1):
                    result += f"`x_{i} = {self.format_expression(sol)}`\n"
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
            result += f"`{value}`\n"
            
            return result
            
        except Exception as e:
            return f"❌ Ошибка при вычислении: {str(e)}"
    
    def solve_general(self, expr, original_str):
        """Решение общих выражений"""
        try:
            simplified = simplify(expr)
            
            result = "**📝 Шаг 1: Упрощение**\n"
            result += f"Исходное: `{self.format_expression(original_str)}`\n"
            result += f"Упрощенное: `{self.format_expression(simplified)}`\n\n"
            
            result += "**✅ ОТВЕТ:**\n"
            result += f"`{self.format_expression(simplified)}`\n"
            
            if simplified.is_number:
                result += f"\n**🔢 Численное значение:** `{float(simplified)}`"
            
            return result
            
        except Exception as e:
            return f"❌ Ошибка при упрощении: {str(e)}"

# Глобальный экземпляр решателя
solver = SmartMathSolver()

def recognize_text_from_image_safe(image_path: str) -> str:
    """Безопасное распознавание текста с обработкой ошибок"""
    if not TESSERACT_AVAILABLE:
        return "Функция распознавания фото временно недоступна"
    
    try:
        image = Image.open(image_path)
        image = image.convert('L')  # Grayscale
        
        # Простая конфигурация
        text = pytesseract.image_to_string(image)
        text = text.strip()
        
        if not text:
            return "Не удалось распознать текст на изображении"
        
        # Базовая очистка
        replacements = {
            'х': 'x', 'у': 'y', 'з': 'z', 
            '—': '-', '–': '-', '×': '*',
            '÷': '/'
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
            
        return text
        
    except Exception as e:
        return f"Ошибка при обработке изображения: {str(e)}"

async def start(update: Update, context: CallbackContext):
    user = update.effective_user
    welcome_text = f"""
👋 Привет, {user.first_name}!

Я - умный математический бот! 🧮

🎯 **Я умею решать:**
• Алгебраические дроби
• Уравнения 
• Многочлены
• Числовые выражения

📝 **Просто отправь мне пример текстом!**

{ "📸 **Или сфотографируй пример!**" if TESSERACT_AVAILABLE else "⚠️ **Распознавание фото временно недоступно**" }
    """
    
    keyboard = [
        [InlineKeyboardButton("🧮 Примеры", callback_data="examples")],
        [InlineKeyboardButton("📝 Как писать примеры", callback_data="syntax_help")]
    ]
    if TESSERACT_AVAILABLE:
        keyboard.append([InlineKeyboardButton("📸 Отправить фото", callback_data="photo_help")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def handle_text(update: Update, context: CallbackContext):
    """Обработка текстовых сообщений"""
    user_input = update.message.text.strip()
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    result_text = solver.solve_expression(user_input)
    
    keyboard = [
        [InlineKeyboardButton("🧮 Новый пример", callback_data="new_example")],
        [InlineKeyboardButton("📚 Другие примеры", callback_data="examples")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(result_text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_photo(update: Update, context: CallbackContext):
    """Обработка фотографий"""
    if not TESSERACT_AVAILABLE:
        await update.message.reply_text(
            "❌ Распознавание фото временно недоступно.\n\n"
            "Пожалуйста, отправьте пример текстом:\n"
            "`(x^2 - 4)/(x - 2)`\n"
            "`2 + 3 * 4`\n"
            "`solve(x^2 - 9 = 0, x)`"
        )
        return
    
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        
        photo_file = await update.message.photo[-1].get_file()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
            temp_path = temp_file.name
        
        await photo_file.download_to_drive(temp_path)
        
        recognized_text = recognize_text_from_image_safe(temp_path)
        
        os.unlink(temp_path)
        
        # Проверяем, удалось ли распознать математическое выражение
        if any(word in recognized_text.lower() for word in ['ошибка', 'не удалось', 'unable']):
            await update.message.reply_text(
                f"❌ {recognized_text}\n\n"
                "📸 **Советы для лучшего распознавания:**\n"
                "• Четкий печатный текст\n"
                "• Хорошее освещение\n"
                "• Пример в одну строку\n"
                "• Контрастные цвета"
            )
            return
        
        await update.message.reply_text(f"📸 **Распознано:** `{recognized_text}`")
        
        # Решаем распознанный пример
        result_text = solver.solve_expression(recognized_text)
        
        keyboard = [
            [InlineKeyboardButton("📸 Еще фото", callback_data="photo_help")],
            [InlineKeyboardButton("🧮 Текстовый пример", callback_data="new_example")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(result_text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(
            f"❌ Ошибка при обработке фото\n\n"
            f"Попробуйте отправить пример текстом:\n"
            f"`(x^2 - 4)/(x - 2)`"
        )

async def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    if query.data == "examples":
        examples_text = """
🧮 **Примеры для тестирования:**

**Дроби:**
`(x^2 - 4)/(x - 2)`
`(x^3 - 8)/(x^2 - 4)`
`1/(x+1) + 2/(x-1)`

**Уравнения:**
`solve(x^2 - 5x + 6 = 0, x)`
`x^2 - 9 = 0`

**Числовые:**
`2 + 3 * 4^2`
`(15 - 3) / 4 + 2^3`

**Многочлены:**
`x^2 + 2x + 1`
`x^3 - 3x^2 + 3x - 1`
        """
        await query.edit_message_text(examples_text, parse_mode='Markdown')
        
    elif query.data == "syntax_help":
        help_text = """
📝 **Как писать примеры:**

**Степени:**
x² → x^2 или x**2

**Дроби:**
(a + b)/(c + d)

**Уравнения:**
solve(x^2 - 4 = 0, x)
или просто
x^2 - 4 = 0

**Умножение:**
2 * x или 2⋅x

**Корни:**
√4 → sqrt(4)
        """
        await query.edit_message_text(help_text, parse_mode='Markdown')
        
    elif query.data == "photo_help" and TESSERACT_AVAILABLE:
        help_text = """
📸 **Как отправить фото:**

1. Напишите пример на бумаге
2. Сфотографируйте при хорошем свете
3. Отправьте фото боту

✅ **Хорошо распознается:**
• Печатные буквы и цифры
• Примеры в одну строку
• Стандартные математические символы

❌ **Плохо распознается:**
• Курсивный почерк
• Сложные дроби в несколько этажей
• Специальные символы
        """
        await query.edit_message_text(help_text, parse_mode='Markdown')
        
    elif query.data == "new_example":
        await query.edit_message_text("✍️ Введите математический пример:")

async def handle_any_message(update: Update, context: CallbackContext):
    if update.message and not (update.message.text or update.message.photo):
        await update.message.reply_text(
            "📝 Отправьте мне математический пример!\n\n"
            "• **Текстом** - напишите пример\n"
            f"{'• **Фото** - сфотографируйте пример' if TESSERACT_AVAILABLE else '• ⚠️ Фото - временно недоступно'}\n\n"
            "Например: `(x^2 - 4)/(x - 2)`"
        )

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.ALL, handle_any_message))
    
    logger.info("🤖 Бот запущен!")
    if not TESSERACT_AVAILABLE:
        logger.warning("Tesseract OCR недоступен - распознавание фото отключено")
    
    application.run_polling()

if __name__ == '__main__':
    main()
