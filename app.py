from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import logging
from datetime import datetime, timedelta
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.error("❌ SUPABASE_URL или SUPABASE_KEY не заданы в переменных окружения!")
    raise ValueError("Missing Supabase credentials")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8704743605:AAHh84GQPHEYh4I6idAHIuZPWCsgx2PYwrw")
ADMIN_IDS = [int(os.environ.get("ADMIN_ID", "8562390004"))]

# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ТОВАРАМИ ==========
def get_all_products():
    try:
        response = supabase.table('products').select('*').eq('is_active', True).execute()
        return response.data
    except Exception as e:
        logger.error(f"Ошибка получения товаров: {e}")
        return []

def add_product(name, price, description, images, created_by):
    try:
        response = supabase.table('products').insert({
            'name': name,
            'price': price,
            'description': description,
            'images': images,
            'created_by': created_by,
            'created_at': datetime.now().isoformat()
        }).execute()
        return response.data[0]['id'] if response.data else None
    except Exception as e:
        logger.error(f"Ошибка добавления товара: {e}")
        return None

def update_product(product_id, name=None, price=None, description=None, images=None):
    try:
        updates = {}
        if name is not None: updates['name'] = name
        if price is not None: updates['price'] = price
        if description is not None: updates['description'] = description
        if images is not None: updates['images'] = images
        if updates:
            supabase.table('products').update(updates).eq('id', product_id).execute()
        return True
    except Exception as e:
        logger.error(f"Ошибка обновления товара {product_id}: {e}")
        return False

def delete_product(product_id):
    try:
        supabase.table('products').update({'is_active': False}).eq('id', product_id).execute()
        return True
    except Exception as e:
        logger.error(f"Ошибка удаления товара {product_id}: {e}")
        return False

# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ПРОМОКОДАМИ ==========
def get_promocode(code):
    try:
        response = supabase.table('promocodes').select('*').eq('code', code.upper()).eq('is_active', True).execute()
        if not response.data: return None
        promo = response.data[0]
        if promo['expires_at'] and datetime.now().isoformat() > promo['expires_at']: return None
        if promo['max_uses'] <= promo['used_count']: return None
        return {'id': promo['id'], 'code': promo['code'], 'type': promo['discount_type'], 'value': promo['discount_value'], 'max_uses': promo['max_uses'], 'used_count': promo['used_count'], 'expires_at': promo['expires_at']}
    except Exception as e:
        logger.error(f"Ошибка получения промокода: {e}")
        return None

def use_promocode(promocode_id, user_id, order_amount):
    try:
        response = supabase.table('promocodes').select('used_count').eq('id', promocode_id).execute()
        if response.data:
            new_count = response.data[0]['used_count'] + 1
            supabase.table('promocodes').update({'used_count': new_count}).eq('id', promocode_id).execute()
        supabase.table('promocode_uses').insert({'promocode_id': promocode_id, 'user_id': user_id, 'order_amount': order_amount}).execute()
        return True
    except Exception as e:
        logger.error(f"Ошибка использования промокода: {e}")
        return False

def create_promocode(code, discount_type, discount_value, max_uses, expires_days, created_by):
    try:
        expires_at = (datetime.now() + timedelta(days=expires_days)).isoformat()
        supabase.table('promocodes').insert({'code': code.upper(), 'discount_type': discount_type, 'discount_value': discount_value, 'max_uses': max_uses, 'expires_at': expires_at, 'created_by': created_by}).execute()
        return True
    except Exception as e:
        logger.error(f"Ошибка создания промокода: {e}")
        return False

def get_all_promocodes():
    try:
        response = supabase.table('promocodes').select('*').order('created_at', desc=True).execute()
        return response.data
    except Exception as e:
        logger.error(f"Ошибка получения промокодов: {e}")
        return []

def delete_promocode(promocode_id):
    try:
        supabase.table('promocodes').update({'is_active': False}).eq('id', promocode_id).execute()
        return True
    except Exception as e:
        logger.error(f"Ошибка удаления промокода: {e}")
        return False

# ========== КЛАВИАТУРА ДЛЯ АДМИНОВ ==========
def get_admin_keyboard(user_id):
    return {"inline_keyboard": [[{"text": "✏️ Ответить", "callback_data": f"reply_{user_id}"}, {"text": "📜 История", "callback_data": f"history_{user_id}"}], [{"text": "📦 Заказы", "callback_data": f"orders_{user_id}"}]]}

# ========== ОТПРАВКА СООБЩЕНИЙ АДМИНАМ ==========
def send_message_to_admins(message, user_id=None):
    import requests
    success_count = 0
    reply_markup = get_admin_keyboard(user_id) if user_id else None
    for admin_id in ADMIN_IDS:
        try:
            payload = {"chat_id": admin_id, "text": message, "parse_mode": "HTML"}
            if reply_markup: payload["reply_markup"] = reply_markup
            response = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json=payload, timeout=30)
            if response.status_code == 200: success_count += 1
        except Exception as e: logger.error(f"Ошибка отправки админу {admin_id}: {e}")
    return success_count

# ========== ОСНОВНЫЕ ЭНДПОИНТЫ ==========
@app.route('/')
def home():
    return jsonify({"status": "ok", "message": "Server running"})

@app.route('/api/test')
def test():
    return jsonify({"status": "ok", "supabase_connected": bool(SUPABASE_URL and SUPABASE_KEY)})

@app.route('/api/products', methods=['GET'])
def get_products():
    try:
        products = get_all_products()
        result = []
        for p in products:
            result.append({'id': p['id'], 'name': p['name'], 'price': p['price'], 'description': p.get('description', ''), 'images': p.get('images', [])})
        return jsonify({"status": "ok", "products": result})
    except Exception as e:
        logger.error(f"Ошибка получения товаров: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/add-product', methods=['POST'])
def add_product_endpoint():
    try:
        data = request.json
        name = data.get('name')
        price = data.get('price')
        description = data.get('description', '')
        images = data.get('images', [])
        created_by = data.get('created_by')
        if not name or not price: return jsonify({"status": "error", "message": "Название и цена обязательны"}), 400
        product_id = add_product(name, price, description, images, created_by)
        if product_id: return jsonify({"status": "ok", "product_id": product_id})
        else: return jsonify({"status": "error", "message": "Ошибка добавления"}), 400
    except Exception as e:
        logger.error(f"Ошибка добавления товара: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/update-product', methods=['POST'])
def update_product_endpoint():
    try:
        data = request.json
        product_id = data.get('product_id')
        if not product_id: return jsonify({"status": "error", "message": "ID товара обязателен"}), 400
        update_product(product_id, name=data.get('name'), price=data.get('price'), description=data.get('description'), images=data.get('images'))
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"Ошибка обновления товара: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/delete-product', methods=['POST'])
def delete_product_endpoint():
    try:
        data = request.json
        product_id = data.get('product_id')
        if not product_id: return jsonify({"status": "error", "message": "ID товара обязателен"}), 400
        delete_product(product_id)
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"Ошибка удаления товара: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/check-promo', methods=['POST'])
def check_promo():
    try:
        data = request.json
        code = data.get('code', '').upper()
        promo = get_promocode(code)
        if not promo: return jsonify({"status": "error", "message": "Промокод не найден или недействителен"})
        return jsonify({"status": "ok", "promo": {"code": promo['code'], "type": promo['type'], "value": promo['value']}})
    except Exception as e:
        logger.error(f"Ошибка проверки промокода: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/create-promo', methods=['POST'])
def create_promo():
    try:
        data = request.json
        success = create_promocode(data.get('code'), data.get('discount_type'), data.get('discount_value'), data.get('max_uses', 1), data.get('expires_days', 30), data.get('created_by'))
        if success: return jsonify({"status": "ok", "message": "Промокод создан"})
        else: return jsonify({"status": "error", "message": "Промокод уже существует"}), 400
    except Exception as e:
        logger.error(f"Ошибка создания промокода: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/promos', methods=['GET'])
def get_promos():
    try:
        promos = get_all_promocodes()
        return jsonify({"status": "ok", "promocodes": promos})
    except Exception as e:
        logger.error(f"Ошибка получения промокодов: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/delete-promo', methods=['POST'])
def delete_promo():
    try:
        data = request.json
        delete_promocode(data.get('promo_id'))
        return jsonify({"status": "ok"})
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
        if username: display_name = f"{full_name} (@{username})"
        elif user_id: display_name = f"{full_name} (ID: {user_id})"
        
        if action in ['order', 'contact_admin']:
            supabase.table('messages').insert({'user_id': user_id, 'username': username, 'message_text': data.get('message', ''), 'message_type': action}).execute()
        
        if action == 'order':
            supabase.table('orders').insert({'user_id': user_id, 'username': username, 'product_name': data.get('productName'), 'quantity': data.get('quantity', 1), 'city': data.get('city'), 'total_price': data.get('finalPrice', data.get('totalPrice'))}).execute()
            promo_info = ""
            if data.get('promocode'):
                promo = data['promocode']
                promo_info = f"\n🎫 Промокод: {promo['code']} ({promo['value']}{'%' if promo['type'] == 'percent' else ' руб'})"
                promo_data = get_promocode(promo['code'])
                if promo_data: use_promocode(promo_data['id'], user_id, data.get('finalPrice', data.get('totalPrice')))
            message = f"🛍 <b>НОВЫЙ ЗАКАЗ!</b>\n\n👤 <b>Покупатель:</b> {display_name}\n🆔 <b>ID:</b> <code>{user_id or 'не указан'}</code>\n🏙️ <b>Город:</b> {data.get('city', 'не указан')}\n📦 <b>Товар:</b> {data.get('productName', 'неизвестно')}\n💰 <b>Цена:</b> {data.get('price', 0)} руб.\n{promo_info}\n💵 <b>Итого:</b> {data.get('finalPrice', data.get('totalPrice', 0))} руб."
            send_message_to_admins(message, user_id)
        elif action == 'contact_admin':
            message = f"📞 <b>ЗАПРОС СВЯЗИ!</b>\n\n👤 <b>Пользователь:</b> {display_name}\n🆔 <b>ID:</b> <code>{user_id or 'не указан'}</code>\n🏙️ <b>Город:</b> {data.get('city', 'не указан')}\n💬 Сообщение: {data.get('message', 'Пользователь хочет связаться с администратором')}"
            send_message_to_admins(message, user_id)
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"Ошибка обработки запроса: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
