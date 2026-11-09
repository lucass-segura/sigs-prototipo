"""S32 · Los vencimientos de las tareas de la demo son relativos al día de carga.

`seed_demo` calcula cada vencimiento a partir de la fecha local (America/Argentina/Buenos_Aires) del día en que
se carga, así la página Tareas siempre muestra tareas vencidas, de hoy, de esta semana y más adelantes. Las fechas
del siniestro (Anexo 1) no cambian.
"""
import io
from datetime import date, timedelta

import pytest
from django.core.management import call_command

from nucleo import demo
from nucleo.models import Siniestro, Tarea, Usuario
from tests.conftest import cliente_de

pytestmark = pytest.mark.django_db

HOY = date(2026, 11, 9)


@pytest.fixture
def demo_al_9_de_noviembre(monkeypatch):
    monkeypatch.setattr(demo, "hoy_local", lambda: HOY)
    call_command("seed_demo", stdout=io.StringIO())


def vencimientos(numero):
    return {t.titulo: t.vence_en for t in Tarea.objects.filter(siniestro__numero_expediente=numero)}


def test_s32_hoy_local_es_la_fecha_en_buenos_aires(monkeypatch):
    from datetime import datetime, timezone

    class Reloj(datetime):
        @classmethod
        def now(cls, tz=None):
            # 02:30 UTC del 10/11 son las 23:30 del 9/11 en Buenos Aires (UTC-3)
            return datetime(2026, 11, 10, 2, 30, tzinfo=timezone.utc).astimezone(tz)

    monkeypatch.setattr(demo, "datetime", Reloj)
    assert demo.hoy_local() == date(2026, 11, 9)


def test_s32_las_tareas_de_0147_vencen_relativas_al_dia_de_carga(demo_al_9_de_noviembre):
    venc = vencimientos("EXP-2026-0147")
    assert venc["Pedir resultado del antecedente S-2025-0381"] == HOY - timedelta(days=2)  # vencida
    assert venc["Redactar informe"] == HOY + timedelta(days=3)  # esta semana
    assert venc["Esperar acta policial"] is None  # sin fecha
    assert venc["Inspección del vehículo"] is None and venc["Entrevista al asegurado"] is None  # hechas
    assert len(venc) == 5


def test_s32_hay_una_tarea_que_vence_hoy_y_otra_mas_adelante(demo_al_9_de_noviembre):
    venc = vencimientos("EXP-2026-0139")
    assert sorted(venc.values()) == [HOY, HOY + timedelta(days=12)]
    todas = Tarea.objects.exclude(estado=Tarea.HECHA)
    assert {t.siniestro.perito.email for t in todas} == {"perito08@sigs.test"}


def test_s32_cambia_el_dia_de_carga_y_corren_los_vencimientos(monkeypatch):
    monkeypatch.setattr(demo, "hoy_local", lambda: date(2027, 1, 20))
    call_command("seed_demo", stdout=io.StringIO())
    assert vencimientos("EXP-2026-0147")["Redactar informe"] == date(2027, 1, 23)


def test_s32_la_pagina_tareas_cubre_vencida_hoy_semana_mas_adelante_y_sin_fecha(demo_al_9_de_noviembre):
    cliente = cliente_de(Usuario.objects.get(email="perito08@sigs.test"))
    fechas = [t["vence_en"] for t in cliente.get("/api/tareas").json()]
    esperadas = {str(HOY - timedelta(days=2)), str(HOY), str(HOY + timedelta(days=3)), str(HOY + timedelta(days=12)), None}
    assert esperadas <= set(fechas)


def test_s32_el_resumen_de_perito08_cuenta_tareas_que_vencen_esta_semana(monkeypatch):
    # Sin parchear: el día real de la prueba. Las tareas son relativas a hoy, así que siempre hay alguna.
    call_command("seed_demo", stdout=io.StringIO())
    cuerpo = cliente_de(Usuario.objects.get(email="perito08@sigs.test")).get("/api/siniestros").json()
    assert cuerpo["resumen"]["tareas_vencen_semana"] > 0


def test_s32_las_fechas_del_siniestro_no_cambian_con_el_dia_de_carga(monkeypatch):
    monkeypatch.setattr(demo, "hoy_local", lambda: date(2030, 5, 5))
    call_command("seed_demo", stdout=io.StringIO())
    caso = Siniestro.objects.get(numero_expediente="EXP-2026-0147")
    assert caso.fecha_hecho.astimezone(demo.ZONA).date() == date(2026, 8, 12)
    assert caso.fecha_denuncia == date(2026, 8, 14)
    assert caso.poliza.inicio_vigencia == date(2026, 7, 20)
