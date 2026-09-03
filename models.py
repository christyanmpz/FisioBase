"""Modelos persistidos do sistema."""

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash


db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    senha = db.Column(db.String(255), nullable=False)
    tipo_usuario = db.Column(db.String(30), nullable=False, index=True)

    @property
    def dashboard_endpoint(self) -> str:
        return (
            "admin_dashboard"
            if self.tipo_usuario == "admin"
            else "physiotherapist_dashboard"
        )

    def set_password(self, password: str) -> None:
        self.senha = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.senha, password)