import smtplib

user = "brunohreis136@gmail.com"
app_password = "ghnjadegvmvslyst"

try:
    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(user, app_password)
        print("Login bem-sucedido!")
except Exception as e:
    print("Erro:", e)
