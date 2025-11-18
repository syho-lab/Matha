import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
import sympy as sp
from sympy import sympify, SympifyError
import asyncio

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен бота из переменных окружения
BOT_TOKEN = os.environ.get('BOT_TOKEN')

if not BOT_TOKEN:
    raise ValueError("Не установлен BOT_TOKEN в переменных окружения")

class MathBot:
    def __init__(self):
        self.app = Application.builder().token(BOT_TOKEN).build()
        self.setup_handlers()
    
    def setup_handlers(self):
        """Настройка обработчиков команд и сообщений"""
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("help", self.help))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.solve_math))
        self.app.add_handler(CallbackQueryHandler(self.button_handler))
        
        # Обработчик для любых сообщений
        self.app.add_handler(MessageHandler(filters.ALL, self.handle_any_message))
    
    async def start(self, update: Update, context: CallbackContext):
        """Обработчик команды /start"""
        user = update.effective_user
        welcome_text = f"""
👋 Привет, {user.first_name}!

Я - математический бот! 🧮

Просто отправь мне математический пример, и я решу его!

Например:
• `2+2`
• `x**2 - 4`
• `sin(pi/2)`
• `integrate(x**2, x)`
• `diff(x**2, x)`

Поддерживаются: алгебра, тригонометрия, производные, интегралы и многое другое!
        """
        
        keyboard = [
            [InlineKeyboardButton("🧮 Простые примеры", callback_data="simple_examples")],
            [InlineKeyboardButton("📚 Сложные примеры", callback_data="complex_examples")],
            [InlineKeyboardButton("❓ Помощь", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    
    async def help(self, update: Update, context: CallbackContext):
        """Обработчик команды /help"""
        help_text = """
📚 **Доступные операции:**

**Арифметика:**
`2 + 3 * 4`, `(2 + 3) * 4`, `sqrt(16)`

**Алгебра:**
`x**2 + 2*x + 1`, `solve(x**2 - 4, x)`

**Тригонометрия:**
`sin(pi/2)`, `cos(0)`, `tan(pi/4)`

**Производные:**
`diff(x**2, x)`, `diff(sin(x), x)`

**Интегралы:**
`integrate(x**2, x)`, `integrate(sin(x), x)`

**Логарифмы:**
`log(100)`, `ln(E)`

**Примеры использования:**
• `2 + 2 * 2`
• `solve(x**2 - 4 = 0, x)`
• `diff(x**3 + 2*x, x)`
• `integrate(2*x, x)`
        """
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def solve_math(self, update: Update, context: CallbackContext):
        """Решение математических примеров"""
        user_input = update.message.text.strip()
        
        try:
            # Показываем, что бот печатает
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            
            result_text = self.process_math_expression(user_input)
            
            # Создаем инлайн кнопки
            keyboard = [
                [InlineKeyboardButton("🧮 Новый пример", callback_data="new_example")],
                [InlineKeyboardButton("📚 Другие примеры", callback_data="more_examples")],
                [InlineKeyboardButton("❓ Помощь", callback_data="help")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(result_text, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            error_text = f"❌ Ошибка при решении примера:\n`{str(e)}`\n\nПопробуйте другой пример или используйте /help"
            await update.message.reply_text(error_text, parse_mode='Markdown')
    
    def process_math_expression(self, expression: str) -> str:
        """Обработка математического выражения"""
        try:
            # Очистка выражения
            expr = expression.strip().replace('=', '==').replace('^', '**')
            
            # Обработка специальных команд
            if expr.startswith('solve'):
                # Решение уравнений
                equation = expr[6:].strip()  # Убираем 'solve'
                if '==' in equation:
                    left, right = equation.split('==', 1)
                    eq = sympify(left) - sympify(right)
                else:
                    eq = sympify(equation)
                
                solutions = sp.solve(eq)
                result = f"🎯 Решение уравнения:\n`{expression}`\n\n"
                if solutions:
                    if len(solutions) == 1:
                        result += f"📌 Решение: `x = {sp.latex(solutions[0])}`"
                    else:
                        result += "📌 Решения:\n"
                        for i, sol in enumerate(solutions, 1):
                            result += f"`x_{i} = {sp.latex(sol)}`\n"
                else:
                    result += "❌ Уравнение не имеет решений"
                    
            elif expr.startswith('diff'):
                # Производные
                diff_expr = expr[5:].strip()  # Убираем 'diff'
                if ',' in diff_expr:
                    func, var = diff_expr.split(',', 1)
                    x = sp.Symbol(var.strip())
                else:
                    func = diff_expr
                    x = sp.Symbol('x')
                
                derivative = sp.diff(sympify(func), x)
                result = f"📈 Производная:\n`{expression}`\n\n"
                result += f"📌 Результат: `{sp.latex(derivative)}`"
                
            elif expr.startswith('integrate'):
                # Интегралы
                int_expr = expr[9:].strip()  # Убираем 'integrate'
                if ',' in int_expr:
                    func, var = int_expr.split(',', 1)
                    x = sp.Symbol(var.strip())
                else:
                    func = int_expr
                    x = sp.Symbol('x')
                
                integral = sp.integrate(sympify(func), x)
                result = f"📊 Интеграл:\n`{expression}`\n\n"
                result += f"📌 Результат: `{sp.latex(integral)} + C`"
                
            else:
                # Простые выражения
                result_expr = sympify(expr)
                simplified = sp.simplify(result_expr)
                
                result = f"🧮 Пример:\n`{expression}`\n\n"
                result += f"📌 Результат: `{sp.latex(simplified)}`\n\n"
                
                # Дополнительная информация
                if simplified.is_number:
                    result += f"🔢 Численное значение: `{float(simplified):.6f}`"
                else:
                    result += f"📐 Упрощенное выражение: `{sp.latex(simplified)}`"
            
            return result
            
        except SympifyError:
            return "❌ Не могу разобрать выражение. Проверьте синтаксис и попробуйте снова.\nИспользуйте /help для справки."
        except Exception as e:
            return f"❌ Ошибка: {str(e)}\nИспользуйте /help для справки."
    
    async def button_handler(self, update: Update, context: CallbackContext):
        """Обработчик нажатий на инлайн кнопки"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "simple_examples":
            examples_text = """
🧮 **Простые примеры для теста:**

`2 + 2 * 2`
`sqrt(25) + 3**2`
`sin(pi/2) + cos(0)`
`log(100, 10)`
`factorial(5)`
            """
            await query.edit_message_text(examples_text, parse_mode='Markdown')
            
        elif query.data == "complex_examples":
            examples_text = """
📚 **Сложные примеры:**

**Уравнения:**
`solve(x**2 - 4 == 0, x)`
`solve(x**3 - 2*x + 1 == 0, x)`

**Производные:**
`diff(x**3 + 2*x**2 - x, x)`
`diff(sin(x)*cos(x), x)`

**Интегралы:**
`integrate(x**2 + 2*x + 1, x)`
`integrate(sin(x) + cos(x), x)`

**Системы уравнений:**
`solve([x + y - 3, x - y - 1], [x, y])`
            """
            await query.edit_message_text(examples_text, parse_mode='Markdown')
            
        elif query.data == "help":
            await self.help_callback(query)
            
        elif query.data == "new_example":
            await query.edit_message_text("✍️ Введите новый математический пример:")
            
        elif query.data == "more_examples":
            keyboard = [
                [InlineKeyboardButton("🧮 Простые", callback_data="simple_examples")],
                [InlineKeyboardButton("📚 Сложные", callback_data="complex_examples")],
                [InlineKeyboardButton("❓ Помощь", callback_data="help")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("Выберите тип примеров:", reply_markup=reply_markup)
    
    async def help_callback(self, query):
        """Помощь через callback"""
        help_text = """
📚 **Справка по использованию бота:**

**Основные операции:**
• `+` - сложение
• `-` - вычитание  
• `*` - умножение
• `/` - деление
• `**` - возведение в степень
• `sqrt()` - квадратный корень

**Функции:**
• `sin(), cos(), tan()` - тригонометрия
• `log(), ln()` - логарифмы
• `pi, E` - константы

**Команды:**
• `/start` - начать работу
• `/help` - помощь

Просто введите математическое выражение и я его решу! 🎯
        """
        await query.edit_message_text(help_text)
    
    async def handle_any_message(self, update: Update, context: CallbackContext):
        """Обработчик любых сообщений"""
        if update.message:
            # Если это не текст, просим отправить математический пример
            if not update.message.text:
                await update.message.reply_text(
                    "📝 Пожалуйста, отправьте математический пример для решения.\n"
                    "Используйте /help для справки по синтаксису."
                )
    
    def run(self):
        """Запуск бота"""
        logger.info("Бот запущен!")
        self.app.run_polling()

# Создание и запуск бота
if __name__ == '__main__':
    bot = MathBot()
    bot.run()
