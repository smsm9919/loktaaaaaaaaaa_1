import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy

# تهيئة التطبيق
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-123")

# إعداد قاعدة البيانات (Postgres أو SQLite كخيار محلي)
db_url = os.getenv("DATABASE_URL")
if db_url:
    if "sslmode=" not in db_url:
        db_url += ("&" if "?" in db_url else "?") + "sslmode=require"
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///flow_market.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# ------------------------------
# الجداول
# ------------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)  # ملاحظة: بدون تشفير هنا
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Float, nullable=False, default=0)
    description = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ------------------------------
# الراوتات
# ------------------------------
@app.route("/")
def index():
    products = Product.query.order_by(Product.created_at.desc()).all()
    return render_template("index.html", products=products)

@app.route("/health")
def health():
    users_count = User.query.count()
    products_count = Product.query.count()
    return jsonify({
        "status": "ok",
        "service": "flow-market",
        "timestamp": datetime.now().isoformat(),
        "users": users_count,
        "products": products_count,
        "version": "1.0.0"
    })

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username").strip().lower()
        email = request.form.get("email").strip().lower()
        password = request.form.get("password")

        if User.query.filter_by(username=username).first():
            flash("اسم المستخدم موجود مسبقاً!", "error")
            return redirect(url_for("register"))

        user = User(username=username, email=email, password=password)
        db.session.add(user)
        db.session.commit()

        flash("تم إنشاء حسابك بنجاح! يمكنك تسجيل الدخول الآن.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username").strip().lower()
        password = request.form.get("password")

        user = User.query.filter_by(username=username, password=password).first()
        if user:
            flash(f"مرحباً بعودتك، {username}!", "success")
            return redirect(url_for("index"))
        else:
            flash("اسم المستخدم أو كلمة المرور غير صحيحة!", "error")

    return render_template("login.html")

@app.route("/add_product", methods=["GET", "POST"])
def add_product():
    if request.method == "POST":
        title = request.form.get("title")
        price = request.form.get("price")
        description = request.form.get("description")
        # مؤقت: صورة ثابتة (ممكن تطوير رفع خارجي لاحقاً)
        image_url = "https://images.unsplash.com/photo-1560472354-b33ff0c44a43?w=400"

        product = Product(
            title=title,
            price=float(price),
            description=description,
            image_url=image_url
        )
        db.session.add(product)
        db.session.commit()

        flash("تم إضافة المنتج بنجاح!", "success")
        return redirect(url_for("index"))

    return render_template("add_product.html")

@app.route("/products")
def products_list():
    products = Product.query.all()
    return jsonify([{
        "id": p.id,
        "title": p.title,
        "price": p.price,
        "description": p.description,
        "image_url": p.image_url,
        "created_at": p.created_at.isoformat()
    } for p in products])

# ------------------------------
# نقطة الدخول
# ------------------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()  # إنشاء الجداول لو مش موجودة
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
