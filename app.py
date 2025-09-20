# app.py
import os
from datetime import datetime
from flask import (
    Flask, render_template, redirect, url_for, request, flash, session, abort
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, login_user, logout_user, login_required, current_user, UserMixin
)
from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, SubmitField, TextAreaField, SelectField, HiddenField
)
from wtforms.validators import DataRequired, Email, EqualTo, Length
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer
from flask_mail import Mail, Message
from forms import LoginForm,SignupForm, AventuraForm,ForgotPasswordForm, SetPasswordForm
from models import Usuario, Personagem, Item, Aventura, Sessao, Participacao, HistoricoMensagens,

# -------------------------
# Config
# -------------------------
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")
# Database: either Postgres via env or local sqlite
if os.getenv("POSTGRES_HOST") and os.getenv("POSTGRES_DB"):
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}"
        f"@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT', '5432')}/{os.getenv('POSTGRES_DB')}"
    )
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///db.sqlite3"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Mail
app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER", "smtp.gmail.com")
app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", 587))
app.config["MAIL_USE_TLS"] = os.getenv("MAIL_USE_TLS", "True") == "True"
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USER")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASS")
app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_FOR", app.config["MAIL_USERNAME"])

# Token serializer for password reset
serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "home"
mail = Mail(app)




# -------------------------
# Login manager
# -------------------------
@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# -------------------------
# Helper: password validation (simple)
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
# Views / Routes
# -------------------------
@app.route("/", methods=["GET", "POST"])
def home():
    login_form = LoginForm()
    signup_form = SignupForm()
    forgot_form = ForgotPasswordForm()

    # login
    if login_form.validate_on_submit() and login_form.submit.data:
        username = login_form.username.data
        pw = login_form.password.data
        user = Usuario.query.filter_by(username=username).first()
        if user and user.check_password(pw):
            login_user(user)
            flash(f"Bem-vindo, {user.username}!", "success")
            next_url = request.args.get("next") or url_for("lista_aventuras")
            return redirect(next_url)
        flash("Usuário ou senha incorretos.", "danger")
        return redirect(url_for("home"))

    # signup
    if signup_form.validate_on_submit() and signup_form.submit.data:
        username = signup_form.username.data
        email = signup_form.email.data
        password1 = signup_form.password1.data
        if Usuario.query.filter_by(username=username).first():
            flash("Usuário já existe.", "danger")
            return redirect(url_for("home"))
        errors = validate_password_rules(password1)
        if errors:
            for e in errors:
                flash(e, "danger")
            return redirect(url_for("home"))
        user = Usuario(username=username, email=email)
        user.set_password(password1)
        db.session.add(user)
        db.session.commit()
        flash("Cadastro realizado com sucesso! Faça login.", "success")
        return redirect(url_for("home"))

    # forgot password (form submit separate action preferred)
    return render_template("core/home.html", login_form=login_form, signup_form=signup_form, forgot_form=forgot_form)

@app.route("/login/", methods=["POST"])
def login_route():
    form = LoginForm()
    if form.validate_on_submit():
        user = Usuario.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash("Bem-vindo!", "success")
            return redirect(url_for("lista_aventuras"))
    flash("Usuário ou senha incorretos.", "danger")
    return redirect(url_for("home"))

@app.route("/signup/", methods=["POST"])
def signup_route():
    form = SignupForm()
    if form.validate_on_submit():
        if Usuario.query.filter_by(username=form.username.data).first():
            flash("Usuário já existe.", "danger")
            return redirect(url_for("home"))
        errors = validate_password_rules(form.password1.data)
        if errors:
            for e in errors:
                flash(e, "danger")
            return redirect(url_for("home"))
        user = Usuario(username=form.username.data, email=form.email.data)
        user.set_password(form.password1.data)
        db.session.add(user)
        db.session.commit()
        flash("Cadastro realizado com sucesso! Faça login.", "success")
    return redirect(url_for("home"))

@app.route("/logout/")
@login_required
def logout_view():
    logout_user()
    flash("Você saiu da conta.", "info")
    return redirect(url_for("home"))

@app.route("/dashboard/")
@login_required
def dashboard():
    narrativa = session.get("narrativa", [
        "Bem-vindo à aventura, herói!",
        "O mestre IA aguarda sua primeira ação."
    ])
    jogador = {"hp": 100, "mp": 50}
    turno = session.get("turno", 1)
    return render_template("core/dashboard.html", narrativa=narrativa, jogador=jogador, turno=turno)

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
    aventuras = Aventura.query.order_by(Aventura.criada_em.desc()).all()
    return render_template("core/aventuras.html", aventuras=aventuras)

@app.route("/aventuras/nova/", methods=["GET", "POST"])
@login_required
def nova_aventura():
    form = AventuraForm()
    if form.validate_on_submit():
        aventura = Aventura(
            titulo=form.titulo.data,
            descricao=form.descricao.data,
            cenario=form.cenario.data,
            status="preparacao",
            criador=current_user
        )
        db.session.add(aventura)
        db.session.commit()
        flash("Aventura criada.", "success")
        return redirect(url_for("lista_aventuras"))
    return render_template("core/nova_aventura.html", form=form)

@app.route("/aventuras/<int:pk>/editar/", methods=["GET", "POST"])
@login_required
def editar_aventura(pk):
    aventura = Aventura.query.get_or_404(pk)
    if aventura.criador_id != current_user.id:
        abort(403)
    form = AventuraForm(obj=aventura)
    if form.validate_on_submit():
        aventura.titulo = form.titulo.data
        aventura.descricao = form.descricao.data
        aventura.cenario = form.cenario.data
        db.session.commit()
        flash("Aventura atualizada.", "success")
        return redirect(url_for("lista_aventuras"))
    return render_template("core/nova_aventura.html", form=form, editando=True)

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
    return render_template("core/confirma_exclusao.html", aventura=aventura)

# -------------------------
# Password reset flow (itsdangerous token, email with link)
# -------------------------
def send_password_reset_email(user):
    token = serializer.dumps(user.email, salt="password-reset-salt")
    reset_url = url_for("password_reset_confirm", token=token, _external=True)
    subject = "Redefinição de senha"
    body = f"Olá {user.username},\n\nPara redefinir sua senha clique no link abaixo:\n\n{reset_url}\n\nSe você não pediu, ignore este email."
    msg = Message(subject=subject, recipients=[user.email], body=body)
    mail.send(msg)

@app.route("/forgot-password/", methods=["POST"])
def forgot_password_view():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        email = form.email.data
        user = Usuario.query.filter_by(email=email).first()
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
        pw = form.new_password1.data
        errors = validate_password_rules(pw)
        if errors:
            for e in errors:
                flash(e, "danger")
            return redirect(url_for("password_reset_confirm", token=token))
        user.set_password(pw)
        db.session.commit()
        flash("Senha redefinida com sucesso.", "success")
        return redirect(url_for("home"))

    return render_template("core/password_reset_confirm.html", form=form)

# -------------------------
# Small utility route: dbinfo (like you requested)
# -------------------------
@app.route("/dbinfo/")
def dbinfo():
    engine = app.config["SQLALCHEMY_DATABASE_URI"]
    try:
        tables = [t[0] for t in db.engine.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public';"
        )]
    except Exception as e:
        tables = [f"Erro: {e}"]
    return render_template("core/dbinfo.html", engine=engine, tables=tables)

# -------------------------
# CLI convenience
# -------------------------
@app.cli.command("init-db")
def init_db():
    """Cria o banco e um superuser de teste (popula)"""
    db.create_all()
    if not Usuario.query.filter_by(username="admin").first():
        u = Usuario(username="admin", email="admin@example.com", is_staff=True, is_superuser=True)
        u.set_password("adminpass")
        db.session.add(u)
        db.session.commit()
        print("Superuser 'admin' criado com senha 'adminpass' (troque depois).")
    print("DB inicializado.")

# -------------------------
# Run
# -------------------------
if __name__ == "__main__":
    # Cria tabelas automaticamente em dev
    db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=os.getenv("DEBUG", "True") == "True")
