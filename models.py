"""Modelos persistidos do sistema."""

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash


db = SQLAlchemy()

ADMIN_PROFILE = "ADMIN"
PHYSIOTHERAPIST_PROFILE = "FISIOTERAPEUTA"


class User(UserMixin, db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    senha_hash = db.Column(db.String(255), nullable=False)
    perfil = db.Column(db.String(30), nullable=False, index=True)
    ativo = db.Column(db.Boolean, nullable=False)
    falhas_login = db.Column(db.Integer, nullable=False)
    bloqueado_ate = db.Column(db.DateTime(timezone=True), nullable=True)
    criado_em = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())

    @property
    def dashboard_endpoint(self) -> str:
        return (
            "admin_dashboard"
            if self.perfil == ADMIN_PROFILE
            else "physiotherapist_dashboard"
        )

    def set_password(self, password: str) -> None:
        self.senha_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.senha_hash, password)