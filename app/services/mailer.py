"""Entrega SMTP Gmail. Nunca informa éxito si el servidor no aceptó el mensaje."""
from __future__ import annotations
from email.message import EmailMessage
from email.utils import parseaddr
import ssl
import smtplib


def parse_recipients(value):
    result = []
    for raw in (value or '').split(','):
        raw = raw.strip()
        if not raw:
            continue
        name, addr = parseaddr(raw)
        if name or addr != raw or '@' not in addr or addr.count('@') != 1 or any(c in addr for c in '\r\n '):
            raise ValueError('Formato de correo no válido.')
        if len(addr) > 254 or len(addr.rsplit('@',1)[1]) < 3 or '.' not in addr.rsplit('@',1)[1]:
            raise ValueError('Dirección de correo no válida.')
        result.append(addr)
    if not result:
        raise ValueError('Se requiere al menos un destinatario.')
    if len(result) > 5:
        raise ValueError('Máximo cinco destinatarios por campo.')
    return result


def send_pdf_mail(config, *, to, cc, subject, body, pdf_data, filename):
    sender = (config.get('MAIL_DEFAULT_SENDER') or '').strip()
    username = (config.get('MAIL_USERNAME') or '').strip()
    password = config.get('MAIL_PASSWORD') or ''
    if not username or not password or not sender:
        raise RuntimeError('Gmail no está configurado. Revisa las variables MAIL_* del servidor.')
    tos = parse_recipients(to)
    ccs = parse_recipients(cc) if cc and cc.strip() else []
    if len(subject or '') > 180 or '\r' in (subject or '') or '\n' in (subject or ''):
        raise ValueError('Asunto no válido.')
    if len(body or '') > 5000:
        raise ValueError('Mensaje demasiado extenso.')
    msg = EmailMessage()
    msg['From'] = sender
    msg['To'] = ', '.join(tos)
    if ccs:
        msg['Cc'] = ', '.join(ccs)
    msg['Subject'] = subject or 'Certificado de calibración Tatronics'
    msg.set_content(body or 'Adjuntamos su certificado de calibración aprobado.')
    msg.add_attachment(pdf_data, maintype='application', subtype='pdf', filename=filename)
    host = config.get('MAIL_SERVER', 'smtp.gmail.com')
    port = int(config.get('MAIL_PORT', 587))
    if port not in (465, 587):
        raise RuntimeError('El SMTP requiere puerto seguro 465 o 587.')
    ctx = ssl.create_default_context()
    timeout = 20
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=timeout, context=ctx) as smtp:
            smtp.login(username, password)
            smtp.send_message(msg, from_addr=sender, to_addrs=tos+ccs)
    else:
        with smtplib.SMTP(host, port, timeout=timeout) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ctx)
            smtp.ehlo()
            smtp.login(username, password)
            smtp.send_message(msg, from_addr=sender, to_addrs=tos+ccs)
    return tos + ccs
