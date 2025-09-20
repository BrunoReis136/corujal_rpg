# -------------------------
# Models
# -------------------------
class Usuario(db.Model, UserMixin):
    __tablename__ = "core_usuario"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(254), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    is_staff = db.Column(db.Boolean, default=False)
    is_superuser = db.Column(db.Boolean, default=False)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

    def get_id(self):
        return str(self.id)

    def __repr__(self):
        return f"<Usuario {self.username}>"

# Personagem, Item, Aventura, Sessao, Participacao, HistoricoMensagens
class Personagem(db.Model):
    __tablename__ = "core_personagem"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100))
    classe = db.Column(db.String(50))
    raca = db.Column(db.String(50))
    atributos = db.Column(db.JSON, default={})
    inventario = db.Column(db.JSON, default=list)
    xp = db.Column(db.Integer, default=0)
    nivel = db.Column(db.Integer, default=1)
    usuario_id = db.Column(db.Integer, db.ForeignKey("core_usuario.id"))
    usuario = db.relationship("Usuario", backref="personagens")

class Item(db.Model):
    __tablename__ = "core_item"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100))
    tipo = db.Column(db.String(50))
    descricao = db.Column(db.Text)
    efeitos = db.Column(db.JSON, default={})

class Aventura(db.Model):
    __tablename__ = "core_aventura"
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200))
    descricao = db.Column(db.Text)
    cenario = db.Column(db.String(100))
    regras = db.Column(db.JSON, default={})
    status = db.Column(db.String(50))
    criada_em = db.Column(db.DateTime, default=datetime.utcnow)
    resumo_atual = db.Column(db.Text, default="")
    ultimo_turno = db.Column(db.JSON, default={})
    metadados = db.Column(db.JSON, default={})
    estado_personagens = db.Column(db.JSON, default={})
    estado_aventura = db.Column(db.JSON, default={})
    criador_id = db.Column(db.Integer, db.ForeignKey("core_usuario.id"), nullable=True)
    criador = db.relationship("Usuario", backref="aventuras_criadas")

class Sessao(db.Model):
    __tablename__ = "core_sessao"
    id = db.Column(db.Integer, primary_key=True)
    aventura_id = db.Column(db.Integer, db.ForeignKey("core_aventura.id"))
    aventura = db.relationship("Aventura", backref="sessoes")
    narrador_ia = db.Column(db.Text)
    acoes_jogadores = db.Column(db.JSON, default=list)
    resultado = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    prompt_usado = db.Column(db.Text, default="")
    resposta_bruta = db.Column(db.Text, default="")

class Participacao(db.Model):
    __tablename__ = "core_participacao"
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("core_usuario.id"))
    usuario = db.relationship("Usuario", backref="participacoes")
    personagem_id = db.Column(db.Integer, db.ForeignKey("core_personagem.id"))
    personagem = db.relationship("Personagem", backref="participacoes")
    aventura_id = db.Column(db.Integer, db.ForeignKey("core_aventura.id"))
    aventura = db.relationship("Aventura", backref="participantes")
    papel = db.Column(db.String(50))

class HistoricoMensagens(db.Model):
    __tablename__ = "core_historicomensagens"
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("core_usuario.id"), nullable=True)
    usuario = db.relationship("Usuario", backref="mensagens")
    aventura_id = db.Column(db.Integer, db.ForeignKey("core_aventura.id"))
    aventura = db.relationship("Aventura", backref="mensagens")
    mensagem = db.Column(db.Text)
    autor = db.Column(db.String(20))
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
