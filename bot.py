import os
import logging
import tempfile
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
import sympy as sp
from sympy import sympify, factor, cancel, apart, latex
from PIL import Image
import pytesseract

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

def format_math_for_notebook(expr_str: str) -> str:
    """Форматирует математическое выражение для записи в тетради"""
    # Заменяем символы для лучшего отображения
    replacements = {
        '**': '^',
        '*': '⋅',
        'sqrt': '√',
        'pi': 'π',
        'oo': '∞'
    }
    
    for old, new in replacements.items():
        expr_str = expr_str.replace(old, new)
    
    return expr_str

def recognize_text_from_image(image_path: str) -> str:
    """Распознает текст с изображения используя OCR"""
    try:
        # Открываем и обрабатываем изображение
        image = Image.open(image_path)
        
        # Увеличиваем контраст для лучшего распознавания
        image = image.convert('L')  # В grayscale
        
        # Используем tesseract для распознавания
        text = pytesseract.image_to_string(image, config='--psm 6 -c tessedit_char_whitelist=0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ()[]{}/*+-=^𝑥𝑦𝑧π∞')
        
        # Очищаем распознанный текст
        text = text.strip()
        
        # Заменяем распознанные символы на правильные математические
        replacements = {
            'х': 'x',
            'у': 'y',
            'з': 'z',
            'с': 'c',
            '—': '-',
            '–': '-',
            '−': '-',
            '×': '*',
            '÷': '/',
            '∗': '*',
            '⋅': '*'
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
            
        return text if text else "Не удалось распознать текст"
        
    except Exception as e:
        return f"Ошибка распознавания: {str(e)}"

async def start(update: Update, context: CallbackContext):
    user = update.effective_user
    welcome_text = f"""
👋 Привет, {user.first_name}!

Я - умный математический бот! 🧮✨

📝 **Я умею:**
• Решать примеры по фото 📸
• Показывать ВСЕ шаги решения
• Форматировать ответ как в тетради
• Работать с дробями, уравнениями и др.

**Просто отправь мне:**
• Текст с примером
• Фото с примером
    """
    
    keyboard = [
        [InlineKeyboardButton("📸 Как отправить фото", callback_data="photo_help")],
        [InlineKeyboardButton("🧮 Примеры", callback_data="examples")],
        [InlineKeyboardButton("📚 Формулы", callback_data="formulas")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

def solve_with_steps(expression: str) -> str:
    """Решает математическое выражение с подробными шагами"""
    try:
        # Очистка выражения
        expr = expression.strip().replace('^', '**').replace('=', '==')
        x, y, z = sp.symbols('x y z')
        
        original_expr = sympify(expr, locals={'x': x, 'y': y, 'z': z})
        
        result = "🧮 **РЕШЕНИЕ ПРИМЕРА**\n\n"
        result += f"**Дано:** `{format_math_for_notebook(str(original_expr))}`\n\n"
        
        # Определяем тип выражения
        if original_expr.is_rational_function():
            return solve_rational_function(original_expr, expr)
        elif 'solve' in expr:
            return solve_equation(expr)
        elif 'diff' in expr:
            return solve_derivative(expr)
        elif 'integrate' in expr:
            return solve_integral(expr)
        else:
            return solve_general_expression(original_expr, expr)
            
    except Exception as e:
        return f"❌ **Ошибка:** Не могу решить этот пример\n`{str(e)}`"

def solve_rational_function(expr, original_str: str) -> str:
    """Решает рациональные функции (дроби)"""
    x = sp.Symbol('x')
    result = "**📝 Шаг 1: Записываем дробь**\n"
    result += f"`{format_math_for_notebook(original_str)}`\n\n"
    
    num, den = expr.as_numer_denom()
    
    result += "**📝 Шаг 2: Выписываем числитель и знаменатель**\n"
    result += f"Числитель: `{format_math_for_notebook(str(num))}`\n"
    result += f"Знаменатель: `{format_math_for_notebook(str(den))}`\n\n"
    
    # Разложение на множители
    result += "**📝 Шаг 3: Разлагаем на множители**\n"
    try:
        num_factored = factor(num)
        den_factored = factor(den)
        result += f"Числитель: `{format_math_for_notebook(str(num_factored))}`\n"
        result += f"Знаменатель: `{format_math_for_notebook(str(den_factored))}`\n\n"
    except:
        result += "Разложение на множители не удалось\n\n"
    
    # Сокращение
    simplified = cancel(expr)
    result += "**📝 Шаг 4: Сокращаем общие множители**\n"
    
    if simplified != expr:
        result += f"После сокращения: `{format_math_for_notebook(str(simplified))}`\n\n"
    else:
        result += "Общих множителей нет\n\n"
    
    # Область определения
    result += "**📝 Шаг 5: Область определения**\n"
    solutions = sp.solve(den, x)
    if solutions:
        result += "Знаменатель ≠ 0:\n"
        for sol in solutions:
            result += f"`x ≠ {format_math_for_notebook(str(sol))}`\n"
    result += "\n"
    
    # Финальный ответ
    result += "**✅ ОТВЕТ:**\n"
    result += f"`{format_math_for_notebook(str(simplified))}`\n\n"
    
    # Дополнительно: десятичное представление если число
    if simplified.is_number:
        result += f"**🔢 Десятичная форма:** `{float(simplified):.6f}`"
    
    return result

def solve_general_expression(expr, original_str: str) -> str:
    """Решает общие математические выражения"""
    result = "**📝 Шаг 1: Исходное выражение**\n"
    result += f"`{format_math_for_notebook(original_str)}`\n\n"
    
    # Упрощение
    simplified = sp.simplify(expr)
    result += "**📝 Шаг 2: Упрощение**\n"
    result += f"`{format_math_for_notebook(str(simplified))}`\n\n"
    
    # Разложение на множители если возможно
    try:
        if simplified.is_polynomial():
            factored = factor(simplified)
            if factored != simplified:
                result += "**📝 Шаг 3: Разложение на множители**\n"
                result += f"`{format_math_for_notebook(str(factored))}`\n\n"
    except:
        pass
    
    result += "**✅ ОТВЕТ:**\n"
    result += f"`{format_math_for_notebook(str(simplified))}`\n\n"
    
    if simplified.is_number:
        result += f"**🔢 Численное значение:** `{float(simplified)}`"
    
    return result

async def handle_text(update: Update, context: CallbackContext):
    """Обработка текстовых сообщений"""
    user_input = update.message.text.strip()
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    result_text = solve_with_steps(user_input)
    
    keyboard = [
        [InlineKeyboardButton("📸 Решить по фото", callback_data="photo_help")],
        [InlineKeyboardButton("🧮 Новый пример", callback_data="new_example")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(result_text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_photo(update: Update, context: CallbackContext):
    """Обработка фотографий с примерами"""
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        
        # Получаем фото
        photo_file = await update.message.photo[-1].get_file()
        
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
            temp_path = temp_file.name
        
        # Скачиваем фото
        await photo_file.download_to_drive(temp_path)
        
        # Распознаем текст
        recognized_text = recognize_text_from_image(temp_path)
        
        # Удаляем временный файл
        os.unlink(temp_path)
        
        if "Не удалось распознать" in recognized_text or not recognized_text:
            await update.message.reply_text(
                "❌ Не удалось распознать пример на фото.\n\n"
                "📸 **Советы для лучшего распознавания:**\n"
                "• Четкий почерк\n"
                "• Хорошее освещение\n"
                "• Пример по центру фото\n"
                "• Контрастные чернила"
            )
            return
        
        await update.message.reply_text(f"📸 **Распознано:** `{recognized_text}`")
        
        # Решаем распознанный пример
        result_text = solve_with_steps(recognized_text)
        
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
    
    if query.data == "photo_help":
        help_text = """
📸 **Как отправить фото для решения:**

1. **Напишите пример** на бумаге четким почерком
2. **Сфотографируйте** при хорошем освещении
3. **Отправьте фото** боту

✅ **Лучше получается распознавать:**
• Печатные цифры и буквы
• Примеры в одну строку
• Хороший контраст (черное на белом)

❌ **Плохо распознается:**
• Курсивный почерк
• Многоэтажные дроби
• Сложные формулы

**Примеры которые хорошо распознаются:**
`(x^2 - 4)/(x - 2)`
`2 + 3 * 5`
`x^2 + 2x + 1`
        """
        await query.edit_message_text(help_text, parse_mode='Markdown')
        
    elif query.data == "examples":
        examples_text = """
🧮 **Примеры для решения:**

**Алгебраические дроби:**
`(x^2 - 4)/(x^2 - 5x + 6)`
`(x^3 - 8)/(x^2 - 4)`

**Упрощение выражений:**
`(x + 2)^2 - (x - 1)^2`
`2(x + 3) - 3(x - 1)`

**Рациональные выражения:**
`1/(x+1) + 2/(x-1)`
`(x/(x-1)) - (1/(x+1))`

**Отправляйте эти примеры текстом или фотографией!**
        """
        await query.edit_message_text(examples_text, parse_mode='Markdown')
        
    elif query.data == "formulas":
        formulas_text = """
📚 **Основные математические обозначения:**

**Степени:**
x² → x^2 или x**2
x³ → x^3 или x**3

**Дроби:**
½ → 1/2
(a+b)/(c+d)

**Корни:**
√4 → sqrt(4)
∛8 → 8**(1/3)

**Греческие буквы:**
π → pi
∞ → oo

**Операции:**
× или * → умножение
÷ или / → деление
        """
        await query.edit_message_text(formulas_text, parse_mode='Markdown')
        
    elif query.data == "new_example":
        await query.edit_message_text("✍️ Введите математический пример или отправьте фото:")

async def handle_any_message(update: Update, context: CallbackContext):
    """Обработчик любых сообщений"""
    if update.message:
        if not (update.message.text or update.message.photo):
            await update.message.reply_text(
                "📝 Отправьте мне математический пример:\n\n"
                "• **Текстом** - напишите пример\n"
                "• **Фото** - сфотографируйте пример\n\n"
                "Я решу его и покажу все шаги решения! 🧮"
            )

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.ALL, handle_any_message))
    
    logger.info("🤖 Бот запущен с распознаванием фото!")
    application.run_polling()

if __name__ == '__main__':
    main()
