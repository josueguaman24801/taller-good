import django.utils.timezone
from django.db import migrations


def crear_ordenes_existentes(apps, schema_editor):
    OrdenTrabajo = apps.get_model("tallermami", "OrdenTrabajo")
    Turno = apps.get_model("tallermami", "Turno")
    db_alias = schema_editor.connection.alias
    estados_con_trabajo = [
        "recibido",
        "diagnostico",
        "reparacion",
        "esperando_repuesto",
        "finalizado",
        "entregado",
        "presupuesto_pendiente",
        "presupuesto_aceptado",
        "presupuesto_rechazado",
    ]

    turnos = Turno.objects.using(db_alias).filter(
        estado__in=estados_con_trabajo,
        cliente_id__isnull=False,
        vehiculo_registrado_id__isnull=False,
    )
    for turno in turnos.iterator():
        fecha_ingreso = django.utils.timezone.localtime(
            turno.fecha_turno
        ).date()
        OrdenTrabajo.objects.using(db_alias).get_or_create(
            turno_id=turno.pk,
            defaults={
                "vehiculo_id": turno.vehiculo_registrado_id,
                "cliente_id": turno.cliente_id,
                "servicio_id": turno.servicio_id,
                "fecha_ingreso": fecha_ingreso,
                "estado": turno.estado,
                "trabajador_id": turno.trabajador_id,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("tallermami", "0008_alter_trabajador_options_alter_trabajo_options"),
    ]

    operations = [
        migrations.RunPython(
            crear_ordenes_existentes,
            migrations.RunPython.noop,
        ),
    ]
