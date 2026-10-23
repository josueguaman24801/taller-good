from datetime import datetime, timezone as datetime_timezone
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase
from django.urls import resolve, reverse
from django.core import mail
from django.test import override_settings
from django.templatetags.static import static
from django.contrib.auth.models import User
from django.db import connection
from unittest.mock import patch
from .forms import SolicitarTurnoForm
from .models import (
    Cliente,
    Disponibilidad,
    OrdenTrabajo,
    PerfilUsuario,
    Repuesto,
    RepuestoUtilizado,
    Trabajo,
    TrabajoRealizado,
    Turno,
    Trabajador,
    Vehiculo,
)

from .email_utils import enviar_correo_cliente
from .utils import generar_pdf_turno
from .views import es_jefe_taller, es_secretario


class JefeTallerUrlTests(SimpleTestCase):
    def test_legacy_url_resolves_to_jefe_taller_view(self):
        match = resolve("/jefe_taller")

        self.assertEqual(match.view_name, "vista_jefe_taller_legacy")

    def test_canonical_url_remains_available(self):
        self.assertEqual(reverse("vista_jefe_taller"), "/jefe-taller/")


class StaticAssetUrlTests(SimpleTestCase):
    def test_static_asset_urls_are_root_relative(self):
        self.assertEqual(static("css/taller.css"), "/static/css/taller.css")


class ClienteIdTests(TestCase):
    def test_cliente_id_is_automatically_generated_primary_key(self):
        cliente = Cliente.objects.create(
            nombre="María",
            apellido="Pérez",
            email="maria@example.com",
            telefono="3511234567",
        )

        self.assertEqual(Cliente._meta.pk.name, "id")
        self.assertIsNotNone(cliente.id)

    def test_contact_details_can_be_blank_for_legacy_accounts(self):
        cliente = Cliente.objects.create(
            nombre="Cuenta",
            apellido="Antigua",
            email="",
            telefono="",
        )

        self.assertEqual(cliente.email, "")
        self.assertEqual(cliente.telefono, "")


class DerSchemaTests(TestCase):
    def test_database_columns_match_the_requested_ids(self):
        expected_columns = {
            Disponibilidad: {"id_disponibilidad"},
            Trabajador: {"id_mecanico", "id_usuario"},
            OrdenTrabajo: {
                "id_orden",
                "id_vehiculo",
                "id_cliente",
                "id_servicio",
                "id_mecanico",
            },
            PerfilUsuario: {"id_usuario", "telefono", "rol"},
        }

        with connection.cursor() as cursor:
            for model, expected in expected_columns.items():
                actual = {
                    field.name
                    for field in connection.introspection.get_table_description(
                        cursor,
                        model._meta.db_table,
                    )
                }
                self.assertTrue(
                    expected.issubset(actual),
                    f"{model._meta.db_table} missing {expected - actual}",
                )

    def test_user_profile_keeps_roles_and_hashed_password_in_django_auth(self):
        user = User.objects.create_user(
            username="cliente",
            password="ClaveSegura123!",
        )
        perfil = PerfilUsuario.objects.create(
            id_usuario=user,
            telefono="3511234567",
            rol="cliente",
        )
        user.refresh_from_db()

        self.assertTrue(user.check_password("ClaveSegura123!"))
        self.assertNotEqual(user.password, "ClaveSegura123!")
        self.assertEqual(perfil.id_usuario_id, user.pk)
        self.assertEqual(
            set(dict(PerfilUsuario.ROLES)),
            {"cliente", "mecanico", "jefe_taller", "secretario"},
        )

    def test_work_order_vehicle_inventory_and_service_records_are_related(self):
        cliente = Cliente.objects.create(
            nombre="María",
            apellido="Pérez",
            email="maria@example.com",
            telefono="3511234567",
        )
        servicio = Trabajo.objects.create(nombre="Diagnóstico")
        vehiculo = Vehiculo.objects.create(
            cliente=cliente,
            marca="Toyota",
            modelo="Corolla",
            anio=2020,
            patente="AB123CD",
        )
        disponibilidad = Disponibilidad.objects.create(
            fecha="2026-11-05",
            hora="10:30",
            estado=False,
        )
        turno = Turno.objects.create(
            cliente=cliente,
            vehiculo_registrado=vehiculo,
            disponibilidad=disponibilidad,
            vehiculo="Toyota Corolla 2020",
            marca="Toyota",
            modelo="Corolla",
            anio=2020,
            patente="AB123CD",
            servicio=servicio,
            fecha_turno=datetime(
                2026,
                11,
                5,
                13,
                30,
                tzinfo=datetime_timezone.utc,
            ),
        )
        orden = OrdenTrabajo.objects.create(
            turno=turno,
            vehiculo=vehiculo,
            cliente=cliente,
            servicio=servicio,
            fecha_ingreso="2026-11-05",
            estado="recibido",
        )
        repuesto = Repuesto.objects.create(
            nombre="Filtro de aceite",
            stock=4,
            precio="2500.00",
        )
        uso = RepuestoUtilizado.objects.create(
            orden_trabajo=orden,
            repuesto=repuesto,
            nombre=repuesto.nombre,
            cantidad=1,
            precio_unitario=repuesto.precio,
            fecha="2026-11-05",
        )
        trabajo_realizado = TrabajoRealizado.objects.create(
            orden_trabajo=orden,
            descripcion="Revisión inicial",
            fecha="2026-11-05",
        )

        self.assertEqual(turno.cliente, cliente)
        self.assertEqual(turno.vehiculo_registrado, vehiculo)
        self.assertEqual(disponibilidad.turno, turno)
        self.assertEqual(orden.repuestos_utilizados.get(), uso)
        self.assertEqual(orden.trabajos_realizados.get(), trabajo_realizado)

        turno.estado = "cancelado"
        turno.save(update_fields=["estado"])
        disponibilidad.refresh_from_db()
        self.assertTrue(disponibilidad.estado)


class SolicitarTurnoFormTests(TestCase):
    def test_vehicle_details_are_required_and_saved_separately(self):
        trabajo = Trabajo.objects.create(nombre="Diagnóstico")
        form = SolicitarTurnoForm(
            data={
                "marca": "Toyota",
                "modelo": "Corolla",
                "anio": "2020",
                "patente": "AB123CD",
                "servicio": trabajo.pk,
                "fecha_turno": "2026-11-05T10:30",
                "observaciones": "",
                "nombre": "María",
                "apellido": "Pérez",
                "email": "maria@example.com",
                "telefono": "3511234567",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        turno = form.save()

        self.assertEqual(turno.marca, "Toyota")
        self.assertEqual(turno.modelo, "Corolla")
        self.assertEqual(turno.anio, 2020)
        self.assertEqual(turno.vehiculo, "Toyota Corolla 2020")

    def test_vehicle_details_are_required(self):
        form = SolicitarTurnoForm()

        self.assertTrue(form.fields["marca"].required)
        self.assertTrue(form.fields["modelo"].required)
        self.assertTrue(form.fields["anio"].required)

    @patch("tallermami.views.guardar_turno_en_excel")
    @patch("tallermami.views.enviar_correo_cliente")
    def test_request_saves_client_vehicle_and_availability_relations(
        self,
        mock_send_email,
        mock_save_excel,
    ):
        servicio = Trabajo.objects.create(nombre="Diagnóstico")

        response = self.client.post(
            reverse("solicitar_turno"),
            {
                "marca": "Toyota",
                "modelo": "Corolla",
                "anio": "2020",
                "patente": "AB123CD",
                "servicio": servicio.pk,
                "fecha_turno": "2030-11-05T10:30",
                "observaciones": "",
                "nombre": "María",
                "apellido": "Pérez",
                "email": "maria@example.com",
                "telefono": "3511234567",
            },
        )

        self.assertEqual(response.status_code, 302)
        turno = Turno.objects.get()
        self.assertEqual(turno.cliente.email, "maria@example.com")
        self.assertEqual(turno.cliente.usuario, turno.usuario)
        self.assertEqual(turno.vehiculo_registrado.patente, "AB123CD")
        self.assertEqual(turno.disponibilidad.estado, False)
        self.assertEqual(turno.disponibilidad.fecha.isoformat(), "2030-11-05")
        self.assertEqual(
            turno.disponibilidad.hora.isoformat(timespec="minutes"),
            "10:30",
        )
        mock_send_email.assert_called_once()
        mock_save_excel.assert_called_once_with(turno)
        self.assertEqual(turno.usuario.perfil_usuario.telefono, "3511234567")


class PerfilUsuarioFlowTests(TestCase):
    def test_registration_creates_a_customer_profile(self):
        response = self.client.post(
            reverse("registro"),
            {
                "username": "maria",
                "email": "maria@example.com",
                "password1": "NuevaClaveSegura456!",
                "password2": "NuevaClaveSegura456!",
            },
        )

        self.assertRedirects(response, reverse("inicio"))
        usuario = User.objects.get(username="maria")
        self.assertEqual(usuario.perfil_usuario.rol, "cliente")
        self.assertEqual(usuario.perfil_usuario.telefono, "")

    def test_staff_roles_grant_their_matching_panel_access(self):
        jefe = User.objects.create_user(username="jefe")
        PerfilUsuario.objects.create(
            id_usuario=jefe,
            rol="jefe_taller",
        )
        secretario = User.objects.create_user(username="secretario")
        PerfilUsuario.objects.create(
            id_usuario=secretario,
            rol="secretario",
        )

        self.assertTrue(es_jefe_taller(jefe))
        self.assertFalse(es_secretario(jefe))
        self.assertTrue(es_secretario(secretario))
        self.assertFalse(es_jefe_taller(secretario))

@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PasswordResetFlowTests(TestCase):
    def setUp(self):
        User.objects.create_user(
            username="cliente",
            email="cliente@example.com",
            password="ClaveSegura123!",
        )

    def test_password_reset_sends_a_link_to_the_confirmation_page(self):
        response = self.client.post(
            reverse("password_reset"),
            {"email": "cliente@example.com"},
        )

        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(
            "/password-reset/",
            mail.outbox[0].body,
        )

    def test_password_reset_page_does_not_render_markdown_fences(self):
        response = self.client.get(reverse("password_reset"))

        self.assertContains(response, "Recuperar contraseña")
        self.assertNotContains(response, "```")

    def test_password_reset_link_changes_password_and_allows_email_login(self):
        self.client.post(
            reverse("password_reset"),
            {"email": "cliente@example.com"},
        )
        url = mail.outbox[0].body.splitlines()
        reset_url = next(line for line in url if "/password-reset/" in line)
        path = reset_url.split("http://testserver", 1)[1]

        response = self.client.get(path, follow=True)
        self.assertContains(response, "Crear nueva contraseña")
        confirm_path = response.request["PATH_INFO"]

        response = self.client.post(
            confirm_path,
            {
                "new_password1": "NuevaClaveSegura456!",
                "new_password2": "NuevaClaveSegura456!",
            },
        )

        self.assertRedirects(response, reverse("password_reset_complete"))
        self.assertTrue(
            User.objects.get(username="cliente").check_password(
                "NuevaClaveSegura456!"
            )
        )

        response = self.client.post(
            reverse("login"),
            {
                "username": "cliente@example.com",
                "password": "NuevaClaveSegura456!",
            },
        )

        self.assertRedirects(response, reverse("inicio"))

    def test_password_reset_notice_does_not_disclose_unknown_email(self):
        response = self.client.post(
            reverse("password_reset"),
            {"email": "no-registrado@example.com"},
            follow=True,
        )

        self.assertContains(response, "Si existe una cuenta asociada al correo")
        self.assertEqual(len(mail.outbox), 0)

    def test_password_reset_complete_shows_success_notice(self):
        response = self.client.get(reverse("password_reset_complete"))

        self.assertContains(response, 'class="alert alert-success"')
        self.assertContains(response, "Tu contraseña fue cambiada correctamente.")
        self.assertNotContains(response, "```")


class ComprobanteTurnoPdfTests(SimpleTestCase):
    def test_pdf_incluye_diseno_y_descarga_con_nombre_de_comprobante(self):
        turno = SimpleNamespace(
            id=42,
            usuario=SimpleNamespace(
                get_full_name=lambda: "María Pérez",
                username="maria",
                email="maria@example.com",
            ),
            vehiculo="Auto de prueba",
            patente="ABC123",
            servicio="Mantenimiento",
            fecha_turno=datetime(2026, 11, 5, 10, 30),
            porcentaje_reparacion=0,
            observaciones="Revisar frenos.",
            get_estado_display=lambda: "Pendiente",
        )

        response = generar_pdf_turno(turno)

        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(
            response["Content-Disposition"],
            'attachment; filename="comprobante_turno_42.pdf"',
        )
        self.assertTrue(response.content.startswith(b"%PDF-"))


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class CorreoClienteTests(SimpleTestCase):
    def test_presupuesto_se_envia_en_html_con_logo_y_version_de_texto(self):
        enviar_correo_cliente(
            asunto="Presupuesto de reparación",
            mensaje="Total estimado: $1500.00",
            destinatarios=["cliente@example.com"],
            contexto={
                "tipo": "presupuesto",
                "titulo": "Presupuesto de reparación",
                "nombre_cliente": "María Pérez",
                "vehiculo": "Auto de prueba",
                "patente": "ABC123",
                "repuestos": [],
                "mano_obra": 1500,
                "total": 1500,
                "observaciones": "Sin observaciones.",
                "aceptar_url": "https://example.com/aceptar",
                "rechazar_url": "https://example.com/rechazar",
            },
        )

        correo = mail.outbox[0]
        html = correo.alternatives[0][0]

        self.assertEqual(correo.body, "Total estimado: $1500.00")
        self.assertIn("cid:logo-taller", html)
        self.assertIn("Aceptar presupuesto", html)
        self.assertIn("Total estimado: $1500,00", html)
        self.assertTrue(
            any(
                getattr(adjunto, "get", lambda *_: None)("Content-ID")
                == "<logo-taller>"
                for adjunto in correo.attachments
            )
        )
