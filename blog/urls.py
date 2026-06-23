from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="Home"),
    path("login/", views.log_in, name="Login"),
    path("accounts/login/", views.log_in, name="Login"),
    path("logout/", views.log_out, name="Logout"),

    path("daftar/", views.daftar, name="Daftar"),
    path("data-pengguna/", views.data_pengguna, name="Data Pengguna"),

    path("dasbor/", views.dasbor, name="Dasbor"),
    path("profil/", views.profil, name="Profil"),
    path("profil/update/", views.profil_update, name="Profil Update"),

    path("hari/", views.hari, name="Hari"),
    path("jam-pembelajaran/", views.jam_pembelajaran, name="Jam Pembelajaran"),
    path("kelas/", views.kelas, name="Kelas"),
    path("ruang-kelas/", views.ruang_kelas, name="Ruang Kelas"),
    path("pengajar/", views.pengajar, name="Pengajar"),
    path("pelajaran/", views.pelajaran, name="Pelajaran"),

    path("data/add/<str:data>/", views.data_add, name="Data Add"),
    path("data/get/<str:data>/<int:id>/", views.data_get, name="Data Get"),
    path("data/update/<str:data>/", views.data_update, name="Data Update"),
    path("data/remove/<str:data>/", views.data_remove, name="Data Remove"),

    path("jadwal/", views.jadwal, name="Jadwal"),
    path("jadwal/add/", views.jadwal_add, name="Jadwal"),
    path("jadwal/view/<int:id>/", views.jadwal_view, name="Jadwal"),
]