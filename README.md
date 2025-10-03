# Flow Market Pro (Arabic RTL)
سوق إلكتروني مع شات فوري ورفع صور خارجي + جاهز للنشر على Render 24/7 (خطة Basic).
- Flask + Flask-SocketIO (eventlet)
- SQLAlchemy (Postgres عبر DATABASE_URL أو SQLite)
- رفع الصور: EXTERNAL_UPLOAD_URL أو IMGBB_API_KEY
- RTL واجهة عربية + ودجت شات

## تشغيل محلي
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py

## Render
startCommand: gunicorn app:app -k eventlet -w 1 -b 0.0.0.0:$PORT
