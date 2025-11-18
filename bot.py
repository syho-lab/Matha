import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
import sympy as sp
from sympy import sympify, SympifyError
from keep_alive import keep_alive

# Запускаем Flask сервер для мониторинга
keep_alive()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')

if not BOT_TOKEN:
    raise ValueError("Не установлен BOT_TOKEN в переменных окружения")

class MathBot:
    def __init__(self):
        self.app = Application.builder().token(BOT_TOKEN).build()
        self.setup_handlers()
    
    def setup_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("help", self.help))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.solve_math))
        self.app.add_handler(CallbackQueryHandler(self.button_handler))
        self.app.add_handler(MessageHandler(filters.ALL, self.handle_any_message))
    
    async def start(self, update: Update, context: CallbackContext):
        user = update.effective_user
        welcome_text = f"""
👋 Привет, {user.first_name}!

Я - математический бот! 🧮

Просто отправь мне математический пример, и я решу его!

Поддерживаются: алгебра, тригонометрия, производные, интегралы и многое другое!
        """
        
        keyboard = [
            [InlineKeyboardButton("🧮 Примеры", callback_data="examples")],
            [InlineKeyboardButton("❓ Помощь", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    
    async def help(self, update: Update, context: CallbackContext):
        help_text = """
📚 **Доступные операции:**

**Арифметика:** `2 + 3 * 4`, `sqrt(16)`
**Алгебра:** `x**2 + 2*x + 1`
**Тригонометрия:** `sin(pi/2)`, `cos(0)`
**Производные:** `diff(x**2, x)`
**Интегралы:** `integrate(x**2, x)`

**Примеры:**
• `2 + 2 * 2`
• `solve(x**2 - 4 = 0, x)`
• `diff(x**3 + 2*x, x)`
        """
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def solve_math(self, update: Update, context: CallbackContext):
        user_input = update.message.text.strip()
        
        try:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            result_text = self.process_math_expression(user_input)
            
            keyboard = [
                [InlineKeyboardButton("🧮 Новый пример", callback_data="new_example")],
                [InlineKeyboardButton("📚 Примеры", callback_data="examples")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(result_text, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            error_text = f"❌ Ошибка: `{str(e)}`\nИспользуйте /help"
            await update.message.reply_text(error_text, parse_mode='Markdown')
    
    def process_math_expression(self, expression: str) -> str:
        try:
            expr = expression.strip().replace('=', '==').replace('^', '**')
            
            if expr.startswith('solve'):
                equation = expr[6:].strip()
                if '==' in equation:
                    left, right = equation.split('==', 1)
                    eq = sympify(left) - sympify(right)
                else:
                    eq = sympify(equation)
                
                solutions = sp.solve(eq)
                result = f"🎯 Уравнение:\n`{expression}`\n\n"
                if solutions:
                    if len(solutions) == 1:
                        result += f"📌 Решение: `x = {sp.latex(solutions[0])}`"
                    else:
                        result += "📌 Решения:\n"
                        for i, sol in enumerate(solutions, 1):
                            result += f"`x_{i} = {sp.latex(sol)}`\n"
                else:
                    result += "❌ Нет решений"
                    
            elif expr.startswith('diff'):
                diff_expr = expr[5:].strip()
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
                int_expr = expr[9:].strip()
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
                result_expr = sympify(expr)
                simplified = sp.simplify(result_expr)
                
                result = f"🧮 Пример:\n`{expression}`\n\n"
                result += f"📌 Результат: `{sp.latex(simplified)}`\n\n"
                
                if simplified.is_number:
                    result += f"🔢 Численно: `{float(simplified):.6f}`"
                else:
                    result += f"📐 Упрощенно: `{sp.latex(simplified)}`"
            
            return result
            
        except SympifyError:
            return "❌ Не могу разобрать выражение.\nИспользуйте /help для справки."
        except Exception as e:
            return f"❌ Ошибка: {str(e)}"
    
    async def button_handler(self, update: Update, context: CallbackContext):
        query = update.callback_query
        await query.answer()
        
        if query.data == "examples":
            examples_text = """
🧮 **Примеры для теста:**

**Простые:**
`2 + 2 * 2`
`sqrt(25)`
`sin(pi/2)`

**Сложные:**
`solve(x**2 - 4 == 0, x)`
`diff(x**3, x)`
`integrate(x**2, x)`
            """
            await query.edit_message_text(examples_text, parse_mode='Markdown')
            
        elif query.data == "help":
            help_text = "📚 Используйте /help для подробной справки"
            await query.edit_message_text(help_text)
            
        elif query.data == "new_example":
            await query.edit_message_text("✍️ Введите новый пример:")
    
    async def handle_any_message(self, update: Update, context: CallbackContext):
        if update.message and not update.message.text:
            await update.message.reply_text(
                "📝 Отправьте математический пример для решения.\n"
                "Используйте /help для справки."
            )
    
    def run(self):
        logger.info("Бот запущен с мониторингом!")
        self.app.run_polling()

if __name__ == '__main__':
    bot = MathBot()
    bot.run()
