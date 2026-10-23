from django.conf import settings
from django.db import migrations


def vincular_turnos_sin_cliente(apps, schema_editor):
    Cliente = apps.get_model("tallermami", "Cliente")
    Turno = apps.get_model("tallermami", "Turno")
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    Vehiculo = apps.get_model("tallermami", "Vehiculo")
    db_alias = schema_editor.connection.alias

    turnos = Turno.objects.using(db_alias).filter(
        cliente_id__isnull=True,
        usuario_id__isnull=False,
    )
    for turno in turnos.iterator():
        usuario = User.objects.using(db_alias).filter(
            pk=turno.usuario_id
        ).first()
        if usuario is None:
            continue

        cliente = Cliente.objects.using(db_alias).filter(
            usuario_id=usuario.pk
        ).first()
        email = (usuario.email or "").strip()
        if cliente is None and email:
            clientes = Cliente.objects.using(db_alias).filter(
                email__iexact=email
            )
            if clientes.count() == 1:
                candidato = clientes.first()
                if candidato.usuario_id in (None, usuario.pk):
                    cliente = candidato

        if cliente is None:
            cliente = Cliente.objects.using(db_alias).create(
                nombre=usuario.first_name or usuario.username,
                apellido=usuario.last_name or "",
                email=email,
                telefono="",
                usuario_id=usuario.pk,
            )
        elif cliente.usuario_id is None:
            cliente.usuario_id = usuario.pk
            cliente.save(using=db_alias, update_fields=["usuario"])

        vehiculo = Vehiculo.objects.using(db_alias).filter(
            cliente_id=cliente.pk,
            patente__iexact=turno.patente,
        ).first()
        if vehiculo is None:
            vehiculo_original = Vehiculo.objects.using(db_alias).filter(
                pk=turno.vehiculo_registrado_id
            ).first()
            vehiculo = Vehiculo.objects.using(db_alias).create(
                cliente_id=cliente.pk,
                marca=turno.marca or (
                    vehiculo_original.marca if vehiculo_original else ""
                ),
                modelo=turno.modelo or (
                    vehiculo_original.modelo
                    if vehiculo_original
                    else turno.vehiculo
                ),
                anio=(
                    turno.anio
                    if turno.anio is not None
                    else (
                        vehiculo_original.anio
                        if vehiculo_original
                        else None
                    )
                ),
                patente=turno.patente,
            )

        turno.cliente_id = cliente.pk
        turno.vehiculo_registrado_id = vehiculo.pk
        turno.save(
            using=db_alias,
            update_fields=["cliente", "vehiculo_registrado"],
        )


class Migration(migrations.Migration):

    dependencies = [
        ("tallermami", "0010_alter_cliente_email_alter_cliente_telefono"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(
            vincular_turnos_sin_cliente,
            migrations.RunPython.noop,
        ),
    ]
