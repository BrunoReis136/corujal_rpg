# -------------------------
# Forms
# -------------------------
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
    submit = SubmitField("Salvar")

class ForgotPasswordForm(FlaskForm):
    email = StringField("E-mail", validators=[DataRequired(), Email()])
    submit = SubmitField("Enviar")

class SetPasswordForm(FlaskForm):
    new_password1 = PasswordField("Nova senha", validators=[DataRequired(), Length(min=6)])
    new_password2 = PasswordField("Confirmar nova senha", validators=[DataRequired(), EqualTo('new_password1')])
    submit = SubmitField("Salvar nova senha")
