from email.mime.image import MIMEImage
from pathlib import Path

from django.contrib.staticfiles import finders
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


def enviar_correo_cliente(
    asunto,
    mensaje,
    destinatarios,
    contexto,
    fail_silently=False,
):
    correo = EmailMultiAlternatives(
        subject=asunto,
        body=mensaje,
        from_email=None,
        to=destinatarios,
    )
    correo.attach_alternative(
        render_to_string(
            "tallermami/correo_cliente.html",
            contexto,
        ),
        "text/html",
    )

    ruta_logo = finders.find("images/Imagen molina henze.jpg")
    if ruta_logo is None:
        raise FileNotFoundError(
            "No se encontró el logo del taller en los archivos estáticos."
        )

    with Path(ruta_logo).open("rb") as archivo_logo:
        imagen_logo = MIMEImage(archivo_logo.read(), _subtype="jpeg")

    imagen_logo.add_header("Content-ID", "<logo-taller>")
    imagen_logo.add_header(
        "Content-Disposition",
        "inline",
        filename="molina-henze.jpg",
    )
    correo.attach(imagen_logo)

    return correo.send(fail_silently=fail_silently)
