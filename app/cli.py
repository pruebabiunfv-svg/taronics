"""Comandos administrativos. Evita contraseñas iniciales en el repositorio."""
import click
from flask.cli import with_appcontext
from app.models.database import execute, query
from app.models.auth import hash_password

def setup_cli(app):
    @app.cli.command('create-admin')
    @click.option('--name', prompt='Nombre completo')
    @click.option('--email', prompt='Correo de administrador')
    @click.password_option(confirmation_prompt=True)
    @with_appcontext
    def create_admin(name, email, password):
        """Crea un administrador inicial con contraseña robusta."""
        email = email.strip().lower()
        if not name.strip() or '@' not in email or len(password) < 12:
            raise click.ClickException('Indique nombre, email y contraseña de al menos 12 caracteres.')
        if query('SELECT id FROM usuarios WHERE email=?', (email,), one=True):
            raise click.ClickException('El correo ya está registrado.')
        execute('INSERT INTO usuarios(nombre,email,password,rol,laboratorio) VALUES(?,?,?,?,?)',
                (name.strip(),email,hash_password(password),'admin',''))
        click.echo('Administrador creado. No se ha mostrado ni guardado la contraseña en texto plano.')

    @app.cli.command('seed-example-catalog')
    @with_appcontext
    def seed_example_catalog():
        """Añade registros DEMO a los catálogos únicamente en desarrollo."""
        from flask import current_app
        from app.models.database import get_db
        from app.models.catalog_examples import seed_catalog_examples
        if not current_app.debug:
            raise click.ClickException('Este comando solo está permitido en el entorno de desarrollo.')
        if not click.confirm('¿Agregar datos de ejemplo ficticios DEMO a la base actual de desarrollo?'):
            return
        with get_db() as conn:
            seed_catalog_examples(conn,allow_existing=True)
        click.echo('Catálogos DEMO añadidos de manera idempotente. No son válidos para certificados reales.')

    @app.cli.command('test-gmail')
    @click.option('--to', 'destination', prompt='Correo de destino de prueba')
    @with_appcontext
    def test_gmail(destination):
        """Envía mensaje de diagnóstico SMTP (sin certificados ni datos de clientes)."""
        from flask import current_app
        from app.services.mailer import parse_recipients
        from email.message import EmailMessage
        import smtplib
        import ssl
        try:
            to = parse_recipients(destination)
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc
        config = current_app.config
        user = config.get('MAIL_USERNAME')
        password = config.get('MAIL_PASSWORD')
        sender = config.get('MAIL_DEFAULT_SENDER')
        if not user or not password or not sender:
            raise click.ClickException('Configure MAIL_USERNAME, MAIL_PASSWORD y MAIL_DEFAULT_SENDER.')
        if not click.confirm('¿Enviar un correo real de prueba a ' + ', '.join(to) + '?'):
            return
        message = EmailMessage()
        message['From'] = sender
        message['To'] = ', '.join(to)
        message['Subject'] = 'Tatronics CalibPro - Prueba de Gmail SMTP'
        message.set_content('Si recibes este mensaje, el servidor SMTP de Gmail aceptó el envío de prueba de CalibPro.')
        try:
            port = int(config.get('MAIL_PORT',587))
            host = config.get('MAIL_SERVER','smtp.gmail.com')
            ctx=ssl.create_default_context()
            if port == 465:
                with smtplib.SMTP_SSL(host,port,timeout=20,context=ctx) as smtp:
                    smtp.login(user,password); smtp.send_message(message)
            elif port == 587:
                with smtplib.SMTP(host,port,timeout=20) as smtp:
                    smtp.ehlo(); smtp.starttls(context=ctx); smtp.ehlo()
                    smtp.login(user,password); smtp.send_message(message)
            else:
                raise ValueError('Use puerto 465 o 587.')
        except (OSError,smtplib.SMTPException,ValueError) as exc:
            raise click.ClickException(f'Gmail no aceptó el envío: {type(exc).__name__}.') from exc
        click.echo('Mensaje aceptado por Gmail SMTP. Verifique la recepción en su bandeja.')
