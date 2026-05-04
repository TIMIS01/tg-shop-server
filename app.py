import smtplib
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, jsonify, request
from flask_cors import CORS
import os
import logging
import hashlib
import time
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
@app.route('/')
def home():
    return jsonify({"status": "ok", "message": "PCGGPRO Backend is running"})
CORS(app)

# ========== SUPABASE ==========
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if SUPABASE_URL and SUPABASE_KEY:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    logger.info("✅ Supabase подключен")
else:
    supabase = None
    logger.warning("⚠️ Supabase не настроен")

# ========== НАСТРОЙКИ ==========
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
SECRET_KEY = os.environ.get("SECRET_KEY", "super-secret-key-change-me")
app.secret_key = SECRET_KEY

# Настройки почты (для регистрации и уведомлений)
BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "pcggpronotif@gmail.com")

# Хранилище токенов и кодов
admin_tokens = set()
verification_codes = {}

# ========== ОБЩИЙ CSS ДЛЯ АДМИН-ПАНЕЛИ ==========
ADMIN_CSS = '''
<style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: 'Segoe UI', Arial, sans-serif; background: #f0f2f5; display: flex; min-height: 100vh; }
    .sidebar { width: 260px; background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%); color: #ecf0f1; min-height: 100vh; padding: 25px 0; position: fixed; left: 0; top: 0; bottom: 0; overflow-y: auto; }
    .sidebar h2 { padding: 0 25px 25px; font-size: 20px; border-bottom: 1px solid rgba(255,255,255,0.1); margin-bottom: 15px; }
    .sidebar a { color: #bdc3c7; text-decoration: none; display: flex; align-items: center; gap: 10px; padding: 14px 25px; transition: all 0.3s; font-size: 14px; }
    .sidebar a:hover, .sidebar a.active { background: rgba(255,255,255,0.08); color: #fff; border-left: 3px solid #3498db; }
    .content { margin-left: 260px; padding: 30px; width: 100%; }
    h1 { color: #1a1a2e; margin-bottom: 25px; font-size: 28px; }
    .card { background: white; padding: 25px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.06); margin-bottom: 25px; }
    table { width: 100%; border-collapse: collapse; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
    th { background: #f8f9fa; color: #1a1a2e; font-weight: 600; padding: 16px; text-align: left; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px; }
    td { padding: 14px 16px; border-bottom: 1px solid #eee; font-size: 14px; }
    tr:hover { background: #f8f9fa; }
    .btn { padding: 10px 18px; border: none; border-radius: 8px; cursor: pointer; font-size: 13px; font-weight: 500; transition: all 0.2s; }
    .btn:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
    .btn-primary { background: #3498db; color: white; }
    .btn-danger { background: #e74c3c; color: white; }
    .btn-success { background: #2ecc71; color: white; }
    .btn-warning { background: #f39c12; color: white; }
    .btn-info { background: #9b59b6; color: white; }
    .badge { padding: 5px 12px; border-radius: 20px; font-size: 11px; font-weight: 600; text-transform: uppercase; }
    .badge-success { background: #d4edda; color: #155724; }
    .badge-warning { background: #fff3cd; color: #856404; }
    .badge-info { background: #d1ecf1; color: #0c5460; }
    .badge-danger { background: #f8d7da; color: #721c24; }
    .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); justify-content: center; align-items: center; z-index: 1000; }
    .modal-content { background: white; padding: 30px; border-radius: 16px; width: 600px; max-height: 80vh; overflow-y: auto; }
    .modal-content input, .modal-content textarea, .modal-content select { width: 100%; padding: 12px; margin-bottom: 15px; border: 1px solid #ddd; border-radius: 8px; font-size: 14px; }
    .modal-content label { font-weight: 600; display: block; margin-bottom: 6px; color: #333; }
    .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 30px; }
    .stat-card { background: white; padding: 25px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.06); text-align: center; }
    .stat-card h3 { font-size: 36px; margin-bottom: 8px; }
    .stat-card p { color: #666; font-size: 14px; }
    .stat-card:nth-child(1) h3 { color: #3498db; }
    .stat-card:nth-child(2) h3 { color: #2ecc71; }
    .stat-card:nth-child(3) h3 { color: #f39c12; }
    .stat-card:nth-child(4) h3 { color: #e74c3c; }
    .detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 20px; }
    .detail-item { padding: 10px 0; border-bottom: 1px solid #eee; }
    .detail-item strong { display: block; color: #666; font-size: 12px; margin-bottom: 3px; }
    .detail-item span { font-size: 15px; }
</style>
'''

# ========== ФУНКЦИИ ОТПРАВКИ ПИСЕМ ==========
def send_email(to_email, subject, body):
    """Отправляет письмо через Brevo API."""
    BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
    SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "pcggpronotif@gmail.com")
    SENDER_NAME = "PCGGPRO"
    
    if not BREVO_API_KEY:
        logger.error("❌ BREVO_API_KEY не задан!")
        return False
    
    try:
        import requests as http_requests
        
        payload = {
            "sender": {"email": SENDER_EMAIL, "name": SENDER_NAME},
            "to": [{"email": to_email}],
            "subject": subject,
            "htmlContent": body
        }
        
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "api-key": BREVO_API_KEY
        }
        
        response = http_requests.post(
            "https://api.brevo.com/v3/smtp/email",
            json=payload,
            headers=headers,
            timeout=15
        )
        
        if response.status_code == 201:
            logger.info(f"✅ Письмо отправлено на {to_email} через Brevo API")
            return True
        else:
            logger.error(f"❌ Ошибка Brevo: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Ошибка отправки письма через Brevo: {e}")
        return False


def send_order_notification(order_data):
    """Отправляет уведомление о новом заказе на почту продавца через Brevo API."""
    BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "pcggpronotif@gmail.com")
    SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "pcggpronotif@gmail.com")
    SENDER_NAME = "PCGGPRO"

    if not BREVO_API_KEY:
        logger.error("❌ BREVO_API_KEY не задан!")
        return False

    try:
        import requests as http_requests

        subject = f"🛒 Новый заказ #{order_data.get('order_id', '—')} | PCGGPRO"
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2 style="color: #4a9eff;">🛒 Новый заказ на PCGGPRO</h2>
            <table style="border-collapse: collapse; width: 100%;">
                <tr><td style="padding: 8px; font-weight: bold;">Номер заказа:</td><td style="padding: 8px;">#{order_data.get('order_id', '—')}</td></tr>
                <tr><td style="padding: 8px; font-weight: bold;">Товары:</td><td style="padding: 8px;">{order_data.get('product_name', '—')}</td></tr>
                <tr><td style="padding: 8px; font-weight: bold;">Сумма:</td><td style="padding: 8px;">{order_data.get('price', 0)} руб.</td></tr>
                <tr><td style="padding: 8px; font-weight: bold;">Город:</td><td style="padding: 8px;">{order_data.get('city', '—')}</td></tr>
                <tr><td style="padding: 8px; font-weight: bold;">Почтовое отделение:</td><td style="padding: 8px;">{order_data.get('postal', '—')}</td></tr>
                <tr><td style="padding: 8px; font-weight: bold;">Комментарий:</td><td style="padding: 8px;">{order_data.get('comment', '—')}</td></tr>
                <tr><td style="padding: 8px; font-weight: bold;">Дата:</td><td style="padding: 8px;">{order_data.get('timestamp', '—')}</td></tr>
            </table>
            <p style="margin-top: 20px; color: #666;">Свяжитесь с покупателем для уточнения деталей.</p>
        </body>
        </html>
        """

        payload = {
            "sender": {"email": SENDER_EMAIL, "name": SENDER_NAME},
            "to": [{"email": ADMIN_EMAIL}],
            "subject": subject,
            "htmlContent": body
        }

        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "api-key": BREVO_API_KEY
        }

        response = http_requests.post(
            "https://api.brevo.com/v3/smtp/email",
            json=payload,
            headers=headers,
            timeout=15
        )

        if response.status_code == 201:
            logger.info(f"✅ Уведомление о заказе отправлено на {ADMIN_EMAIL}")
            return True
        else:
            logger.error(f"❌ Ошибка Brevo: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Ошибка отправки уведомления: {e}")
        return False


# ========== API ДЛЯ ТОВАРОВ ==========
@app.route('/api/products', methods=['GET'])
def get_products():
    try:
        response = supabase.table('products').select('*').eq('is_active', True).execute()
        products = response.data
        return jsonify({"status": "ok", "products": products})
    except Exception as e:
        logger.error(f"Ошибка получения товаров: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/products', methods=['POST'])
def add_product():
    data = request.json
    try:
        response = supabase.table('products').insert({
            'name': data['name'],
            'price': int(data['price']),
            'cpu': data.get('cpu', ''),
            'gpu': data.get('gpu', ''),
            'ram': data.get('ram', ''),
            'storage': data.get('storage', ''),
            'psu': data.get('psu', ''),
            'description': data.get('description', ''),
            'images': data.get('images', []),
            'is_active': True,
            'created_at': datetime.now().isoformat()
        }).execute()
        return jsonify({"status": "ok", "product": response.data[0]})
    except Exception as e:
        logger.error(f"Ошибка добавления товара: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    data = request.json
    try:
        updates = {}
        for field in ['name', 'price', 'cpu', 'gpu', 'ram', 'storage', 'psu', 'description', 'images', 'is_active']:
            if field in data:
                updates[field] = data[field]
        
        if updates:
            supabase.table('products').update(updates).eq('id', product_id).execute()
        
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"Ошибка обновления товара: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    try:
        supabase.table('products').update({'is_active': False}).eq('id', product_id).execute()
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"Ошибка удаления товара: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ========== API ДЛЯ ЗАКАЗОВ ==========
@app.route('/api/orders', methods=['GET'])
def get_orders():
    try:
        response = supabase.table('orders').select('*').order('created_at', desc=True).execute()
        return jsonify({"status": "ok", "orders": response.data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/orders/by-email', methods=['GET'])
def get_orders_by_email():
    email = request.args.get('email', '').strip().lower()
    if not email:
        return jsonify({"status": "error", "message": "Email не указан"}), 400
    try:
        response = supabase.table('orders').select('*').eq('user_email', email).order('created_at', desc=True).execute()
        return jsonify({"status": "ok", "orders": response.data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/orders/<int:order_id>/status', methods=['PUT'])
def update_order_status(order_id):
    data = request.json
    try:
        updates = {}
        if 'status' in data:
            updates['status'] = data['status']
        if 'tracking_number' in data:
            updates['tracking_number'] = data['tracking_number']
        
        if updates:
            supabase.table('orders').update(updates).eq('id', order_id).execute()
        
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ========== API ДЛЯ ПОЛЬЗОВАТЕЛЕЙ ==========
@app.route('/api/users', methods=['GET'])
def get_users():
    try:
        response = supabase.table('users').select('*').order('created_at', desc=True).execute()
        return jsonify({"status": "ok", "users": response.data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ========== АВТОРИЗАЦИЯ И РЕГИСТРАЦИЯ ==========
@app.route('/api/send-verification', methods=['POST'])
def send_verification_code():
    """Отправляет код подтверждения на почту."""
    data = request.json
    email = data.get('email', '').strip().lower()

    if not email or '@' not in email:
        return jsonify({"status": "error", "message": "Некорректный email"}), 400

    # ✅ НОВАЯ ПРОВЕРКА: если пользователь с такой почтой уже есть — запрещаем
    try:
        existing_user = supabase.table('users').select('id').eq('email', email).execute()
        if existing_user.data and len(existing_user.data) > 0:
            return jsonify({"status": "error", "message": "Пользователь с такой почтой уже зарегистрирован. Войдите или используйте другую почту."}), 409
    except Exception as e:
        logger.error(f"Ошибка проверки существующего пользователя: {e}")
        # Если произошла ошибка проверки, продолжаем выполнение, чтобы не блокировать регистрацию

    # Генерируем 6-значный код
    code = str(random.randint(100000, 999999))
    
    # Сохраняем код
    verification_codes[email] = {
        "code": code,
        "timestamp": time.time(),
        "attempts": 0
    }

    # Отправляем письмо
    subject = "Подтверждение почты | PCGGPRO"
    body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto;">
        <h2 style="color: #4a9eff;">🖥️ PCGGPRO</h2>
        <p>Ваш код подтверждения:</p>
        <h1 style="letter-spacing: 5px; color: #333;">{code}</h1>
        <p>Введите этот код на странице регистрации для подтверждения вашей почты.</p>
        <p style="color: #999; font-size: 12px;">Код действителен в течение 10 минут.</p>
    </div>
    """

    if send_email(email, subject, body):
        return jsonify({"status": "ok", "code": code})
    else:
        return jsonify({"status": "error", "message": "Не удалось отправить код"}), 500

@app.route('/api/verify-email', methods=['POST'])
def verify_email_code():
    data = request.json
    email = data.get('email', '').strip().lower()
    code = data.get('code', '').strip()

    if email not in verification_codes:
        return jsonify({"status": "error", "message": "Код не найден или истёк"}), 400

    stored_data = verification_codes[email]

    if time.time() - stored_data["timestamp"] > 600:
        del verification_codes[email]
        return jsonify({"status": "error", "message": "Код истёк. Запросите новый"}), 400

    if stored_data["attempts"] >= 3:
        del verification_codes[email]
        return jsonify({"status": "error", "message": "Превышено количество попыток. Запросите новый код"}), 400

    stored_data["attempts"] += 1

    if stored_data["code"] == code:
        del verification_codes[email]
        return jsonify({"status": "ok", "message": "Почта подтверждена"})
    else:
        return jsonify({"status": "error", "message": "Неверный код"}), 400

@app.route('/api/register', methods=['POST'])
def register_user():
    data = request.json
    try:
        existing = supabase.table('users').select('id').eq('email', data['email']).execute()
        if existing.data:
            return jsonify({"status": "error", "message": "Пользователь с таким email уже существует"}), 400

        password_hash = hashlib.sha256(data['password'].encode()).hexdigest()

        response = supabase.table('users').insert({
            'full_name': data.get('full_name', ''),
            'email': data['email'].lower(),
            'telegram': data.get('telegram', ''),
            'city': data.get('city', ''),
            'password_hash': password_hash,
            'email_verified': data.get('email_verified', False),
            'created_at': datetime.now().isoformat()
        }).execute()

        return jsonify({"status": "ok", "user": response.data[0]})
    except Exception as e:
        logger.error(f"Ошибка регистрации: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/login', methods=['POST'])
def login_user():
    data = request.json
    try:
        response = supabase.table('users').select('*').eq('email', data['email'].lower()).execute()
        if not response.data:
            return jsonify({"status": "error", "message": "Неверный email или пароль"}), 401

        user = response.data[0]
        password_hash = hashlib.sha256(data['password'].encode()).hexdigest()

        if user['password_hash'] != password_hash:
            return jsonify({"status": "error", "message": "Неверный email или пароль"}), 401

        token = hashlib.sha256(f"{SECRET_KEY}{user['id']}{time.time()}".encode()).hexdigest()

        return jsonify({
            "status": "ok",
            "token": token,
            "user": {
                "id": user['id'],
                "full_name": user['full_name'],
                "email": user['email'],
                "telegram": user.get('telegram', ''),
                "city": user.get('city', '')
            }
        })
    except Exception as e:
        logger.error(f"Ошибка входа: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ========== ВЕБХУК ДЛЯ БОТА И САЙТА ==========
@app.route('/api/webhook', methods=['POST'])
def webhook():
    try:
        data = request.json
        logger.info(f"📥 Получены данные из Mini App: {data}")
        
        action = data.get('action')
        
        if action == 'order':
            order_data = {
                'user_id': str(data.get('userId', 'website_user')),
                'username': data.get('username', data.get('full_name', 'Пользователь')),
                'full_name': data.get('full_name', data.get('username', 'Пользователь')),
                'user_email': data.get('user_email', ''),
                'telegram': data.get('telegram', ''),
                'product_name': data.get('productName'),
                'quantity': data.get('quantity', 1),
                'city': data.get('city'),
                'total_price': data.get('finalPrice', data.get('totalPrice', data.get('price', 0))),
                'status': 'оформлен',
                'created_at': datetime.now().isoformat()
            }
            
            # Удаляем ключи со значением None, чтобы не пытаться вставить их в БД
            order_data = {k: v for k, v in order_data.items() if v is not None}
            
            response = supabase.table('orders').insert(order_data).execute()
            
            # Отправка уведомления о новом заказе на почту
            order_notification_data = {
                "order_id": response.data[0]['id'] if response.data else '—',
                "product_name": data.get('productName', '—'),
                "price": data.get('price', data.get('totalPrice', 0)),
                "city": data.get('city', '—'),
                "postal": data.get('postal', '—'),
                "comment": data.get('comment', '—'),
                "timestamp": datetime.now().strftime("%d.%m.%Y %H:%M")
            }
            send_order_notification(order_notification_data)
            
            return jsonify({"status": "ok", "message": "Заказ принят"}), 200
        
        return jsonify({"status": "ok", "message": "Обработано"}), 200
        
    except Exception as e:
        logger.error(f"Ошибка обработки данных Mini App: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ========== АДМИН-ПАНЕЛЬ: СТРАНИЦЫ ==========
@app.route('/admin')
def admin_login_page():
    return f'''
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Вход в админ-панель | PC Shop</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); display: flex; justify-content: center; align-items: center; height: 100vh; }}
            .login-box {{ background: white; padding: 50px; border-radius: 20px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); width: 400px; }}
            .login-box h2 {{ text-align: center; margin-bottom: 35px; color: #1a1a2e; font-size: 28px; }}
            .login-box input {{ width: 100%; padding: 15px; margin-bottom: 20px; border: 2px solid #e0e0e0; border-radius: 12px; font-size: 16px; transition: border-color 0.3s; }}
            .login-box input:focus {{ border-color: #667eea; outline: none; }}
            .login-box button {{ width: 100%; padding: 15px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 12px; font-size: 16px; font-weight: 600; cursor: pointer; transition: transform 0.2s; }}
            .login-box button:hover {{ transform: translateY(-2px); }}
            .error {{ color: #e74c3c; text-align: center; margin-top: 15px; display: none; }}
        </style>
    </head>
    <body>
        <div class="login-box">
            <h2>🔒 Админ-панель</h2>
            <form id="loginForm">
                <input type="password" id="password" placeholder="Введите пароль" required>
                <button type="submit">Войти</button>
                <div class="error" id="error">Неверный пароль</div>
            </form>
        </div>
        <script>
            document.getElementById('loginForm').addEventListener('submit', async (e) => {{
                e.preventDefault();
                const password = document.getElementById('password').value;
                const response = await fetch('/api/admin/login', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ password: password }})
                }});
                if (response.ok) {{
                    const data = await response.json();
                    localStorage.setItem('admin_token', data.token);
                    window.location.href = '/admin/dashboard';
                }} else {{
                    document.getElementById('error').style.display = 'block';
                }}
            }});
        </script>
    </body>
    </html>
    '''

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    data = request.json
    if data.get('password') == ADMIN_PASSWORD:
        token = hashlib.sha256(f"{SECRET_KEY}{time.time()}".encode()).hexdigest()
        admin_tokens.add(token)
        return jsonify({"status": "ok", "token": token})
    return jsonify({"status": "error", "message": "Неверный пароль"}), 401

@app.route('/admin/dashboard')
def admin_dashboard():
    return f'''
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Дашборд | Админ-панель</title>
        {ADMIN_CSS}
    </head>
    <body>
        <div class="sidebar">
            <h2>🖥️ PC Shop</h2>
            <a href="/admin/dashboard" class="active">📊 Дашборд</a>
            <a href="/admin/products">📦 Товары</a>
            <a href="/admin/orders">🛒 Заказы</a>
            <a href="/admin/users">👥 Пользователи</a>
            <a href="/admin/support">💬 Поддержка</a>
            <a href="/admin/chats">💬 Чаты</a>
            <a href="#" onclick="logout()" style="margin-top: auto;">🚪 Выйти</a>
        </div>
        <div class="content">
            <h1>📊 Дашборд</h1>
            <div class="stats">
                <div class="stat-card">
                    <h3 id="productsCount">0</h3>
                    <p>Товаров в каталоге</p>
                </div>
                <div class="stat-card">
                    <h3 id="ordersCount">0</h3>
                    <p>Всего заказов</p>
                </div>
                <div class="stat-card">
                    <h3 id="newOrdersCount">0</h3>
                    <p>Новых заказов</p>
                </div>
                <div class="stat-card">
                    <h3 id="revenueCount">0 ₽</h3>
                    <p>Выручка</p>
                </div>
            </div>
        </div>
        <script>
            async function loadStats() {{
                const productsRes = await fetch('/api/products');
                const productsData = await productsRes.json();
                document.getElementById('productsCount').textContent = productsData.products?.length || 0;
                
                const ordersRes = await fetch('/api/orders');
                const ordersData = await ordersRes.json();
                const orders = ordersData.orders || [];
                document.getElementById('ordersCount').textContent = orders.length;
                document.getElementById('newOrdersCount').textContent = orders.filter(o => o.status === 'оформлен').length;
                
                const totalRevenue = orders.reduce((sum, o) => sum + (o.total_price || 0), 0);
                document.getElementById('revenueCount').textContent = totalRevenue.toLocaleString() + ' ₽';
            }}
            
            function logout() {{
                localStorage.removeItem('admin_token');
                window.location.href = '/admin';
            }}
            
            loadStats();
        </script>
    </body>
    </html>
    '''

@app.route('/admin/products')
def admin_products():
    return f'''
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Товары | Админ-панель</title>
        {ADMIN_CSS}
    </head>
    <body>
        <div class="sidebar">
            <h2>🖥️ PC Shop</h2>
            <a href="/admin/dashboard">📊 Дашборд</a>
            <a href="/admin/products" class="active">📦 Товары</a>
            <a href="/admin/orders">🛒 Заказы</a>
            <a href="/admin/users">👥 Пользователи</a>
            <a href="/admin/support">💬 Поддержка</a>
            <a href="/admin/chats">💬 Чаты</a>
            <a href="#" onclick="logout()">🚪 Выйти</a>
        </div>
        <div class="content">
            <h1>📦 Управление товарами</h1>
            <button class="btn btn-success" onclick="openAddModal()" style="margin-bottom: 25px;">+ Добавить товар</button>
            <div class="card">
                <table id="productsTable">
                    <thead>
                        <tr><th>ID</th><th>Название</th><th>Цена</th><th>Характеристики</th><th>Действия</th></tr>
                    </thead>
                    <tbody></tbody>
                </table>
            </div>
        </div>
        
        <div class="modal" id="productModal">
            <div class="modal-content">
                <h2 id="modalTitle">Добавить товар</h2>
                <form id="productForm">
                    <input type="hidden" id="productId">
                    <label>Название</label>
                    <input type="text" id="name" required>
                    <label>Цена (₽)</label>
                    <input type="number" id="price" required>
                    <div class="detail-grid">
                        <div><label>Процессор</label><input type="text" id="cpu"></div>
                        <div><label>Видеокарта</label><input type="text" id="gpu"></div>
                        <div><label>ОЗУ</label><input type="text" id="ram"></div>
                        <div><label>Накопитель</label><input type="text" id="storage"></div>
                        <div><label>Блок питания</label><input type="text" id="psu"></div>
                    </div>
                    <label>Описание</label>
                    <textarea id="description" rows="4"></textarea>
                    <div style="margin-top: 20px; display: flex; gap: 10px;">
                        <button type="submit" class="btn btn-primary">Сохранить</button>
                        <button type="button" class="btn btn-danger" onclick="closeModal()">Отмена</button>
                    </div>
                </form>
            </div>
        </div>
        <script>
            let editingId = null;
            
            async function loadProducts() {{
                const response = await fetch('/api/products');
                const data = await response.json();
                const tbody = document.querySelector('#productsTable tbody');
                tbody.innerHTML = (data.products || []).map(p => `
                    <tr>
                        <td>${{p.id}}</td>
                        <td><strong>${{p.name}}</strong></td>
                        <td>${{p.price.toLocaleString()}} ₽</td>
                        <td><small>${{[p.cpu, p.gpu, p.ram].filter(Boolean).join(' / ') || '—'}}</small></td>
                        <td>
                            <button class="btn btn-primary" onclick="editProduct(${{p.id}})">✏️</button>
                            <button class="btn btn-danger" onclick="deleteProduct(${{p.id}})">🗑️</button>
                        </td>
                    </tr>
                `).join('');
            }}
            
            function openAddModal() {{ editingId = null; document.getElementById('modalTitle').textContent = 'Добавить товар'; document.getElementById('productForm').reset(); document.getElementById('productModal').style.display = 'flex'; }}
            function closeModal() {{ document.getElementById('productModal').style.display = 'none'; }}
            
            async function editProduct(id) {{
                editingId = id;
                document.getElementById('modalTitle').textContent = 'Редактировать товар';
                const response = await fetch('/api/products');
                const data = await response.json();
                const product = (data.products || []).find(p => p.id === id);
                if (product) {{
                    document.getElementById('productId').value = product.id;
                    document.getElementById('name').value = product.name || '';
                    document.getElementById('price').value = product.price || '';
                    document.getElementById('cpu').value = product.cpu || '';
                    document.getElementById('gpu').value = product.gpu || '';
                    document.getElementById('ram').value = product.ram || '';
                    document.getElementById('storage').value = product.storage || '';
                    document.getElementById('psu').value = product.psu || '';
                    document.getElementById('description').value = product.description || '';
                    document.getElementById('productModal').style.display = 'flex';
                }}
            }}
            
            async function deleteProduct(id) {{
                if (confirm('Удалить товар навсегда?')) {{
                    await fetch(`/api/products/${{id}}`, {{ method: 'DELETE' }});
                    loadProducts();
                }}
            }}
            
            document.getElementById('productForm').addEventListener('submit', async (e) => {{
                e.preventDefault();
                const productData = {{
                    name: document.getElementById('name').value,
                    price: parseInt(document.getElementById('price').value),
                    cpu: document.getElementById('cpu').value,
                    gpu: document.getElementById('gpu').value,
                    ram: document.getElementById('ram').value,
                    storage: document.getElementById('storage').value,
                    psu: document.getElementById('psu').value,
                    description: document.getElementById('description').value,
                    images: []
                }};
                
                if (editingId) {{
                    await fetch(`/api/products/${{editingId}}`, {{ method: 'PUT', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify(productData) }});
                }} else {{
                    await fetch('/api/products', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify(productData) }});
                }}
                closeModal();
                loadProducts();
            }});
            
            function logout() {{ localStorage.removeItem('admin_token'); window.location.href = '/admin'; }}
            loadProducts();
        </script>
    </body>
    </html>
    '''

@app.route('/admin/orders')
def admin_orders():
    return f'''
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Заказы | Админ-панель</title>
        {ADMIN_CSS}
    </head>
    <body>
        <div class="sidebar">
            <h2>🖥️ PC Shop</h2>
            <a href="/admin/dashboard">📊 Дашборд</a>
            <a href="/admin/products">📦 Товары</a>
            <a href="/admin/orders" class="active">🛒 Заказы</a>
            <a href="/admin/users">👥 Пользователи</a>
            <a href="/admin/support">💬 Поддержка</a>
            <a href="/admin/chats">💬 Чаты</a>
            <a href="#" onclick="logout()">🚪 Выйти</a>
        </div>
        <div class="content">
            <h1>🛒 Заказы</h1>
            <div class="card">
                <table id="ordersTable">
                    <thead>
                        <tr><th>ID</th><th>Клиент</th><th>Email</th><th>Товар</th><th>Сумма</th><th>Город</th><th>Статус</th><th>Дата</th><th>Действия</th></tr>
                    </thead>
                    <tbody></tbody>
                </table>
            </div>
        </div>
        
        <div class="modal" id="orderModal">
            <div class="modal-content">
                <h2>Детали заказа</h2>
                <div id="orderDetails"></div>
                <div style="margin-top: 20px;">
                    <label>Изменить статус</label>
                    <select id="orderStatus" style="width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 8px;">
                        <option value="оформлен">Оформлен</option>
                        <option value="принят">Принят</option>
                        <option value="в сборке">В сборке</option>
                        <option value="отправлен">Отправлен</option>
                        <option value="доставлен">Доставлен</option>
                        <option value="отменён">Отменён</option>
                    </select>
                    <label style="margin-top: 15px;">Трек-номер</label>
                    <input type="text" id="trackingNumber" placeholder="Введите трек-номер">
                    <div style="margin-top: 15px; display: flex; gap: 10px;">
                        <button class="btn btn-primary" onclick="saveOrderStatus()">Сохранить</button>
                        <button class="btn btn-danger" onclick="closeModal()">Закрыть</button>
                    </div>
                </div>
            </div>
        </div>
        <script>
            let currentOrderId = null;
            
            async function loadOrders() {{
                const response = await fetch('/api/orders');
                const data = await response.json();
                const tbody = document.querySelector('#ordersTable tbody');
                const statusBadges = {{
                    'оформлен': 'badge-info',
                    'принят': 'badge-warning',
                    'в сборке': 'badge-warning',
                    'отправлен': 'badge-primary',
                    'доставлен': 'badge-success',
                    'отменён': 'badge-danger'
                }};
                
                tbody.innerHTML = (data.orders || []).map(o => {{
                    const date = new Date(o.created_at || o.order_date);
                    const dateStr = date.toLocaleString('ru-RU', {{ day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }});
                    return `
                        <tr>
                            <td>#${{o.id}}</td>
                            <td><strong>${{o.full_name || o.username || '—'}}</strong></td>
                            <td>${{o.user_email || '—'}}</td>
                            <td>${{o.product_name || '—'}}</td>
                            <td>${{(o.total_price || 0).toLocaleString()}} ₽</td>
                            <td>${{o.city || '—'}}</td>
                            <td><span class="badge ${{statusBadges[o.status] || 'badge-info'}}">${{o.status || 'оформлен'}}</span></td>
                            <td>${{dateStr}}</td>
                            <td><button class="btn btn-info" onclick="viewOrder(${{o.id}})">👁️</button></td>
                        </tr>
                    `;
                }}).join('');
            }}
            
            async function viewOrder(id) {{
                currentOrderId = id;
                const response = await fetch('/api/orders');
                const data = await response.json();
                const order = (data.orders || []).find(o => o.id === id);
                if (order) {{
                    document.getElementById('orderStatus').value = order.status || 'оформлен';
                    document.getElementById('trackingNumber').value = order.tracking_number || '';
                    document.getElementById('orderDetails').innerHTML = `
                        <div class="detail-grid">
                            <div class="detail-item"><strong>Клиент</strong><span>${{order.full_name || order.username || '—'}}</span></div>
                            <div class="detail-item"><strong>Email</strong><span>${{order.user_email || '—'}}</span></div>
                            <div class="detail-item"><strong>Telegram</strong><span>${{order.telegram || '—'}}</span></div>
                            <div class="detail-item"><strong>Товар</strong><span>${{order.product_name || '—'}}</span></div>
                            <div class="detail-item"><strong>Количество</strong><span>${{order.quantity || 1}}</span></div>
                            <div class="detail-item"><strong>Цена</strong><span>${{(order.total_price || 0).toLocaleString()}} ₽</span></div>
                            <div class="detail-item"><strong>Город</strong><span>${{order.city || '—'}}</span></div>
                            <div class="detail-item"><strong>Почтовое отделение</strong><span>${{order.postal || '—'}}</span></div>
                            <div class="detail-item"><strong>Комментарий</strong><span>${{order.comment || '—'}}</span></div>
                            <div class="detail-item"><strong>Статус</strong><span>${{order.status || 'оформлен'}}</span></div>
                            <div class="detail-item"><strong>Трек-номер</strong><span>${{order.tracking_number || '—'}}</span></div>
                            <div class="detail-item"><strong>Дата</strong><span>${{new Date(order.created_at || order.order_date).toLocaleString('ru-RU')}}</span></div>
                        </div>
                    `;
                    document.getElementById('orderModal').style.display = 'flex';
                }}
            }}
            
            async function saveOrderStatus() {{
                if (currentOrderId) {{
                    const newStatus = document.getElementById('orderStatus').value;
                    const trackingNumber = document.getElementById('trackingNumber').value.trim();
                    await fetch(`/api/orders/${{currentOrderId}}/status`, {{
                        method: 'PUT',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ status: newStatus, tracking_number: trackingNumber }})
                    }});
                    closeModal();
                    loadOrders();
                }}
            }}
            
            function closeModal() {{ document.getElementById('orderModal').style.display = 'none'; }}
            function logout() {{ localStorage.removeItem('admin_token'); window.location.href = '/admin'; }}
            loadOrders();
        </script>
    </body>
    </html>
    '''

@app.route('/admin/users')
def admin_users():
    return f'''
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Пользователи | Админ-панель</title>
        {ADMIN_CSS}
    </head>
    <body>
        <div class="sidebar">
            <h2>🖥️ PC Shop</h2>
            <a href="/admin/dashboard">📊 Дашборд</a>
            <a href="/admin/products">📦 Товары</a>
            <a href="/admin/orders">🛒 Заказы</a>
            <a href="/admin/users" class="active">👥 Пользователи</a>
            <a href="#" onclick="logout()">🚪 Выйти</a>
        </div>
        <div class="content">
            <h1>👥 Пользователи</h1>
            <div class="card">
                <table id="usersTable">
                    <thead>
                        <tr><th>ID</th><th>Имя</th><th>Email</th><th>Город</th><th>Заказов</th><th>Дата регистрации</th></tr>
                    </thead>
                    <tbody></tbody>
                </table>
            </div>
        </div>
        <script>
            async function loadUsers() {{
                const response = await fetch('/api/users');
                const data = await response.json();
                const tbody = document.querySelector('#usersTable tbody');
                
                const ordersRes = await fetch('/api/orders');
                const ordersData = await ordersRes.json();
                const orders = ordersData.orders || [];
                
                tbody.innerHTML = (data.users || []).map(u => {{
                    const userOrders = orders.filter(o => o.user_email == u.email);
                    const date = new Date(u.created_at);
                    const dateStr = date.toLocaleString('ru-RU', {{ day: 'numeric', month: 'short', year: 'numeric' }});
                    return `
                        <tr>
                            <td>${{u.id}}</td>
                            <td><strong>${{u.full_name || '—'}}</strong></td>
                            <td>${{u.email || '—'}}</td>
                            <td>${{u.city || '—'}}</td>
                            <td><span class="badge badge-info">${{userOrders.length}}</span></td>
                            <td>${{dateStr}}</td>
                        </tr>
                    `;
                }}).join('');
            }}
            
            function logout() {{ localStorage.removeItem('admin_token'); window.location.href = '/admin'; }}
            loadUsers();
        </script>
    </body>
    </html>
    '''



# ========== ВОССТАНОВЛЕНИЕ ПАРОЛЯ ==========
reset_tokens = {}

@app.route('/api/forgot-password', methods=['POST'])
def forgot_password():
    """Отправляет код восстановления пароля на почту."""
    data = request.json
    email = data.get('email', '').strip().lower()

    if not email or '@' not in email:
        return jsonify({"status": "error", "message": "Некорректный email"}), 400

    # Проверяем, существует ли пользователь с такой почтой
    try:
        existing = supabase.table('users').select('id').eq('email', email).execute()
        if not existing.data:
            # Не говорим, что пользователь не найден (безопасность)
            return jsonify({"status": "ok", "message": "Если такой email зарегистрирован, код отправлен"}), 200
    except:
        return jsonify({"status": "error", "message": "Ошибка сервера"}), 500

    # Генерируем код и токен
    code = str(random.randint(100000, 999999))
    reset_token = hashlib.sha256(f"{SECRET_KEY}{email}{time.time()}".encode()).hexdigest()

    reset_tokens[email] = {
        "code": code,
        "token": reset_token,
        "timestamp": time.time(),
        "attempts": 0
    }

    subject = "Восстановление пароля | PCGGPRO"
    body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto;">
        <h2 style="color: #4a9eff;">🖥️ PCGGPRO</h2>
        <p>Ваш код для восстановления пароля:</p>
        <h1 style="letter-spacing: 5px; color: #333;">{code}</h1>
        <p>Введите этот код на странице восстановления пароля.</p>
        <p style="color: #999; font-size: 12px;">Код действителен в течение 10 минут.</p>
    </div>
    """

    if send_email(email, subject, body):
        return jsonify({"status": "ok", "reset_token": reset_token})
    else:
        return jsonify({"status": "error", "message": "Не удалось отправить код"}), 500


@app.route('/api/verify-reset-code', methods=['POST'])
def verify_reset_code():
    """Проверяет код восстановления пароля."""
    data = request.json
    email = data.get('email', '').strip().lower()
    code = data.get('code', '').strip()
    token = data.get('reset_token', '').strip()

    if email not in reset_tokens:
        return jsonify({"status": "error", "message": "Код не найден или истёк"}), 400

    stored = reset_tokens[email]

    if stored["token"] != token:
        return jsonify({"status": "error", "message": "Неверный токен"}), 400

    if time.time() - stored["timestamp"] > 600:
        del reset_tokens[email]
        return jsonify({"status": "error", "message": "Код истёк. Запросите новый"}), 400

    if stored["attempts"] >= 3:
        del reset_tokens[email]
        return jsonify({"status": "error", "message": "Превышено количество попыток"}), 400

    stored["attempts"] += 1

    if stored["code"] == code:
        return jsonify({"status": "ok", "message": "Код подтверждён"})
    else:
        return jsonify({"status": "error", "message": "Неверный код"}), 400


@app.route('/api/reset-password', methods=['POST'])
def reset_password():
    """Устанавливает новый пароль."""
    data = request.json
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    token = data.get('reset_token', '')

    if email not in reset_tokens:
        return jsonify({"status": "error", "message": "Токен не найден или истёк"}), 400

    stored = reset_tokens[email]

    if stored["token"] != token:
        return jsonify({"status": "error", "message": "Неверный токен"}), 400

    if len(password) < 6:
        return jsonify({"status": "error", "message": "Пароль должен быть не менее 6 символов"}), 400

    try:
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        supabase.table('users').update({'password_hash': password_hash}).eq('email', email).execute()
        del reset_tokens[email]
        return jsonify({"status": "ok", "message": "Пароль изменён"})
    except Exception as e:
        logger.error(f"Ошибка смены пароля: {e}")
        return jsonify({"status": "error", "message": "Ошибка смены пароля"}), 500
    







# ========== ПОДДЕРЖКА ==========
@app.route('/api/support', methods=['POST'])
def support_message():
    """Сохраняет обращение в поддержку."""
    data = request.json
    try:
        supabase.table('support_messages').insert({
            'name': data.get('name', ''),
            'email': data.get('email', ''),
            'message': data.get('message', ''),
            'status': 'новое',
            'created_at': datetime.now().isoformat()
        }).execute()
        
        # Отправляем уведомление тебе на почту
        notification_data = {
            "order_id": f"SUPPORT-{datetime.now().strftime('%H%M%S')}",
            "product_name": f"Запрос от {data.get('name', '—')} ({data.get('email', '—')})",
            "price": 0,
            "city": "Поддержка",
            "postal": data.get('message', ''),
            "comment": '',
            "timestamp": datetime.now().strftime("%d.%m.%Y %H:%M")
        }
        send_order_notification(notification_data)
        
        return jsonify({"status": "ok", "message": "Сообщение отправлено"}), 200
    except Exception as e:
        logger.error(f"Ошибка сохранения обращения: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/support', methods=['GET'])
def get_support_messages():
    """Получает все обращения в поддержку."""
    try:
        response = supabase.table('support_messages').select('*').order('created_at', desc=True).execute()
        return jsonify({"status": "ok", "messages": response.data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500







@app.route('/admin/support')
def admin_support():
    return f'''
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Поддержка | Админ-панель</title>
        {ADMIN_CSS}
    </head>
    <body>
        <div class="sidebar">
            <h2>🖥️ PC Shop</h2>
            <a href="/admin/dashboard">📊 Дашборд</a>
            <a href="/admin/products">📦 Товары</a>
            <a href="/admin/orders">🛒 Заказы</a>
            <a href="/admin/users">👥 Пользователи</a>
            <a href="/admin/support">💬 Поддержка</a>
            <a href="/admin/chats" class="active">💬 Чаты</a>
            <a href="#" onclick="logout()">🚪 Выйти</a>
        </div>
        <div class="content">
            <h1>💬 Запросы в поддержку</h1>
            <div class="card">
                <table id="supportTable">
                    <thead>
                        <tr><th>ID</th><th>Имя</th><th>Email</th><th>Сообщение</th><th>Статус</th><th>Дата</th></tr>
                    </thead>
                    <tbody></tbody>
                </table>
            </div>
        </div>
        <script>
            async function loadMessages() {{
                const response = await fetch('/api/support');
                const data = await response.json();
                const tbody = document.querySelector('#supportTable tbody');
                const statusBadges = {{
                    'новое': 'badge-info',
                    'отвечено': 'badge-success'
                }};
                
                tbody.innerHTML = (data.messages || []).map(m => {{
                    const date = new Date(m.created_at);
                    const dateStr = date.toLocaleString('ru-RU');
                    return `
                        <tr>
                            <td>${{m.id}}</td>
                            <td><strong>${{m.name || '—'}}</strong></td>
                            <td>${{m.email || '—'}}</td>
                            <td>${{m.message || '—'}}</td>
                            <td><span class="badge ${{statusBadges[m.status] || 'badge-info'}}">${{m.status || 'новое'}}</span></td>
                            <td>${{dateStr}}</td>
                        </tr>
                    `;
                }}).join('');
            }}
            
            function logout() {{ localStorage.removeItem('admin_token'); window.location.href = '/admin'; }}
            loadMessages();
        </script>
    </body>
    </html>
    '''





# ========== ЧАТ ПОДДЕРЖКИ ==========
import uuid

@app.route('/api/chat/start', methods=['POST'])
def start_chat():
    """Начинает новую сессию чата."""
    data = request.json
    session_id = str(uuid.uuid4())
    
    try:
        supabase.table('chat_sessions').insert({
            'id': session_id,
            'name': data.get('name', ''),
            'email': data.get('email', ''),
            'status': 'active',
            'created_at': datetime.now().isoformat()
        }).execute()
        
        # Первое сообщение
        supabase.table('chat_messages').insert({
            'session_id': session_id,
            'sender': 'system',
            'message': f'Чат начат пользователем {data.get("name", "")} ({data.get("email", "")})',
            'created_at': datetime.now().isoformat()
        }).execute()
        
        return jsonify({"status": "ok", "session_id": session_id}), 200
    except Exception as e:
        logger.error(f"Ошибка создания чата: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/chat/message', methods=['POST'])
def chat_message():
    """Отправляет сообщение в чат."""
    data = request.json
    
    try:
        supabase.table('chat_messages').insert({
            'session_id': data.get('session_id', ''),
            'sender': data.get('sender', 'user'),
            'message': data.get('message', ''),
            'created_at': datetime.now().isoformat()
        }).execute()
        
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/chat/messages', methods=['GET'])
def get_chat_messages():
    """Получает сообщения чата по session_id."""
    session_id = request.args.get('session_id', '')
    
    try:
        response = supabase.table('chat_messages').select('*').eq('session_id', session_id).order('created_at', asc=True).execute()
        return jsonify({"status": "ok", "messages": response.data}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/chat/sessions', methods=['GET'])
def get_chat_sessions():
    """Получает все активные сессии чата."""
    try:
        response = supabase.table('chat_sessions').select('*').eq('status', 'active').order('created_at', desc=True).execute()
        return jsonify({"status": "ok", "sessions": response.data}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/admin/chats')
def admin_chats():
    return f'''
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Чаты | Админ-панель</title>
        {ADMIN_CSS}
    </head>
    <body>
        <div class="sidebar">
            <h2>🖥️ PC Shop</h2>
            <a href="/admin/dashboard">📊 Дашборд</a>
            <a href="/admin/products">📦 Товары</a>
            <a href="/admin/orders">🛒 Заказы</a>
            <a href="/admin/users">👥 Пользователи</a>
            <a href="/admin/support">💬 Поддержка</a>
            <a href="/admin/chats" class="active">💬 Чаты</a>
            <a href="#" onclick="logout()">🚪 Выйти</a>
        </div>
        <div class="content">
            <h1>💬 Активные чаты</h1>
            <div class="card">
                <table id="sessionsTable">
                    <thead>
                        <tr><th>ID</th><th>Имя</th><th>Email</th><th>Дата</th><th>Действия</th></tr>
                    </thead>
                    <tbody></tbody>
                </table>
            </div>
        </div>
        
        <div class="modal" id="chatModal">
            <div class="modal-content" style="width: 500px;">
                <h2>Чат с клиентом</h2>
                <div id="chatMessagesBox" style="height: 300px; overflow-y: auto; padding: 10px; background: #f5f5f5; border-radius: 8px; margin-bottom: 15px;"></div>
                <div style="display: flex; gap: 10px;">
                    <input type="text" id="adminChatInput" placeholder="Ваш ответ..." style="flex: 1; padding: 10px; border: 1px solid #ddd; border-radius: 8px;">
                    <button class="btn btn-primary" onclick="sendAdminMessage()">Отправить</button>
                </div>
                <button class="btn btn-danger" onclick="closeModal()" style="margin-top: 10px;">Закрыть</button>
            </div>
        </div>
        <script>
            let currentSessionId = null;
            let adminPollingInterval = null;
            
            async function loadSessions() {{
                const response = await fetch('/api/chat/sessions');
                const data = await response.json();
                const tbody = document.querySelector('#sessionsTable tbody');
                
                tbody.innerHTML = (data.sessions || []).map(s => {{
                    const date = new Date(s.created_at);
                    return `
                        <tr>
                            <td>${{s.id.slice(0, 8)}}...</td>
                            <td><strong>${{s.name || '—'}}</strong></td>
                            <td>${{s.email || '—'}}</td>
                            <td>${{date.toLocaleString('ru-RU')}}</td>
                            <td><button class="btn btn-info" onclick="openChat('${{s.id}}', '${{s.name}}')">💬</button></td>
                        </tr>
                    `;
                }}).join('');
            }}
            
            function openChat(sessionId, name) {{
                currentSessionId = sessionId;
                document.getElementById('chatModal').style.display = 'flex';
                document.getElementById('chatMessagesBox').innerHTML = '<div style="text-align: center; color: #999;">Загрузка...</div>';
                loadChatMessages();
                startAdminPolling();
            }}
            
            async function loadChatMessages() {{
                if (!currentSessionId) return;
                const response = await fetch(`/api/chat/messages?session_id=${{currentSessionId}}`);
                const data = await response.json();
                
                const box = document.getElementById('chatMessagesBox');
                box.innerHTML = (data.messages || []).map(m => {{
                    const align = m.sender === 'user' ? 'right' : 'left';
                    const bg = m.sender === 'user' ? '#4a9eff' : '#00d4aa';
                    const color = m.sender === 'user' ? 'white' : '#000';
                    return `<div style="text-align: ${{align}}; margin: 5px 0;">
                        <span style="background: ${{bg}}; color: ${{color}}; padding: 8px 12px; border-radius: 12px; display: inline-block; max-width: 80%;">${{m.message}}</span>
                    </div>`;
                }}).join('');
                box.scrollTop = box.scrollHeight;
            }}
            
            async function sendAdminMessage() {{
                const input = document.getElementById('adminChatInput');
                const message = input.value.trim();
                if (!message || !currentSessionId) return;
                
                await fetch('/api/chat/message', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ session_id: currentSessionId, message, sender: 'admin' }})
                }});
                
                input.value = '';
                loadChatMessages();
            }}
            
            function startAdminPolling() {{
                stopAdminPolling();
                adminPollingInterval = setInterval(loadChatMessages, 3000);
            }}
            
            function stopAdminPolling() {{
                if (adminPollingInterval) {{
                    clearInterval(adminPollingInterval);
                    adminPollingInterval = null;
                }}
            }}
            
            function closeModal() {{
                document.getElementById('chatModal').style.display = 'none';
                stopAdminPolling();
                currentSessionId = null;
            }}
            
            function logout() {{ localStorage.removeItem('admin_token'); window.location.href = '/admin'; }}
            loadSessions();
        </script>
    </body>
    </html>
    '''

# ========== ЗАПУСК ==========
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"🚀 Сервер запущен на порту {port}")
    app.run(host='0.0.0.0', port=port)
