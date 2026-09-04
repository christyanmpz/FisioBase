"""Aplicação Flask inicial do sistema do consultório de fisioterapia."""

from functools import wraps
import os
from pathlib import Path

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)

from models import User, db


BASE_DIR = Path(__file__).resolve().parent

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message = "Entre para acessar esta área."
login_manager.login_message_category = "info"


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("SESSION_SECRET", "chave-local-de-desenvolvimento"),
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{BASE_DIR / 'instance' / 'fisioterapia.db'}",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        REMEMBER_COOKIE_HTTPONLY=True,
    )

    (BASE_DIR / "instance").mkdir(exist_ok=True)
    db.init_app(app)
    login_manager.init_app(app)

    with app.app_context():
        db.create_all()
        seed_users()

    register_routes(app)
    register_error_handlers(app)
    return app


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    return db.session.get(User, int(user_id))


def seed_users() -> None:
    """Cria usuários de demonstração somente quando o banco está vazio."""
    if User.query.first() is not None:
        return

    admin = User(
        nome="Marina Almeida",
        email="admin@fisio.com",
        tipo_usuario="admin",
    )
    admin.set_password("Admin@123")

    fisioterapeuta = User(
        nome="Rafael Santos",
        email="fisio@fisio.com",
        tipo_usuario="fisioterapeuta",
    )
    fisioterapeuta.set_password("Fisio@123")

    db.session.add_all([admin, fisioterapeuta])
    db.session.commit()


def role_required(role: str):
    """Restringe uma rota a um tipo de usuário específico."""

    def decorator(view_function):
        @wraps(view_function)
        @login_required
        def wrapped_view(*args, **kwargs):
            if current_user.tipo_usuario != role:
                abort(403)
            return view_function(*args, **kwargs)

        return wrapped_view

    return decorator


def user_payload(user: User) -> dict[str, str | int]:
    """Representa um usuário sem expor o hash de senha ao cliente."""
    return {
        "id": user.id,
        "nome": user.nome,
        "email": user.email,
        "tipo_usuario": user.tipo_usuario,
    }


def register_routes(app: Flask) -> None:
    @app.post("/api/auth/login")
    def api_login():
        """Autentica o front React usando a sessão real do Flask-Login."""
        if current_user.is_authenticated:
            user = current_user
            return jsonify(
                {
                    "authenticated": True,
                    "user": user_payload(user),
                    "redirect_path": url_for(user.dashboard_endpoint),
                }
            )

        data = request.get_json(silent=True) or request.form
        email = str(data.get("email", "")).strip().lower()
        password = str(data.get("senha", ""))
        user = db.session.scalar(db.select(User).where(User.email == email))

        if user is None or not user.check_password(password):
            return (
                jsonify(
                    {
                        "authenticated": False,
                        "message": "E-mail ou senha incorretos. Confira os dados e tente novamente.",
                    }
                ),
                401,
            )

        login_user(user)
        return jsonify(
            {
                "authenticated": True,
                "user": user_payload(user),
                "redirect_path": url_for(user.dashboard_endpoint),
            }
        )

    @app.get("/api/auth/session")
    def api_session():
        """Retorna a identidade vinculada ao cookie de sessão atual."""
        if not current_user.is_authenticated:
            return jsonify({"authenticated": False, "user": None})

        return jsonify({"authenticated": True, "user": user_payload(current_user)})

    @app.post("/api/auth/logout")
    def api_logout():
        """Encerra a sessão Flask-Login sem renderizar uma página HTML."""
        if current_user.is_authenticated:
            logout_user()
        return jsonify({"authenticated": False})

    @app.get("/api/admin/users")
    @role_required("admin")
    def api_admin_users():
        """Fornece ao dashboard administrativo os usuários persistidos."""
        profissionais = User.query.order_by(User.nome).all()
        return jsonify(
            {
                "users": [user_payload(profissional) for profissional in profissionais],
                "totals": {
                    "users": len(profissionais),
                    "admins": sum(
                        profissional.tipo_usuario == "admin"
                        for profissional in profissionais
                    ),
                    "fisioterapeutas": sum(
                        profissional.tipo_usuario == "fisioterapeuta"
                        for profissional in profissionais
                    ),
                },
            }
        )

    @app.get("/")
    def index():
        if not current_user.is_authenticated:
            return redirect(url_for("login"))
        return redirect(url_for(current_user.dashboard_endpoint))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for(current_user.dashboard_endpoint))

        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("senha", "")
            user = db.session.scalar(db.select(User).where(User.email == email))

            if user is None or not user.check_password(password):
                flash("E-mail ou senha incorretos. Confira os dados e tente novamente.", "error")
                return render_template("login.html", email=email), 401

            login_user(user)
            flash(f"Bem-vindo(a), {user.nome.split()[0]}!", "success")
            return redirect(url_for(user.dashboard_endpoint))

        return render_template("login.html", email="")

    @app.post("/logout")
    @login_required
    def logout():
        logout_user()
        flash("Você saiu do sistema com segurança.", "success")
        return redirect(url_for("login"))

    @app.get("/dashboard/admin")
    @role_required("admin")
    def admin_dashboard():
        profissionais = User.query.order_by(User.nome).all()
        total_admins = User.query.filter_by(tipo_usuario="admin").count()
        total_fisioterapeutas = User.query.filter_by(tipo_usuario="fisioterapeuta").count()
        return render_template(
            "dashboard_admin.html",
            profissionais=profissionais,
            total_admins=total_admins,
            total_fisioterapeutas=total_fisioterapeutas,
        )

    @app.get("/dashboard/fisioterapeuta")
    @role_required("fisioterapeuta")
    def physiotherapist_dashboard():
        return render_template("dashboard_fisioterapeuta.html")


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("403.html"), 403

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("404.html"), 404


app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)