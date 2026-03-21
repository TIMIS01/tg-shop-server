from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import logging
from datetime import datetime, timedelta
from supabase import create_client, Client
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# ========== НАСТРОЙКА ==========
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# ========== SUPABASE КЛИЕНТ ==========
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.error("❌ SUPABASE_URL или SUPABASE_KEY не заданы в переменных окружения!")
    raise ValueError("Missing Supabase credentials")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ========== ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ==========
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8758750734:AAHw9HokfvqB3ltT6M9g289zfcNut-9TVSs")
ADMIN_IDS = [int(os.environ.get("ADMIN_ID", "8562390004"))]

# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ТОВАРАМИ ==========
def get_all_products():
    """Получить список всех активных товаров"""
    try:
        response = supabase.table('products').select('*').eq('is_active', True).execute()
        return response.data
    except Exception as e:
        logger.error(f"Ошибка получения товаров: {e}")
        return []

def get_product(product_id):
    """Получить товар по ID"""
    try:
        response = supabase.table('products').select('*').eq('id', product_id).eq('is_active', True).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        logger.error(f"Ошибка получения товара {product_id}: {e}")
        return None

def add_product(name, price, unit, image_url, created_by):
    """Добавить новый товар"""
    try:
        response = supabase.table('products').insert({
            'name': name,
            'price': price,
            'unit': unit,
            'image_url': image_url,
            'created_by': created_by,
            'created_at': datetime.now().isoformat()
        }).execute()
        return response.data[0]['id'] if response.data else None
    except Exception as e:
        logger.error(f"Ошибка добавления товара: {e}")
        return None

def update_product(product_id, name=None, price=None, unit=None, image_url=None):
    """Обновить товар"""
    try:
        updates = {}
        if name is not None:
            updates['name'] = name
        if price is not None:
            updates['price'] = price
        if unit is not None:
            updates['unit'] = unit
        if image_url is not None:
            updates['image_url'] = image_url
        
        if updates:
            supabase.table('products').update(updates).eq('id', product_id).execute()
        return True
    except Exception as e:
        logger.error(f"Ошибка обновления товара {product_id}: {e}")
        return False

def delete_product(product_id):
    """Удалить товар (деактивировать)"""
    try:
        supabase.table('products').update({'is_active': False}).eq('id', product_id).execute()
        return True
    except Exception as e:
        logger.error(f"Ошибка удаления товара {product_id}: {e}")
        return False

# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ПРОМОКОДАМИ ==========
def get_promocode(code):
    """Получить промокод по коду"""
    try:
        response = supabase.table('promocodes').select('*').eq('code', code.upper()).eq('is_active', True).execute()
        if not response.data:
            return None
        
        promo = response.data[0]
        # Проверка срока действия
        if promo['expires_at'] and datetime.now().isoformat() > promo['expires_at']:
            return None
        # Проверка лимита использований
        if promo['max_uses'] <= promo['used_count']:
            return None
        
        return {
            'id': promo['id'],
            'code': promo['code'],
            'type': promo['discount_type'],
            'value': promo['discount_value'],
            'max_uses': promo['max_uses'],
            'used_count': promo['used_count'],
            'expires_at': promo['expires_at']
        }
    except Exception as e:
        logger.error(f"Ошибка получения промокода: {e}")
        return None

def use_promocode(promocode_id, user_id, order_amount):
    """Увеличить счетчик использований промокода"""
    try:
        # Получаем текущий used_count
        response = supabase.table('promocodes').select('used_count').eq('id', promocode_id).execute()
        if response.data:
            new_count = response.data[0]['used_count'] + 1
            supabase.table('promocodes').update({'used_count': new_count}).eq('id', promocode_id).execute()
        
        # Записываем использование
        supabase.table('promocode_uses').insert({
            'promocode_id': promocode_id,
            'user_id': user_id,
            'order_amount': order_amount
        }).execute()
        return True
    except Exception as e:
        logger.error(f"Ошибка использования промокода: {e}")
        return False

def create_promocode(code, discount_type, discount_value, max_uses, expires_days, created_by):
    """Создать новый промокод"""
    try:
        expires_at = (datetime.now() + timedelta(days=expires_days)).isoformat()
        response = supabase.table('promocodes').insert({
            'code': code.upper(),
            'discount_type': discount_type,
            'discount_value': discount_value,
            'max_uses': max_uses,
            'expires_at': expires_at,
            'created_by': created_by
        }).execute()
        return response.data is not None
    except Exception as e:
        logger.error(f"Ошибка создания промокода: {e}")
        return False

def get_all_promocodes():
    """Получить все промокоды"""
    try:
        response = supabase.table('promocodes').select('*').order('created_at', desc=True).execute()
        return response.data
    except Exception as e:
        logger.error(f"Ошибка получения промокодов: {e}")
        return []

def delete_promocode(promocode_id):
    """Деактивировать промокод"""
    try:
        supabase.table('promocodes').update({'is_active': False}).eq('id', promocode_id).execute()
        return True
    except Exception as e:
        logger.error(f"Ошибка удаления промокода: {e}")
        return False

# ========== КЛАВИАТУРА ДЛЯ АДМИНОВ ==========
def get_admin_keyboard(user_id):
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
    import requests
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
        except Exception as e:
            logger.error(f"Ошибка отправки админу {admin_id}: {e}")
    
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
        "supabase_connected": bool(SUPABASE_URL and SUPABASE_KEY),
        "time": datetime.now().isoformat()
    })

@app.route('/api/products', methods=['GET'])
def get_products():
    """Получить список товаров для Mini App"""
    try:
        products = get_all_products()
        
        result = []
        for p in products:
            result.append({
                'id': p['id'],
                'name': p['name'],
                'price': p['price'],
                'unit': p.get('unit', 'гр'),
                'image': p.get('image_url') or f'https://via.placeholder.com/300x200?text={p["name"]}'
            })
        
        return jsonify({"status": "ok", "products": result}), 200
    except Exception as e:
        logger.error(f"Ошибка получения товаров: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/add-product', methods=['POST'])
def add_product_endpoint():
    try:
        data = request.json
        name = data.get('name')
        price = data.get('price')
        unit = data.get('unit', 'гр')
        image_url = data.get('image_url')
        created_by = data.get('created_by')
        
        if not name or not price:
            return jsonify({"status": "error", "message": "Название и цена обязательны"}), 400
        
        product_id = add_product(name, price, unit, image_url, created_by)
        
        if product_id:
            logger.info(f"✅ Товар добавлен: {name} (ID: {product_id})")
            return jsonify({"status": "ok", "product_id": product_id}), 200
        else:
            return jsonify({"status": "error", "message": "Ошибка добавления"}), 400
    except Exception as e:
        logger.error(f"Ошибка добавления товара: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/update-product', methods=['POST'])
def update_product_endpoint():
    try:
        data = request.json
        product_id = data.get('product_id')
        
        if not product_id:
            return jsonify({"status": "error", "message": "ID товара обязателен"}), 400
        
        update_product(
            product_id,
            name=data.get('name'),
            price=data.get('price'),
            unit=data.get('unit'),
            image_url=data.get('image_url')
        )
        
        logger.info(f"✅ Товар обновлен: ID {product_id}")
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"Ошибка обновления товара: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/delete-product', methods=['POST'])
def delete_product_endpoint():
    try:
        data = request.json
        product_id = data.get('product_id')
        
        if not product_id:
            return jsonify({"status": "error", "message": "ID товара обязателен"}), 400
        
        delete_product(product_id)
        
        logger.info(f"✅ Товар удален: ID {product_id}")
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"Ошибка удаления товара: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/check-promo', methods=['POST'])
def check_promo():
    try:
        data = request.json
        code = data.get('code', '').upper()
        
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
        logger.error(f"Ошибка проверки промокода: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/create-promo', methods=['POST'])
def create_promo():
    try:
        data = request.json
        code = data.get('code')
        discount_type = data.get('discount_type')
        discount_value = data.get('discount_value')
        max_uses = data.get('max_uses', 1)
        expires_days = data.get('expires_days', 30)
        created_by = data.get('created_by')
        
        success = create_promocode(code, discount_type, discount_value, max_uses, expires_days, created_by)
        
        if success:
            logger.info(f"✅ Промокод создан: {code}")
            return jsonify({"status": "ok", "message": "Промокод создан"}), 200
        else:
            return jsonify({"status": "error", "message": "Промокод уже существует"}), 400
            
    except Exception as e:
        logger.error(f"Ошибка создания промокода: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/promos', methods=['GET'])
def get_promos():
    try:
        promos = get_all_promocodes()
        return jsonify({"status": "ok", "promocodes": promos}), 200
    except Exception as e:
        logger.error(f"Ошибка получения промокодов: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/delete-promo', methods=['POST'])
def delete_promo():
    try:
        data = request.json
        promo_id = data.get('promo_id')
        delete_promocode(promo_id)
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"Ошибка удаления промокода: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/webhook', methods=['POST'])
def webhook():
    try:
        data = request.json
        logger.info(f"📥 Получены данные: {data}")
        
        action = data.get('action')
        
        user_id = data.get('userId')
        username = data.get('username')
        first_name = data.get('firstName')
        last_name = data.get('lastName')
        full_name = data.get('fullName') or f"{first_name or ''} {last_name or ''}".strip() or "Пользователь"
        
        display_name = full_name
        if username:
            display_name = f"{full_name} (@{username})"
        elif user_id:
            display_name = f"{full_name} (ID: {user_id})"
        
        # Сохраняем сообщение в базу
        if action in ['order', 'contact_admin']:
            supabase.table('messages').insert({
                'user_id': user_id,
                'username': username,
                'message_text': data.get('message', ''),
                'message_type': action
            }).execute()
        
        if action == 'order':
            # Сохраняем заказ
            supabase.table('orders').insert({
                'user_id': user_id,
                'username': username,
                'product_name': data.get('productName'),
                'quantity': data.get('quantity', 1),
                'city': data.get('city'),
                'total_price': data.get('finalPrice', data.get('totalPrice'))
            }).execute()
            
            promo_info = ""
            if data.get('promocode'):
                promo = data['promocode']
                promo_type = data.get('promoType', 'discount')
                
                if promo_type == 'discount':
                    promo_info = f"\n🎫 Промокод: {promo['code']} (скидка {promo['value']}%)"
                else:
                    promo_info = f"\n🎫 Промокод: {promo['code']} (+{promo['value']}% бонус к количеству)"
                    if data.get('finalQuantity'):
                        promo_info += f"\n🎁 Бонус: {data.get('quantity', 1)} {data.get('unit', 'гр')} → {data.get('finalQuantity', 0):.2f} {data.get('unit', 'гр')}"
                
                promo_data = get_promocode(promo['code'])
                if promo_data:
                    use_promocode(promo_data['id'], user_id, data.get('finalPrice', data.get('totalPrice')))
            
            quantity_display = f"{data.get('quantity', 1)} {data.get('unit', 'гр')}"
            if data.get('finalQuantity') and data.get('finalQuantity') != data.get('quantity'):
                quantity_display = f"{data.get('quantity', 1)} {data.get('unit', 'гр')} → {data.get('finalQuantity', 0):.2f} {data.get('unit', 'гр')}"
            
            message = (
                f"🛍 <b>НОВЫЙ ЗАКАЗ!</b>\n\n"
                f"👤 <b>Покупатель:</b> {display_name}\n"
                f"🆔 <b>ID:</b> <code>{user_id or 'не указан'}</code>\n"
                f"🏙️ <b>Город:</b> {data.get('city', 'не указан')}\n"
                f"📦 <b>Товар:</b> {data.get('productName', 'неизвестно')}\n"
                f"📊 <b>Количество:</b> {quantity_display}\n"
                f"💰 <b>Цена:</b> {data.get('pricePerUnit', 0)} руб / {data.get('unit', 'гр')}\n"
                f"💵 <b>Сумма:</b> {data.get('totalPrice', 0)} руб.\n"
                f"{promo_info}\n"
                f"💵 <b>Итого к оплате:</b> {data.get('finalPrice', data.get('totalPrice', 0))} руб.\n"
                f"📅 <b>Время:</b> {data.get('timestamp', datetime.now().isoformat())}"
            )
            
            if user_id:
                send_message_to_admins(message, user_id)
            else:
                send_message_to_admins(message)
            
        elif action == 'contact_admin':
            message = (
                f"📞 <b>ЗАПРОС СВЯЗИ!</b>\n\n"
                f"👤 <b>Пользователь:</b> {display_name}\n"
                f"🆔 <b>ID:</b> <code>{user_id or 'не указан'}</code>\n"
                f"🏙️ <b>Город:</b> {data.get('city', 'не указан')}\n"
                f"📅 <b>Время:</b> {data.get('timestamp', datetime.now().isoformat())}\n\n"
                f"💬 Сообщение: {data.get('message', 'Пользователь хочет связаться с администратором')}"
            )
            
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
        logger.error(f"Ошибка обработки запроса: {e}")
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
