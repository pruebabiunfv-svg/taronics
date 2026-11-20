"""SMTP con simulador local; nunca envía correo real al ejecutarse."""
from app.services.mailer import parse_recipients, send_pdf_mail
import pytest


def test_recipient_validation():
    assert parse_recipients('uno@example.com,dos@example.com')==['uno@example.com','dos@example.com']
    with pytest.raises(ValueError): parse_recipients('malicioso@example.com\nBcc:evil@example.com')
    with pytest.raises(ValueError): parse_recipients('')


def test_smtp_starttls_and_pdf_attachment(monkeypatch):
    class FakeSMTP:
        sent=None
        def __init__(self,host,port,timeout=None):
            assert host=='smtp.gmail.com' and port==587
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def ehlo(self): pass
        def starttls(self,context): assert context
        def login(self,username,password):
            assert username=='laboratorio@gmail.com' and password=='app-password-de-prueba'
        def send_message(self,msg,from_addr,to_addrs):
            assert msg['Subject']=='Certificado de prueba'
            assert msg.get_body(preferencelist=('plain',)).get_content()=='Saludos\n'
            assert msg.get_payload()[-1].get_content_type()=='application/pdf'
            assert msg.get_payload()[-1].get_payload(decode=True)==b'%PDF-FAKE-TEST'
    import app.services.mailer as mailer
    monkeypatch.setattr(mailer.smtplib,'SMTP',FakeSMTP)
    sent=send_pdf_mail({'MAIL_SERVER':'smtp.gmail.com','MAIL_PORT':587,'MAIL_USERNAME':'laboratorio@gmail.com',
           'MAIL_PASSWORD':'app-password-de-prueba','MAIL_DEFAULT_SENDER':'laboratorio@gmail.com'},
           to='cliente@example.com',cc='',subject='Certificado de prueba',body='Saludos',
           pdf_data=b'%PDF-FAKE-TEST',filename='CERT-001.pdf')
    assert sent==['cliente@example.com']
