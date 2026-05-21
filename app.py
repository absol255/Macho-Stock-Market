from flask import (
    Flask,
    request,
    jsonify,
    render_template,
    redirect,
    url_for,
    session,
)
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from config import Config
from models import db, Stock, StockPrice, StockAdmin, User, Holding
from decimal import Decimal
import os
import time
import click
import random
import threading
import json

app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static",
)

app.config.from_object(Config)

if os.getenv("VERCEL"):
    from werkzeug.middleware.proxy_fix import ProxyFix

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

HISTORY_LIMIT = 48


def init_db():
    with app.app_context():
        db.create_all()


def ensure_tables():
    """Create tables if missing. Returns an error string or None."""
    try:
        db.create_all()
        return None
    except Exception as exc:
        app.logger.exception("ensure_tables failed")
        return str(exc)

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

app.json_encoder = DecimalEncoder

def maybe_bootstrap_admin():
    """Optional: set BOOTSTRAP_ADMIN_USER + BOOTSTRAP_ADMIN_PASSWORD in Vercel once."""
    user = os.getenv("BOOTSTRAP_ADMIN_USER")
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD")
    if not user or not password:
        return
    try:
        if StockAdmin.query.count() > 0:
            return
        admin = StockAdmin(username=user.strip()[:64])
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        app.logger.info("Bootstrapped admin user: %s", user)
    except Exception:
        app.logger.exception("bootstrap admin failed")
        db.session.rollback()


@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(StockAdmin, int(user_id))
    except (TypeError, ValueError):
        return None


@login_manager.unauthorized_handler
def unauthorized():
    if request.path.startswith("/api/"):
        return jsonify({"error": "Login required"}), 401
    return redirect(url_for("login"))


def get_portfolio_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.session.get(User, user_id)


def record_price(stock, value):
    value = Decimal(str(value)).quantize(Decimal("0.01"))

    stock.value = value
    db.session.add(
        StockPrice(stock_id=stock.id, value=value)
    )


# -----------------------
# PAGES
# -----------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/portfolio")
def portfolio():
    return render_template("portfolio.html")


@app.route("/admin")
@login_required
def admin():
    return render_template("admin.html")


@app.route("/login")
def login():
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/")


# -----------------------
# PUBLIC STOCK APIs
# -----------------------

@app.route("/api/stocks")
def api_stocks():
    stocks = Stock.query.order_by(Stock.stock_name).all()
    return jsonify([s.to_dict() for s in stocks])


@app.route("/api/stocks/history")
def api_stocks_history():
    """One DB round-trip: recent price points for every stock."""
    stock_ids = [
        row[0]
        for row in db.session.query(Stock.id).all()
    ]
    if not stock_ids:
        return jsonify({})

    rows = (
        StockPrice.query.filter(StockPrice.stock_id.in_(stock_ids))
        .order_by(StockPrice.stock_id, StockPrice.recorded_at.desc())
        .all()
    )

    by_stock = {}
    for row in rows:
        bucket = by_stock.setdefault(row.stock_id, [])
        if len(bucket) >= HISTORY_LIMIT:
            continue
        bucket.append({"value": float(row.value), "t": row.recorded_at.isoformat()})

    for stock_id in by_stock:
        by_stock[stock_id].reverse()

    return jsonify({str(k): v for k, v in by_stock.items()})


# -----------------------
# PORTFOLIO APIs
# -----------------------

@app.route("/api/portfolio/session", methods=["POST"])
def portfolio_session():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()[:64]
    bank_raw = data.get("bank_account_number")

    if not username:
        return jsonify({"error": "Username required"}), 400

    try:
        bank_account_number = int(bank_raw)
    except (TypeError, ValueError):
        return jsonify({"error": "Valid bank account number required"}), 400

    user = User.query.filter_by(
        username=username,
        bank_account_number=bank_account_number,
    ).first()

    if not user:
        return jsonify({"error": "Invalid username or bank account number"}), 401

    session.permanent = True
    session["user_id"] = user.id
    return jsonify(user.to_dict())


@app.route("/api/portfolio/logout", methods=["POST"])
def portfolio_logout():
    session.pop("user_id", None)
    return jsonify({"success": True})


@app.route("/api/portfolio/me")
def portfolio_me():
    user = get_portfolio_user()
    if not user:
        return jsonify({"error": "Not signed in"}), 401

    holdings = (
        db.session.query(Holding, Stock)
        .join(Stock, Holding.stock_id == Stock.id)
        .filter(Holding.trader_id == user.id, Holding.quantity > 0)
        .all()
    )

    return jsonify({
        "user": user.to_dict(),
        "holdings": [
            {
                "stock_id": stock.id,
                "stock_name": stock.stock_name,
                "quantity": holding.quantity,
                "value": stock.value,
                "worth": float(Decimal(stock.value) * Decimal(holding.quantity)),
            }
            for holding, stock in holdings
        ],
    })


@app.route("/api/portfolio/buy", methods=["POST"])
def portfolio_buy():
    user = get_portfolio_user()
    if not user:
        return jsonify({"error": "Not signed in"}), 401

    data = request.get_json(silent=True) or {}
    stock_id = data.get("stock_id")
    quantity = data.get("quantity")

    try:
        stock_id = int(stock_id)
        quantity = int(quantity)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid stock or quantity"}), 400

    if quantity <= 0:
        return jsonify({"error": "Quantity must be positive"}), 400

    stock = db.session.get(Stock, stock_id)
    if not stock:
        return jsonify({"error": "Stock not found"}), 404

    cost = Decimal(str(stock.value)) * Decimal(quantity)
    if Decimal(user.macho_bucks) < cost:
        return jsonify({"error": "Insufficient macho bucks"}), 400

    holding = Holding.query.filter_by(
        trader_id=user.id,
        stock_id=stock.id,
    ).first()

    if not holding:
        holding = Holding(trader_id=user.id, stock_id=stock.id, quantity=0)
        db.session.add(holding)

    user.macho_bucks = Decimal(str(user.macho_bucks)) - cost
    holding.quantity += quantity
    db.session.commit()

    return jsonify({
        "success": True,
        "macho_bucks": user.macho_bucks,
        "quantity": holding.quantity,
    })

@app.route("/api/portfolio/sell", methods=["POST"])
def portfolio_sell():
    user = get_portfolio_user()

    if not user:
        return jsonify({"error": "Not signed in"}), 401

    data = request.get_json(silent=True) or {}

    stock_id = data.get("stock_id")
    quantity = data.get("quantity")

    try:
        stock_id = int(stock_id)
        quantity = int(quantity)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid stock or quantity"}), 400

    if quantity <= 0:
        return jsonify({"error": "Quantity must be positive"}), 400

    stock = db.session.get(Stock, stock_id)

    if not stock:
        return jsonify({"error": "Stock not found"}), 404

    holding = Holding.query.filter_by(
        trader_id=user.id,
        stock_id=stock.id,
    ).first()

    if not holding:
        return jsonify({"error": "You do not own this stock"}), 400

    if holding.quantity < quantity:
        return jsonify({"error": "Not enough shares"}), 400

    payout = Decimal(str(stock.value)) * Decimal(quantity)

    holding.quantity -= quantity
    user.macho_bucks = Decimal(str(user.macho_bucks)) + payout

    if holding.quantity == 0:
        db.session.delete(holding)

    db.session.commit()

    return jsonify({
        "success": True,
        "macho_bucks": user.macho_bucks,
        "quantity": holding.quantity if holding.quantity > 0 else 0,
    })

# -----------------------
# ADMIN AUTH
# -----------------------

def _config_error():
    if not app.config.get("SECRET_KEY"):
        return "SECRET_KEY is not set on the server"
    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        return "DATABASE_URL is not set on the server"
    return None


@app.route("/api/health")
def api_health():
    err = _config_error()
    if err:
        return jsonify({"ok": False, "error": err}), 503
    try:
        db.session.execute(db.text("SELECT 1"))
        table_err = ensure_tables()
        maybe_bootstrap_admin()
        admin_count = StockAdmin.query.count()
        payload = {
            "ok": table_err is None,
            "db": True,
            "tables_ok": table_err is None,
            "admin_count": admin_count,
        }
        if table_err:
            payload["error"] = table_err
        elif admin_count == 0:
            payload["hint"] = (
                "No admin users. Run: flask --app app create-admin USER PASS "
                "with production DATABASE_URL, or set BOOTSTRAP_ADMIN_USER and "
                "BOOTSTRAP_ADMIN_PASSWORD in Vercel temporarily."
            )
        status = 503 if table_err else 200
        return jsonify(payload), status
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 503


@app.route("/api/login", methods=["POST"])
def api_login():
    err = _config_error()
    if err:
        return jsonify({"error": err}), 503

    table_err = ensure_tables()
    if table_err:
        return jsonify({"error": "Tables not ready: " + table_err}), 503

    maybe_bootstrap_admin()

    data = request.get_json(silent=True) or {}

    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    try:
        admin = StockAdmin.query.filter_by(username=username).first()
    except Exception as exc:
        app.logger.exception("login database error")
        return jsonify({"error": "Database error: " + str(exc)}), 503

    if not admin:
        if not os.getenv("VERCEL"):
            time.sleep(1)
        return jsonify({
            "error": "Invalid username (no admin in this database — check /api/health admin_count)",
        }), 401

    if not admin.check_password(password):
        if not os.getenv("VERCEL"):
            time.sleep(1)
        return jsonify({"error": "Invalid password"}), 401

    session.permanent = True
    login_user(admin)
    return jsonify({"success": True, "username": admin.username})


# -----------------------
# ADMIN STOCK APIs
# -----------------------

@app.route("/api/admin/stocks")
@login_required
def admin_stocks():
    stocks = Stock.query.order_by(Stock.stock_name).all()
    return jsonify([s.to_dict() for s in stocks])


@app.route("/api/admin/stocks", methods=["POST"])
@login_required
def admin_create_stock():
    data = request.get_json(silent=True) or {}
    name = (data.get("stock_name") or "").strip()[:64]
    value = data.get("value", 0)

    try:
        value = Decimal(str(value))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid value"}), 400

    if not name:
        return jsonify({"error": "Name required"}), 400

    if Stock.query.filter_by(stock_name=name).first():
        return jsonify({"error": "Stock already exists"}), 409

    stock = Stock(stock_name=name, value=value)
    db.session.add(stock)
    db.session.flush()
    record_price(stock, value)
    db.session.commit()

    return jsonify(stock.to_dict()), 201

@app.route("/api/admin/addstock", methods=["POST"])
@login_required
def admin_addstock():
    data = request.get_json(silent=True) or {}

    username = data.get("username")
    stock_id = data.get("stock_id")
    quantity = data.get("quantity")

    try:
        username = str(username)
        stock_id = int(stock_id)
        quantity = int(quantity)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid stock or quantity or username"}), 400

    if quantity <= 0:
        return jsonify({"error": "Quantity must be positive"}), 400

    stock = db.session.get(Stock, stock_id)
    if not stock:
        return jsonify({"error": "Stock not found"}), 404

    user = User.query.filter_by(
        username=username
    ).first()
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    holding = Holding.query.filter_by(
        trader_id=user.id,
        stock_id=stock.id,
    ).first()

    if not holding:
        holding = Holding(trader_id=user.id, stock_id=stock.id, quantity=0)
        db.session.add(holding)

    holding.quantity += quantity
    db.session.commit()

    return jsonify({
        "success": True,
        "user": user.to_dict(),
        "quantity": holding.quantity,
    })


@app.route("/api/admin/stocks/<int:stock_id>", methods=["PATCH"])
@login_required
def admin_update_stock(stock_id):
    stock = Stock.query.get(stock_id)
    if not stock:
        return jsonify({"error": "Not found"}), 404

    data = request.get_json(silent=True) or {}

    if "stock_name" in data:
        name = (data.get("stock_name") or "").strip()[:64]
        if name:
            stock.stock_name = name

    if "value" in data:
        try:
            value = Decimal(str(data["value"]))
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid value"}), 400
        record_price(stock, value)

    
    db.session.commit()
    return jsonify(stock.to_dict())


@app.route("/api/admin/stocks/<int:stock_id>", methods=["DELETE"])
@login_required
def admin_delete_stock(stock_id):
    stock = Stock.query.get(stock_id)
    if not stock:
        return jsonify({"error": "Not found"}), 404

    db.session.delete(stock)
    db.session.commit()
    return jsonify({"success": True})


@app.cli.command("create-admin")
@click.argument("username")
@click.argument("password")
def create_admin(username, password):
    """Create a stock admin (run once): flask create-admin user pass"""
    init_db()
    if StockAdmin.query.filter_by(username=username).first():
        click.echo("Admin already exists.")
        return
    admin = StockAdmin(username=username)
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    click.echo("Admin created: " + username)

def update_stocks_randomly():
    with app.app_context():
        while True:
            stocks = Stock.query.all()

            for stock in stocks:
                rando = random.randint(3, 40)

                change = Decimal("0.0")

                if rando == 40:
                    change = Decimal("0.4")
                elif rando == 39:
                    change = Decimal("-0.4")

                elif rando in (36, 35):
                    change = Decimal("0.3")
                elif rando in (34, 33):
                    change = Decimal("-0.3")

                elif rando in (32, 31, 30, 29):
                    change = Decimal("0.2")
                elif rando in (28, 27, 26, 25):
                    change = Decimal("-0.2")

                elif rando in range(15, 25):
                    change = Decimal("0.1")
                else:
                    change = Decimal("-0.1")

                record_price(stock, Decimal(str(stock.value)) + change)

            db.session.commit()
            time.sleep(43200)

            
try:
    threading.Thread(target=update_stocks_randomly, daemon=True).start()
    init_db()
except Exception:
    pass
