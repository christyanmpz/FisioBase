"""Aplicação Flask do sistema do consultório de fisioterapia."""

from functools import wraps
import os
from datetime import date

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

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
from flask_wtf.csrf import CSRFProtect
from sqlalchemy.pool import NullPool

from models import (
    ADMIN_PROFILE,
    PHYSIOTHERAPIST_PROFILE,
    Patient,
    TreatmentCycle,
    User,
    db,
)

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message = "Entre para acessar esta área."
login_manager.login_message_category = "info"

csrf = CSRFProtect()

REGIOES = ("OMBRO", "JOELHO", "COLUNA", "OUTRO")
MODALIDADES = ("INDIVIDUAL", "GRUPO")
STATUS_ENCERRAMENTO = ("CONCLUIDO", "ALTA", "ABANDONO")


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
            SESSION_COOKIE_SECURE=os.getenv("VERCEL") is not None,
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

    # ------------------------------------------------------------------
    # Pacientes
    # ------------------------------------------------------------------

    def _dados_do_formulario(paciente):
        """Preenche o paciente com o formulário. Devolve a mensagem de erro ou None."""
        nome = request.form.get("nome", "").strip()
        if not nome:
            return "O nome do paciente é obrigatório."

        data_nascimento = request.form.get("data_nascimento", "").strip()
        if data_nascimento:
            try:
                paciente.data_nascimento = date.fromisoformat(data_nascimento)
            except ValueError:
                return "Data de nascimento inválida."
        else:
            paciente.data_nascimento = None

        paciente.nome = nome
        paciente.cpf = request.form.get("cpf", "").strip() or None
        paciente.telefone = request.form.get("telefone", "").strip() or None
        paciente.email = request.form.get("email", "").strip() or None
        paciente.endereco = request.form.get("endereco", "").strip() or None
        paciente.cid = request.form.get("cid", "").strip() or None
        paciente.diagnostico = request.form.get("diagnostico", "").strip() or None
        paciente.observacoes = request.form.get("observacoes", "").strip() or None
        return None

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
            paciente = Patient(ativo=True, fisioterapeuta_id=current_user.id)
            erro = _dados_do_formulario(paciente)
            if erro:
                flash(erro, "error")
                return render_template("paciente_form.html", paciente=None), 400

            db.session.add(paciente)
            db.session.commit()
            flash(f"Paciente {paciente.nome} cadastrado.", "success")
            return redirect(url_for("listar_pacientes"))

        return render_template("paciente_form.html", paciente=None)

    @app.route("/pacientes/<int:paciente_id>/editar", methods=["GET", "POST"])
    @login_required
    def editar_paciente(paciente_id: int):
        paciente = db.session.get(Patient, paciente_id)
        if paciente is None:
            abort(404)
        if not paciente.acessivel_por(current_user):
            abort(403)

        if request.method == "POST":
            erro = _dados_do_formulario(paciente)
            if erro:
                flash(erro, "error")
                return render_template("paciente_form.html", paciente=paciente), 400

            db.session.commit()
            flash(f"Dados de {paciente.nome} atualizados.", "success")
            return redirect(url_for("listar_pacientes"))

        return render_template("paciente_form.html", paciente=paciente)

    @app.post("/pacientes/<int:paciente_id>/desativar")
    @login_required
    def desativar_paciente(paciente_id: int):
        paciente = db.session.get(Patient, paciente_id)
        if paciente is None:
            abort(404)
        if not paciente.acessivel_por(current_user):
            abort(403)

        paciente.ativo = False
        db.session.commit()
        flash(f"{paciente.nome} foi desativado.", "success")
        return redirect(url_for("listar_pacientes"))

    # ------------------------------------------------------------------
    # Usuários
    # ------------------------------------------------------------------

    @app.get("/usuarios")
    @role_required(ADMIN_PROFILE)
    def listar_usuarios():
        usuarios = User.query.order_by(User.nome).all()
        return render_template("usuarios_lista.html", usuarios=usuarios)

    @app.route("/usuarios/novo", methods=["GET", "POST"])
    @role_required(ADMIN_PROFILE)
    def novo_usuario():
        if request.method == "POST":
            nome = request.form.get("nome", "").strip()
            email = request.form.get("email", "").strip().lower()
            senha = request.form.get("senha", "")
            perfil = request.form.get("perfil", "").strip().upper()

            if not nome or not email or not senha:
                flash("Nome, e-mail e senha são obrigatórios.", "error")
                return render_template("usuario_form.html"), 400

            if perfil not in (ADMIN_PROFILE, PHYSIOTHERAPIST_PROFILE):
                flash("Perfil inválido.", "error")
                return render_template("usuario_form.html"), 400

            if len(senha) < 8:
                flash("A senha deve ter ao menos 8 caracteres.", "error")
                return render_template("usuario_form.html"), 400

            if db.session.scalar(db.select(User).where(User.email == email)):
                flash("Já existe um usuário com esse e-mail.", "error")
                return render_template("usuario_form.html"), 400

            usuario = User(
                nome=nome, email=email, perfil=perfil, ativo=True, falhas_login=0
            )
            usuario.set_password(senha)
            db.session.add(usuario)
            db.session.commit()
            flash(f"Usuário {usuario.nome} criado.", "success")
            return redirect(url_for("listar_usuarios"))

        return render_template("usuario_form.html")

    @app.post("/usuarios/<int:usuario_id>/desativar")
    @role_required(ADMIN_PROFILE)
    def desativar_usuario(usuario_id: int):
        usuario = db.session.get(User, usuario_id)
        if usuario is None:
            abort(404)

        if usuario.id == current_user.id:
            flash("Você não pode desativar a própria conta.", "error")
            return redirect(url_for("listar_usuarios"))

        usuario.ativo = False
        db.session.commit()
        flash(f"{usuario.nome} foi desativado.", "success")
        return redirect(url_for("listar_usuarios"))

    # ------------------------------------------------------------------
    # Ciclos de tratamento
    # ------------------------------------------------------------------

    @app.get("/pacientes/<int:paciente_id>/ciclos")
    @login_required
    def listar_ciclos(paciente_id: int):
        paciente = db.session.get(Patient, paciente_id)
        if paciente is None:
            abort(404)
        if not paciente.acessivel_por(current_user):
            abort(403)

        ciclos = (
            TreatmentCycle.query.filter_by(paciente_id=paciente.id)
            .order_by(TreatmentCycle.data_avaliacao.desc())
            .all()
        )
        return render_template("ciclos_lista.html", paciente=paciente, ciclos=ciclos)

    @app.route("/pacientes/<int:paciente_id>/ciclos/novo", methods=["GET", "POST"])
    @login_required
    def novo_ciclo(paciente_id: int):
        paciente = db.session.get(Patient, paciente_id)
        if paciente is None:
            abort(404)
        if not paciente.acessivel_por(current_user):
            abort(403)

        if request.method == "POST":
            regiao = request.form.get("regiao", "").strip().upper()
            modalidade = request.form.get("modalidade", "INDIVIDUAL").strip().upper()

            if regiao not in REGIOES:
                flash("Selecione uma região válida.", "error")
                return render_template("ciclo_form.html", paciente=paciente), 400

            if modalidade not in MODALIDADES:
                flash("Modalidade inválida.", "error")
                return render_template("ciclo_form.html", paciente=paciente), 400

            try:
                data_avaliacao = date.fromisoformat(
                    request.form.get("data_avaliacao", "").strip()
                )
            except ValueError:
                flash("Informe uma data de avaliação válida.", "error")
                return render_template("ciclo_form.html", paciente=paciente), 400

            try:
                sessoes = int(request.form.get("total_sessoes", "10").strip())
            except ValueError:
                flash("Número de sessões inválido.", "error")
                return render_template("ciclo_form.html", paciente=paciente), 400

            if not 1 <= sessoes <= 30:
                flash("O número de sessões deve estar entre 1 e 30.", "error")
                return render_template("ciclo_form.html", paciente=paciente), 400

            ciclo = TreatmentCycle(
                paciente_id=paciente.id,
                fisioterapeuta_id=paciente.fisioterapeuta_id or current_user.id,
                regiao=regiao,
                modalidade=modalidade,
                data_avaliacao=data_avaliacao,
                total_sessoes=sessoes,
                status="ATIVO",
                observacoes=request.form.get("observacoes", "").strip() or None,
            )
            db.session.add(ciclo)
            db.session.commit()
            flash("Ciclo de tratamento aberto.", "success")
            return redirect(url_for("listar_ciclos", paciente_id=paciente.id))

        return render_template("ciclo_form.html", paciente=paciente)

    @app.post("/ciclos/<int:ciclo_id>/encerrar")
    @login_required
    def encerrar_ciclo(ciclo_id: int):
        ciclo = db.session.get(TreatmentCycle, ciclo_id)
        if ciclo is None:
            abort(404)
        if not ciclo.acessivel_por(current_user):
            abort(403)

        novo_status = request.form.get("status", "").strip().upper()
        if novo_status not in STATUS_ENCERRAMENTO:
            flash("Status de encerramento inválido.", "error")
            return redirect(url_for("listar_ciclos", paciente_id=ciclo.paciente_id))

        ciclo.status = novo_status
        ciclo.data_alta = date.today()
        db.session.commit()
        flash("Ciclo encerrado.", "success")
        return redirect(url_for("listar_ciclos", paciente_id=ciclo.paciente_id))


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
