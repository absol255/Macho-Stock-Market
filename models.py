from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from sqlalchemy import Numeric

db = SQLAlchemy()


class Stock(db.Model):
    __tablename__ = "stocks"

    id = db.Column(db.BigInteger, primary_key=True)

    stock_name = db.Column(
        db.String(64),
        unique=True,
        nullable=False,
        index=True,
    )

    value = db.Column(db.Numeric(10, 2), nullable=False)

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
    )

    prices = db.relationship(
        "StockPrice",
        back_populates="stock",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "stock_name": self.stock_name,
            "value": float(self.value),
        }


class StockPrice(db.Model):
    __tablename__ = "stock_prices"

    id = db.Column(db.BigInteger, primary_key=True)

    stock_id = db.Column(
        db.BigInteger,
        db.ForeignKey("stocks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    value = db.Column(db.Numeric(10, 2), nullable=False)

    recorded_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )

    stock = db.relationship("Stock", back_populates="prices")

    __table_args__ = (
        db.Index("ix_stock_prices_stock_recorded", "stock_id", "recorded_at"),
    )


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.BigInteger, primary_key=True)

    username = db.Column(
        db.String(64),
        unique=True,
        nullable=False,
        index=True,
    )

    macho_bucks = db.Column(
        db.Numeric,
        default=0,
        nullable=False,
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
    )

    bank_account_number = db.Column(
        db.BigInteger,
        default=999,
    )

    holdings = db.relationship(
        "Holding",
        back_populates="user",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "macho_bucks": self.macho_bucks,
            "bank_account_number": self.bank_account_number,
        }


class Holding(db.Model):
    __tablename__ = "holdings"

    id = db.Column(db.BigInteger, primary_key=True)

    trader_id = db.Column(
        db.BigInteger,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    stock_id = db.Column(
        db.BigInteger,
        db.ForeignKey("stocks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    quantity = db.Column(db.BigInteger, default=0, nullable=False)

    user = db.relationship("User", back_populates="holdings")
    stock = db.relationship("Stock")

    __table_args__ = (
        db.UniqueConstraint("trader_id", "stock_id", name="uq_trader_stock"),
    )


class StockAdmin(UserMixin, db.Model):
    __tablename__ = "stock_admins"

    id = db.Column(db.BigInteger, primary_key=True)

    username = db.Column(
        db.String(64),
        unique=True,
        nullable=False,
    )

    password_hash = db.Column(
        db.String(256),
        nullable=False,
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(
            self.password_hash,
            password,
        )
