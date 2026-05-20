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
from models import db, Stock, StockPrice, StockAdmin, Trader, Holding
import time
import click

app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static",
)

app.config.from_object(Config)

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

HISTORY_LIMIT = 48
STARTING_BALANCE = 10_000


def init_db():
    with app.app_context():
        db.create_all()


@login_manager.user_loader
def load_user(user_id):
    return StockAdmin.query.get(int(user_id))


@login_manager.unauthorized_handler
def unauthorized():
    if request.path.startswith("/api/"):
        return jsonify({"error": "Login required"}), 401
    return redirect(url_for("login"))


def get_trader():
    trader_id = session.get("trader_id")
    if not trader_id:
        return None
    return Trader.query.get(trader_id)


def record_price(stock, value):
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
        bucket.append({"value": row.value, "t": row.recorded_at.isoformat()})

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

    if not username:
        return jsonify({"error": "Username required"}), 400

    trader = Trader.query.filter_by(username=username).first()
    if not trader:
        trader = Trader(username=username, balance=STARTING_BALANCE)
        db.session.add(trader)
        db.session.commit()

    session["trader_id"] = trader.id
    return jsonify(trader.to_dict())


@app.route("/api/portfolio/me")
def portfolio_me():
    trader = get_trader()
    if not trader:
        return jsonify({"error": "Not signed in"}), 401

    holdings = (
        db.session.query(Holding, Stock)
        .join(Stock, Holding.stock_id == Stock.id)
        .filter(Holding.trader_id == trader.id, Holding.quantity > 0)
        .all()
    )

    return jsonify({
        "trader": trader.to_dict(),
        "holdings": [
            {
                "stock_id": stock.id,
                "stock_name": stock.stock_name,
                "quantity": holding.quantity,
                "value": stock.value,
                "worth": holding.quantity * stock.value,
            }
            for holding, stock in holdings
        ],
    })


@app.route("/api/portfolio/buy", methods=["POST"])
def portfolio_buy():
    trader = get_trader()
    if not trader:
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

    stock = Stock.query.get(stock_id)
    if not stock:
        return jsonify({"error": "Stock not found"}), 404

    cost = stock.value * quantity
    if trader.balance < cost:
        return jsonify({"error": "Insufficient balance"}), 400

    holding = Holding.query.filter_by(
        trader_id=trader.id,
        stock_id=stock.id,
    ).first()

    if not holding:
        holding = Holding(trader_id=trader.id, stock_id=stock.id, quantity=0)
        db.session.add(holding)

    trader.balance -= cost
    holding.quantity += quantity
    db.session.commit()

    return jsonify({
        "success": True,
        "balance": trader.balance,
        "quantity": holding.quantity,
    })


# -----------------------
# ADMIN AUTH
# -----------------------

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}

    username = data.get("username")
    password = data.get("password")

    admin = StockAdmin.query.filter_by(username=username).first()

    if not admin:
        time.sleep(1)
        return jsonify({"error": "Invalid username"}), 401

    if not admin.check_password(password):
        time.sleep(1)
        return jsonify({"error": "Invalid password"}), 401

    login_user(admin)
    return jsonify({"success": True})


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
        value = int(value)
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
            value = int(data["value"])
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


try:
    init_db()
except Exception:
    pass
