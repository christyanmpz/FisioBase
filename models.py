"""Modelos persistidos do sistema."""

from datetime import date

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()

ADMIN_PROFILE = "ADMIN"
PHYSIOTHERAPIST_PROFILE = "FISIOTERAPEUTA"

# Espelham as restrições chk_grupo_regiao e chk_grupo_cap do banco.
GROUP_REGIONS = ("OMBRO", "JOELHO", "COLUNA", "OUTRO")
GROUP_CAPACITY_MIN = 1
GROUP_CAPACITY_MAX = 20
GROUP_CAPACITY_DEFAULT = 14

# Índice = valor de grupos.dia_semana (convenção do Python: 0 = segunda).
WEEKDAY_NAMES = (
    "Segunda-feira",
    "Terça-feira",
    "Quarta-feira",
    "Quinta-feira",
    "Sexta-feira",
    "Sábado",
    "Domingo",
)


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
    criado_em = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=db.func.now()
    )

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


class Patient(db.Model):
    __tablename__ = "pacientes"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    cpf = db.Column(db.String(14), unique=True, nullable=True)
    data_nascimento = db.Column(db.Date, nullable=True)
    telefone = db.Column(db.String(30), nullable=True)
    email = db.Column(db.String(150), nullable=True)
    endereco = db.Column(db.String(255), nullable=True)
    cid = db.Column(db.String(30), nullable=True)
    diagnostico = db.Column(db.Text, nullable=True)
    observacoes = db.Column(db.Text, nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    fisioterapeuta_id = db.Column(
        db.Integer, db.ForeignKey("usuarios.id"), nullable=True
    )
    criado_em = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=db.func.now()
    )

    fisioterapeuta = db.relationship("User", backref="pacientes")

    def acessivel_por(self, usuario) -> bool:
        """Um ADMIN vê qualquer paciente; um fisioterapeuta, só os seus."""
        if usuario.perfil == ADMIN_PROFILE:
            return True
        return self.fisioterapeuta_id == usuario.id


class TreatmentCycle(db.Model):
    __tablename__ = "ciclos_tratamento"

    id = db.Column(db.Integer, primary_key=True)
    paciente_id = db.Column(db.Integer, db.ForeignKey("pacientes.id"), nullable=False)
    fisioterapeuta_id = db.Column(
        db.Integer, db.ForeignKey("usuarios.id"), nullable=False
    )
    regiao = db.Column(db.String(30), nullable=True)
    modalidade = db.Column(db.String(20), nullable=False, default="INDIVIDUAL")
    data_avaliacao = db.Column(db.Date, nullable=False)
    total_sessoes = db.Column(db.Integer, nullable=False, default=10)
    status = db.Column(db.String(20), nullable=False, default="ATIVO")
    data_alta = db.Column(db.Date, nullable=True)
    observacoes = db.Column(db.Text, nullable=True)
    criado_em = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=db.func.now()
    )

    paciente = db.relationship("Patient", backref="ciclos")
    fisioterapeuta = db.relationship("User", backref="ciclos")

    def acessivel_por(self, usuario) -> bool:
        """Um ADMIN vê qualquer ciclo; um fisioterapeuta, só os seus."""
        if usuario.perfil == ADMIN_PROFILE:
            return True
        return self.fisioterapeuta_id == usuario.id


class Group(db.Model):
    """Grupo terapêutico com horário fixo semanal.

    dia_semana segue date.weekday() do Python: 0 = segunda ... 6 = domingo.
    Atenção: no PostgreSQL, extract(dow ...) usa 0 = domingo. Converter
    se algum dia esta coluna for comparada com dow em SQL.

    As CheckConstraints abaixo já existem no Supabase com os mesmos nomes.
    Aqui elas só servem para o SQLite dos testes rejeitar os mesmos valores
    que o banco de produção rejeita.
    """

    __tablename__ = "grupos"
    __table_args__ = (
        db.CheckConstraint(
            "capacidade_max >= 1 AND capacidade_max <= 20", name="chk_grupo_cap"
        ),
        db.CheckConstraint("dia_semana >= 0 AND dia_semana <= 6", name="chk_grupo_dia"),
        db.CheckConstraint(
            "regiao IN ('OMBRO', 'JOELHO', 'COLUNA', 'OUTRO')",
            name="chk_grupo_regiao",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    regiao = db.Column(db.String(30), nullable=False)
    fisioterapeuta_id = db.Column(
        db.Integer, db.ForeignKey("usuarios.id"), nullable=False
    )
    dia_semana = db.Column(db.SmallInteger, nullable=True)
    hora = db.Column(db.Time, nullable=True)
    capacidade_max = db.Column(
        db.Integer, nullable=False, default=GROUP_CAPACITY_DEFAULT
    )
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    criado_em = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=db.func.now()
    )

    fisioterapeuta = db.relationship("User", backref="grupos")
    participacoes = db.relationship(
        "GroupPatient", back_populates="grupo", order_by="GroupPatient.id"
    )

    def acessivel_por(self, usuario) -> bool:
        """Um ADMIN vê qualquer grupo; um fisioterapeuta, só os que conduz."""
        if usuario.perfil == ADMIN_PROFILE:
            return True
        return self.fisioterapeuta_id == usuario.id

    @property
    def participacoes_ativas(self) -> list:
        """Participações sem data de saída, ou seja, quem está no grupo hoje."""
        return [p for p in self.participacoes if p.data_saida is None]

    @property
    def vagas_disponiveis(self) -> int:
        return max(self.capacidade_max - len(self.participacoes_ativas), 0)

    @property
    def lotado(self) -> bool:
        return self.vagas_disponiveis == 0

    @property
    def dia_semana_nome(self) -> str:
        if self.dia_semana is None:
            return "—"
        return WEEKDAY_NAMES[self.dia_semana]

    def participacao_ativa_de(self, paciente_id: int):
        """Devolve a participação ativa do paciente neste grupo, ou None."""
        for participacao in self.participacoes_ativas:
            if participacao.paciente_id == paciente_id:
                return participacao
        return None


class GroupPatient(db.Model):
    """Passagem de um paciente por um grupo.

    Sair do grupo preenche data_saida; a linha nunca é apagada, para não
    perder o histórico de presença. Se o paciente voltar, entra uma
    linha nova.
    """

    __tablename__ = "grupo_pacientes"

    id = db.Column(db.Integer, primary_key=True)
    grupo_id = db.Column(
        db.Integer, db.ForeignKey("grupos.id", ondelete="CASCADE"), nullable=False
    )
    paciente_id = db.Column(db.Integer, db.ForeignKey("pacientes.id"), nullable=False)
    ciclo_id = db.Column(
        db.Integer, db.ForeignKey("ciclos_tratamento.id"), nullable=True
    )
    data_entrada = db.Column(db.Date, nullable=False, default=date.today)
    data_saida = db.Column(db.Date, nullable=True)

    grupo = db.relationship("Group", back_populates="participacoes")
    paciente = db.relationship("Patient", backref="participacoes_grupo")
    ciclo = db.relationship("TreatmentCycle", backref="participacoes_grupo")

    @property
    def ativa(self) -> bool:
        return self.data_saida is None


class Appointment(db.Model):
    __tablename__ = "agendamentos"

    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(20), nullable=False)
    paciente_id = db.Column(db.Integer, db.ForeignKey("pacientes.id"), nullable=True)
    grupo_id = db.Column(db.Integer, db.ForeignKey("grupos.id"), nullable=True)
    ciclo_id = db.Column(
        db.Integer, db.ForeignKey("ciclos_tratamento.id"), nullable=True
    )
    fisioterapeuta_id = db.Column(
        db.Integer, db.ForeignKey("usuarios.id"), nullable=False
    )
    data = db.Column(db.Date, nullable=False)
    hora = db.Column(db.Time, nullable=False)
    duracao_min = db.Column(db.Integer, nullable=False, default=30)
    numero_sessao = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="AGENDADO")
    observacoes = db.Column(db.Text, nullable=True)
    criado_em = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=db.func.now()
    )

    paciente = db.relationship("Patient", backref="agendamentos")
    grupo = db.relationship("Group", backref="agendamentos")
    ciclo = db.relationship("TreatmentCycle", backref="agendamentos")
    fisioterapeuta = db.relationship("User", backref="agendamentos")

    def acessivel_por(self, usuario) -> bool:
        """Um ADMIN vê qualquer agendamento; um fisioterapeuta, só os seus."""
        if usuario.perfil == ADMIN_PROFILE:
            return True
        return self.fisioterapeuta_id == usuario.id


class Evolution(db.Model):
    __tablename__ = "evolucoes"

    id = db.Column(db.Integer, primary_key=True)
    ciclo_id = db.Column(
        db.Integer, db.ForeignKey("ciclos_tratamento.id"), nullable=True
    )
    paciente_id = db.Column(db.Integer, db.ForeignKey("pacientes.id"), nullable=False)
    agendamento_id = db.Column(
        db.Integer, db.ForeignKey("agendamentos.id"), nullable=True
    )
    fisioterapeuta_id = db.Column(
        db.Integer, db.ForeignKey("usuarios.id"), nullable=False
    )
    data = db.Column(db.Date, nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    evolucao = db.Column(db.Text, nullable=True)
    observacoes = db.Column(db.Text, nullable=True)
    criado_em = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=db.func.now()
    )

    paciente = db.relationship("Patient", backref="evolucoes")
    ciclo = db.relationship("TreatmentCycle", backref="evolucoes")
    agendamento = db.relationship("Appointment", backref="evolucao")
    fisioterapeuta = db.relationship("User", backref="evolucoes")

    def editavel_por(self, usuario) -> bool:
        """O admin, quem escreveu e o fisioterapeuta da sessão podem corrigir."""
        if usuario.perfil == ADMIN_PROFILE:
            return True
        if self.fisioterapeuta_id == usuario.id:
            return True
        return (
            self.agendamento is not None
            and self.agendamento.fisioterapeuta_id == usuario.id
        )
