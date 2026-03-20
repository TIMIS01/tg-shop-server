from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
import logging
from datetime import datetime

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Разрешаем запросы с любых доменов

# Получаем переменные окружения (их настроим позже на Render)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8650034473:AAHOoD4BmYUBTrJCG1o2y8fMjabNIZN3hm8")
ADMIN_IDS = [int(os.environ.get("ADMIN_ID", "8562390004"))]

# Дополнительные админы можно добавить через запятую
# ADMIN_IDS = [8562390004, 123456789, 987654321]

@app.route('/', methods=['GET'])
def home():
    """Проверка, что сервер работает"""
    return jsonify({
        "status": "ok",
        "message": "Telegram Shop Bot Webhook Server is running!",
        "time": datetime.now().isoformat()
    })

@app.route('/api/webhook', methods=['POST'])
def webhook():
    """Основной эндпоинт для приема данных из Mini App"""
    try:
        # Получаем данные из Mini App
        data = request.json
        logger.info(f"📥 Получены данные: {data}")
        
        # Проверяем тип действия
        action = data.get('action')
        
        if action == 'order':
            # Формируем красивое сообщение для заказа
            message = (
                f"🛍 <b>НОВЫЙ ЗАКАЗ!</b>\n\n"
                f"👤 <b>Пользователь:</b> @{data.get('username', 'unknown')}\n"
                f"🆔 <b>ID:</b> <code>{data.get('userId', 'неизвестно')}</code>\n"
                f"🏙️ <b>Город:</b> {data.get('city', 'не указан')}\n"
                f"📦 <b>Товар:</b> {data.get('productName', 'неизвестно')}\n"
                f"📊 <b>Количество:</b> {data.get('quantity', 1)} гр\n"
                f"💰 <b>Сумма:</b> {data.get('totalPrice', 0)} руб.\n"
                f"📅 <b>Время:</b> {data.get('timestamp', datetime.now().isoformat())}"
            )
            
        elif action == 'contact_admin':
            # Формируем сообщение для запроса связи
            message = (
                f"📞 <b>ЗАПРОС СВЯЗИ!</b>\n\n"
                f"👤 <b>Пользователь:</b> @{data.get('username', 'unknown')}\n"
                f"🆔 <b>ID:</b> <code>{data.get('userId', 'неизвестно')}</code>\n"
                f"🏙️ <b>Город:</b> {data.get('city', 'не указан')}\n"
                f"📅 <b>Время:</b> {data.get('timestamp', datetime.now().isoformat())}\n\n"
                f"💬 Сообщение: {data.get('message', 'Пользователь хочет связаться с администратором')}"
            )
        else:
            # Неизвестное действие
            message = f"⚠️ Неизвестное действие: {action}\nДанные: {data}"
        
        # Отправляем сообщение всем администраторам
        success_count = 0
        for admin_id in ADMIN_IDS:
            try:
                response = requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={
                        "chat_id": admin_id,
                        "text": message,
                        "parse_mode": "HTML"
                    },
                    timeout=10
                )
                
                if response.status_code == 200:
                    success_count += 1
                    logger.info(f"✅ Сообщение отправлено админу {admin_id}")
                else:
                    logger.error(f"❌ Ошибка отправки админу {admin_id}: {response.text}")
                    
            except Exception as e:
                logger.error(f"❌ Ошибка при отправке админу {admin_id}: {e}")
        
        # Возвращаем ответ Mini App
        return jsonify({
            "status": "ok",
            "message": f"Отправлено {success_count} из {len(ADMIN_IDS)} админам"
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Ошибка обработки запроса: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/api/test', methods=['GET'])
def test():
    """Тестовый эндпоинт для проверки"""
    return jsonify({
        "status": "ok",
        "message": "Webhook is working!",
        "bot_token_configured": bool(BOT_TOKEN and BOT_TOKEN != "YOUR_BOT_TOKEN_HERE"),
        "admin_count": len(ADMIN_IDS)
    })

# Для локального запуска
if __name__ == '__main__':
    print("\n" + "="*50)
    print("🚀 ЗАПУСК WEBHOOK СЕРВЕРА")
    print("="*50)
    print(f"📡 Локальный адрес: http://127.0.0.1:5000")
    print(f"🔄 Эндпоинт: http://127.0.0.1:5000/api/webhook")
    print(f"🧪 Тест: http://127.0.0.1:5000/api/test")
    print("="*50 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True)