import os
import logging
import tempfile
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
import sympy as sp
from sympy import sympify, factor, cancel, apart, expand, simplify, solve, diff, integrate, symbols, fraction
from PIL import Image
import pytesseract

# Настройка pytesseract
try:
    pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'
    TESSERACT_AVAILABLE = True
except:
    TESSERACT_AVAILABLE = False

try:
    from keep_alive import keep_alive
    keep_alive()
except:
    pass

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не установлен")

class SmartMathSolver:
    def __init__(self):
        self.x, self.y, self.z = symbols('x y z')
    
    def format_expr(self, expr):
        """Форматирование выражения для вывода"""
        expr_str = str(expr)
        replacements = {
            '**': '^',
            '*': '⋅',
            'sqrt': '√',
            'pi': 'π'
        }
        for old, new in replacements.items():
            expr_str = expr_str.replace(old, new)
        return expr_str
    
    def preprocess_expression(self, expr_str):
        """Предобработка выражения - добавляет * между числами и переменными"""
        # Добавляем * между цифрами и буквами (3x -> 3*x)
        expr_str = re.sub(r'(\d)([a-zA-Z])', r'\1*\2', expr_str)
        # Добавляем * между буквами и скобками (x( -> x*()
        expr_str = re.sub(r'([a-zA-Z])\(', r'\1*(', expr_str)
        # Добавляем * между скобками )( -> )*(
        expr_str = re.sub(r'\)\(', ')*(', expr_str)
        
        # Заменяем символы
        expr_str = expr_str.replace('^', '**').replace('=', '==')
        expr_str = expr_str.replace('÷', '/').replace('×', '*')
        
        return expr_str
    
    def detect_type(self, expr_str):
        """Автоопределение типа примера"""
        expr_clean = expr_str.lower().replace(' ', '')
        
        # Уравнения
        if 'solve(' in expr_clean or ('=' in expr_clean and 'x' in expr_clean):
            return 'equation'
        
        # Производные
        if 'diff(' in expr_clean:
            return 'derivative'
        
        # Интегралы
        if 'integrate(' in expr_clean:
            return 'integral'
        
        # Дроби (есть деление и переменные/скобки)
        if '/' in expr_clean and ('(' in expr_clean or 'x' in expr_clean or 'y' in expr_clean):
            return 'fraction'
        
        # Многочлены (переменные со степенями или умножениями)
        if any(char in expr_clean for char in ['x', 'y', 'z']) and any(op in expr_clean for op in ['+', '-', '*', '^']):
            return 'polynomial'
        
        # Числовые выражения
        if all(char in '0123456789+-*/.()^ ' for char in expr_clean):
            return 'numeric'
        
        return 'general'
    
    def solve_expression(self, expr_str):
        """Умное решение с автоопределением типа"""
        try:
            # Предобработка выражения
            processed_expr = self.preprocess_expression(expr_str)
            
            # Определяем тип
            expr_type = self.detect_type(expr_str)
            
            # Парсим выражение
            sympy_expr = sympify(processed_expr, locals={'x': self.x, 'y': self.y, 'z': self.z})
            
            result = f"🧮 **Решаем:** `{expr_str}`\n\n"
            
            if expr_type == 'fraction':
                return result + self.solve_fraction(sympy_expr, expr_str)
            elif expr_type == 'equation':
                return result + self.solve_equation(expr_str)
            elif expr_type == 'polynomial':
                return result + self.solve_polynomial(sympy_expr, expr_str)
            elif expr_type == 'numeric':
                return result + self.solve_numeric(sympy_expr, expr_str)
            elif expr_type == 'derivative':
                return result + self.solve_derivative(expr_str)
            elif expr_type == 'integral':
                return result + self.solve_integral(expr_str)
            else:
                return result + self.solve_general(sympy_expr, expr_str)
                
        except Exception as e:
            return "❌ *Пример не понятный*"
    
    def solve_fraction(self, expr, expr_str):
        """Решение дробей"""
        try:
            num, den = fraction(expr)
            result = ""
            
            # Разложение на множители
            num_factored = factor(num)
            den_factored = factor(den)
            
            if num_factored != num or den_factored != den:
                result += "**📝 Разложение на множители:**\n"
                result += f"`{self.format_expr(num_factored)} / {self.format_expr(den_factored)}`\n\n"
            
            # Сокращение
            simplified = cancel(expr)
            if simplified != expr:
                result += "**📝 После сокращения:**\n"
                result += f"`{self.format_expr(simplified)}`\n\n"
            
            # Область определения
            if den.has(self.x):
                solutions = solve(den, self.x)
                if solutions:
                    result += "**📝 Область определения:**\n"
                    for sol in solutions:
                        result += f"`x ≠ {self.format_expr(sol)}`\n"
                    result += "\n"
            
            result += "**✅ Ответ:**\n"
            result += f"`{self.format_expr(simplified)}`"
            
            return result
            
        except Exception:
            return "❌ *Пример не понятный*"
    
    def solve_polynomial(self, expr, expr_str):
        """Решение многочленов"""
        try:
            simplified = simplify(expr)
            result = "**📝 Упрощение:**\n"
            result += f"`{self.format_expr(simplified)}`\n\n"
            
            # Разложение на множители
            factored = factor(simplified)
            if factored != simplified:
                result += "**📝 Разложение на множители:**\n"
                result += f"`{self.format_expr(factored)}`\n\n"
            
            # Корни для полиномов
            if simplified.is_polynomial() and simplified.has(self.x):
                roots = solve(simplified, self.x)
                if roots:
                    result += "**📝 Корни:**\n"
                    for i, root in enumerate(roots, 1):
                        result += f"`x_{i} = {self.format_expr(root)}`\n"
                    result += "\n"
            
            result += "**✅ Ответ:**\n"
            result += f"`{self.format_expr(simplified)}`"
            
            return result
            
        except Exception:
            return "❌ *Пример не понятный*"
    
    def solve_equation(self, expr_str):
        """Решение уравнений"""
        try:
            processed = self.preprocess_expression(expr_str)
            
            # Извлекаем уравнение
            if 'solve(' in processed:
                match = re.search(r'solve\((.*),\s*(\w+)\)', processed)
                if match:
                    eq_part = match.group(1).strip()
                    var_str = match.group(2).strip()
                    var = symbols(var_str)
                    
                    if '==' in eq_part:
                        left, right = eq_part.split('==', 1)
                        equation = sympify(left) - sympify(right)
                    else:
                        equation = sympify(eq_part)
                else:
                    return "❌ *Пример не понятный*"
            else:
                # Простое уравнение
                if '=' in processed:
                    left, right = processed.split('=', 1)
                    equation = sympify(left.strip()) - sympify(right.strip())
                    var = self.x
                else:
                    return "❌ *Пример не понятный*"
            
            solutions = solve(equation, var)
            
            result = "**📝 Решения уравнения:**\n"
            if solutions:
                for i, sol in enumerate(solutions, 1):
                    result += f"`{var}_{i} = {self.format_expr(sol)}`\n"
            else:
                result += "Решений нет"
            
            return result
            
        except Exception:
            return "❌ *Пример не понятный*"
    
    def solve_numeric(self, expr, expr_str):
        """Решение числовых выражений"""
        try:
            value = float(expr)
            result = "**✅ Ответ:**\n"
            result += f"`{value}`"
            
            if value != int(value):
                result += f"\n\n**📝 Дробь:** `{expr}`"
            
            return result
            
        except Exception:
            return "❌ *Пример не понятный*"
    
    def solve_general(self, expr, expr_str):
        """Решение общих выражений"""
        try:
            simplified = simplify(expr)
            
            result = "**✅ Ответ:**\n"
            result += f"`{self.format_expr(simplified)}`"
            
            if simplified.is_number:
                result += f"\n\n**📝 Число:** `{float(simplified)}`"
            
            return result
            
        except Exception:
            return "❌ *Пример не понятный*"

solver = SmartMathSolver()

def recognize_text_safe(image_path):
    """Безопасное распознавание текста"""
    if not TESSERACT_AVAILABLE:
        return "OCR недоступен"
    
    try:
        image = Image.open(image_path)
        # Увеличиваем изображение для лучшего распознавания
        image = image.resize((image.width * 2, image.height * 2), Image.Resampling.LANCZOS)
        image = image.convert('L')  # Grayscale
        
        # Конфигурация для математических выражений
        custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ()[]{}/*+-=^'
        text = pytesseract.image_to_string(image, config=custom_config)
        text = text.strip()
        
        if not text:
            return "Текст не распознан"
        
        # Замены для математических символов
        replacements = {
            'х': 'x', 'у': 'y', 'з': 'z', 
            '—': '-', '–': '-', '×': '*',
            '÷': '/', 'с': 'c', 'о': 'o'
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
            
        return text
        
    except Exception as e:
        return f"Ошибка: {str(e)}"

async def start(update: Update, context: CallbackContext):
    user = update.effective_user
    text = f"""
👋 Привет, {user.first_name}!

Я умный математический бот! 🧠

**Просто напиши пример:**
• `3*x^2 - 12*x + 12` - многочлены
• `(x^2 - 4)/(x - 2)` - дроби  
• `x^2 - 5*x + 6 = 0` - уравнения
• `2 + 3 * 4^2` - числовые

💡 **Важно:** Используй * для умножения: `3*x` вместо `3x`

Я сам пойму что ты хочешь! ✨
    """
    
    keyboard = [
        [InlineKeyboardButton("🧮 Примеры", callback_data="examples")],
        [InlineKeyboardButton("📝 Синтаксис", callback_data="syntax")]
    ]
    if TESSERACT_AVAILABLE:
        keyboard.append([InlineKeyboardButton("📸 Фото", callback_data="photo_help")])
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_text(update: Update, context: CallbackContext):
    user_input = update.message.text.strip()
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    result = solver.solve_expression(user_input)
    
    keyboard = [[InlineKeyboardButton("🧮 Новый пример", callback_data="new")]]
    await update.message.reply_text(result, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_photo(update: Update, context: CallbackContext):
    if not TESSERACT_AVAILABLE:
        await update.message.reply_text("📸 Распознавание фото временно недоступно")
        return
    
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        
        photo = await update.message.photo[-1].get_file()
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as f:
            temp_path = f.name
        
        await photo.download_to_drive(temp_path)
        text = recognize_text_safe(temp_path)
        os.unlink(temp_path)
        
        if "не распознан" in text.lower() or "ошибка" in text.lower():
            await update.message.reply_text("❌ Не вижу пример на фото")
            return
        
        await update.message.reply_text(f"📸 Вижу: `{text}`")
        
        # Предобработка распознанного текста
        processed_text = solver.preprocess_expression(text)
        result = solver.solve_expression(processed_text)
        
        keyboard = [[InlineKeyboardButton("📸 Еще фото", callback_data="photo_help")]]
        await update.message.reply_text(result, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text("❌ Ошибка с фото")

async def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    if query.data == "examples":
        text = """
🧮 **Примеры:**

**Многочлены:**
`3*x^2 - 12*x + 12`
`x^2 + 2*x + 1`
`2*x^3 - 5*x^2 + 3*x`

**Дроби:**
`(x^2 - 4)/(x - 2)`
`1/(x+1) + 2/(x-1)`

**Уравнения:**
`x^2 - 5*x + 6 = 0`
`solve(x^2 - 9 = 0, x)`

**Числовые:**
`2 + 3 * 4^2`
`(15 - 3) / 4`
        """
        await query.edit_message_text(text, parse_mode='Markdown')
    
    elif query.data == "syntax":
        text = """
📝 **Как писать:**

• Умножение: `3*x` (обязательно!)
• Степень: `x^2` или `x**2`  
• Дроби: `(a+b)/(c+d)`
• Уравнения: `x^2 - 4 = 0`
• Производные: `diff(x^2, x)`
• Интегралы: `integrate(x^2, x)`

💡 **Важно:** Всегда ставь * между числами и переменными!
        """
        await query.edit_message_text(text, parse_mode='Markdown')
    
    elif query.data == "photo_help":
        text = """
📸 **Фото:**

• Четкий печатный текст
• Хорошее освещение
• Пример в одну строку
• Используй * для умножения

✅ **Хорошо:** `3*x^2 - 12`
❌ **Плохо:** `3x^2 - 12`
        """
        await query.edit_message_text(text, parse_mode='Markdown')
    
    elif query.data == "new":
        await query.edit_message_text("✍️ Напиши пример:")

async def handle_any(update: Update, context: CallbackContext):
    if update.message and not (update.message.text or update.message.photo):
        await update.message.reply_text("Напиши математический пример ✍️")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.ALL, handle_any))
    
    logger.info("🤖 Бот запущен!")
    if not TESSERACT_AVAILABLE:
        logger.warning("Tesseract OCR недоступен")
    
    app.run_polling()

if __name__ == '__main__':
    main()
