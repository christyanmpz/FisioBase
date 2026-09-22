"""Aplicação Flask do sistema do consultório de fisioterapia."""

from functools import wraps
import os
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

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
    GROUP_CAPACITY_DEFAULT,
    GROUP_CAPACITY_MAX,
    GROUP_CAPACITY_MIN,
    GROUP_REGIONS,
    GROUP_WEEKS_DEFAULT,
    GROUP_WEEKS_MAX,
    PHYSIOTHERAPIST_PROFILE,
    SESSOES_POR_ENCONTRO_DE_GRUPO,
    WEEKDAY_NAMES,
    Appointment,
    Card,
    Evolution,
    Group,
    GroupEvolution,
    GroupPatient,
    Holiday,
    Patient,
    ScreeningSlot,
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
LIMITE_POR_HORARIO = 2
# Quantos pacientes por página na listagem.
PACIENTES_POR_PAGINA = 20
# Quantas vezes por semana o paciente pode ser atendido.
FREQUENCIAS = (1, 2, 3)
STATUS_AGENDAMENTO = (
    "AGENDADO",
    "CONFIRMADO",
    "REALIZADO",
    "CANCELADO",
    "FALTOU",
    "FALTA_JUSTIFICADA",
)
# Falta justificada conta como falta nos números, mas guarda o motivo.
# O paciente não veio, seja avisando ou não: nenhuma delas recebe evolução.
STATUS_DE_AUSENCIA = ("FALTOU", "FALTA_JUSTIFICADA")
# Para os números do setor, a falta justificada conta como atendimento: o
# horário foi reservado e o profissional ficou disponível.
STATUS_DE_ATENDIMENTO = ("REALIZADO", "FALTA_JUSTIFICADA")
# Só a falta não avisada entra como falta nos indicadores.
STATUS_DE_FALTA = ("FALTOU",)
# Cancelamento pelo setor e falta justificada dão direito a reposição ao
# fim do ciclo; a falta não avisada, não.
STATUS_QUE_REPOEM = ("CANCELADO", "FALTA_JUSTIFICADA")
# Marca técnica na observação da reposição: evita criar duas para a mesma
# sessão se o status for alterado de novo.
MARCA_REPOSICAO = "[rep:{id}]"
# Como cada situação aparece na tela e nas folhas impressas.
ROTULOS_DE_STATUS = {
    "AGENDADO": "Agendado",
    "CONFIRMADO": "Confirmado",
    "REALIZADO": "Compareceu",
    "CANCELADO": "Cancelado",
    "FALTOU": "Faltou",
    "FALTA_JUSTIFICADA": "Falta justificada",
}
# Nomes dos meses, para os filtros e os títulos dos relatórios.
MESES = (
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
)
# Como cada situação do ciclo de tratamento aparece na tela e na impressão.
ROTULOS_DE_CICLO = {
    "ATIVO": "Em tratamento",
    "CONCLUIDO": "Concluído",
    "ALTA": "Alta",
    "ABANDONO": "Abandono",
}
# Expediente da clínica: 07:30 às 15:30, sessões de 30 min, encerrando às 16h.
# O almoço fica fora da grade para todos; bloqueios por profissional virão
# com a tela de disponibilidade (triagens fixas, reunião e horários fechados).
HORARIO_ALMOCO = "12:00"
HORARIOS = [
    f"{h:02d}:{m:02d}"
    for h in range(7, 16)
    for m in (0, 30)
    if (h, m) >= (7, 30) and f"{h:02d}:{m:02d}" != HORARIO_ALMOCO
]
# A clínica não atende sábado nem domingo (0 = segunda ... 6 = domingo).
DIAS_DE_ATENDIMENTO = (0, 1, 2, 3, 4)
# A sessão de grupo dura 1 hora: ocupa dois horários seguidos da grade.
SLOTS_POR_GRUPO = 2
# Status em que a sessão aceita evolução clínica (e só a partir do dia dela).
STATUS_COM_EVOLUCAO = ("AGENDADO", "CONFIRMADO", "REALIZADO")
# Status que registram comparecimento; só valem a partir do dia da sessão.
# Expediente da clínica: 07:30 às 15:30, sessões de 30 min, encerrando às 16h.
# O almoço fica fora da grade para todos; bloqueios por profissional virão
# com a tela de disponibilidade (triagens fixas, reunião e horários fechados).
HORARIO_ALMOCO = "12:00"
HORARIOS = [
    f"{h:02d}:{m:02d}"
    for h in range(7, 16)
    for m in (0, 30)
    if (h, m) >= (7, 30) and f"{h:02d}:{m:02d}" != HORARIO_ALMOCO
]
# A clínica não atende sábado nem domingo (0 = segunda ... 6 = domingo).
DIAS_DE_ATENDIMENTO = (0, 1, 2, 3, 4)
# A sessao de grupo dura 1 hora: ocupa dois horarios seguidos da grade.
SLOTS_POR_GRUPO = 2
# Status em que a sessão aceita evolução clínica (e só a partir do dia dela).
STATUS_COM_EVOLUCAO = ("AGENDADO", "CONFIRMADO", "REALIZADO")
# Status que registram comparecimento; só valem a partir do dia da sessão.
# Comparecer só pode ser registrado a partir do dia da sessão. As ausências
# são registradas antes: o paciente avisa com antecedência.
STATUS_SO_A_PARTIR_DO_DIA = ("REALIZADO",)
FUSO_CLINICA = ZoneInfo("America/Sao_Paulo")


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

    app.jinja_env.globals["ROTULOS_DE_STATUS"] = ROTULOS_DE_STATUS
    app.jinja_env.globals["ROTULOS_DE_CICLO"] = ROTULOS_DE_CICLO
    app.jinja_env.globals["MESES"] = MESES
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


def cpf_valido(cpf: str) -> bool:
    """Valida os dois dígitos verificadores do CPF."""
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False

    for posicao in (9, 10):
        soma = sum(int(cpf[i]) * (posicao + 1 - i) for i in range(posicao))
        digito = (soma * 10) % 11
        if digito == 10:
            digito = 0
        if digito != int(cpf[posicao]):
            return False

    return True


def hoje(agora: datetime | None = None) -> date:
    """Data de hoje no fuso da clínica.

    O servidor da Vercel roda em UTC: depois das 21h de Brasília,
    date.today() já devolveria o dia seguinte.
    """
    agora = agora or datetime.now(FUSO_CLINICA)
    return agora.astimezone(FUSO_CLINICA).date()


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

    def _resumo_do_mes(consulta_base, dia_atual):
        """Conta realizados, faltas e taxa de presença no mês corrente."""
        inicio = dia_atual.replace(day=1)
        fim = (
            date(inicio.year + 1, 1, 1)
            if inicio.month == 12
            else date(inicio.year, inicio.month + 1, 1)
        )
        # O bloco do grupo na agenda não é atendimento: quem conta é a
        # presença de cada inscrito, registrada uma por paciente.
        itens = consulta_base.filter(
            Appointment.data >= inicio,
            Appointment.data < fim,
            Appointment.tipo != "GRUPO",
        ).all()
        realizados = sum(1 for i in itens if i.status in STATUS_DE_ATENDIMENTO)
        faltas = sum(1 for i in itens if i.status in STATUS_DE_FALTA)
        previstos = realizados + faltas
        return {
            "realizados": realizados,
            "faltas": faltas,
            "taxa_presenca": (round(realizados * 100 / previstos) if previstos else 0),
        }

    @app.get("/dashboard/admin")
    @role_required(ADMIN_PROFILE)
    def admin_dashboard():
        profissionais = User.query.order_by(User.nome).all()
        dia_atual = hoje()

        agenda_de_hoje = (
            Appointment.query.filter(Appointment.data == dia_atual)
            .order_by(Appointment.hora)
            .all()
        )

        return render_template(
            "dashboard_admin.html",
            profissionais=profissionais,
            total_admins=sum(p.perfil == ADMIN_PROFILE for p in profissionais),
            total_fisioterapeutas=sum(
                p.perfil == PHYSIOTHERAPIST_PROFILE for p in profissionais
            ),
            dia_atual=dia_atual,
            agenda_de_hoje=agenda_de_hoje,
            pacientes_ativos=Patient.query.filter_by(ativo=True).count(),
            ciclos_ativos=TreatmentCycle.query.filter_by(status="ATIVO").count(),
            grupos_ativos=Group.query.filter_by(ativo=True).count(),
            resumo=_resumo_do_mes(Appointment.query, dia_atual),
        )

    @app.get("/dashboard/fisioterapeuta")
    @role_required(PHYSIOTHERAPIST_PROFILE)
    def physiotherapist_dashboard():
        dia_atual = hoje()
        meus = Appointment.query.filter(
            Appointment.fisioterapeuta_id == current_user.id
        )

        agenda_de_hoje = (
            meus.filter(Appointment.data == dia_atual).order_by(Appointment.hora).all()
        )
        proximos = (
            meus.filter(
                Appointment.data > dia_atual,
                Appointment.status.in_(("AGENDADO", "CONFIRMADO")),
            )
            .order_by(Appointment.data, Appointment.hora)
            .limit(5)
            .all()
        )

        return render_template(
            "dashboard_fisioterapeuta.html",
            dia_atual=dia_atual,
            agenda_de_hoje=agenda_de_hoje,
            proximos=proximos,
            meus_pacientes=Patient.query.filter_by(
                ativo=True, fisioterapeuta_id=current_user.id
            ).count(),
            meus_grupos=Group.query.filter_by(
                ativo=True, fisioterapeuta_id=current_user.id
            ).all(),
            resumo=_resumo_do_mes(meus, dia_atual),
        )

    # ------------------------------------------------------------------
    # Pacientes
    # ------------------------------------------------------------------

    def _fisioterapeutas_ativos():
        """Lista os fisioterapeutas ativos, para o admin escolher o responsável."""
        return (
            User.query.filter_by(perfil=PHYSIOTHERAPIST_PROFILE, ativo=True)
            .order_by(User.nome)
            .all()
        )

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
        cpf = "".join(c for c in request.form.get("cpf", "") if c.isdigit())
        if cpf:
            if len(cpf) != 11:
                return "O CPF deve ter 11 dígitos."
            if not cpf_valido(cpf):
                return "CPF inválido. Confira os números digitados."
            existente = db.session.scalar(db.select(Patient).where(Patient.cpf == cpf))
            if existente and existente.id != paciente.id:
                return "Já existe um paciente cadastrado com este CPF."
        paciente.cpf = cpf or None
        paciente.telefone = request.form.get("telefone", "").strip() or None
        paciente.email = request.form.get("email", "").strip() or None
        paciente.endereco = request.form.get("endereco", "").strip() or None

        # Cartão do cidadão: identificação do município, não do paciente em si.
        # Nem todo paciente tem, então o campo é opcional — mas quando vem
        # preenchido precisa ser um número de 10 a 15 dígitos.
        cartao = "".join(
            c for c in request.form.get("cartao_cidadao", "") if c.isdigit()
        )
        if cartao and not 10 <= len(cartao) <= 15:
            return "O número do cartão cidadão deve ter de 10 a 15 dígitos."
        paciente.cartao_cidadao = cartao or None

        paciente.observacoes = request.form.get("observacoes", "").strip() or None

        if current_user.perfil == ADMIN_PROFILE:
            responsavel_id = request.form.get("fisioterapeuta_id", "").strip()
            if responsavel_id:
                responsavel = db.session.get(User, int(responsavel_id))
                if responsavel is None or not responsavel.ativo:
                    return "Selecione um fisioterapeuta responsável válido."
                paciente.fisioterapeuta_id = responsavel.id

        return None

    def _data_digitada(texto):
        """Entende a data de nascimento como a recepção costuma digitar.

        Aceita 01/10/1983, 01-10-1983, 1983-10-01 e 01101983. Devolve None
        quando o texto não é uma data — aí a busca segue só por nome e CPF.
        """
        limpo = texto.strip()
        digitos = "".join(c for c in limpo if c.isdigit())
        if len(digitos) == 8 and not any(c in limpo for c in "/-."):
            limpo = f"{digitos[:2]}/{digitos[2:4]}/{digitos[4:]}"

        for separador in ("/", "-", "."):
            limpo = limpo.replace(separador, "/")

        partes = limpo.split("/")
        if len(partes) != 3 or not all(p.isdigit() for p in partes):
            return None

        if len(partes[0]) == 4:  # 1983/10/01
            ano, mes, dia = partes
        else:  # 01/10/1983
            dia, mes, ano = partes

        try:
            return date(int(ano), int(mes), int(dia))
        except ValueError:
            return None

    @app.get("/pacientes")
    @login_required
    def listar_pacientes():
        busca = request.args.get("q", "").strip()

        consulta = Patient.query
        if current_user.perfil != ADMIN_PROFILE:
            consulta = consulta.filter_by(fisioterapeuta_id=current_user.id)

        if busca:
            somente_digitos = "".join(c for c in busca if c.isdigit())
            filtros = [Patient.nome.ilike(f"%{busca}%")]
            if somente_digitos:
                filtros.append(Patient.cpf.ilike(f"%{somente_digitos}%"))
                filtros.append(Patient.cartao_cidadao.ilike(f"%{somente_digitos}%"))
            nascimento = _data_digitada(busca)
            if nascimento is not None:
                filtros.append(Patient.data_nascimento == nascimento)
            consulta = consulta.filter(db.or_(*filtros))

        try:
            pagina = max(int(request.args.get("pagina", 1)), 1)
        except ValueError:
            pagina = 1

        paginacao = consulta.order_by(Patient.nome).paginate(
            page=pagina, per_page=PACIENTES_POR_PAGINA, error_out=False
        )

        return render_template(
            "pacientes_lista.html",
            pacientes=paginacao.items,
            paginacao=paginacao,
            busca=busca,
        )

    def _historico_por_ciclo(ciclos, atendimentos):
        """Agrupa o histórico por ciclo de tratamento.

        Misturados por data, os atendimentos de ciclos antigos se confundem
        com os do tratamento atual. A clínica lê de cima para baixo: o ciclo
        em andamento primeiro, depois os encerrados do mais recente para o
        mais antigo. Dentro de cada ciclo as sessões ficam na ordem em que
        aconteceram, como no cartão do paciente.

        Atendimento sem ciclo — uma triagem avulsa, por exemplo — vai num
        bloco final, para não sumir do prontuário.
        """
        por_ciclo = {}
        avulsos = []
        for item in atendimentos:
            if item.ciclo_id is None:
                avulsos.append(item)
            else:
                por_ciclo.setdefault(item.ciclo_id, []).append(item)

        def peso(ciclo):
            # Ativo primeiro; entre os encerrados, o mais recente antes.
            return (ciclo.status != "ATIVO", -ciclo.data_avaliacao.toordinal())

        blocos = [
            {
                "ciclo": ciclo,
                "atendimentos": sorted(
                    por_ciclo.get(ciclo.id, []), key=lambda i: (i.data, i.hora)
                ),
            }
            for ciclo in sorted(ciclos, key=peso)
        ]
        if avulsos:
            blocos.append(
                {
                    "ciclo": None,
                    "atendimentos": sorted(avulsos, key=lambda i: (i.data, i.hora)),
                }
            )
        return blocos

    @app.get("/pacientes/<int:paciente_id>")
    @login_required
    def ficha_paciente(paciente_id: int):
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

        atendimentos = (
            Appointment.query.filter_by(paciente_id=paciente.id)
            .order_by(Appointment.data.desc(), Appointment.hora.desc())
            .all()
        )

        def contar(status):
            return sum(1 for item in atendimentos if item.status == status)

        realizados = sum(1 for i in atendimentos if i.status in STATUS_DE_ATENDIMENTO)
        faltas = sum(1 for i in atendimentos if i.status in STATUS_DE_FALTA)
        cancelados = contar("CANCELADO")
        previstos = len(atendimentos) - cancelados
        taxa_falta = round(faltas * 100 / previstos, 1) if previstos else 0

        acoes_evolucao = {
            item.id: _acao_evolucao(
                item, item.evolucao[0] if item.evolucao else None, current_user
            )
            for item in atendimentos
        }

        return render_template(
            "paciente_ficha.html",
            paciente=paciente,
            ciclos=ciclos,
            blocos=_historico_por_ciclo(ciclos, atendimentos),
            atendimentos=atendimentos,
            acoes_evolucao=acoes_evolucao,
            total=len(atendimentos),
            realizados=realizados,
            faltas=faltas,
            cancelados=cancelados,
            taxa_falta=taxa_falta,
        )

    @app.get("/pacientes/<int:paciente_id>/prontuario")
    @login_required
    def prontuario_paciente(paciente_id: int):
        """Histórico completo para impressão, o equivalente à folha que hoje
        vai grampeada ao prontuário de papel."""
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

        atendimentos = (
            Appointment.query.filter(
                Appointment.paciente_id == paciente.id,
                Appointment.status != "CANCELADO",
            )
            .order_by(Appointment.data, Appointment.hora)
            .all()
        )

        evolucoes = {
            e.agendamento_id: e
            for e in Evolution.query.filter(Evolution.paciente_id == paciente.id).all()
        }

        realizados = sum(1 for i in atendimentos if i.status in STATUS_DE_ATENDIMENTO)
        faltas = sum(1 for i in atendimentos if i.status in STATUS_DE_FALTA)

        return render_template(
            "prontuario_impressao.html",
            paciente=paciente,
            ciclos=ciclos,
            blocos=_historico_por_ciclo(ciclos, atendimentos),
            atendimentos=atendimentos,
            evolucoes=evolucoes,
            realizados=realizados,
            faltas=faltas,
            emitido_em=hoje(),
        )

    @app.route("/pacientes/novo", methods=["GET", "POST"])
    @login_required
    def novo_paciente():
        def form(codigo=200):
            return (
                render_template(
                    "paciente_form.html",
                    paciente=None,
                    fisioterapeutas=_fisioterapeutas_ativos(),
                ),
                codigo,
            )

        if request.method == "POST":
            paciente = Patient(ativo=True, fisioterapeuta_id=current_user.id)
            erro = _dados_do_formulario(paciente)
            if erro:
                flash(erro, "error")
                return form(400)

            db.session.add(paciente)
            db.session.commit()
            flash(f"Paciente {paciente.nome} cadastrado.", "success")
            return redirect(url_for("listar_pacientes"))

        return form()

    @app.route("/pacientes/<int:paciente_id>/editar", methods=["GET", "POST"])
    @login_required
    def editar_paciente(paciente_id: int):
        paciente = db.session.get(Patient, paciente_id)
        if paciente is None:
            abort(404)
        if not paciente.acessivel_por(current_user):
            abort(403)

        def form(codigo=200):
            return (
                render_template(
                    "paciente_form.html",
                    paciente=paciente,
                    fisioterapeutas=_fisioterapeutas_ativos(),
                ),
                codigo,
            )

        if request.method == "POST":
            erro = _dados_do_formulario(paciente)
            if erro:
                flash(erro, "error")
                return form(400)

            db.session.commit()
            flash(f"Dados de {paciente.nome} atualizados.", "success")
            return redirect(url_for("listar_pacientes"))

        return form()

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
        return render_template(
            "ciclos_lista.html",
            paciente=paciente,
            ciclos=ciclos,
            fisioterapeutas=_fisioterapeutas_ativos(),
        )

    @app.route("/pacientes/<int:paciente_id>/ciclos/novo", methods=["GET", "POST"])
    @login_required
    def novo_ciclo(paciente_id: int):
        paciente = db.session.get(Patient, paciente_id)
        if paciente is None:
            abort(404)
        if not paciente.acessivel_por(current_user):
            abort(403)

        def form(codigo=200):
            return (
                render_template(
                    "ciclo_form.html",
                    paciente=paciente,
                    fisioterapeutas=_fisioterapeutas_ativos(),
                ),
                codigo,
            )

        if request.method == "POST":
            regiao = request.form.get("regiao", "").strip().upper()
            modalidade = request.form.get("modalidade", "INDIVIDUAL").strip().upper()

            if regiao not in REGIOES:
                flash("Selecione uma região válida.", "error")
                return form(400)

            if modalidade not in MODALIDADES:
                flash("Modalidade inválida.", "error")
                return form(400)

            try:
                data_avaliacao = date.fromisoformat(
                    request.form.get("data_avaliacao", "").strip()
                )
            except ValueError:
                flash("Informe uma data de avaliação válida.", "error")
                return form(400)

            try:
                sessoes = int(request.form.get("total_sessoes", "10").strip())
            except ValueError:
                flash("Número de sessões inválido.", "error")
                return form(400)

            if not 1 <= sessoes <= 30:
                flash("O número de sessões deve estar entre 1 e 30.", "error")
                return form(400)

            responsavel_id = paciente.fisioterapeuta_id or current_user.id
            if current_user.perfil == ADMIN_PROFILE:
                escolhido = request.form.get("fisioterapeuta_id", "").strip()
                if escolhido:
                    responsavel = db.session.get(User, int(escolhido))
                    if responsavel is None or not responsavel.ativo:
                        flash(
                            "Selecione um fisioterapeuta responsável válido.", "error"
                        )
                        return form(400)
                    responsavel_id = responsavel.id

            ciclo = TreatmentCycle(
                paciente_id=paciente.id,
                fisioterapeuta_id=responsavel_id,
                regiao=regiao,
                cid=request.form.get("cid", "").strip().upper() or None,
                diagnostico=request.form.get("diagnostico", "").strip() or None,
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

        return form()

    @app.route("/ciclos/<int:ciclo_id>/editar", methods=["GET", "POST"])
    @login_required
    def editar_ciclo(ciclo_id: int):
        """Corrige os dados do ciclo sem mexer nas sessões já agendadas."""
        ciclo = db.session.get(TreatmentCycle, ciclo_id)
        if ciclo is None:
            abort(404)
        if not ciclo.acessivel_por(current_user):
            abort(403)

        paciente = ciclo.paciente

        def form(codigo=200):
            return (
                render_template(
                    "ciclo_form.html",
                    ciclo=ciclo,
                    paciente=paciente,
                    fisioterapeutas=_fisioterapeutas_ativos(),
                ),
                codigo,
            )

        if request.method == "GET":
            return form()

        regiao = request.form.get("regiao", "").strip().upper()
        modalidade = request.form.get("modalidade", "INDIVIDUAL").strip().upper()

        if regiao not in REGIOES:
            flash("Selecione uma região válida.", "error")
            return form(400)

        if modalidade not in MODALIDADES:
            flash("Modalidade inválida.", "error")
            return form(400)

        try:
            data_avaliacao = date.fromisoformat(
                request.form.get("data_avaliacao", "").strip()
            )
        except ValueError:
            flash("Informe uma data de avaliação válida.", "error")
            return form(400)

        try:
            sessoes = int(request.form.get("total_sessoes", "10").strip())
        except ValueError:
            flash("Número de sessões inválido.", "error")
            return form(400)

        if not 1 <= sessoes <= 30:
            flash("O número de sessões deve estar entre 1 e 30.", "error")
            return form(400)

        # Diminuir o total abaixo do que já foi marcado deixaria o ciclo com
        # mais sessões na agenda do que no papel.
        ja_agendadas = Appointment.query.filter(
            Appointment.ciclo_id == ciclo.id,
            Appointment.tipo == "SESSAO",
            Appointment.status != "CANCELADO",
        ).count()
        if sessoes < ja_agendadas:
            flash(
                f"Este ciclo já tem {ja_agendadas} sessões agendadas. "
                "Cancele as que sobram antes de reduzir o total.",
                "error",
            )
            return form(400)

        ciclo.regiao = regiao
        ciclo.cid = request.form.get("cid", "").strip().upper() or None
        ciclo.diagnostico = request.form.get("diagnostico", "").strip() or None
        ciclo.modalidade = modalidade
        ciclo.data_avaliacao = data_avaliacao
        ciclo.total_sessoes = sessoes
        ciclo.observacoes = request.form.get("observacoes", "").strip() or None
        db.session.commit()

        flash("Ciclo atualizado.", "success")
        return redirect(url_for("listar_ciclos", paciente_id=paciente.id))

    def _feriados_no_periodo(inicio, fim):
        """Datas a pular: feriados nacionais, municipais e pontos facultativos."""
        return {
            f.data: f.nome
            for f in Holiday.query.filter(
                Holiday.data >= inicio, Holiday.data <= fim
            ).all()
        }

    def _datas_das_sessoes(inicio, dias_da_semana, quantidade, feriados):
        """Gera as datas do ciclo, pulando fim de semana e feriado.

        Devolve (datas, pulados). O limite de 400 dias evita laço infinito
        se a combinação de dias e feriados nunca fechar a conta.
        """
        datas = []
        pulados = []
        dia = inicio
        limite = inicio + timedelta(days=400)

        while len(datas) < quantidade and dia <= limite:
            if dia.weekday() in dias_da_semana:
                if dia in feriados:
                    pulados.append((dia, feriados[dia]))
                else:
                    datas.append(dia)
            dia += timedelta(days=1)

        return datas, pulados

    @app.route("/ciclos/<int:ciclo_id>/sessoes", methods=["GET", "POST"])
    @login_required
    def gerar_sessoes(ciclo_id: int):
        """Cria de uma vez as sessões restantes do ciclo, como a clínica faz
        no dia da triagem."""
        ciclo = db.session.get(TreatmentCycle, ciclo_id)
        if ciclo is None:
            abort(404)
        if not ciclo.acessivel_por(current_user):
            abort(403)

        ja_agendadas = Appointment.query.filter(
            Appointment.ciclo_id == ciclo.id,
            Appointment.tipo == "SESSAO",
            Appointment.status != "CANCELADO",
        ).count()
        restantes = max(ciclo.total_sessoes - ja_agendadas, 0)

        def form(codigo=200, valores=None):
            return (
                render_template(
                    "gerar_sessoes.html",
                    ciclo=ciclo,
                    paciente=ciclo.paciente,
                    restantes=restantes,
                    ja_agendadas=ja_agendadas,
                    horarios=HORARIOS,
                    dias=[(i, WEEKDAY_NAMES[i]) for i in DIAS_DE_ATENDIMENTO],
                    valores=valores or {},
                    hoje=hoje(),
                ),
                codigo,
            )

        if request.method == "GET":
            return form()

        valores = {
            "inicio": request.form.get("inicio", "").strip(),
            "hora": request.form.get("hora", "").strip(),
            "quantidade": request.form.get("quantidade", "").strip(),
            "dias": request.form.getlist("dias"),
        }

        if ciclo.status != "ATIVO":
            flash("Só é possível gerar sessões de um ciclo ativo.", "error")
            return form(400, valores)

        # O ciclo de grupo segue o calendário do grupo, não uma grade própria.
        if ciclo.modalidade == "GRUPO":
            flash(
                "As datas de um tratamento em grupo vêm do próprio grupo. "
                "Gere os encontros na tela do grupo.",
                "error",
            )
            return form(400, valores)

        if restantes == 0:
            flash(
                f"Este ciclo já tem as {ciclo.total_sessoes} sessões agendadas.",
                "error",
            )
            return form(400, valores)

        try:
            inicio = date.fromisoformat(valores["inicio"])
        except ValueError:
            flash("Informe a data de início.", "error")
            return form(400, valores)

        if inicio < hoje():
            flash("A data de início não pode estar no passado.", "error")
            return form(400, valores)

        if valores["hora"] not in HORARIOS:
            flash("Escolha um horário do expediente.", "error")
            return form(400, valores)
        hora = time.fromisoformat(valores["hora"])

        try:
            dias_da_semana = {int(d) for d in valores["dias"]}
        except ValueError:
            dias_da_semana = set()
        if not dias_da_semana or not dias_da_semana <= set(DIAS_DE_ATENDIMENTO):
            flash("Escolha ao menos um dia da semana, de segunda a sexta.", "error")
            return form(400, valores)

        try:
            quantidade = int(valores["quantidade"] or restantes)
        except ValueError:
            flash("Quantidade de sessões inválida.", "error")
            return form(400, valores)
        if not 1 <= quantidade <= restantes:
            flash(f"A quantidade deve estar entre 1 e {restantes}.", "error")
            return form(400, valores)

        datas, pulados = _datas_das_sessoes(
            inicio,
            dias_da_semana,
            quantidade,
            _feriados_no_periodo(inicio, inicio + timedelta(days=400)),
        )

        if len(datas) < quantidade:
            flash(
                "Não foi possível gerar todas as datas. Reveja os dias da semana.",
                "error",
            )
            return form(400, valores)

        ocupados = [
            data
            for data in datas
            if not _horario_disponivel(ciclo.fisioterapeuta_id, data, hora)
        ]
        if ocupados:
            primeiro = ocupados[0].strftime("%d/%m/%Y")
            flash(
                f"O horário {valores['hora']} já está cheio em {primeiro}. "
                "Escolha outro horário ou outros dias.",
                "error",
            )
            return form(400, valores)

        for data in datas:
            db.session.add(
                Appointment(
                    tipo="SESSAO",
                    paciente_id=ciclo.paciente_id,
                    ciclo_id=ciclo.id,
                    fisioterapeuta_id=ciclo.fisioterapeuta_id,
                    data=data,
                    hora=hora,
                    duracao_min=30,
                    status="AGENDADO",
                )
            )
        db.session.commit()

        if pulados:
            nomes = ", ".join(f"{d.strftime('%d/%m')} ({nome})" for d, nome in pulados)
            flash(f"Datas puladas por feriado: {nomes}.", "info")
        flash(f"{len(datas)} sessão(ões) agendada(s).", "success")
        return redirect(url_for("cartao_do_ciclo", ciclo_id=ciclo.id))

    @app.route("/ciclos/<int:ciclo_id>/remarcar", methods=["GET", "POST"])
    @login_required
    def remarcar_ciclo(ciclo_id: int):
        """Muda o dia da semana e o horário do restante do ciclo.

        O paciente arrumou outro compromisso e não pode mais na terça: em vez
        de mexer sessão por sessão, o setor remarca de uma vez o que ainda não
        aconteceu. Sessão já realizada, falta e cancelamento ficam como estão.
        """
        ciclo = db.session.get(TreatmentCycle, ciclo_id)
        if ciclo is None:
            abort(404)
        if not ciclo.acessivel_por(current_user):
            abort(403)

        pendentes = (
            Appointment.query.filter(
                Appointment.ciclo_id == ciclo.id,
                Appointment.tipo == "SESSAO",
                Appointment.status.in_(("AGENDADO", "CONFIRMADO")),
                Appointment.data >= hoje(),
            )
            .order_by(Appointment.data, Appointment.hora)
            .all()
        )

        def form(codigo=200, valores=None):
            return (
                render_template(
                    "remarcar_ciclo.html",
                    ciclo=ciclo,
                    paciente=ciclo.paciente,
                    pendentes=pendentes,
                    horarios=HORARIOS,
                    dias=[(i, WEEKDAY_NAMES[i]) for i in DIAS_DE_ATENDIMENTO],
                    valores=valores or {},
                    hoje=hoje(),
                ),
                codigo,
            )

        if request.method == "GET":
            return form()

        valores = {
            "inicio": request.form.get("inicio", "").strip(),
            "hora": request.form.get("hora", "").strip(),
            "dias": request.form.getlist("dias"),
        }

        if ciclo.status != "ATIVO":
            flash("Só é possível remarcar as sessões de um ciclo ativo.", "error")
            return form(400, valores)

        # Remarcar aqui separaria o paciente do resto do grupo.
        if ciclo.modalidade == "GRUPO":
            flash(
                "Para mudar as datas de um tratamento em grupo, altere o grupo.",
                "error",
            )
            return form(400, valores)

        if not pendentes:
            flash("Este ciclo não tem sessões futuras para remarcar.", "error")
            return form(400, valores)

        try:
            inicio = date.fromisoformat(valores["inicio"])
        except ValueError:
            flash("Informe a partir de que data remarcar.", "error")
            return form(400, valores)

        if inicio < hoje():
            flash("A data de início não pode estar no passado.", "error")
            return form(400, valores)

        if valores["hora"] not in HORARIOS:
            flash("Escolha um horário do expediente.", "error")
            return form(400, valores)
        hora = time.fromisoformat(valores["hora"])

        try:
            dias_da_semana = {int(d) for d in valores["dias"]}
        except ValueError:
            dias_da_semana = set()
        if not dias_da_semana or not dias_da_semana <= set(DIAS_DE_ATENDIMENTO):
            flash("Escolha ao menos um dia da semana, de segunda a sexta.", "error")
            return form(400, valores)

        datas, pulados = _datas_das_sessoes(
            inicio,
            dias_da_semana,
            len(pendentes),
            _feriados_no_periodo(inicio, inicio + timedelta(days=400)),
        )

        if len(datas) < len(pendentes):
            flash(
                "Não foi possível gerar todas as datas. Reveja os dias da semana.",
                "error",
            )
            return form(400, valores)

        # As sessões que estão sendo movidas não ocupam o horário de destino.
        movidas = {sessao.id for sessao in pendentes}
        ocupados = [
            data
            for data in datas
            if not _horario_disponivel(
                ciclo.fisioterapeuta_id, data, hora, ignorar_ids=movidas
            )
        ]
        if ocupados:
            primeiro = ocupados[0].strftime("%d/%m/%Y")
            flash(
                f"O horário {valores['hora']} já está cheio em {primeiro}. "
                "Escolha outro horário ou outros dias.",
                "error",
            )
            return form(400, valores)

        for sessao, data in zip(pendentes, datas):
            sessao.data = data
            sessao.hora = hora
        db.session.commit()

        if pulados:
            nomes = ", ".join(f"{d.strftime('%d/%m')} ({nome})" for d, nome in pulados)
            flash(f"Datas puladas por feriado: {nomes}.", "info")
        flash(
            f"{len(pendentes)} sessão(ões) remarcada(s) a partir de "
            f"{datas[0].strftime('%d/%m/%Y')}.",
            "success",
        )
        return redirect(url_for("cartao_do_ciclo", ciclo_id=ciclo.id))

    @app.get("/ciclos/<int:ciclo_id>/cartao")
    @login_required
    def cartao_do_ciclo(ciclo_id: int):
        """Cartão com as datas, para imprimir e entregar ao paciente."""
        ciclo = db.session.get(TreatmentCycle, ciclo_id)
        if ciclo is None:
            abort(404)
        if not ciclo.acessivel_por(current_user):
            abort(403)

        sessoes = (
            Appointment.query.filter(
                Appointment.ciclo_id == ciclo.id,
                Appointment.status != "CANCELADO",
            )
            .order_by(Appointment.data, Appointment.hora)
            .all()
        )

        registro = db.session.scalar(db.select(Card).where(Card.ciclo_id == ciclo.id))
        if registro is None:
            registro = Card(ciclo_id=ciclo.id, gerado_por=current_user.id)
            db.session.add(registro)
            db.session.commit()

        return render_template(
            "cartao_impressao.html",
            ciclo=ciclo,
            paciente=ciclo.paciente,
            sessoes=sessoes,
            cartao=registro,
            emitido_em=hoje(),
            nomes_dos_dias=WEEKDAY_NAMES,
        )

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
        ciclo.data_alta = hoje()
        db.session.commit()
        flash("Ciclo encerrado.", "success")
        return redirect(url_for("listar_ciclos", paciente_id=ciclo.paciente_id))

    @app.post("/ciclos/<int:ciclo_id>/responsavel")
    @role_required(ADMIN_PROFILE)
    def trocar_responsavel_ciclo(ciclo_id: int):
        """Apenas o admin redireciona um tratamento para outro profissional."""
        ciclo = db.session.get(TreatmentCycle, ciclo_id)
        if ciclo is None:
            abort(404)

        escolhido = request.form.get("fisioterapeuta_id", "").strip()
        responsavel = db.session.get(User, int(escolhido)) if escolhido else None

        if responsavel is None or not responsavel.ativo:
            flash("Selecione um fisioterapeuta responsável válido.", "error")
            return redirect(url_for("listar_ciclos", paciente_id=ciclo.paciente_id))

        ciclo.fisioterapeuta_id = responsavel.id
        db.session.commit()
        flash(f"{responsavel.nome} agora conduz este tratamento.", "success")
        return redirect(url_for("listar_ciclos", paciente_id=ciclo.paciente_id))

    # ------------------------------------------------------------------
    # Agenda
    # ------------------------------------------------------------------

    def _horario_disponivel(
        fisioterapeuta_id, data_agenda, hora, ignorar_id=None, ignorar_ids=()
    ):
        """Verifica o limite de 2 pacientes por profissional no mesmo horário.

        `ignorar_ids` serve para remarcar em lote: as sessões que estão sendo
        movidas não podem contar como ocupando o horário para onde vão.
        """
        consulta = Appointment.query.filter(
            Appointment.fisioterapeuta_id == fisioterapeuta_id,
            Appointment.data == data_agenda,
            Appointment.hora == hora,
            Appointment.status != "CANCELADO",
            Appointment.tipo != "GRUPO",
            # A presença de cada inscrito no grupo não ocupa uma vaga da
            # agenda individual: quem segura o horário é o encontro do grupo.
            Appointment.grupo_id.is_(None),
        )
        if ignorar_id is not None:
            consulta = consulta.filter(Appointment.id != ignorar_id)
        if ignorar_ids:
            consulta = consulta.filter(Appointment.id.notin_(tuple(ignorar_ids)))
        return consulta.count() < LIMITE_POR_HORARIO

    def _sem_presenca_de_grupo(consulta):
        """Tira da agenda a presença individual de quem está em grupo.

        O encontro do grupo já ocupa a grade uma vez, com o nome do grupo.
        Listar ali os 14 inscritos entupiria a tela e não é assim que a
        clínica lê a agenda — a chamada é feita na lista de presença.
        """
        return consulta.filter(
            db.or_(
                Appointment.grupo_id.is_(None),
                Appointment.paciente_id.is_(None),
            )
        )

    def _somente_ciclos_ativos(consulta):
        """Tira da agenda as sessões de ciclos já encerrados.

        O histórico continua inteiro no prontuário do paciente; o que a
        clínica pediu é que a agenda do dia mostre só quem ainda está em
        tratamento. Avaliação e grupo não têm ciclo e seguem aparecendo.
        """
        encerrados = db.select(TreatmentCycle.id).where(
            TreatmentCycle.status != "ATIVO"
        )
        return consulta.filter(
            db.or_(
                Appointment.ciclo_id.is_(None),
                Appointment.ciclo_id.notin_(encerrados),
            )
        )

    @app.get("/agenda")
    @login_required
    def agenda():
        dia = request.args.get("data", "").strip()
        try:
            data_agenda = date.fromisoformat(dia) if dia else hoje()
        except ValueError:
            data_agenda = hoje()

        consulta = _sem_presenca_de_grupo(
            _somente_ciclos_ativos(
                Appointment.query.filter(Appointment.data == data_agenda)
            )
        )
        if current_user.perfil != ADMIN_PROFILE:
            consulta = consulta.filter(Appointment.fisioterapeuta_id == current_user.id)

        agendamentos = consulta.order_by(Appointment.hora).all()
        return render_template(
            "agenda.html",
            agendamentos=agendamentos,
            data_agenda=data_agenda,
            dia_anterior=data_agenda - timedelta(days=1),
            dia_seguinte=data_agenda + timedelta(days=1),
        )

    def _segunda_da_semana(data_base):
        return data_base - timedelta(days=data_base.weekday())

    def _grade_de(agendamentos, chave):
        """Monta {horario: {chave: [agendamentos]}} e a lista de horários.

        Além da grade fixa do expediente, entram linhas para horários fora
        dela — agendamentos antigos, de antes da grade atual. Descartar esses
        horários fazia o atendimento sumir da tela sem aviso nenhum.
        """
        grade = {rotulo: {} for rotulo in HORARIOS}
        for item in agendamentos:
            rotulo = item.hora.strftime("%H:%M")
            grade.setdefault(rotulo, {}).setdefault(chave(item), []).append(item)
        return grade, sorted(grade)

    def _primeiro_com_agenda(profissionais, inicio, fim):
        """Primeiro profissional da lista com atendimento no período.

        A grade é de um profissional por vez. Abrir sempre no primeiro em
        ordem alfabética mostrava uma semana vazia e dava a impressão de que
        os agendamentos tinham sumido.
        """
        if not profissionais:
            return None
        ocupados = set(
            db.session.scalars(
                db.select(Appointment.fisioterapeuta_id)
                .where(
                    Appointment.data >= inicio,
                    Appointment.data <= fim,
                    Appointment.status != "CANCELADO",
                )
                .distinct()
            )
        )
        return next((p for p in profissionais if p.id in ocupados), None)

    @app.get("/agenda/semana")
    @login_required
    def agenda_semanal():
        """Grade semanal de um profissional, no formato da planilha da clínica."""
        try:
            base = date.fromisoformat(request.args.get("data", "").strip())
        except ValueError:
            base = hoje()
        segunda = _segunda_da_semana(base)
        dias = [segunda + timedelta(days=n) for n in DIAS_DE_ATENDIMENTO]

        profissionais = _fisioterapeutas_ativos()
        escolhido = current_user
        if current_user.perfil == ADMIN_PROFILE:
            pedido = request.args.get("fisioterapeuta_id", "").strip()
            escolhido = db.session.get(User, int(pedido)) if pedido.isdigit() else None
            if escolhido is None:
                escolhido = _primeiro_com_agenda(profissionais, dias[0], dias[-1]) or (
                    profissionais[0] if profissionais else current_user
                )

        agendamentos = (
            _sem_presenca_de_grupo(
                _somente_ciclos_ativos(
                    Appointment.query.filter(
                        Appointment.fisioterapeuta_id == escolhido.id,
                        Appointment.data >= dias[0],
                        Appointment.data <= dias[-1],
                        Appointment.status != "CANCELADO",
                    )
                )
            )
            .order_by(Appointment.data, Appointment.hora)
            .all()
        )
        grade, horarios = _grade_de(agendamentos, lambda i: i.data.isoformat())

        return render_template(
            "agenda_semanal.html",
            grade=grade,
            horarios=horarios,
            # Os horários reservados para triagem aparecem marcados na grade,
            # como as células "T =" coloridas da planilha da clínica.
            triagens=_marcas_de_triagem(escolhido.id),
            dias=dias,
            nomes_dos_dias=[WEEKDAY_NAMES[d.weekday()] for d in dias],
            profissional=escolhido,
            profissionais=profissionais,
            semana_anterior=segunda - timedelta(days=7),
            semana_seguinte=segunda + timedelta(days=7),
            total=len(agendamentos),
        )

    @app.get("/agenda/dia")
    @login_required
    def agenda_diaria():
        """Grade do dia com todos os profissionais lado a lado."""
        try:
            data_agenda = date.fromisoformat(request.args.get("data", "").strip())
        except ValueError:
            data_agenda = hoje()

        profissionais = _fisioterapeutas_ativos()
        if current_user.perfil != ADMIN_PROFILE:
            profissionais = [p for p in profissionais if p.id == current_user.id]

        consulta = _sem_presenca_de_grupo(
            _somente_ciclos_ativos(
                Appointment.query.filter(
                    Appointment.data == data_agenda,
                    Appointment.status != "CANCELADO",
                )
            )
        )
        if current_user.perfil != ADMIN_PROFILE:
            consulta = consulta.filter(Appointment.fisioterapeuta_id == current_user.id)

        agendamentos = consulta.order_by(Appointment.hora).all()
        grade, horarios = _grade_de(agendamentos, lambda i: i.fisioterapeuta_id)

        return render_template(
            "agenda_diaria.html",
            grade=grade,
            horarios=horarios,
            profissionais=profissionais,
            data_agenda=data_agenda,
            nome_do_dia=WEEKDAY_NAMES[data_agenda.weekday()],
            dia_anterior=data_agenda - timedelta(days=1),
            dia_seguinte=data_agenda + timedelta(days=1),
            total=len(agendamentos),
        )

    # ------------------------------------------------------------------
    # Triagem
    # ------------------------------------------------------------------

    def _horarios_de_triagem(fisioterapeuta_id=None):
        """Os horários fixos de triagem, na ordem em que aparecem na agenda."""
        consulta = ScreeningSlot.query.filter(ScreeningSlot.ativo.is_(True))
        if fisioterapeuta_id is not None:
            consulta = consulta.filter(
                ScreeningSlot.fisioterapeuta_id == fisioterapeuta_id
            )
        return consulta.order_by(
            ScreeningSlot.dia_semana, ScreeningSlot.hora, ScreeningSlot.id
        ).all()

    def _marcas_de_triagem(fisioterapeuta_id):
        """{(dia da semana, 'HH:MM')} para a grade destacar as células."""
        return {
            (slot.dia_semana, slot.hora.strftime("%H:%M"))
            for slot in _horarios_de_triagem(fisioterapeuta_id)
        }

    @app.get("/triagem")
    @login_required
    def agenda_de_triagem():
        """Agenda separada da triagem, que vem antes do ciclo de tratamento.

        A avaliação é o primeiro contato: acontece antes de existir ciclo, e
        nem sempre vira tratamento — o paciente pode sair orientado e com
        alta na própria avaliação.
        """
        try:
            base = date.fromisoformat(request.args.get("data", "").strip())
        except ValueError:
            base = hoje()
        segunda = _segunda_da_semana(base)
        dias = [segunda + timedelta(days=n) for n in DIAS_DE_ATENDIMENTO]

        profissionais = _fisioterapeutas_ativos()
        if current_user.perfil != ADMIN_PROFILE:
            profissionais = [p for p in profissionais if p.id == current_user.id]

        ids = [p.id for p in profissionais] or [0]
        slots = [
            s
            for s in _horarios_de_triagem()
            if s.fisioterapeuta_id in ids and s.dia_semana in DIAS_DE_ATENDIMENTO
        ]

        # O que já está marcado como avaliação nesta semana.
        marcadas = Appointment.query.filter(
            Appointment.tipo == "AVALIACAO",
            Appointment.data >= dias[0],
            Appointment.data <= dias[-1],
            Appointment.status != "CANCELADO",
            Appointment.fisioterapeuta_id.in_(ids),
        ).all()
        ocupados = {(a.fisioterapeuta_id, a.data, a.hora): a for a in marcadas}

        # Uma linha por horário fixo em cada dia útil da semana escolhida.
        linhas = []
        for slot in slots:
            dia = segunda + timedelta(days=slot.dia_semana)
            linhas.append(
                {
                    "slot": slot,
                    "data": dia,
                    "agendamento": ocupados.get(
                        (slot.fisioterapeuta_id, dia, slot.hora)
                    ),
                }
            )
        linhas.sort(
            key=lambda l: (l["data"], l["slot"].hora, l["slot"].fisioterapeuta.nome)
        )

        # Avaliações de urgência caem fora dos horários fixos.
        chaves_fixas = {
            (l["slot"].fisioterapeuta_id, l["data"], l["slot"].hora) for l in linhas
        }
        urgencias = [a for chave, a in ocupados.items() if chave not in chaves_fixas]
        urgencias.sort(key=lambda a: (a.data, a.hora))

        return render_template(
            "triagem_agenda.html",
            linhas=linhas,
            urgencias=urgencias,
            dias=dias,
            profissionais=profissionais,
            semana_anterior=segunda - timedelta(days=7),
            semana_seguinte=segunda + timedelta(days=7),
            hoje=hoje(),
        )

    @app.route("/triagem/horarios", methods=["GET", "POST"])
    @login_required
    def horarios_de_triagem():
        """Onde cada profissional define seus horários fixos de triagem."""
        profissionais = _fisioterapeutas_ativos()
        if current_user.perfil != ADMIN_PROFILE:
            profissionais = [p for p in profissionais if p.id == current_user.id]

        def form(codigo=200):
            ids = [p.id for p in profissionais] or [0]
            return (
                render_template(
                    "triagem_horarios.html",
                    profissionais=profissionais,
                    horarios=[
                        s for s in _horarios_de_triagem() if s.fisioterapeuta_id in ids
                    ],
                    grade=HORARIOS,
                    dias=[(i, WEEKDAY_NAMES[i]) for i in DIAS_DE_ATENDIMENTO],
                ),
                codigo,
            )

        if request.method == "GET":
            return form()

        escolhido = request.form.get("fisioterapeuta_id", "").strip()
        alvo = current_user
        if current_user.perfil == ADMIN_PROFILE:
            alvo = db.session.get(User, int(escolhido)) if escolhido.isdigit() else None
            if alvo is None or not alvo.ativo:
                flash("Selecione um fisioterapeuta ativo.", "error")
                return form(400)
        elif escolhido and escolhido != str(current_user.id):
            abort(403)

        try:
            dia = int(request.form.get("dia_semana", ""))
        except ValueError:
            dia = -1
        if dia not in DIAS_DE_ATENDIMENTO:
            flash("Escolha um dia de segunda a sexta-feira.", "error")
            return form(400)

        rotulo = request.form.get("hora", "").strip()
        if rotulo not in HORARIOS:
            flash("Escolha um horário do expediente.", "error")
            return form(400)
        hora = time.fromisoformat(rotulo)

        existente = db.session.scalar(
            db.select(ScreeningSlot).where(
                ScreeningSlot.fisioterapeuta_id == alvo.id,
                ScreeningSlot.dia_semana == dia,
                ScreeningSlot.hora == hora,
            )
        )
        if existente is not None:
            if existente.ativo:
                flash("Este horário de triagem já existe.", "error")
                return form(400)
            existente.ativo = True
        else:
            db.session.add(
                ScreeningSlot(
                    fisioterapeuta_id=alvo.id,
                    dia_semana=dia,
                    hora=hora,
                    ativo=True,
                )
            )
        db.session.commit()

        flash(
            f"Triagem de {alvo.nome} às {rotulo}, {WEEKDAY_NAMES[dia].lower()}.",
            "success",
        )
        return redirect(url_for("horarios_de_triagem"))

    @app.post("/triagem/horarios/<int:slot_id>/remover")
    @login_required
    def remover_horario_de_triagem(slot_id: int):
        """Desativa em vez de apagar: o histórico de quem passou ali continua."""
        slot = db.session.get(ScreeningSlot, slot_id)
        if slot is None:
            abort(404)
        if (
            current_user.perfil != ADMIN_PROFILE
            and slot.fisioterapeuta_id != current_user.id
        ):
            abort(403)

        slot.ativo = False
        db.session.commit()
        flash("Horário de triagem removido.", "success")
        return redirect(url_for("horarios_de_triagem"))

    @app.route("/triagem/agendar", methods=["GET", "POST"])
    @login_required
    def agendar_triagem():
        """Marca a avaliação do paciente, nos horários fixos ou como urgência.

        Urgência é o que a clínica encaixa fora da grade de triagem: fratura,
        AVC, pré e pós-operatório. Por isso exige motivo escrito.
        """
        if current_user.perfil == ADMIN_PROFILE:
            pacientes = Patient.query.filter_by(ativo=True).order_by(Patient.nome).all()
            profissionais = _fisioterapeutas_ativos()
        else:
            pacientes = (
                Patient.query.filter_by(ativo=True, fisioterapeuta_id=current_user.id)
                .order_by(Patient.nome)
                .all()
            )
            profissionais = [current_user]

        def form(codigo=200, valores=None):
            return (
                render_template(
                    "triagem_form.html",
                    pacientes=pacientes,
                    profissionais=profissionais,
                    horarios=HORARIOS,
                    valores=valores or {},
                    hoje=hoje(),
                ),
                codigo,
            )

        if request.method == "GET":
            valores = {
                chave: request.args.get(chave, "").strip()
                for chave in ("data", "hora", "fisioterapeuta_id")
            }
            return form(valores=valores)

        valores = {
            chave: request.form.get(chave, "").strip()
            for chave in ("data", "hora", "fisioterapeuta_id", "urgencia", "motivo")
        }

        paciente = db.session.get(Patient, int(request.form.get("paciente_id") or 0))
        if paciente is None or not paciente.ativo:
            flash("Selecione um paciente ativo.", "error")
            return form(400, valores)
        if not paciente.acessivel_por(current_user):
            abort(403)

        responsavel = current_user
        if current_user.perfil == ADMIN_PROFILE:
            escolhido = valores["fisioterapeuta_id"]
            responsavel = (
                db.session.get(User, int(escolhido)) if escolhido.isdigit() else None
            )
            if responsavel is None or not responsavel.ativo:
                flash("Selecione o fisioterapeuta que fará a avaliação.", "error")
                return form(400, valores)

        try:
            data_agenda = date.fromisoformat(valores["data"])
        except ValueError:
            flash("Informe a data da avaliação.", "error")
            return form(400, valores)

        if data_agenda < hoje():
            flash("Não é possível agendar em data que já passou.", "error")
            return form(400, valores)

        if data_agenda.weekday() not in DIAS_DE_ATENDIMENTO:
            flash("A clínica atende de segunda a sexta-feira.", "error")
            return form(400, valores)

        if valores["hora"] not in HORARIOS:
            flash("Escolha um horário do expediente.", "error")
            return form(400, valores)
        hora = time.fromisoformat(valores["hora"])

        urgencia = valores["urgencia"] == "1"
        motivo = valores["motivo"]

        if urgencia:
            if not motivo:
                flash(
                    "Descreva a urgência: fratura, AVC, pré ou pós-operatório.",
                    "error",
                )
                return form(400, valores)
        else:
            # Fora da urgência, a avaliação vai nos horários fixos de triagem.
            reservados = _marcas_de_triagem(responsavel.id)
            if (data_agenda.weekday(), valores["hora"]) not in reservados:
                flash(
                    f"{responsavel.nome} não tem triagem neste dia e horário. "
                    "Escolha um horário da agenda de triagem, ou marque como "
                    "urgência.",
                    "error",
                )
                return form(400, valores)

        if not _horario_disponivel(responsavel.id, data_agenda, hora):
            flash(
                "Este horário já tem 2 pacientes para o profissional. "
                "Escolha outro horário.",
                "error",
            )
            return form(400, valores)

        observacoes = f"Urgência: {motivo}" if urgencia else None
        db.session.add(
            Appointment(
                tipo="AVALIACAO",
                paciente_id=paciente.id,
                fisioterapeuta_id=responsavel.id,
                data=data_agenda,
                hora=hora,
                duracao_min=30,
                status="AGENDADO",
                observacoes=observacoes,
            )
        )
        db.session.commit()

        flash(
            f"Avaliação de {paciente.nome} marcada para "
            f"{data_agenda.strftime('%d/%m/%Y')} às {valores['hora']}.",
            "success",
        )
        return redirect(url_for("agenda_de_triagem", data=data_agenda.isoformat()))

    @app.route("/agenda/novo", methods=["GET", "POST"])
    @login_required
    def novo_agendamento():
        if current_user.perfil == ADMIN_PROFILE:
            pacientes = Patient.query.filter_by(ativo=True).order_by(Patient.nome).all()
        else:
            pacientes = (
                Patient.query.filter_by(ativo=True, fisioterapeuta_id=current_user.id)
                .order_by(Patient.nome)
                .all()
            )

        # Ciclo de grupo não entra aqui: as datas dele vêm do grupo.
        ciclos = (
            TreatmentCycle.query.filter(
                TreatmentCycle.status == "ATIVO",
                TreatmentCycle.modalidade != "GRUPO",
                TreatmentCycle.paciente_id.in_([p.id for p in pacientes] or [0]),
            )
            .order_by(TreatmentCycle.data_avaliacao.desc())
            .all()
        )

        def form(codigo=200):
            return (
                render_template(
                    "agenda_form.html",
                    pacientes=pacientes,
                    horarios=HORARIOS,
                    ciclos=ciclos,
                    hoje=hoje(),
                ),
                codigo,
            )

        if request.method == "POST":
            tipo = request.form.get("tipo", "").strip().upper()
            if tipo not in ("AVALIACAO", "SESSAO"):
                flash("Tipo de agendamento inválido.", "error")
                return form(400)

            paciente = db.session.get(
                Patient, int(request.form.get("paciente_id") or 0)
            )
            if paciente is None:
                flash("Selecione um paciente.", "error")
                return form(400)
            if not paciente.acessivel_por(current_user):
                abort(403)

            try:
                data_agenda = date.fromisoformat(request.form.get("data", "").strip())
                hora = time.fromisoformat(request.form.get("hora", "").strip())
            except ValueError:
                flash("Informe data e horário válidos.", "error")
                return form(400)

            if data_agenda.weekday() not in DIAS_DE_ATENDIMENTO:
                flash("A clínica atende de segunda a sexta-feira.", "error")
                return form(400)

            if data_agenda < hoje():
                flash("Não é possível agendar em data que já passou.", "error")
                return form(400)

            if hora.strftime("%H:%M") not in HORARIOS:
                flash(
                    f"Horário fora do expediente. Escolha entre {HORARIOS[0]} "
                    f"e {HORARIOS[-1]}, de 30 em 30 minutos.",
                    "error",
                )
                return form(400)

            fisioterapeuta_id = paciente.fisioterapeuta_id or current_user.id

            if not _horario_disponivel(fisioterapeuta_id, data_agenda, hora):
                flash(
                    "Este horário já tem 2 pacientes para o profissional. "
                    "Escolha outro horário.",
                    "error",
                )
                return form(400)

            ciclo = None
            ciclo_id = request.form.get("ciclo_id", "").strip()
            if ciclo_id:
                ciclo = db.session.get(TreatmentCycle, int(ciclo_id))
                if ciclo is None or ciclo.paciente_id != paciente.id:
                    flash("Ciclo inválido para este paciente.", "error")
                    return form(400)

            if tipo == "SESSAO" and ciclo is None:
                flash("Selecione o ciclo de tratamento da sessão.", "error")
                return form(400)

            numero_sessao = None
            if tipo == "SESSAO":
                realizadas = Appointment.query.filter(
                    Appointment.ciclo_id == ciclo.id,
                    Appointment.tipo == "SESSAO",
                    Appointment.status == "REALIZADO",
                ).count()
                if realizadas >= ciclo.total_sessoes:
                    flash(
                        f"Este ciclo já tem {ciclo.total_sessoes} sessões realizadas.",
                        "error",
                    )
                    return form(400)
                numero_sessao = realizadas + 1

            agendamento = Appointment(
                tipo=tipo,
                paciente_id=paciente.id,
                ciclo_id=ciclo.id if ciclo else None,
                fisioterapeuta_id=fisioterapeuta_id,
                data=data_agenda,
                hora=hora,
                duracao_min=30,
                numero_sessao=numero_sessao,
                status="AGENDADO",
                observacoes=request.form.get("observacoes", "").strip() or None,
            )
            db.session.add(agendamento)
            db.session.commit()
            flash("Agendamento criado.", "success")
            return redirect(url_for("agenda", data=data_agenda.isoformat()))

        return form()

    def _data_de_reposicao(agendamento):
        """Onde encaixar a reposição: na sequência, depois da última sessão já
        marcada do ciclo, no mesmo dia da semana e horário da sessão perdida.

        Pula feriado e horário cheio. Devolve None se não achar vaga em
        quatro meses, o que na prática significa rever o ciclo à mão.
        """
        ultima = db.session.scalar(
            db.select(db.func.max(Appointment.data)).where(
                Appointment.ciclo_id == agendamento.ciclo_id,
                Appointment.status != "CANCELADO",
            )
        )
        inicio = max(ultima or agendamento.data, agendamento.data)
        limite = inicio + timedelta(days=120)
        feriados = _feriados_no_periodo(inicio, limite)

        dia = inicio + timedelta(days=1)
        while dia <= limite:
            if (
                dia.weekday() == agendamento.data.weekday()
                and dia.weekday() in DIAS_DE_ATENDIMENTO
                and dia not in feriados
                and _horario_disponivel(
                    agendamento.fisioterapeuta_id, dia, agendamento.hora
                )
            ):
                return dia
            dia += timedelta(days=1)
        return None

    def _criar_reposicao(agendamento):
        """Cancelamento pelo setor e falta justificada não consomem sessão.

        O sistema encaixa a reposição ao fim do ciclo. Em grupo não há
        reposição: a regra da clínica é de tratamento fechado em 6 encontros.
        """
        if agendamento.tipo != "SESSAO" or agendamento.ciclo_id is None:
            return None
        if agendamento.paciente_id is None or agendamento.grupo_id is not None:
            return None

        ciclo = agendamento.ciclo
        if ciclo is None or ciclo.status != "ATIVO" or ciclo.modalidade == "GRUPO":
            return None

        marca = MARCA_REPOSICAO.format(id=agendamento.id)
        if db.session.scalar(
            db.select(Appointment.id).where(
                Appointment.ciclo_id == ciclo.id,
                Appointment.observacoes.like(f"%{marca}%"),
            )
        ):
            return None

        data = _data_de_reposicao(agendamento)
        if data is None:
            return None

        reposicao = Appointment(
            tipo="SESSAO",
            paciente_id=agendamento.paciente_id,
            ciclo_id=ciclo.id,
            fisioterapeuta_id=agendamento.fisioterapeuta_id,
            data=data,
            hora=agendamento.hora,
            duracao_min=agendamento.duracao_min,
            status="AGENDADO",
            observacoes=(
                "Reposição da sessão de "
                f"{agendamento.data.strftime('%d/%m/%Y')}. {marca}"
            ),
        )
        db.session.add(reposicao)
        return reposicao

    @app.post("/agendamentos/<int:agendamento_id>/status")
    @login_required
    def alterar_status_agendamento(agendamento_id: int):
        agendamento = db.session.get(Appointment, agendamento_id)
        if agendamento is None:
            abort(404)
        if not agendamento.acessivel_por(current_user):
            abort(403)

        novo_status = request.form.get("status", "").strip().upper()
        if novo_status not in STATUS_AGENDAMENTO:
            flash("Status inválido.", "error")
            return redirect(url_for("agenda", data=agendamento.data.isoformat()))

        # Ausências são avisadas antes; só o comparecimento espera o dia.
        if novo_status in STATUS_SO_A_PARTIR_DO_DIA and agendamento.data > hoje():
            flash(
                "O comparecimento só pode ser registrado a partir do dia da sessão.",
                "error",
            )
            return redirect(url_for("agenda", data=agendamento.data.isoformat()))

        if novo_status == "FALTA_JUSTIFICADA":
            motivo = request.form.get("justificativa", "").strip()
            if not motivo:
                flash("Informe o motivo da falta justificada.", "error")
                return redirect(url_for("agenda", data=agendamento.data.isoformat()))
            agendamento.observacoes = motivo

        status_anterior = agendamento.status
        agendamento.status = novo_status

        reposicao = None
        if novo_status in STATUS_QUE_REPOEM and status_anterior != novo_status:
            reposicao = _criar_reposicao(agendamento)

        db.session.commit()

        if reposicao is not None:
            flash(
                "Reposição agendada para "
                f"{reposicao.data.strftime('%d/%m/%Y')} às "
                f"{reposicao.hora.strftime('%H:%M')}.",
                "info",
            )
        flash("Status atualizado.", "success")
        return redirect(url_for("agenda", data=agendamento.data.isoformat()))

    # ------------------------------------------------------------------
    # Relatórios
    # ------------------------------------------------------------------

    def _resumo_numerico(itens):
        """Os mesmos números que a clínica soma hoje na mão, na planilha.

        Separa sessão de triagem porque são coisas diferentes no setor: a
        sessão é o tratamento, a triagem é o primeiro contato. Comparecimento
        e falta justificada contam como atendimento; só a falta não avisada
        entra como falta.

        O encontro do grupo em si não é contado: ele é o bloco que segura o
        horário na agenda. Quem conta é a presença de cada inscrito, que
        entra como sessão igual à do atendimento individual.
        """
        itens = [i for i in itens if i.tipo != "GRUPO"]

        def contar(tipos, status):
            return sum(1 for i in itens if i.tipo in tipos and i.status in status)

        sessoes = ("SESSAO",)
        triagens = ("AVALIACAO",)

        sessoes_feitas = contar(sessoes, STATUS_DE_ATENDIMENTO)
        triagens_feitas = contar(triagens, STATUS_DE_ATENDIMENTO)
        faltas_sessoes = contar(sessoes, STATUS_DE_FALTA)
        faltas_triagens = contar(triagens, STATUS_DE_FALTA)

        return {
            "sessoes": sessoes_feitas,
            "triagens": triagens_feitas,
            "faltas_sessoes": faltas_sessoes,
            "faltas_triagens": faltas_triagens,
            "atendimentos": sessoes_feitas + triagens_feitas,
            "faltas": faltas_sessoes + faltas_triagens,
        }

    def _intervalo_do_relatorio(periodo, mes, ano, referencia):
        """Traduz o filtro escolhido em (início, fim, rótulo para a tela).

        O fim é sempre exclusivo: o primeiro dia depois do período.
        """
        if periodo == "semana":
            segunda = referencia - timedelta(days=referencia.weekday())
            return (
                segunda,
                segunda + timedelta(days=7),
                f"Semana de {segunda.strftime('%d/%m')} a "
                f"{(segunda + timedelta(days=6)).strftime('%d/%m/%Y')}",
            )
        if periodo == "ano":
            return date(ano, 1, 1), date(ano + 1, 1, 1), f"Ano de {ano}"

        inicio = date(ano, mes, 1)
        fim = date(ano + 1, 1, 1) if mes == 12 else date(ano, mes + 1, 1)
        return inicio, fim, f"{MESES[mes - 1]} de {ano}"

    @app.get("/relatorios")
    @login_required
    def relatorios():
        dia_atual = hoje()
        periodo = request.args.get("periodo", "mes").strip().lower()
        if periodo not in ("semana", "mes", "ano"):
            periodo = "mes"

        try:
            mes = int(request.args.get("mes", dia_atual.month))
            ano = int(request.args.get("ano", dia_atual.year))
        except ValueError:
            mes, ano = dia_atual.month, dia_atual.year

        if not 1 <= mes <= 12:
            mes = dia_atual.month

        try:
            referencia = date.fromisoformat(request.args.get("data", "").strip())
        except ValueError:
            referencia = dia_atual

        if periodo == "semana":
            # A semana escolhida manda no ano do total anual, senão o rodapé
            # some do período que está na tela.
            ano = referencia.year

        inicio, fim, rotulo_do_periodo = _intervalo_do_relatorio(
            periodo, mes, ano, referencia
        )

        def no_periodo(consulta, campo):
            return consulta.filter(campo >= inicio, campo < fim)

        agendamentos = no_periodo(Appointment.query, Appointment.data)
        ciclos = no_periodo(TreatmentCycle.query, TreatmentCycle.data_avaliacao)

        if current_user.perfil != ADMIN_PROFILE:
            agendamentos = agendamentos.filter(
                Appointment.fisioterapeuta_id == current_user.id
            )
            ciclos = ciclos.filter(TreatmentCycle.fisioterapeuta_id == current_user.id)

        # O bloco do grupo na agenda é excluído dos números: quem conta é a
        # presença de cada inscrito.
        itens = agendamentos.filter(Appointment.tipo != "GRUPO").all()
        lista_ciclos = ciclos.all()

        def contar(status):
            return sum(1 for item in itens if item.status == status)

        # A clínica conta a falta justificada como atendimento realizado.
        compareceram = contar("REALIZADO")
        faltas_justificadas = contar("FALTA_JUSTIFICADA")
        realizados = compareceram + faltas_justificadas
        faltas = contar("FALTOU")
        cancelados = contar("CANCELADO")
        previstos = realizados + faltas
        taxa_falta = round(faltas * 100 / previstos, 1) if previstos else 0

        por_regiao = {}
        for ciclo in lista_ciclos:
            rotulo = (ciclo.regiao or "OUTRO").capitalize()
            por_regiao[rotulo] = por_regiao.get(rotulo, 0) + 1

        por_horario = {}
        for item in itens:
            if item.status == "CANCELADO":
                continue
            rotulo = item.hora.strftime("%H:%M")
            por_horario[rotulo] = por_horario.get(rotulo, 0) + 1

        por_profissional = {}
        if current_user.perfil == ADMIN_PROFILE:
            for item in itens:
                if item.status not in STATUS_DE_ATENDIMENTO:
                    continue
                nome = item.fisioterapeuta.nome
                por_profissional[nome] = por_profissional.get(nome, 0) + 1

        # A clínica fecha o ano somando os meses; o sistema já entrega a conta.
        do_ano = Appointment.query.filter(
            Appointment.data >= date(ano, 1, 1),
            Appointment.data < date(ano + 1, 1, 1),
        )
        if current_user.perfil != ADMIN_PROFILE:
            do_ano = do_ano.filter(Appointment.fisioterapeuta_id == current_user.id)

        return render_template(
            "relatorios.html",
            periodo=periodo,
            rotulo_do_periodo=rotulo_do_periodo,
            inicio=inicio,
            fim=fim - timedelta(days=1),
            resumo=_resumo_numerico(itens),
            resumo_anual=_resumo_numerico(do_ano.all()),
            mes=mes,
            ano=ano,
            anos=range(dia_atual.year - 2, dia_atual.year + 2),
            total=len(itens),
            realizados=realizados,
            faltas=faltas,
            faltas_justificadas=faltas_justificadas,
            cancelados=cancelados,
            taxa_falta=taxa_falta,
            ciclos_abertos=len(lista_ciclos),
            por_regiao=por_regiao,
            por_horario=dict(sorted(por_horario.items())),
            por_profissional=por_profissional,
        )

    # ------------------------------------------------------------------
    # Evolução clínica
    # ------------------------------------------------------------------

    def _motivo_bloqueio_evolucao(agendamento):
        """Explica por que a sessão não aceita evolução, ou devolve None."""
        if agendamento.status in STATUS_DE_AUSENCIA:
            return "Não é possível registrar evolução em sessão marcada como falta."
        if agendamento.status not in STATUS_COM_EVOLUCAO:
            return "Não é possível registrar evolução em sessão cancelada."
        if agendamento.data > hoje():
            return (
                "A evolução só pode ser registrada a partir do dia da sessão "
                f"({agendamento.data.strftime('%d/%m/%Y')})."
            )
        return None

    def _acao_evolucao(agendamento, evolucao, usuario):
        """O que o usuário pode fazer com a evolução desta sessão.

        Devolve "registrar", "editar", "ver" ou None (nenhuma ação).
        - Quem acessa a sessão registra e edita, se a sessão aceitar evolução.
        - Quem acessa só o paciente (por exemplo, o novo responsável) apenas lê.
        """
        acessa_sessao = agendamento.acessivel_por(usuario)
        acessa_paciente = (
            agendamento.paciente is not None
            and agendamento.paciente.acessivel_por(usuario)
        )
        if not (acessa_sessao or acessa_paciente):
            return None

        sessao_aceita = _motivo_bloqueio_evolucao(agendamento) is None

        if evolucao is None:
            return "registrar" if acessa_sessao and sessao_aceita else None

        if acessa_sessao and sessao_aceita and evolucao.editavel_por(usuario):
            return "editar"
        return "ver"

    @app.route("/agendamentos/<int:agendamento_id>/evolucao", methods=["GET", "POST"])
    @login_required
    def registrar_evolucao(agendamento_id: int):
        agendamento = db.session.get(Appointment, agendamento_id)
        # Sessão de grupo não tem paciente: a evolução de grupo será outra tela.
        if agendamento is None or agendamento.paciente_id is None:
            abort(404)

        evolucao = db.session.scalar(
            db.select(Evolution).where(Evolution.agendamento_id == agendamento.id)
        )
        acao = _acao_evolucao(agendamento, evolucao, current_user)

        def recusar():
            """Quem cuida da sessão recebe o motivo; os demais, 403."""
            motivo = _motivo_bloqueio_evolucao(agendamento)
            if motivo and agendamento.acessivel_por(current_user):
                flash(motivo, "error")
                return redirect(
                    url_for("ficha_paciente", paciente_id=agendamento.paciente_id)
                )
            abort(403)

        if acao is None:
            return recusar()

        somente_leitura = acao == "ver"

        def form(codigo=200):
            return (
                render_template(
                    "evolucao_form.html",
                    agendamento=agendamento,
                    evolucao=evolucao,
                    somente_leitura=somente_leitura,
                ),
                codigo,
            )

        if request.method == "POST":
            if somente_leitura:
                return recusar()

            descricao = request.form.get("descricao", "").strip()
            if not descricao:
                flash("Descreva o que foi realizado na sessão.", "error")
                return form(400)

            if evolucao is None:
                evolucao = Evolution(
                    paciente_id=agendamento.paciente_id,
                    ciclo_id=agendamento.ciclo_id,
                    agendamento_id=agendamento.id,
                    fisioterapeuta_id=current_user.id,
                    data=agendamento.data,
                )
                db.session.add(evolucao)

            evolucao.descricao = descricao
            evolucao.evolucao = request.form.get("evolucao", "").strip() or None
            evolucao.observacoes = request.form.get("observacoes", "").strip() or None

            if agendamento.status in ("AGENDADO", "CONFIRMADO"):
                agendamento.status = "REALIZADO"

            db.session.commit()
            flash("Evolução registrada.", "success")
            return redirect(
                url_for("ficha_paciente", paciente_id=agendamento.paciente_id)
            )

        return form()

    # ------------------------------------------------------------------
    # Grupos terapêuticos
    # ------------------------------------------------------------------

    def _slots_do_grupo(rotulo_hora):
        """Horários da grade que uma sessão de grupo ocupa, ou None.

        O grupo dura 1 hora, então precisa de dois horários seguidos. Não
        serve um início que caia antes do almoço ou no fim do expediente,
        porque aí o segundo horário não existe.
        """
        if rotulo_hora not in HORARIOS:
            return None
        inicio = HORARIOS.index(rotulo_hora)
        if inicio + SLOTS_POR_GRUPO > len(HORARIOS):
            return None
        slots = HORARIOS[inicio : inicio + SLOTS_POR_GRUPO]
        anterior = time.fromisoformat(slots[0])
        for rotulo in slots[1:]:
            atual = time.fromisoformat(rotulo)
            minutos = (atual.hour * 60 + atual.minute) - (
                anterior.hour * 60 + anterior.minute
            )
            if minutos != 30:
                return None
            anterior = atual
        return slots

    HORARIOS_DE_GRUPO = [h for h in HORARIOS if _slots_do_grupo(h)]

    def _grupo_no_mesmo_horario(fisioterapeuta_id, dia_semana, hora, ignorar_id=None):
        """Outro grupo ativo do mesmo condutor que ocupe algum horário em comum."""
        slots = set(_slots_do_grupo(hora.strftime("%H:%M")) or [])
        consulta = Group.query.filter(
            Group.fisioterapeuta_id == fisioterapeuta_id,
            Group.dia_semana == dia_semana,
            Group.ativo.is_(True),
        )
        if ignorar_id is not None:
            consulta = consulta.filter(Group.id != ignorar_id)
        for outro in consulta.all():
            if outro.hora is None:
                continue
            ocupados = set(_slots_do_grupo(outro.hora.strftime("%H:%M")) or [])
            if slots & ocupados:
                return outro
        return None

    def _dados_do_grupo(grupo=None):
        """Lê e valida o formulário. Devolve (valores, mensagem_de_erro)."""
        valores = {
            "nome": request.form.get("nome", "").strip(),
            "regiao": request.form.get("regiao", "").strip().upper(),
            "dia_semana": request.form.get("dia_semana", "").strip(),
            "hora": request.form.get("hora", "").strip(),
            "capacidade_max": request.form.get("capacidade_max", "").strip(),
            "fisioterapeuta_id": request.form.get("fisioterapeuta_id", "").strip(),
        }

        if not valores["nome"]:
            return valores, "Informe o nome do grupo."
        if len(valores["nome"]) > 100:
            return valores, "O nome do grupo deve ter até 100 caracteres."
        if valores["regiao"] not in GROUP_REGIONS:
            return valores, "Selecione uma região válida."

        try:
            dia = int(valores["dia_semana"])
        except ValueError:
            return valores, "Selecione o dia da semana."
        if dia not in DIAS_DE_ATENDIMENTO:
            return valores, "A clínica atende de segunda a sexta-feira."

        if valores["hora"] not in HORARIOS_DE_GRUPO:
            return valores, (
                "Horário inválido para grupo. A sessão dura 1 hora e precisa de "
                "dois horários seguidos dentro do expediente."
            )

        try:
            capacidade = int(valores["capacidade_max"] or GROUP_CAPACITY_DEFAULT)
        except ValueError:
            return valores, "Capacidade inválida."
        if not GROUP_CAPACITY_MIN <= capacidade <= GROUP_CAPACITY_MAX:
            return valores, (
                f"A capacidade deve estar entre {GROUP_CAPACITY_MIN} e "
                f"{GROUP_CAPACITY_MAX} pessoas."
            )

        condutor_id = grupo.fisioterapeuta_id if grupo else current_user.id
        if current_user.perfil == ADMIN_PROFILE and valores["fisioterapeuta_id"]:
            condutor = db.session.get(User, int(valores["fisioterapeuta_id"]))
            if condutor is None or not condutor.ativo:
                return valores, "Selecione um profissional válido para conduzir."
            condutor_id = condutor.id

        hora = time.fromisoformat(valores["hora"])
        conflito = _grupo_no_mesmo_horario(
            condutor_id, dia, hora, ignorar_id=grupo.id if grupo else None
        )
        if conflito is not None:
            return valores, (
                f"O profissional já conduz o grupo {conflito.nome} neste horário."
            )

        valores["dia"] = dia
        valores["capacidade"] = capacidade
        valores["condutor_id"] = condutor_id
        valores["hora_obj"] = hora
        return valores, None

    @app.get("/grupos")
    @login_required
    def listar_grupos():
        consulta = Group.query
        if current_user.perfil != ADMIN_PROFILE:
            consulta = consulta.filter(Group.fisioterapeuta_id == current_user.id)

        regiao = request.args.get("regiao", "").strip().upper()
        if regiao in GROUP_REGIONS:
            consulta = consulta.filter(Group.regiao == regiao)
        else:
            regiao = ""

        # Consultar se um paciente está em algum grupo, ou já passou por um.
        paciente = request.args.get("paciente", "").strip()
        if paciente:
            consulta = consulta.filter(
                Group.id.in_(
                    db.select(GroupPatient.grupo_id)
                    .join(Patient, Patient.id == GroupPatient.paciente_id)
                    .where(Patient.nome.ilike(f"%{paciente}%"))
                )
            )

        # Os mais recentes no topo: é neles que o setor mexe no dia a dia.
        grupos = consulta.order_by(
            Group.ativo.desc(), Group.criado_em.desc(), Group.id.desc()
        ).all()

        # Para o caso de busca por paciente, mostrar em que grupo ele está.
        participacoes = {}
        if paciente:
            for grupo in grupos:
                encontradas = [
                    p
                    for p in grupo.participacoes
                    if paciente.lower() in p.paciente.nome.lower()
                ]
                if encontradas:
                    participacoes[grupo.id] = encontradas

        return render_template(
            "grupos_lista.html",
            grupos=grupos,
            regioes=GROUP_REGIONS,
            regiao=regiao,
            paciente=paciente,
            participacoes=participacoes,
        )

    @app.route("/grupos/novo", methods=["GET", "POST"])
    @login_required
    def novo_grupo():
        def form(codigo=200, valores=None):
            return (
                render_template(
                    "grupo_form.html",
                    grupo=None,
                    valores=valores or {},
                    regioes=GROUP_REGIONS,
                    horarios=HORARIOS_DE_GRUPO,
                    dias=[(i, WEEKDAY_NAMES[i]) for i in DIAS_DE_ATENDIMENTO],
                    capacidade_padrao=GROUP_CAPACITY_DEFAULT,
                    fisioterapeutas=_fisioterapeutas_ativos(),
                ),
                codigo,
            )

        if request.method == "POST":
            valores, erro = _dados_do_grupo()
            if erro:
                flash(erro, "error")
                return form(400, valores)

            grupo = Group(
                nome=valores["nome"],
                regiao=valores["regiao"],
                fisioterapeuta_id=valores["condutor_id"],
                dia_semana=valores["dia"],
                hora=valores["hora_obj"],
                capacidade_max=valores["capacidade"],
                ativo=True,
            )
            db.session.add(grupo)
            db.session.commit()
            flash("Grupo criado.", "success")
            return redirect(url_for("listar_grupos"))

        return form()

    @app.route("/grupos/<int:grupo_id>/editar", methods=["GET", "POST"])
    @login_required
    def editar_grupo(grupo_id: int):
        grupo = db.session.get(Group, grupo_id)
        if grupo is None:
            abort(404)
        if not grupo.acessivel_por(current_user):
            abort(403)

        # Grupo desativado é histórico: mudar dia, horário ou região agora
        # bagunçaria os encontros e a lista de presença já registrados.
        if not grupo.ativo:
            flash(
                "Grupo desativado não pode ser editado. Reative-o antes.",
                "error",
            )
            return redirect(url_for("listar_grupos"))

        def form(codigo=200, valores=None):
            return (
                render_template(
                    "grupo_form.html",
                    grupo=grupo,
                    valores=valores or {},
                    regioes=GROUP_REGIONS,
                    horarios=HORARIOS_DE_GRUPO,
                    dias=[(i, WEEKDAY_NAMES[i]) for i in DIAS_DE_ATENDIMENTO],
                    capacidade_padrao=GROUP_CAPACITY_DEFAULT,
                    fisioterapeutas=_fisioterapeutas_ativos(),
                ),
                codigo,
            )

        if request.method == "POST":
            valores, erro = _dados_do_grupo(grupo)
            if erro:
                flash(erro, "error")
                return form(400, valores)

            if valores["condutor_id"] != grupo.fisioterapeuta_id:
                ativos = len(grupo.participacoes_ativas)
                if ativos:
                    flash(
                        f"Este grupo tem {ativos} paciente(s). Troque o condutor "
                        "apenas em grupo vazio.",
                        "error",
                    )
                    return form(400, valores)

            if valores["capacidade"] < len(grupo.participacoes_ativas):
                flash(
                    "A capacidade não pode ser menor que o número de pacientes "
                    "já no grupo.",
                    "error",
                )
                return form(400, valores)

            grupo.nome = valores["nome"]
            grupo.regiao = valores["regiao"]
            grupo.fisioterapeuta_id = valores["condutor_id"]
            grupo.dia_semana = valores["dia"]
            grupo.hora = valores["hora_obj"]
            grupo.capacidade_max = valores["capacidade"]
            db.session.commit()
            flash("Grupo atualizado.", "success")
            return redirect(url_for("listar_grupos"))

        return form()

    @app.post("/grupos/<int:grupo_id>/situacao")
    @login_required
    def alternar_situacao_grupo(grupo_id: int):
        """Desativa ou reativa o grupo. Grupo nunca é excluído: a composição
        e o histórico de presença dependem dele."""
        grupo = db.session.get(Group, grupo_id)
        if grupo is None:
            abort(404)
        if not grupo.acessivel_por(current_user):
            abort(403)

        grupo.ativo = not grupo.ativo
        db.session.commit()
        flash(
            f"Grupo {'reativado' if grupo.ativo else 'desativado'}.",
            "success",
        )
        return redirect(url_for("listar_grupos"))

    # ------------------------------------------------------------------
    # Composição do grupo
    # ------------------------------------------------------------------

    def _pacientes_para_o_grupo(grupo):
        """Quem o usuário pode adicionar: ativos, fora do grupo e acessíveis.

        O fisioterapeuta só compõe com pacientes que já acompanha; o admin
        monta o grupo com qualquer paciente ativo.
        """
        ja_no_grupo = {p.paciente_id for p in grupo.participacoes_ativas}
        consulta = Patient.query.filter(Patient.ativo.is_(True))
        if current_user.perfil != ADMIN_PROFILE:
            consulta = consulta.filter(Patient.fisioterapeuta_id == current_user.id)
        return [
            p for p in consulta.order_by(Patient.nome).all() if p.id not in ja_no_grupo
        ]

    def _encontros_do_grupo(grupo, a_partir_de=None):
        """Os encontros já marcados do grupo, do mais antigo ao mais novo."""
        consulta = Appointment.query.filter(
            Appointment.grupo_id == grupo.id,
            Appointment.tipo == "GRUPO",
            Appointment.status != "CANCELADO",
        )
        if a_partir_de is not None:
            consulta = consulta.filter(Appointment.data >= a_partir_de)
        return consulta.order_by(Appointment.data).all()

    def _ciclo_do_grupo(grupo, paciente, encontros):
        """Abre o ciclo do paciente para este grupo.

        O tratamento em grupo é fechado: cada encontro de 1 hora vale por 2
        sessões individuais. Quem entra no meio do caminho recebe um ciclo do
        tamanho do que ainda falta, senão o cartão prometeria datas que já
        passaram.
        """
        ciclo = TreatmentCycle(
            paciente_id=paciente.id,
            fisioterapeuta_id=grupo.fisioterapeuta_id,
            regiao=grupo.regiao,
            modalidade="GRUPO",
            data_avaliacao=hoje(),
            total_sessoes=len(encontros) * SESSOES_POR_ENCONTRO_DE_GRUPO,
            status="ATIVO",
            observacoes=f"Tratamento em grupo: {grupo.nome}.",
        )
        db.session.add(ciclo)
        db.session.flush()
        return ciclo

    def _inscrever_nos_encontros(grupo, paciente, ciclo, encontros):
        """Cria a linha de presença do paciente em cada encontro do grupo.

        Uma linha por paciente por data é o que faz a participação aparecer
        no histórico dele, no cartão e nos relatórios — a mesma estrutura do
        atendimento individual, com o grupo anotado junto.
        """
        for ordem, encontro in enumerate(encontros, start=1):
            db.session.add(
                Appointment(
                    tipo="SESSAO",
                    paciente_id=paciente.id,
                    grupo_id=grupo.id,
                    ciclo_id=ciclo.id,
                    fisioterapeuta_id=grupo.fisioterapeuta_id,
                    data=encontro.data,
                    hora=encontro.hora,
                    duracao_min=encontro.duracao_min,
                    status="AGENDADO",
                    numero_sessao=ordem * SESSOES_POR_ENCONTRO_DE_GRUPO,
                )
            )

    @app.route("/grupos/<int:grupo_id>/sessoes", methods=["GET", "POST"])
    @login_required
    def gerar_encontros_do_grupo(grupo_id: int):
        """Monta o calendário do grupo: um encontro por semana.

        Vira o ciclo padrão do grupo — quem for inscrito depois entra nas
        datas que ainda faltam e recebe o cartão com elas.
        """
        grupo = db.session.get(Group, grupo_id)
        if grupo is None:
            abort(404)
        if not grupo.acessivel_por(current_user):
            abort(403)

        marcados = _encontros_do_grupo(grupo)

        def form(codigo=200, valores=None):
            return (
                render_template(
                    "grupo_sessoes.html",
                    grupo=grupo,
                    marcados=marcados,
                    evolucoes={
                        e.data: e
                        for e in GroupEvolution.query.filter(
                            GroupEvolution.grupo_id == grupo.id
                        ).all()
                    },
                    valores=valores or {},
                    hoje=hoje(),
                    semanas_padrao=grupo.total_semanas,
                ),
                codigo,
            )

        if request.method == "GET":
            return form()

        valores = {
            "inicio": request.form.get("inicio", "").strip(),
            "semanas": request.form.get("semanas", "").strip(),
        }

        if not grupo.ativo:
            flash("Grupo desativado não recebe encontros. Reative-o antes.", "error")
            return form(400, valores)

        if marcados:
            flash(
                "Este grupo já tem encontros marcados. Para refazer o "
                "calendário, cancele os encontros existentes primeiro.",
                "error",
            )
            return form(400, valores)

        if grupo.dia_semana is None or grupo.hora is None:
            flash("Defina o dia e o horário do grupo antes de gerar.", "error")
            return form(400, valores)

        try:
            inicio = date.fromisoformat(valores["inicio"])
        except ValueError:
            flash("Informe a data do primeiro encontro.", "error")
            return form(400, valores)

        if inicio < hoje():
            flash("A data do primeiro encontro não pode estar no passado.", "error")
            return form(400, valores)

        try:
            semanas = int(valores["semanas"] or grupo.total_semanas)
        except ValueError:
            flash("Número de semanas inválido.", "error")
            return form(400, valores)

        if not 1 <= semanas <= GROUP_WEEKS_MAX:
            flash(
                f"O número de semanas deve estar entre 1 e {GROUP_WEEKS_MAX}.", "error"
            )
            return form(400, valores)

        datas, pulados = _datas_das_sessoes(
            inicio,
            {grupo.dia_semana},
            semanas,
            _feriados_no_periodo(inicio, inicio + timedelta(days=400)),
        )

        if len(datas) < semanas:
            flash("Não foi possível gerar todas as datas do grupo.", "error")
            return form(400, valores)

        for data in datas:
            db.session.add(
                Appointment(
                    tipo="GRUPO",
                    grupo_id=grupo.id,
                    fisioterapeuta_id=grupo.fisioterapeuta_id,
                    data=data,
                    hora=grupo.hora,
                    duracao_min=60,
                    status="AGENDADO",
                )
            )

        grupo.total_semanas = semanas
        db.session.flush()

        # Quem já estava inscrito antes do calendário existir entra agora.
        encontros = _encontros_do_grupo(grupo)
        for participacao in grupo.participacoes_ativas:
            if participacao.ciclo_id is not None:
                continue
            ciclo = _ciclo_do_grupo(grupo, participacao.paciente, encontros)
            participacao.ciclo_id = ciclo.id
            _inscrever_nos_encontros(grupo, participacao.paciente, ciclo, encontros)

        db.session.commit()

        if pulados:
            nomes = ", ".join(f"{d.strftime('%d/%m')} ({nome})" for d, nome in pulados)
            flash(f"Datas puladas por feriado: {nomes}.", "info")
        flash(
            f"{len(datas)} encontro(s) marcado(s), equivalentes a "
            f"{len(datas) * SESSOES_POR_ENCONTRO_DE_GRUPO} sessões.",
            "success",
        )
        return redirect(url_for("composicao_do_grupo", grupo_id=grupo.id))

    @app.get("/grupos/<int:grupo_id>/pacientes")
    @login_required
    def composicao_do_grupo(grupo_id: int):
        grupo = db.session.get(Group, grupo_id)
        if grupo is None:
            abort(404)
        if not grupo.acessivel_por(current_user):
            abort(403)

        disponiveis = _pacientes_para_o_grupo(grupo)
        return render_template(
            "grupo_composicao.html",
            grupo=grupo,
            participacoes=grupo.participacoes_ativas,
            historico=[p for p in grupo.participacoes if p.data_saida is not None],
            disponiveis=disponiveis,
            encontros=len(_encontros_do_grupo(grupo, a_partir_de=hoje())),
        )

    @app.post("/grupos/<int:grupo_id>/pacientes")
    @login_required
    def adicionar_ao_grupo(grupo_id: int):
        grupo = db.session.get(Group, grupo_id)
        if grupo is None:
            abort(404)
        if not grupo.acessivel_por(current_user):
            abort(403)

        def voltar():
            return redirect(url_for("composicao_do_grupo", grupo_id=grupo.id))

        if not grupo.ativo:
            flash("Grupo desativado não recebe pacientes. Reative-o antes.", "error")
            return voltar()

        paciente = db.session.get(Patient, int(request.form.get("paciente_id") or 0))
        if paciente is None or not paciente.ativo:
            flash("Selecione um paciente ativo.", "error")
            return voltar()
        if not paciente.acessivel_por(current_user):
            abort(403)

        if grupo.participacao_ativa_de(paciente.id) is not None:
            flash(f"{paciente.nome} já está neste grupo.", "error")
            return voltar()

        if grupo.lotado:
            flash(
                f"O grupo está com a lotação máxima ({grupo.capacidade_max} pessoas).",
                "error",
            )
            return voltar()

        # O ciclo do paciente sai do próprio grupo: o profissional não
        # escolhe mais um ciclo à mão na hora de inscrever.
        encontros = _encontros_do_grupo(grupo, a_partir_de=hoje())
        ciclo = None
        if encontros:
            ciclo = _ciclo_do_grupo(grupo, paciente, encontros)
            _inscrever_nos_encontros(grupo, paciente, ciclo, encontros)

        db.session.add(
            GroupPatient(
                grupo_id=grupo.id,
                paciente_id=paciente.id,
                ciclo_id=ciclo.id if ciclo else None,
                data_entrada=hoje(),
            )
        )
        db.session.commit()

        if ciclo is None:
            flash(
                f"{paciente.nome} entrou no grupo. Gere os encontros para "
                "criar o cartão com as datas.",
                "info",
            )
        else:
            flash(
                f"{paciente.nome} entrou no grupo, com {len(encontros)} "
                f"encontro(s) e {ciclo.total_sessoes} sessões no cartão.",
                "success",
            )
        return voltar()

    @app.get("/grupos/<int:grupo_id>/presenca")
    @login_required
    def presenca_do_grupo(grupo_id: int):
        """Lista de presença do grupo: inscritos nas linhas, datas nas colunas.

        É a folha que hoje é impressa e preenchida à mão, e que fica anexada
        ao prontuário de papel.
        """
        grupo = db.session.get(Group, grupo_id)
        if grupo is None:
            abort(404)
        if not grupo.acessivel_por(current_user):
            abort(403)

        encontros = _encontros_do_grupo(grupo)
        datas = [e.data for e in encontros]

        presencas = Appointment.query.filter(
            Appointment.grupo_id == grupo.id,
            Appointment.paciente_id.isnot(None),
        ).all()

        # {paciente_id: {data: agendamento}} — o template lê célula a célula.
        grade = {}
        for item in presencas:
            grade.setdefault(item.paciente_id, {})[item.data] = item

        inscritos = sorted(
            grupo.participacoes,
            key=lambda p: (p.data_saida is not None, p.paciente.nome),
        )

        return render_template(
            "grupo_presenca.html",
            grupo=grupo,
            inscritos=inscritos,
            datas=datas,
            grade=grade,
            hoje=hoje(),
            emitido_em=hoje(),
        )

    @app.post("/grupos/<int:grupo_id>/presenca/<int:agendamento_id>")
    @login_required
    def marcar_presenca_no_grupo(grupo_id: int, agendamento_id: int):
        """Registra presença, falta ou falta justificada de um inscrito.

        Mesma regra do atendimento individual: a ausência pode ser lançada
        antes do dia, porque o paciente avisa com antecedência; só o
        comparecimento espera a data chegar.
        """
        grupo = db.session.get(Group, grupo_id)
        if grupo is None:
            abort(404)
        if not grupo.acessivel_por(current_user):
            abort(403)

        presenca = db.session.get(Appointment, agendamento_id)
        if presenca is None or presenca.grupo_id != grupo.id:
            abort(404)
        if presenca.paciente_id is None:
            abort(404)

        def voltar():
            return redirect(url_for("presenca_do_grupo", grupo_id=grupo.id))

        novo_status = request.form.get("status", "").strip().upper()
        if novo_status not in STATUS_AGENDAMENTO:
            flash("Situação inválida.", "error")
            return voltar()

        if novo_status in STATUS_SO_A_PARTIR_DO_DIA and presenca.data > hoje():
            flash(
                "O comparecimento só pode ser registrado a partir do dia do encontro.",
                "error",
            )
            return voltar()

        if novo_status == "FALTA_JUSTIFICADA":
            motivo = request.form.get("justificativa", "").strip()
            if not motivo:
                flash("Informe o motivo da falta justificada.", "error")
                return voltar()
            presenca.observacoes = motivo

        presenca.status = novo_status
        db.session.commit()
        flash(
            f"{presenca.paciente.nome}: "
            f"{ROTULOS_DE_STATUS.get(novo_status, novo_status).lower()} em "
            f"{presenca.data.strftime('%d/%m/%Y')}.",
            "success",
        )
        return voltar()

    @app.post("/grupos/<int:grupo_id>/pacientes/<int:participacao_id>/saida")
    @login_required
    def registrar_saida_do_grupo(grupo_id: int, participacao_id: int):
        """Marca a saída sem apagar a linha: o histórico de presença depende dela."""
        grupo = db.session.get(Group, grupo_id)
        if grupo is None:
            abort(404)
        if not grupo.acessivel_por(current_user):
            abort(403)

        participacao = db.session.get(GroupPatient, participacao_id)
        if participacao is None or participacao.grupo_id != grupo.id:
            abort(404)

        if participacao.data_saida is not None:
            flash("Este paciente já havia saído do grupo.", "error")
            return redirect(url_for("composicao_do_grupo", grupo_id=grupo.id))

        participacao.data_saida = hoje()
        # O motivo entra na alta e no histórico: a clínica precisa saber se
        # foi pedido do paciente, alta ou mudança de horário.
        participacao.motivo_saida = request.form.get("motivo", "").strip() or None

        # As datas que ele não vai mais cumprir saem da agenda dele.
        Appointment.query.filter(
            Appointment.grupo_id == grupo.id,
            Appointment.paciente_id == participacao.paciente_id,
            Appointment.data > hoje(),
            Appointment.status.in_(("AGENDADO", "CONFIRMADO")),
        ).update({"status": "CANCELADO"}, synchronize_session=False)

        db.session.commit()
        flash(f"{participacao.paciente.nome} saiu do grupo.", "success")
        return redirect(url_for("composicao_do_grupo", grupo_id=grupo.id))

    @app.route(
        "/grupos/<int:grupo_id>/encontros/<int:agendamento_id>/evolucao",
        methods=["GET", "POST"],
    )
    @login_required
    def evolucao_do_grupo(grupo_id: int, agendamento_id: int):
        """Anotação do encontro inteiro, não de paciente em paciente.

        No grupo os exercícios são os mesmos para todos; o que muda por
        pessoa é só a presença, registrada na lista de presença.
        """
        grupo = db.session.get(Group, grupo_id)
        if grupo is None:
            abort(404)
        if not grupo.acessivel_por(current_user):
            abort(403)

        encontro = db.session.get(Appointment, agendamento_id)
        if encontro is None or encontro.grupo_id != grupo.id:
            abort(404)
        if encontro.tipo != "GRUPO":
            abort(404)

        evolucao = db.session.scalar(
            db.select(GroupEvolution).where(
                GroupEvolution.grupo_id == grupo.id,
                GroupEvolution.data == encontro.data,
            )
        )

        somente_leitura = evolucao is not None and not evolucao.editavel_por(
            current_user
        )

        def form(codigo=200, valores=None):
            return (
                render_template(
                    "grupo_evolucao.html",
                    grupo=grupo,
                    encontro=encontro,
                    evolucao=evolucao,
                    somente_leitura=somente_leitura,
                    valores=valores or {},
                    presentes=_presentes_no_encontro(grupo, encontro.data),
                ),
                codigo,
            )

        if request.method == "GET":
            return form()

        if somente_leitura:
            abort(403)

        # O encontro ainda não aconteceu: não há o que relatar.
        if encontro.data > hoje():
            flash(
                "A evolução só pode ser registrada a partir do dia do encontro.",
                "error",
            )
            return form(400)

        descricao = request.form.get("descricao", "").strip()
        if not descricao:
            flash("Descreva o que foi feito no encontro.", "error")
            return form(400, {"observacoes": request.form.get("observacoes", "")})

        if evolucao is None:
            evolucao = GroupEvolution(
                grupo_id=grupo.id,
                agendamento_id=encontro.id,
                fisioterapeuta_id=current_user.id,
                data=encontro.data,
            )
            db.session.add(evolucao)

        evolucao.descricao = descricao
        evolucao.observacoes = request.form.get("observacoes", "").strip() or None
        db.session.commit()

        flash(
            f"Evolução do encontro de {encontro.data.strftime('%d/%m/%Y')} salva.",
            "success",
        )
        return redirect(url_for("gerar_encontros_do_grupo", grupo_id=grupo.id))

    def _presentes_no_encontro(grupo, data):
        """Quem tem presença registrada naquela data, para a folha."""
        return (
            Appointment.query.filter(
                Appointment.grupo_id == grupo.id,
                Appointment.paciente_id.isnot(None),
                Appointment.data == data,
            )
            .join(Patient, Patient.id == Appointment.paciente_id)
            .order_by(Patient.nome)
            .all()
        )

    @app.get("/grupos/<int:grupo_id>/resumo")
    @login_required
    def resumo_do_grupo(grupo_id: int):
        """Resumo para imprimir: evolução de cada data e presença de cada um.

        É o que a clínica arquiva quando o grupo termina, no lugar das
        folhas soltas grampeadas à lista de presença.
        """
        grupo = db.session.get(Group, grupo_id)
        if grupo is None:
            abort(404)
        if not grupo.acessivel_por(current_user):
            abort(403)

        encontros = _encontros_do_grupo(grupo)
        datas = [e.data for e in encontros]

        evolucoes = {
            e.data: e
            for e in GroupEvolution.query.filter(
                GroupEvolution.grupo_id == grupo.id
            ).all()
        }

        presencas = Appointment.query.filter(
            Appointment.grupo_id == grupo.id,
            Appointment.paciente_id.isnot(None),
        ).all()

        grade = {}
        for item in presencas:
            grade.setdefault(item.paciente_id, {})[item.data] = item

        # Quantas vezes cada inscrito compareceu, e quanto isso vale.
        resumo_por_paciente = {}
        for participacao in grupo.participacoes:
            linhas = grade.get(participacao.paciente_id, {})
            compareceu = sum(
                1 for i in linhas.values() if i.status in STATUS_DE_ATENDIMENTO
            )
            resumo_por_paciente[participacao.id] = {
                "compareceu": compareceu,
                "faltou": sum(
                    1 for i in linhas.values() if i.status in STATUS_DE_FALTA
                ),
                "sessoes": compareceu * SESSOES_POR_ENCONTRO_DE_GRUPO,
            }

        return render_template(
            "grupo_resumo.html",
            grupo=grupo,
            encontros=encontros,
            datas=datas,
            evolucoes=evolucoes,
            grade=grade,
            inscritos=sorted(
                grupo.participacoes,
                key=lambda p: (p.data_saida is not None, p.paciente.nome),
            ),
            resumo_por_paciente=resumo_por_paciente,
            emitido_em=hoje(),
        )


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
