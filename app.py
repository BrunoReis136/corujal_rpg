# app.py
import os
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, flash, session, abort, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from itsdangerous import URLSafeTimedSerializer
from forms import LoginForm, SignupForm, AventuraForm, ForgotPasswordForm, SetPasswordForm, TurnoForm, PersonagemForm
from models import db, Usuario, Personagem, Item, Aventura, Sessao, Participacao, HistoricoMensagens
from sqlalchemy import text
from flask_mail import Mail, Message


import json

# -------------------------
# Config
# -------------------------
app = Flask(__name__)


app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///db.sqlite3")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
# app.config['SERVER_NAME'] = 'corujal-rpg.onrender.com'

# Mail
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USER")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASS")
app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_TO", app.config["MAIL_USERNAME"])

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Token serializer for password reset
serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])

# -------------------------
# Extensions
# -------------------------
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login = "home"

mail = Mail(app)

with app.app_context():
    db.create_all()
    
# -------------------------
# Login manager
# -------------------------
@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))



# -------------------------
# Password validation
# -------------------------
COMMON_PASSWORDS = {"password", "123456", "12345678", "qwerty", "abc123"}

def validate_password_rules(pw):
    errors = []
    if len(pw) < 6:
        errors.append("A senha deve ter pelo menos 6 caracteres.")
    if pw.isdigit():
        errors.append("Senha não pode ser somente números.")
    if pw.lower() in COMMON_PASSWORDS:
        errors.append("Senha muito comum, escolha outra.")
    return errors


# -------------------------
# Functions
# -------------------------


def safe_json(data):
    if not data:
        return {}
    try:
        return json.loads(data)
    except Exception:
        return {}

def send_password_reset_email(user):
    # Gera token de redefinição de senha
    token = serializer.dumps(user.email, salt="password-reset-salt")
    reset_url = url_for("password_reset_confirm", token=token, _external=True)

    # Cria mensagem de e-mail
    msg = Message(
        subject="Redefinição de senha",
        recipients=[user.email]
    )
    
    # Corpo HTML via template
    msg.html = render_template(
        "password_reset_email.html",
        user=user,
        reset_url=reset_url
    )
    
    # Envia e-mail
    mail.send(msg)

# -------------------------
# Routes
# -------------------------

@app.route("/", methods=["GET", "POST"])
def home():
    login_form = LoginForm()
    signup_form = SignupForm()
    forgot_form = ForgotPasswordForm()

    # -------------------------
    # LOGIN
    # -------------------------
    if login_form.validate_on_submit() and login_form.submit.data:
        user = Usuario.query.filter_by(username=login_form.username.data).first()
        if user and user.check_password(login_form.password.data):
            login_user(user)
            flash(f"Bem-vindo, {user.username}!", "success")
            next_url = request.args.get("next") or url_for("lista_aventuras")
            return redirect(next_url)
        flash("Usuário ou senha incorretos.", "danger")
        return redirect(url_for("home"))

    # Obs: signup_form e forgot_form não são tratados aqui.
    return render_template(
        "home.html",
        login_form=login_form,
        signup_form=signup_form,
        forgot_form=forgot_form
    )


@app.route("/signup", methods=["POST"])
def signup():
    form = SignupForm()
    if form.validate_on_submit():
        username = form.username.data
        email = form.email.data
        password = form.password1.data

        existente = Usuario.query.filter(
            (Usuario.username == username) | (Usuario.email == email)
        ).first()

        if existente:
            flash("Usuário ou e-mail já cadastrado!", "danger")
            return redirect(url_for("home"))
        else:
            novo = Usuario(username=username, email=email)
            novo.set_password(password)
            db.session.add(novo)
            db.session.commit()
            login_user(novo)
            flash("Cadastro realizado com sucesso!", "success")
            return redirect(url_for("lista_aventuras"))

    flash("Erro ao processar cadastro.", "danger")
    return redirect(url_for("home"))


# -------------------------
# Rota de recuperação
# -------------------------
@app.route("/forgot-password/", methods=["POST"])
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = Usuario.query.filter_by(email=form.email.data).first()
        if user:
            try:
                send_password_reset_email(user)
                flash("Link de redefinição enviado para seu e-mail.", "success")
            except Exception as e:
                flash(f"Erro ao enviar e-mail: {e}", "danger")
        else:
            flash("E-mail não encontrado.", "danger")
    else:
        flash("Formulário inválido.", "danger")
    
    return redirect(url_for("home"))

@app.route("/logout/")
@login_required
def logout():
    logout_user()
    flash("Você saiu da conta.", "info")
    return redirect(url_for("home"))

@app.route("/dashboard")
@login_required
def dashboard():
    participacao = Participacao.query.filter_by(usuario_id=current_user.id).first()

    if not participacao:
        flash("Você ainda não participa de nenhuma aventura.", "warning")
        return redirect(url_for("lista_aventuras"))

    personagem = participacao.personagem
    aventura = participacao.aventura

    mensagens = HistoricoMensagens.query \
        .filter_by(aventura_id=aventura.id) \
        .order_by(HistoricoMensagens.criado_em.asc()) \
        .all()

    ultima_sessao = Sessao.query \
        .filter_by(aventura_id=aventura.id) \
        .order_by(Sessao.criado_em.desc()) \
        .first()

    turno_form = TurnoForm()
    personagem_form = PersonagemForm()  # Usado se personagem for None

    return render_template(
        "dashboard.html",
        personagem=personagem,
        aventura=aventura,
        mensagens=mensagens,
        ultima_sessao=ultima_sessao,
        form=turno_form,
        personagem_form=personagem_form
    )



@app.route("/acao/", methods=["POST"])
@login_required
def acao_jogador():
    acao = request.form.get("acao")
    comando = request.form.get("comando")
    narrativa = session.get("narrativa", [])
    turno = session.get("turno", 1)
    if acao:
        narrativa.append(f"O jogador escolheu: {acao}")
    if comando:
        narrativa.append(f"Você digitou: {comando}")
    narrativa.append(f"Mestre IA responde para o turno {turno}...")
    turno += 1
    session["narrativa"] = narrativa
    session["turno"] = turno
    return redirect(url_for("dashboard"))

# Aventuras CRUD
@app.route("/aventuras/")
@login_required
def lista_aventuras():
    aventuras = Aventura.query.filter_by(criador=current_user).order_by(Aventura.criada_em.desc()).all()
    return render_template("aventuras.html", aventuras=aventuras)

@app.route("/aventuras/nova/", methods=["GET", "POST"])
@login_required
def nova_aventura():
    form = AventuraForm()
    if form.validate_on_submit():
        aventura = Aventura(
            titulo=form.titulo.data,
            descricao=form.descricao.data,
            cenario=form.cenario.data,
            status=form.status.data,
            regras=safe_json(form.regras.data),
            criador=current_user
        )
        db.session.add(aventura)
        db.session.commit()

        # Adicionar o criador como participante
        participacao = Participacao(
            usuario_id=current_user.id,
            aventura_id=aventura.id,
            personagem_id=None,  # Vai criar depois na dashboard
            papel="Jogador"  # ou "Mestre", dependendo do seu sistema
        )
        db.session.add(participacao)
        db.session.commit()

        
        flash("Aventura criada.", "success")
        return redirect(url_for("lista_aventuras"))
    return render_template("nova_aventura.html", form=form)

@app.route("/aventuras/<int:pk>/editar/", methods=["GET", "POST"])
@login_required
def editar_aventura(pk):
    aventura = Aventura.query.get_or_404(pk)
    if aventura.criador_id != current_user.id:
        abort(403)

    form = AventuraForm(
        obj=aventura,
        regras=json.dumps(aventura.regras or {}, indent=2),
    )

    if form.validate_on_submit():
        aventura.titulo = form.titulo.data
        aventura.descricao = form.descricao.data
        aventura.cenario = form.cenario.data
        aventura.status = form.status.data
        aventura.regras = safe_json(form.regras.data)

        db.session.commit()
        flash("Aventura atualizada.", "success")
        return redirect(url_for("lista_aventuras"))

    return render_template("nova_aventura.html", form=form, editando=True)


@app.route("/aventuras/<int:pk>/entrar/")
@login_required
def entrar_aventura(pk):
    aventura = Aventura.query.get_or_404(pk)

    participacao = Participacao.query.filter_by(
        usuario_id=current_user.id,
        aventura_id=aventura.id
    ).first()

    if not participacao:
        nova_participacao = Participacao(
            usuario_id=current_user.id,
            aventura_id=aventura.id,
            personagem_id=None,
            papel="Jogador"
        )
        db.session.add(nova_participacao)
        db.session.commit()

    session["aventura_id"] = aventura.id
    flash(f"Entrou na aventura: {aventura.titulo}", "success")
    return redirect(url_for("dashboard"))

@app.route("/aventuras/<int:pk>/excluir/", methods=["GET", "POST"])
@login_required
def excluir_aventura(pk):
    aventura = Aventura.query.get_or_404(pk)
    if aventura.criador_id != current_user.id:
        abort(403)
    if request.method == "POST":
        db.session.delete(aventura)
        db.session.commit()
        flash("Aventura excluída.", "success")
        return redirect(url_for("lista_aventuras"))
    return render_template("confirma_exclusao.html", aventura=aventura)




@app.route("/reset/<token>/", methods=["GET", "POST"])
def password_reset_confirm(token):
    try:
        email = serializer.loads(token, salt="password-reset-salt", max_age=3600)
    except Exception:
        flash("Token inválido ou expirado.", "danger")
        return redirect(url_for("home"))

    user = Usuario.query.filter_by(email=email).first_or_404()
    form = SetPasswordForm()

    if form.validate_on_submit():
        errors = validate_password_rules(form.new_password1.data)
        if errors:
            for e in errors:
                flash(e, "danger")
            return redirect(url_for("password_reset_confirm", token=token))

        user.set_password(form.new_password1.data)
        db.session.commit()
        flash("Senha redefinida com sucesso.", "success")
        return render_template("password_reset_complete.html")

    return render_template("password_reset_confirm.html", form=form)


@app.route("/sobre/")
def sobre():
    return render_template("sobre.html")

@app.route("/contato/")
def contato():
    return render_template("contato.html")

@app.route("/servicos/")
def servicos():
    return render_template("servicos.html")



'''
@app.route("/db_reset")
def db_reset():
    try:
        # Lista das tabelas do seu models.py com prefixo core_
        tabelas = [
            "core_historicomensagens",
            "core_participacao",
            "core_sessao",
            "core_aventura",
            "core_item",
            "core_personagem",
            "core_usuario"
        ]

        # Derruba apenas essas tabelas
        for tabela in tabelas:
            db.session.execute(text(f'DROP TABLE IF EXISTS {tabela} CASCADE'))

        db.session.commit()

        # Recria de acordo com os models atuais
        db.create_all()

        return jsonify({"status": "ok", "msg": "Tabelas core_* resetadas com sucesso!"})

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "erro", "msg": str(e)})
'''


@app.route('/enviar_turno', methods=['POST'])
@login_required
def enviar_turno():
    form = TurnoForm()

    if form.validate_on_submit():
        participacao = Participacao.query.filter_by(usuario_id=current_user.id).first()
        if not participacao:
            flash("Você não está participando de nenhuma aventura.", "danger")
            return redirect(url_for("aventuras"))

        aventura = participacao.aventura
        personagem = participacao.personagem

        # Mensagens anteriores da aventura
        mensagens = HistoricoMensagens.query.filter_by(aventura_id=aventura.id).order_by(HistoricoMensagens.criado_em.asc()).all()

        # Montar prompt com resumo, último turno e ação do jogador
        prompt_parts = []

        if aventura.resumo_atual:
            prompt_parts.append(f"Resumo da aventura até agora:\n{aventura.resumo_atual}")

        if aventura.ultimo_turno:
            prompt_parts.append(f"Último turno:\n{aventura.ultimo_turno.get('texto', '')}")

        if form.contexto.data:
            prompt_parts.append(f"Contexto adicional do jogador:\n{form.contexto.data}")

        prompt_parts.append(f"Ação de {personagem.nome}:\n{form.acao.data}")

        prompt_final = "\n\n".join(prompt_parts)

        # Chamada à OpenAI
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Você é um mestre de RPG, narrando a aventura para os jogadores."},
                    {"role": "user", "content": prompt_final}
                ],
                temperature=0.8,
                max_tokens=800
            )
            resultado_turno = response.choices[0].message.content.strip()

        except Exception as e:
            flash(f"Erro ao processar o turno: {e}", "danger")
            return redirect(url_for("dashboard"))

        # Salvar no banco: Sessao e duas mensagens (jogador + mestre)
        nova_sessao = Sessao(
            aventura_id=aventura.id,
            narrador_ia=resultado_turno,
            acoes_jogadores=[form.acao.data],
            resultado=resultado_turno,
            prompt_usado=prompt_final,
            resposta_bruta=str(response)
        )
        db.session.add(nova_sessao)

        mensagem_jogador = HistoricoMensagens(
            usuario_id=current_user.id,
            aventura_id=aventura.id,
            mensagem=form.acao.data,
            autor=personagem.nome
        )
        db.session.add(mensagem_jogador)

        mensagem_mestre = HistoricoMensagens(
            usuario_id=None,  # IA
            aventura_id=aventura.id,
            mensagem=resultado_turno,
            autor="Mestre IA"
        )
        db.session.add(mensagem_mestre)

        # Atualizar último turno na aventura
        aventura.ultimo_turno = {"texto": resultado_turno}
        db.session.commit()

        flash("Turno enviado e processado com sucesso!", "success")

    else:
        flash("Erro no envio do formulário.", "danger")

    return redirect(url_for("dashboard"))



@app.route("/criar_personagem", methods=["POST"])
@login_required
def criar_personagem():
    form = PersonagemForm()

    if not form.validate_on_submit():
        flash("Erro ao validar o formulário de personagem.", "danger")
        return redirect(url_for("dashboard"))

    participacao = Participacao.query.filter_by(usuario_id=current_user.id).first()
    if not participacao:
        flash("Você não participa de nenhuma aventura.", "danger")
        return redirect(url_for("aventuras"))

    aventura = participacao.aventura

    atributos = {
        "Força": form.forca.data,
        "Destreza": form.destreza.data,
        "Inteligência": form.inteligencia.data
    }

    novo_personagem = Personagem(
        nome=form.nome.data,
        classe=form.classe.data,
        raca=form.raca.data,
        atributos=atributos,
        usuario_id=current_user.id
    )

    db.session.add(novo_personagem)
    db.session.commit()

    participacao.personagem_id = novo_personagem.id
    db.session.commit()

    # Prompt inicial
    import json
    prompt_inicial = f"""
Você é o mestre de uma campanha de RPG de mesa online. Um novo personagem acaba de ser criado e vai iniciar sua jornada.

📜 Aventura:
Título: {aventura.titulo}
Descrição: {aventura.descricao}
Cenário: {aventura.cenario}
Regras relevantes:
{json.dumps(aventura.regras, ensure_ascii=False, indent=2)}

🧝 Personagem criado:
Nome: {novo_personagem.nome}
Classe: {novo_personagem.classe}
Raça: {novo_personagem.raca}
Nível: {novo_personagem.nivel}
Atributos:
{json.dumps(novo_personagem.atributos, ensure_ascii=False, indent=2)}

🎯 Sua tarefa:
Crie a introdução da história dessa aventura incluindo este personagem de forma natural, imersiva e envolvente, sem mencionar que foi gerado por IA. Faça parecer o início de uma sessão de RPG conduzida por um mestre humano.
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Você é um mestre de RPG, narrando a aventura para os jogadores."},
                {"role": "user", "content": prompt_inicial}
            ],
            temperature=0.8,
            max_tokens=800
        )

        narrativa_inicial = response.choices[0].message.content.strip()

        nova_sessao = Sessao(
            aventura_id=aventura.id,
            narrador_ia=narrativa_inicial,
            resultado=narrativa_inicial,
            acoes_jogadores=[],
            prompt_usado=prompt_inicial,
            resposta_bruta=str(response)
        )
        db.session.add(nova_sessao)

        mensagem_mestre = HistoricoMensagens(
            usuario_id=None,
            aventura_id=aventura.id,
            mensagem=narrativa_inicial,
            autor="Mestre IA"
        )
        db.session.add(mensagem_mestre)

        aventura.ultimo_turno = {"texto": narrativa_inicial}
        db.session.commit()

        flash("Personagem criado e aventura iniciada com sucesso!", "success")
    except Exception as e:
        flash(f"Erro ao iniciar a aventura com IA: {e}", "danger")

    return redirect(url_for("dashboard"))






# -------------------------
# CLI convenience
# -------------------------
@app.cli.command("init-db")
def init_db():
    db.create_all()
    if not Usuario.query.filter_by(username="admin").first():
        u = Usuario(username="admin", email="admin@example.com")
        u.set_password("adminpass")
        db.session.add(u)
        db.session.commit()
        print("Superuser 'admin' criado com senha 'adminpass'.")
    print("DB inicializado.")

# -------------------------
# Run
# -------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=os.getenv("DEBUG", "False") == "True")
