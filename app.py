from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
import sqlite3
import secrets
import string
import logging
import time
from datetime import datetime, timedelta

# ========== НАСТРОЙКА ==========
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# ========== ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ==========
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8650034473:AAHOoD4BmYUBTrJCG1o2y8fMjabNIZN3hm8")
ADMIN_IDS = [int(os.environ.get("ADMIN_ID", "8562390004"))]

# ========== БАЗА ДАННЫХ ПРОМОКОДОВ ==========
def init_promocodes_db():
    """Инициализация базы данных промокодов"""
    conn = sqlite3.connect('promocodes.db')
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS promocodes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE,
        discount_type TEXT,
        discount_value INTEGER,
        max_uses INTEGER DEFAULT 1,
        used_count INTEGER DEFAULT 0,
        expires_at TEXT,
        created_by INTEGER,
        created_at TEXT,
        is_active INTEGER DEFAULT 1
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS promocode_uses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        promocode_id INTEGER,
        user_id INTEGER,
        used_at TEXT,
        order_amount INTEGER
    )
    ''')
    conn.commit()
    conn.close()
    logger.info("✅ База данных промокодов инициализирована")

init_promocodes_db()

# ========== ФУНКЦИИ ПРОМОКОДОВ ==========
def generate_promocode(length=8):
    """Генерирует случайный промокод"""
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def create_promocode(code, discount_type, discount_value, max_uses=1, expires_days=30, created_by=None):
    """Создает новый промокод"""
    conn = sqlite3.connect('promocodes.db')
    cursor = conn.cursor()
    
    expires_at = (datetime.now() + timedelta(days=expires_days)).isoformat()
    
    try:
        cursor.execute('''
        INSERT INTO promocodes (code, discount_type, discount_value, max_uses, expires_at, created_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (code.upper(), discount_type, discount_value, max_uses, expires_at, created_by, datetime.now().isoformat()))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_promocode(code):
    """Получает информацию о промокоде"""
    conn = sqlite3.connect('promocodes.db')
    cursor = conn.cursor()
    cursor.execute('''
    SELECT id, code, discount_type, discount_value, max_uses, used_count, expires_at, is_active
    FROM promocodes WHERE code = ? AND is_active = 1
    ''', (code.upper(),))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        if datetime.now().isoformat() > result[6]:
            return None
        if result[4] <= result[5]:
            return None
        return {
            'id': result[0],
            'code': result[1],
            'type': result[2],
            'value': result[3],
            'max_uses': result[4],
            'used_count': result[5],
            'expires_at': result[6]
        }
    return None

def use_promocode(promocode_id, user_id, order_amount):
    """Использует промокод"""
    conn = sqlite3.connect('promocodes.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE promocodes SET used_count = used_count + 1 WHERE id = ?', (promocode_id,))
    cursor.execute('''
    INSERT INTO promocode_uses (promocode_id, user_id, used_at, order_amount)
    VALUES (?, ?, ?, ?)
    ''', (promocode_id, user_id, datetime.now().isoformat(), order_amount))
    conn.commit()
    conn.close()

def get_all_promocodes():
    """Получает список всех промокодов"""
    conn = sqlite3.connect('promocodes.db')
    cursor = conn.cursor()
    cursor.execute('''
    SELECT id, code, discount_type, discount_value, max_uses, used_count, expires_at, is_active, created_at
    FROM promocodes ORDER BY created_at DESC
    ''')
    results = cursor.fetchall()
    conn.close()
    
    promocodes = []
    for r in results:
        promocodes.append({
            'id': r[0],
            'code': r[1],
            'type': r[2],
            'value': r[3],
            'max_uses': r[4],
            'used_count': r[5],
            'expires_at': r[6],
            'is_active': r[7],
            'created_at': r[8]
        })
    return promocodes

def delete_promocode(promocode_id):
    """Деактивирует промокод"""
    conn = sqlite3.connect('promocodes.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE promocodes SET is_active = 0 WHERE id = ?', (promocode_id,))
    conn.commit()
    conn.close()

# ========== КЛАВИАТУРА ДЛЯ АДМИНОВ ==========
def get_admin_keyboard(user_id):
    """Создает клавиатуру с кнопками для администратора"""
    return {
        "inline_keyboard": [
            [
                {"text": "✏️ Ответить", "callback_data": f"reply_{user_id}"},
                {"text": "📜 История", "callback_data": f"history_{user_id}"}
            ],
            [
                {"text": "📦 Заказы", "callback_data": f"orders_{user_id}"}
            ]
        ]
    }

# ========== ОТПРАВКА СООБЩЕНИЙ АДМИНАМ ==========
def send_message_to_admins(message, user_id=None):
    """Отправляет сообщение всем админам с кнопками"""
    success_count = 0
    
    reply_markup = None
    if user_id:
        reply_markup = get_admin_keyboard(user_id)
    
    for admin_id in ADMIN_IDS:
        try:
            payload = {
                "chat_id": admin_id,
                "text": message,
                "parse_mode": "HTML"
            }
            if reply_markup:
                payload["reply_markup"] = reply_markup
            
            response = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                success_count += 1
                logger.info(f"✅ Сообщение отправлено админу {admin_id}")
            else:
                logger.error(f"❌ Ошибка отправки админу {admin_id}: {response.text}")
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке админу {admin_id}: {e}")
    
    return success_count

# ========== ОСНОВНЫЕ ЭНДПОИНТЫ ==========
@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "status": "ok",
        "message": "Telegram Shop Bot Webhook Server is running!",
        "time": datetime.now().isoformat()
    })

@app.route('/api/test', methods=['GET'])
def test():
    return jsonify({
        "status": "ok",
        "message": "Webhook is working!",
        "bot_token_configured": bool(BOT_TOKEN),
        "admin_count": len(ADMIN_IDS),
        "time": datetime.now().isoformat()
    })

@app.route('/api/check-promo', methods=['POST'])
def check_promo():
    """Проверка промокода"""
    try:
        data = request.json
        code = data.get('code', '').upper()
        user_id = data.get('userId')
        order_amount = data.get('orderAmount', 0)
        
        promo = get_promocode(code)
        
        if not promo:
            return jsonify({
                "status": "error",
                "message": "Промокод не найден или недействителен"
            }), 200
        
        return jsonify({
            "status": "ok",
            "promo": {
                "code": promo['code'],
                "type": promo['type'],
                "value": promo['value']
            },
            "message": "Промокод применен!"
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Ошибка проверки промокода: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/api/create-promo', methods=['POST'])
def create_promo():
    """Создание промокода (вызывается из бота)"""
    try:
        data = request.json
        code = data.get('code')
        discount_type = data.get('discount_type')
        discount_value = data.get('discount_value')
        max_uses = data.get('max_uses', 1)
        expires_days = data.get('expires_days', 30)
        created_by = data.get('created_by')
        
        success = create_promocode(
            code=code,
            discount_type=discount_type,
            discount_value=discount_value,
            max_uses=max_uses,
            expires_days=expires_days,
            created_by=created_by
        )
        
        if success:
            logger.info(f"✅ Промокод создан: {code}")
            return jsonify({"status": "ok", "message": "Промокод создан"}), 200
        else:
            return jsonify({"status": "error", "message": "Промокод уже существует"}), 400
            
    except Exception as e:
        logger.error(f"❌ Ошибка создания промокода: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/promos', methods=['GET'])
def get_promos():
    """Получить список всех промокодов"""
    try:
        promos = get_all_promocodes()
        return jsonify({"status": "ok", "promocodes": promos}), 200
    except Exception as e:
        logger.error(f"❌ Ошибка получения промокодов: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/delete-promo', methods=['POST'])
def delete_promo():
    """Удалить промокод"""
    try:
        data = request.json
        promo_id = data.get('promo_id')
        delete_promocode(promo_id)
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"❌ Ошибка удаления промокода: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/webhook', methods=['POST'])
def webhook():
    """Основной эндпоинт для приема данных из Mini App"""
    try:
        data = request.json
        logger.info(f"📥 Получены данные: {data}")
        
        action = data.get('action')
        
        # Получаем данные пользователя
        user_id = data.get('userId')
        username = data.get('username')
        first_name = data.get('firstName')
        last_name = data.get('lastName')
        full_name = data.get('fullName') or f"{first_name or ''} {last_name or ''}".strip() or "Пользователь"
        
        # Формируем отображаемое имя
        display_name = full_name
        if username:
            display_name = f"{full_name} (@{username})"
        elif user_id:
            display_name = f"{full_name} (ID: {user_id})"
        
        if action == 'order':
            # Получаем информацию о промокоде
            promo_info = ""
            if data.get('promocode'):
                promo = data['promocode']
                promo_info = f"\n🎫 Промокод: {promo['code']} ({promo['value']}{'%' if promo['type'] == 'percent' else ' руб'})"
                
                # Записываем использование промокода
                promo_data = get_promocode(promo['code'])
                if promo_data:
                    use_promocode(promo_data['id'], user_id, data.get('finalPrice', data.get('totalPrice')))
            
            # Формируем сообщение для заказа
            message = (
                f"🛍 <b>НОВЫЙ ЗАКАЗ!</b>\n\n"
                f"👤 <b>Покупатель:</b> {display_name}\n"
                f"🆔 <b>ID:</b> <code>{user_id or 'не указан'}</code>\n"
                f"🏙️ <b>Город:</b> {data.get('city', 'не указан')}\n"
                f"📦 <b>Товар:</b> {data.get('productName', 'неизвестно')}\n"
                f"📊 <b>Количество:</b> {data.get('quantity', 1)} гр\n"
                f"💰 <b>Сумма:</b> {data.get('totalPrice', 0)} руб.\n"
                f"{promo_info}\n"
                f"💵 <b>Итого:</b> {data.get('finalPrice', data.get('totalPrice', 0))} руб.\n"
                f"📅 <b>Время:</b> {data.get('timestamp', datetime.now().isoformat())}"
            )
            
            # Отправляем админам с кнопками
            if user_id:
                send_message_to_admins(message, user_id)
            else:
                send_message_to_admins(message)
            
        elif action == 'contact_admin':
            # Формируем сообщение для запроса связи
            message = (
                f"📞 <b>ЗАПРОС СВЯЗИ!</b>\n\n"
                f"👤 <b>Пользователь:</b> {display_name}\n"
                f"🆔 <b>ID:</b> <code>{user_id or 'не указан'}</code>\n"
                f"🏙️ <b>Город:</b> {data.get('city', 'не указан')}\n"
                f"📅 <b>Время:</b> {data.get('timestamp', datetime.now().isoformat())}\n\n"
                f"💬 Сообщение: {data.get('message', 'Пользователь хочет связаться с администратором')}"
            )
            
            # Отправляем админам с кнопками
            if user_id:
                send_message_to_admins(message, user_id)
            else:
                send_message_to_admins(message)
        
        else:
            message = f"⚠️ Неизвестное действие: {action}\nДанные: {data}"
            send_message_to_admins(message)
        
        return jsonify({
            "status": "ok",
            "message": "Заказ обработан"
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Ошибка обработки запроса: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print("\n" + "="*50)
    print("🚀 ЗАПУСК WEBHOOK СЕРВЕРА")
    print("="*50)
    print(f"🤖 BOT_TOKEN: {BOT_TOKEN[:10]}...{BOT_TOKEN[-5:] if BOT_TOKEN else 'не задан'}")
    print(f"👥 ADMIN_IDS: {ADMIN_IDS}")
    print(f"📡 Порт: {port}")
    print("="*50 + "\n")
    app.run(host='0.0.0.0', port=port)
