
import os, base64, requests
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from flask_socketio import SocketIO, join_room, leave_room, emit
from sqlalchemy import func

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-123')

# Database
db_url = os.getenv("DATABASE_URL")
if db_url:
    if "sslmode=" not in db_url:
        db_url += ("&" if "?" in db_url else "?") + "sslmode=require"
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///flow_market.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# Models
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    def set_password(self, pw): self.password_hash = generate_password_hash(pw)
    def check_password(self, pw): return check_password_hash(self.password_hash, pw)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Float, nullable=False, default=0)
    description = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.Text)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    owner = db.relationship("User")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room = db.Column(db.String(120), index=True, nullable=False)
    sender = db.Column(db.String(120), nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

# Auth
login_manager = LoginManager(app)
login_manager.login_view = "login"
@login_manager.user_loader
def load_user(uid): return User.query.get(int(uid))

# Socket.IO
REDIS_URL = os.getenv("REDIS_URL")
if REDIS_URL:
    from socketio import RedisManager
    mgr = RedisManager(REDIS_URL)
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet", client_manager=mgr)
else:
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

def room_for_product(pid:int) -> str: return f"product_{pid}"

# External Upload
EXTERNAL_UPLOAD_URL = os.getenv("EXTERNAL_UPLOAD_URL")
IMGBB_KEY = os.getenv("IMGBB_API_KEY")

def upload_image_external(file_storage):
    if EXTERNAL_UPLOAD_URL:
        files = {'file': (file_storage.filename, file_storage.stream, file_storage.mimetype)}
        r = requests.post(EXTERNAL_UPLOAD_URL, files=files, timeout=25)
        r.raise_for_status()
        data = r.json()
        if not data or (not data.get("ok")): raise RuntimeError(f"external upload failed: {data}")
        return data["url"]
    elif IMGBB_KEY:
        b64 = base64.b64encode(file_storage.read())
        payload = {"key": IMGBB_KEY, "name": file_storage.filename.rsplit('.',1)[0], "image": b64}
        r = requests.post("https://api.imgbb.com/1/upload", data=payload, timeout=25)
        r.raise_for_status()
        data = r.json()
        if not data.get("success"): raise RuntimeError(f"img upload failed: {data}")
        return data["data"]["url"]
    else:
        raise RuntimeError("No external uploader configured (set EXTERNAL_UPLOAD_URL or IMGBB_API_KEY)")

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files: return jsonify({"ok": False, "error": "no file"}), 400
    f = request.files['file']
    if not f or f.filename == "": return jsonify({"ok": False, "error": "empty filename"}), 400
    try:
        url = upload_image_external(f)
        return jsonify({"ok": True, "url": url}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 502

# Views
@app.route('/')
def index():
    products = Product.query.order_by(Product.id.desc()).limit(60).all()
    return render_template('index.html', products=products)

@app.route('/health')
def health():
    count_products = db.session.query(func.count(Product.id)).scalar()
    count_msgs = db.session.query(func.count(Message.id)).scalar()
    return jsonify({"ok": True, "service": "flow-market", "products": int(count_products or 0), "messages": int(count_msgs or 0), "ts": datetime.utcnow().isoformat()})

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip().lower()
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        if not (username and email and password):
            flash('أكمل البيانات', 'error'); return redirect(url_for('register'))
        if User.query.filter((User.username==username)|(User.email==email)).first():
            flash('الاسم أو البريد مستخدم من قبل', 'error'); return redirect(url_for('register'))
        u = User(username=username, email=email); u.set_password(password)
        db.session.add(u); db.session.commit()
        login_user(u, remember=True)
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip().lower()
        password = request.form.get('password') or ''
        u = User.query.filter_by(username=username).first()
        if not u or not u.check_password(password):
            flash('بيانات غير صحيحة', 'error'); return redirect(url_for('login'))
        login_user(u, remember=True)
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user(); return redirect(url_for('index'))

@app.route('/add_product', methods=['GET','POST'])
@login_required
def add_product():
    if request.method == 'POST':
        title = (request.form.get('title') or '').strip()
        price = request.form.get('price') or '0'
        description = (request.form.get('description') or '').strip()
        image_url = (request.form.get('image_url') or '').strip()
        if not (title and description and image_url):
            flash('أكمل البيانات وأرفِق صورة', 'error'); return redirect(url_for('add_product'))
        p = Product(title=title, price=float(price or 0), description=description, image_url=image_url, owner=current_user)
        db.session.add(p); db.session.commit()
        flash('تم إضافة المنتج', 'success')
        return redirect(url_for('index'))
    return render_template('add_product.html')

# APIs
@app.route('/api/messages/<room>')
def api_messages(room):
    rows = Message.query.filter_by(room=room).order_by(Message.id.desc()).limit(50).all()
    rows = list(reversed(rows))
    return jsonify([{"sender":r.sender,"text":r.text,"ts":r.created_at.isoformat()} for r in rows])

# Socket events
@socketio.on('connect')
def sio_connect():
    emit('connected', {'ok': True})

@socketio.on('join')
def sio_join(data):
    room = data.get('room')
    if not room: return
    join_room(room)
    emit('system', {'text': f'انضممت إلى الغرفة {room}'}, room=request.sid)

@socketio.on('message')
def sio_message(data):
    room = data.get('room'); text = (data.get('text') or '').strip()
    sender = (data.get('sender') or 'مجهول').strip()[:120]
    if not (room and text): return
    msg = Message(room=room, sender=sender, text=text)
    db.session.add(msg); db.session.commit()
    emit('message', {'room': room, 'sender': sender, 'text': text, 'ts': msg.created_at.isoformat()}, room=room)

@socketio.on('leave')
def sio_leave(data):
    room = data.get('room'); 
    if not room: return
    leave_room(room)
    emit('system', {'text': f'غادرت الغرفة {room}'}, room=request.sid)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
