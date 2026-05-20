from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from sqlalchemy import BigInteger

db = SQLAlchemy()

# -----------------------
# USER MODEL
# -----------------------

class Stock(db.Model):
    __tablename__ = "stocks"

    id = db.Column(db.BigInteger, primary_key=True)

    stock_name = db.Column(
        db.String(64),
        unique=True,
        nullable=False
    )

    value = db.Column(
        db.BigInteger,
        default=0,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    def to_dict(self):
        return {
            "id": self.id,
            "stock_name": self.stock_name,
            "value": self.value
        }

# -----------------------
# ADMIN MODEL
# -----------------------

class StockAdmin(UserMixin, db.Model):
    __tablename__ = "stock_admins"

    id = db.Column(db.BigInteger, primary_key=True)

    username = db.Column(
        db.String(64),
        unique=True,
        nullable=False
    )

    password_hash = db.Column(
        db.String(256),
        nullable=False
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(
            self.password_hash,
            password
        )