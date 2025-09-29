from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, SelectField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional

# -------------------------
# Forms
# -------------------------

class TurnoForm(FlaskForm):
    acao = TextAreaField("Ação do Jogador", validators=[DataRequired(), Length(min=1, max=1000)])
    contexto = TextAreaField("Contexto do Turno", validators=[Length(max=2000)])
    submit = SubmitField("Enviar Turno")

class LoginForm(FlaskForm):
    username = StringField("Usuário", validators=[DataRequired()])
    password = PasswordField("Senha", validators=[DataRequired()])
    submit = SubmitField("Entrar")

class SignupForm(FlaskForm):
    username = StringField("Usuário", validators=[DataRequired(), Length(min=3, max=150)])
    email = StringField("E-mail", validators=[DataRequired(), Email()])
    password1 = PasswordField("Senha", validators=[DataRequired(), Length(min=6)])
    password2 = PasswordField("Confirme a senha", validators=[DataRequired(), EqualTo('password1')])
    submit = SubmitField("Cadastrar")

class AventuraForm(FlaskForm):
    titulo = StringField("Título", validators=[DataRequired()])
    descricao = TextAreaField("Descrição", validators=[DataRequired()])
    cenario = StringField("Cenário", validators=[DataRequired()])

    # extras
    status = SelectField(
        "Status",
        choices=[("preparacao", "Preparação"),
                 ("andamento", "Em Andamento"),
                 ("concluida", "Concluída")],
        validators=[DataRequired()]
    )
    regras = TextAreaField("Regras (JSON)", validators=[Optional()])
    resumo_atual = TextAreaField("Resumo Atual", validators=[Optional()])
    ultimo_turno = TextAreaField("Último Turno (JSON)", validators=[Optional()])
    metadados = TextAreaField("Metadados (JSON)", validators=[Optional()])
    estado_personagens = TextAreaField("Estado dos Personagens (JSON)", validators=[Optional()])
    estado_aventura = TextAreaField("Estado da Aventura (JSON)", validators=[Optional()])

    submit = SubmitField("Salvar")

class ForgotPasswordForm(FlaskForm):
    email = StringField("E-mail", validators=[DataRequired(), Email()])
    submit = SubmitField("Enviar")

class SetPasswordForm(FlaskForm):
    new_password1 = PasswordField("Nova senha", validators=[DataRequired(), Length(min=6)])
    new_password2 = PasswordField("Confirmar nova senha", validators=[DataRequired(), EqualTo('new_password1')])
    submit = SubmitField("Salvar nova senha")
