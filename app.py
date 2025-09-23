# app.py
import os
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, flash, session, abort, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
from forms import LoginForm, SignupForm, AventuraForm, ForgotPasswordForm, SetPasswordForm
from models import db, Usuario, Personagem, Item, Aventura, Sessao, Participacao, HistoricoMensagens
from sqlalchemy import text

import json

# -------------------------
# Config
# -------------------------
app = Flask(__name__)


app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///db.sqlite3")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

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

    # -------------------------
    # SIGNUP
    # -------------------------
    if signup_form.validate_on_submit() and signup_form.submit.data:
        username = signup_form.username.data
        email = signup_form.email.data
        password = signup_form.password1.data

        existente = Usuario.query.filter(
            (Usuario.username == username) | (Usuario.email == email)
        ).first()

        if existente:
            flash("Usuário ou e-mail já cadastrado!", "danger")
        else:
            novo = Usuario(username=username, email=email)
            novo.set_password(password)
            db.session.add(novo)
            db.session.commit()
            login_user(novo)
            flash("Cadastro realizado com sucesso!", "success")
            return redirect(url_for("lista_aventura"))

    # -------------------------
    # FORGOT PASSWORD
    # -------------------------
    if forgot_form.validate_on_submit() and forgot_form.submit.data:
        user = Usuario.query.filter_by(email=forgot_form.email.data).first()
        if user:
            # você já tem a função send_password_reset_email
            send_password_reset_email(user)
            flash("Link de redefinição enviado para seu e-mail.", "success")
        else:
            flash("E-mail não encontrado.", "danger")
        return redirect(url_for("home"))

    return render_template(
        "home.html",
        login_form=login_form,
        signup_form=signup_form,
        forgot_form=forgot_form
    )


@app.route("/logout/")
@login_required
def logout():
    logout_user()
    flash("Você saiu da conta.", "info")
    return redirect(url_for("home"))

@app.route("/dashboard/")
@login_required
def dashboard():
    narrativa = session.get("narrativa", ["Bem-vindo à aventura, herói!", "O mestre IA aguarda sua primeira ação."])
    jogador = {"hp": 100, "mp": 50}
    turno = session.get("turno", 1)
    return render_template("dashboard.html", narrativa=narrativa, jogador=jogador, turno=turno)

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
    aventuras = Aventura.query.filter_by(criador_id= current_user).order_by(Aventura.criada_em.desc()).all()
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

# -------------------------
# Password reset flow
# -------------------------
def send_password_reset_email(user):
    token = serializer.dumps(user.email, salt="password-reset-salt")
    reset_url = url_for("password_reset_confirm", token=token, _external=True)

    msg = Message(
        subject="Redefinição de senha",
        recipients=[user.email]
    )
    msg.html = render_template(
        "password_reset_email.html",
        user=user,
        reset_url=reset_url
    )
    mail.send(msg)

@app.route("/forgot-password/", methods=["POST"])
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = Usuario.query.filter_by(email=form.email.data).first()
        if user:
            send_password_reset_email(user)
            flash("Link de redefinição enviado para seu e-mail.", "success")
        else:
            flash("E-mail não encontrado.", "danger")
    return redirect(url_for("home"))

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
        return redirect(url_for("home"))
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
