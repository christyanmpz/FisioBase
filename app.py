"""Aplicação Flask inicial do sistema do consultório de fisioterapia."""

from functools import wraps
import os
from datetime import date
from dotenv import load_dotenv

from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from sqlalchemy.pool import NullPool

from flask_wtf.csrf import CSRFProtect

from models import ADMIN_PROFILE, PHYSIOTHERAPIST_PROFILE, Patient, User, db

load_dotenv()

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message = "Entre para acessar esta área."
login_manager.login_message_category = "info"


csrf = CSRFProtect()


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        REMEMBER_COOKIE_HTTPONLY=True,
    )

    if test_config is None:
        database_url = os.getenv("SUPABASE_DB_URL")
        if not database_url:
            raise RuntimeError(
                "SUPABASE_DB_URL não está configurada; a aplicação não iniciará sem um banco PostgreSQL."
            )

        session_secret = os.getenv("SESSION_SECRET")
        if not session_secret:
            raise RuntimeError(
                "SESSION_SECRET não está configurada; a aplicação não iniciará sem uma chave de sessão."
            )

        if database_url.startswith("postgres://"):
            database_url = "postgresql://" + database_url[len("postgres://") :]

        app.config.update(
            SECRET_KEY=session_secret,
            SQLALCHEMY_DATABASE_URI=database_url,
            SQLALCHEMY_ENGINE_OPTIONS={"poolclass": NullPool},
        )
    else:
        app.config.update(test_config)
        if not app.config.get("SQLALCHEMY_DATABASE_URI"):
            raise RuntimeError(
                "test_config deve informar SQLALCHEMY_DATABASE_URI, por exemplo sqlite:///:memory:."
            )
        if not app.config.get("SECRET_KEY"):
            raise RuntimeError("test_config deve informar SECRET_KEY para os testes.")

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    register_routes(app)
    csrf.exempt(app.view_functions["api_login"])
    csrf.exempt(app.view_functions["api_logout"])
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
        perfil=ADMIN_PROFILE,
        ativo=True,
        falhas_login=0,
    )
    admin.set_password("Admin@123")

    fisioterapeuta = User(
        nome="Rafael Santos",
        email="fisio@fisio.com",
        perfil=PHYSIOTHERAPIST_PROFILE,
        ativo=True,
        falhas_login=0,
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
            if current_user.perfil != role:
                abort(403)
            return view_function(*args, **kwargs)

        return wrapped_view

    return decorator


def user_payload(user: User) -> dict[str, str | int | bool | None]:
    """Representa um usuário sem expor o hash de senha ao cliente."""
    return {
        "id": user.id,
        "nome": user.nome,
        "email": user.email,
        "perfil": user.perfil,
        "ativo": user.ativo,
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

        if user is None or not user.check_password(password) or not user.ativo:
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
    @role_required(ADMIN_PROFILE)
    def api_admin_users():
        """Fornece ao dashboard administrativo os usuários persistidos."""
        profissionais = User.query.order_by(User.nome).all()
        return jsonify(
            {
                "users": [user_payload(profissional) for profissional in profissionais],
                "totals": {
                    "users": len(profissionais),
                    "admins": sum(
                        profissional.perfil == ADMIN_PROFILE
                        for profissional in profissionais
                    ),
                    "fisioterapeutas": sum(
                        profissional.perfil == PHYSIOTHERAPIST_PROFILE
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

            if user is None or not user.check_password(password) or not user.ativo:
                flash(
                    "E-mail ou senha incorretos. Confira os dados e tente novamente.",
                    "error",
                )
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
    @role_required(ADMIN_PROFILE)
    def admin_dashboard():
        profissionais = User.query.order_by(User.nome).all()
        total_admins = User.query.filter_by(perfil=ADMIN_PROFILE).count()
        total_fisioterapeutas = User.query.filter_by(
            perfil=PHYSIOTHERAPIST_PROFILE
        ).count()
        return render_template(
            "dashboard_admin.html",
            profissionais=profissionais,
            total_admins=total_admins,
            total_fisioterapeutas=total_fisioterapeutas,
        )

    @app.get("/dashboard/fisioterapeuta")
    @role_required(PHYSIOTHERAPIST_PROFILE)
    def physiotherapist_dashboard():
        return render_template("dashboard_fisioterapeuta.html")

    @app.get("/pacientes")
    @login_required
    def listar_pacientes():
        consulta = Patient.query
        if current_user.perfil != ADMIN_PROFILE:
            consulta = consulta.filter_by(fisioterapeuta_id=current_user.id)
        pacientes = consulta.order_by(Patient.nome).all()
        return render_template("pacientes_lista.html", pacientes=pacientes)

    @app.route("/pacientes/novo", methods=["GET", "POST"])
    @login_required
    def novo_paciente():
        if request.method == "POST":
            nome = request.form.get("nome", "").strip()
            if not nome:
                flash("O nome do paciente é obrigatório.", "error")
                return render_template("paciente_form.html", paciente=None), 400

            paciente = Patient(
                nome=nome,
                cpf=request.form.get("cpf", "").strip() or None,
                telefone=request.form.get("telefone", "").strip() or None,
                email=request.form.get("email", "").strip() or None,
                endereco=request.form.get("endereco", "").strip() or None,
                cid=request.form.get("cid", "").strip() or None,
                diagnostico=request.form.get("diagnostico", "").strip() or None,
                observacoes=request.form.get("observacoes", "").strip() or None,
                ativo=True,
                fisioterapeuta_id=current_user.id,
            )

            data_nascimento = request.form.get("data_nascimento", "").strip()
            if data_nascimento:
                try:
                    paciente.data_nascimento = date.fromisoformat(data_nascimento)
                except ValueError:
                    flash("Data de nascimento inválida.", "error")
                    return render_template("paciente_form.html", paciente=None), 400

            db.session.add(paciente)
            db.session.commit()
            flash(f"Paciente {paciente.nome} cadastrado.", "success")
            return redirect(url_for("listar_pacientes"))

        return render_template("paciente_form.html", paciente=None) 
    

def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("403.html"), 403

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("404.html"), 404


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    create_app().run(host="0.0.0.0", port=port, debug=True)
