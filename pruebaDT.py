import smtplib
from email.message import EmailMessage

def sms_alert(asunto, cuerpo, para):
    msg = EmailMessage()
    msg.set_content(cuerpo)
    msg['subject'] = asunto
    msg['to'] = para

    user = 'gbecerra0407@gmail.com'
    msg['from'] = user
    password = 'raairuxvolunmali'

    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(user, password)
    server.send_message(msg)

    server.quit()
