# app.py
import os
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, flash, session, abort, jsonify, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from itsdangerous import URLSafeTimedSerializer
from forms import LoginForm, SignupForm, AventuraForm, ForgotPasswordForm, SetPasswordForm, TurnoForm, PersonagemForm
from models import db, Usuario, Personagem, Item, Aventura, Sessao, Participacao, HistoricoMensagens
from sqlalchemy import text
from flask_mail import Mail, Message
from openai import OpenAI


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


client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Token serializer for password reset
serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])

# -------------------------
# Extensions
# -------------------------
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login = "home"
login_manager.login_view = "home"  
login_manager.login_message = "Você precisa estar logado para acessar essa página."
login_manager.login_message_category = "warning"

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
    aventura_id = session.get("aventura_id")

    if not aventura_id:
        flash("Nenhuma aventura ativa. Entre em uma aventura primeiro.", "warning")
        return redirect(url_for("lista_aventuras"))

    participacao = Participacao.query.filter_by(
        usuario_id=current_user.id,
        aventura_id=aventura_id
    ).first()

    if not participacao:
        flash("Você não participa desta aventura.", "warning")
        return redirect(url_for("lista_aventuras"))

    # Personagem atual (caso já tenha um)
    personagem = None
    if participacao.personagem_id:
        personagem = Personagem.query.filter_by(
            id=participacao.personagem_id,
            usuario_id=current_user.id
        ).first()

    # Aventura e dados relacionados
    aventura = participacao.aventura

    mensagens = (
        HistoricoMensagens.query
        .filter_by(aventura_id=aventura.id)
        .order_by(HistoricoMensagens.criado_em.asc())
        .all()
    )

    ultima_sessao = (
        Sessao.query
        .filter_by(aventura_id=aventura.id)
        .order_by(Sessao.criado_em.desc())
        .first()
    )

    turno_form = TurnoForm()
    personagem_form = PersonagemForm()

    # Todos os personagens do usuário nesta aventura
    personagens = (
        Personagem.query
        .join(Participacao)
        .filter(
            Participacao.aventura_id == aventura.id,
            Personagem.usuario_id == current_user.id
        )
        .all()
    )



    # Garante que a aventura tenha regras válidas (evita erro se for None)
    regras = aventura.regras if hasattr(aventura, "regras") and aventura.regras else {
        "erro_critico": 5,
        "erro_normal": 50,
        "acerto_normal": 90,
        "acerto_critico": 100
    }

    return render_template(
        "dashboard.html",
        personagem=personagem,
        personagens=personagens,
        aventura=aventura,
        regras=regras,  # passa regras explícitas também
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
    aventuras = (
        Aventura.query
        .filter_by(criador=current_user)
        .order_by(Aventura.criada_em.desc())
        .all()
    )
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
            regras={
                "erro_critico_max": form.erro_critico_max.data,
                "erro_normal_max": form.erro_normal_max.data,
                "acerto_normal_max": form.acerto_normal_max.data,
                "acerto_critico_min": 100  # sempre fixo em 100 agora
            },
            criador=current_user
        )
        db.session.add(aventura)
        db.session.commit()

        # Adiciona o criador como participante (padrão)
        participacao = Participacao(
            usuario_id=current_user.id,
            aventura_id=aventura.id,
            personagem_id=None,
            papel="Jogador"
        )
        db.session.add(participacao)
        db.session.commit()

        flash("Aventura criada com sucesso.", "success")
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
        erro_critico_max=aventura.regras.get("erro_critico_max", 15),
        erro_normal_max=aventura.regras.get("erro_normal_max", 49),
        acerto_normal_max=aventura.regras.get("acerto_normal_max", 85),
        acerto_critico_min=aventura.regras.get("acerto_critico_min", 100),
    )

    if form.validate_on_submit():
        aventura.titulo = form.titulo.data
        aventura.descricao = form.descricao.data
        aventura.cenario = form.cenario.data
        aventura.status = form.status.data
        aventura.regras = {
            "erro_critico_max": form.erro_critico_max.data,
            "erro_normal_max": form.erro_normal_max.data,
            "acerto_normal_max": form.acerto_normal_max.data,
            "acerto_critico_min": 100  # fixo, não editável
        }

        db.session.commit()
        flash("Aventura atualizada com sucesso.", "success")
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
        flash("Aventura excluída com sucesso.", "success")
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


import json
from flask import current_app

@app.route('/enviar_turno', methods=['POST'])
@login_required
def enviar_turno():
    form = TurnoForm()

    # detecta se a chamada é AJAX (fetch/XHR) ou JSON
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json

    # --- 1) Ler rolagens (suporta vários formatos) ---
    rolagens = []
    try:
        # se cliente enviou JSON no body (ex: fetch(..., body: JSON.stringify({...})))
        if request.is_json:
            payload = request.get_json(silent=True) or {}
            # payload pode ter "rolagens" (lista) ou "rolagem" (single)
            if isinstance(payload, dict):
                rolagens = payload.get("rolagens") or payload.get("rolagem") or []
                # se for string JSON, tentar parsear
                if isinstance(rolagens, str):
                    try:
                        rolagens = json.loads(rolagens)
                    except Exception:
                        rolagens = []
        else:
            # se formulário (FormData) com vários campos 'rolagem[]'
            raw_list = request.form.getlist("rolagem[]")
            if raw_list:
                for item in raw_list:
                    try:
                        rolagens.append(json.loads(item))
                    except Exception:
                        # se não for JSON, guarda como string
                        rolagens.append({"raw": item})
            else:
                # fallback: talvez o cliente tenha enviado 'rolagens' como string JSON única
                raw = request.form.get("rolagens") or request.form.get("rolagem")
                if raw:
                    try:
                        parsed = json.loads(raw)
                        if isinstance(parsed, list):
                            rolagens = parsed
                        elif isinstance(parsed, dict):
                            rolagens = [parsed]
                    except Exception:
                        # não conseguiu parsear - ignora
                        current_app.logger.debug("rolagens: não foi possível parsear campo 'rolagens'")
    except Exception as e:
        current_app.logger.exception("Erro lendo rolagens: %s", e)

    # --- 2) Validar formulário (CSRF etc) ---
    if not form.validate_on_submit():
        # fallback: se não for AJAX, redireciona para dashboard para evitar mostrar JSON cru
        if not is_ajax:
            flash("Erro no envio do formulário.", "danger")
            return redirect(url_for("dashboard"))
        return jsonify({"status": "error", "error": "Erro no envio do formulário."})

    # --- 3) verificar aventura / participação ---
    aventura_id = session.get("aventura_id")
    if not aventura_id:
        if not is_ajax: 
            flash("Nenhuma aventura ativa.", "warning")
            return redirect(url_for("lista_aventuras"))
        return jsonify({"status": "error", "error": "Nenhuma aventura ativa."})

    participacao = Participacao.query.filter_by(usuario_id=current_user.id, aventura_id=aventura_id).first()
    if not participacao:
        if not is_ajax:
            flash("Você não está participando desta aventura.", "warning")
            return redirect(url_for("lista_aventuras"))
        return jsonify({"status": "error", "error": "Você não está participando desta aventura."})

    aventura = participacao.aventura
    personagem = participacao.personagem

    # --- 4) Atualizar checkboxes de personagens ativos ---
    try:
        personagens_usuario = Personagem.query.filter_by(usuario_id=current_user.id).all()
        for p in personagens_usuario:
            marcado = f"personagem_{p.id}" in request.form
            if p.ativo_na_sessao != marcado:
                p.ativo_na_sessao = marcado
                db.session.add(p)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Erro atualizando ativo_na_sessao")

    # --- 5) Personagens ativos na aventura (construir prompt) ---
    personagens_ativos = (
        Personagem.query.join(Participacao)
        .filter(Participacao.aventura_id == aventura.id, Personagem.ativo_na_sessao == True)
        .all()
    )

    prompt_parts = []
    if aventura.resumo_atual:
        prompt_parts.append(f"Resumo da aventura até agora:\n{aventura.resumo_atual}")
    if aventura.ultimo_turno:
        prompt_parts.append(f"Último turno:\n{aventura.ultimo_turno.get('texto', '')}")
    if form.contexto.data:
        prompt_parts.append(f"Contexto adicional do jogador:\n{form.contexto.data}")

    prompt_parts.append(f"Ação de {personagem.nome}:\n{form.acao.data}")

    # anexar rolagens textualmente, se houver
    if rolagens:
        try:
            rolagens_texto = []
            for r in rolagens:
                # r pode ser dicionário com keys varias (personagem_id, valor, resultado, tipo, bonus)
                pid = r.get("personagem_id", r.get("personagem") or r.get("p", "?"))
                valor = r.get("valor", r.get("v", "?"))
                tipo = r.get("tipo", r.get("atributo", ""))
                resultado = r.get("resultado", r.get("texto", r.get("resultado_texto", "")))
                rolagens_texto.append(f"- Personagem {pid} | {tipo} => {valor} ({resultado})")
            prompt_parts.append("Rolagens de dados nesta rodada:\n" + "\n".join(rolagens_texto))
        except Exception:
            current_app.logger.exception("Erro formatando rolagens para prompt")

    if personagens_ativos:
        detalhes_personagens = []
        for p in personagens_ativos:
            atributos_str = ", ".join([f"{k}: {v}" for k, v in (p.atributos or {}).items()])
            detalhes_personagens.append(f"- {p.nome} ({p.classe}, {atributos_str}) - {p.descricao}")
        prompt_parts.append("Personagens ativos na cena:\n" + "\n".join(detalhes_personagens))

    prompt_final = "\n\n".join(prompt_parts)

    current_app.logger.info(f"PROMPT FINAL ENVIADO À IA:\n{prompt_final}")
    
    # --- 6) Chamada IA (mantive seu bloco) ---
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Você é um mestre de RPG, narrando a aventura para os jogadores de forma concisa e interessante."},
                {"role": "user", "content": prompt_final}
            ],
            temperature=0.8,
            max_tokens=800
        )
        resultado_turno = response.choices[0].message.content.strip()
    except Exception as e:
        current_app.logger.exception("Erro OpenAI: %s", e)
        if not is_ajax:
            flash("Erro ao processar o turno (IA).", "danger")
            return redirect(url_for("dashboard"))
        return jsonify({"status": "error", "error": f"Erro ao processar o turno: {e}"})

    # --- 7) Gravar sessão e histórico (igual ao seu fluxo) ---
    try:
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
            usuario_id=None,
            aventura_id=aventura.id,
            mensagem=resultado_turno,
            autor="Mestre IA"
        )
        db.session.add(mensagem_mestre)

        aventura.ultimo_turno = {"texto": resultado_turno}
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Erro gravando sessão/histórico")
        if not is_ajax:
            flash("Erro ao salvar o turno.", "danger")
            return redirect(url_for("dashboard"))
        return jsonify({"status": "error", "error": "Erro ao salvar o turno."})

    # --- 8) Preparar resposta ---
    mensagens = HistoricoMensagens.query.filter_by(aventura_id=aventura.id)\
        .order_by(HistoricoMensagens.criado_em.asc()).all()
    mensagens_serializadas = [
        {"autor": m.autor, "mensagem": m.mensagem, "criado_em": m.criado_em.strftime("%d/%m %H:%M")}
        for m in mensagens
    ]

    if not is_ajax:
        # se o envio foi normal (sem JS), redireciona para dashboard (evita mostrar JSON cru)
        flash("Turno enviado.", "success")
        return redirect(url_for("dashboard"))

    return jsonify({"status": "ok", "mensagens": mensagens_serializadas})






@app.route("/criar_personagem", methods=["POST"])
@login_required
def criar_personagem():
    form = PersonagemForm()
    if not form.validate_on_submit():
        flash("Erro ao validar o formulário de personagem.", "danger")
        return redirect(url_for("dashboard"))

    aventura_id = session.get("aventura_id")
    if not aventura_id:
        flash("Nenhuma aventura ativa.", "warning")
        return redirect(url_for("lista_aventuras"))

    participacao = Participacao.query.filter_by(
        usuario_id=current_user.id,
        aventura_id=aventura_id
    ).first()

    if not participacao:
        flash("Você não participa desta aventura.", "danger")
        return redirect(url_for("lista_aventuras"))

    aventura = participacao.aventura

    # Limites de atributos
    forca = max(1, min(99, form.forca.data))
    destreza = max(1, min(99, form.destreza.data))
    inteligencia = max(1, min(99, form.inteligencia.data))
    total_pontos = forca + destreza + inteligencia

    if total_pontos > 200:
        flash("Distribuição de atributos inválida! O total de pontos deve ser até 50 adicionais à base.", "danger")
        return redirect(url_for("dashboard"))

    atributos = {"Força": forca, "Destreza": destreza, "Inteligência": inteligencia}

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

    # Criar prompt inicial e gerar narrativa
    import json
    prompt_inicial = f"""
Você é o mestre de uma campanha de RPG de mesa online. Um novo personagem acaba de ser criado.

Aventura: {aventura.titulo}
Descrição: {aventura.descricao}
Cenário: {aventura.cenario}
Regras relevantes: {json.dumps(aventura.regras, ensure_ascii=False, indent=2)}

Personagem criado: {novo_personagem.nome}, {novo_personagem.classe}, {novo_personagem.raca}
Atributos: {json.dumps(novo_personagem.atributos, ensure_ascii=False, indent=2)}

Crie a introdução da história desta aventura incluindo este personagem levando em consideração as informações da aventura de forma concisa e interessante, sem mencionar IA.
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Você é um mestre de RPG narrando a aventura."},
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


@app.route("/add_personagem", methods=["POST"])
@login_required
def add_personagem():
    form = PersonagemForm()
    if form.validate_on_submit():
        # Captura personagem_id do hidden field para edição
        personagem_id = request.form.get("personagem_id")

        # Validar atributos
        forca = max(1, min(99, form.forca.data))
        destreza = max(1, min(99, form.destreza.data))
        inteligencia = max(1, min(99, form.inteligencia.data))

        total_pontos = forca + destreza + inteligencia
        if total_pontos > 200:
            flash("Distribuição de atributos inválida! O total de pontos deve ser até 200.", "danger")
            return redirect(url_for("dashboard"))

        atributos = {
            "Força": forca,
            "Destreza": destreza,
            "Inteligência": inteligencia
        }

        if personagem_id:  # EDITAR existente
            personagem = Personagem.query.get_or_404(personagem_id)
            personagem.nome = form.nome.data
            personagem.classe = form.classe.data
            personagem.raca = form.raca.data
            personagem.atributos = atributos
            personagem.descricao = form.descricao.data if hasattr(form, "descricao") else None
            db.session.commit()
            flash("Personagem atualizado com sucesso!", "success")
        else:  # CRIAR novo
            novo = Personagem(
                nome=form.nome.data,
                classe=form.classe.data,
                raca=form.raca.data,
                atributos=atributos,
                descricao=form.descricao.data if hasattr(form, "descricao") else None,
                ativo_na_sessao=False,  # começa fora da cena
                usuario_id=current_user.id
            )
            db.session.add(novo)
            db.session.commit()

            # Criar participação na aventura ativa
            aventura_id = session.get("aventura_id")
            if aventura_id:
                participacao = Participacao(
                    usuario_id=current_user.id,
                    personagem_id=novo.id,
                    aventura_id=aventura_id
                )
                db.session.add(participacao)
                db.session.commit()

            flash("Novo personagem criado e vinculado à aventura!", "success")
    else:
        flash("Erro ao criar/editar personagem. Verifique os dados.", "danger")

    return redirect(url_for("dashboard"))




@app.route("/aumentar_tamanho_autor")
def aumentar_tamanho_autor():
    try:
        # ALTER TABLE para mudar o tipo da coluna autor para VARCHAR(100)
        db.session.execute(
            text("ALTER TABLE core_historicomensagens ALTER COLUMN autor TYPE VARCHAR(100)")
        )
        db.session.commit()
        return "Coluna 'autor' atualizada para VARCHAR(100) com sucesso!"
    except Exception as e:
        db.session.rollback()
        return f"Erro: {e}"




# Rota para excluir personagem
@app.route("/excluir_personagem/<int:personagem_id>", methods=["POST"])
def excluir_personagem(personagem_id):
    personagem = Personagem.query.get_or_404(personagem_id)
    try:
        db.session.delete(personagem)
        db.session.commit()
        flash("Personagem excluído com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao excluir: {e}", "danger")

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
