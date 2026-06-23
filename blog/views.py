import json

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.validators import UnicodeUsernameValidator

from django.core.exceptions import ValidationError
from django.forms.models import model_to_dict
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.translation import override
from django.views.decorators.http import require_POST

from . import models

def home(request):
    return render(request, 'home.html')

def log_in(request):
    if request.user.is_authenticated:
        return redirect('/dasbor/')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('/dasbor/')
        else:
            messages.error(request, 'Username atau password salah.')
    
    return render(request, 'login.html')

def log_out(request):
    logout(request)
    return redirect('/login/')

def daftar(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        if not username:
            messages.error(request, 'Username wajib diisi.')
            return render(request, 'daftar.html')

        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')

        if not password or not password_confirm:
            messages.error(request, 'Password wajib diisi.')
            return render(request, 'daftar.html')
        if password != password_confirm:
            messages.error(request, 'Konfirmasi password tidak cocok.')
            return render(request, 'daftar.html')

        if ' ' in username:
            messages.error(request, 'Username tidak valid.')
            return render(request, 'daftar.html')
        
        try:
            UnicodeUsernameValidator()(username)
        except ValidationError:
            messages.error(request, 'Username tidak valid.')
            return render(request, 'daftar.html')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username sudah dipakai.')
            return render(request, 'daftar.html')
        
        with override('id'):
            try:
                validate_password(password)
            except ValidationError as e:
                for message in e.messages:
                    messages.error(request, message)
                return render(request, 'daftar.html')
        
        request.session['register_data'] = {
            'username': username,
            'password': password,
        }
        return redirect('/data-pengguna/')
    
    return render(request, 'daftar.html')

def data_pengguna(request):
    temp = request.session.get('register_data')
    if not temp:
        return redirect('/daftar/')
    
    if request.method == 'POST':
        username=temp['username']
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username sudah diambil duluan.')
            del request.session['register_data']
            return redirect('/daftar/')
        
        name = request.POST.get('name')
        institute_name = request.POST.get('institute_name')

        if not name or not institute_name:
            messages.error(request, 'Semua data wajib diisi.')
            return render(request, 'data_pengguna.html')
        
        user = User.objects.create_user(
            username=username,
            password=temp['password'],
            first_name=name,
        )
        models.Profile.objects.create(
            user=user,
            institute_name=institute_name,
        )
        
        del request.session['register_data']
        login(request, user)
        return redirect('/dasbor/')

    return render(request, 'data_pengguna.html')

@login_required
def dasbor(request):
    user = request.user
    context = {
        'jadwal_count': models.Schedule.objects.filter(user=user).count(),
        'hari_count': models.Day.objects.filter(user=user).count(),
        'jam_pembelajaran_count': models.LessonHour.objects.filter(user=user).count(),
        'kelas_count': models.Class.objects.filter(user=user).count(),
        'ruang_kelas_count': models.Classroom.objects.filter(user=user).count(),
        'pengajar_count': models.Educator.objects.filter(user=user).count(),
        'pelajaran_count': models.Lesson.objects.filter(user=user).count(),
    }
    return render(request, 'dasbor.html', context)

@login_required
def profil(request):
    return render(request, 'profil.html')

@login_required
@require_POST
def profil_update(request):
    user = request.user

    current_password = request.POST.get('password', False)
    if current_password:
        if not user.check_password(current_password):
            messages.error(request, 'Password saat ini salah.')
            return redirect('/profil/')

        new_password = request.POST.get('password_new')
        confirm_password = request.POST.get('password_new_confirm')

        if not new_password or not confirm_password or new_password != confirm_password:
            messages.error(request, 'Konfirmasi password tidak cocok.')
            return redirect('/profil/')
        
        user.set_password(new_password)

    name = request.POST.get('name')
    institute_name = request.POST.get('institute_name')

    if not name:
        messages.error(request, 'Harap isi Nama.')
        return redirect('/profil/')
    if not institute_name:
        messages.error(request, 'Harap isi Nama Institusi.')
        return redirect('/profil/')

    user.first_name = name
    user.profile.institute_name = institute_name

    user.save()
    user.profile.save()

    update_session_auth_hash(request, user)

    messages.success(request, 'Data profil berhasil diperbarui.')
    return redirect('/profil/')

@login_required
def hari(request):
    context = {
        'path': 'hari',
        'is_data_page': True,
        'title': 'Data Hari',
        'table_columns': {
            'name': {'label': 'Nama', 'type': 'text'},
            'sequence': {'label': 'Urutan', 'type': 'number'},
            'active': {'label': 'Aktif', 'type': 'checkbox'},
        },
        'table_order': [[2, 'asc']],
        'datas': models.Day.objects.filter(user=request.user).values(),
    }
    return render(request, 'data.html', context)

@login_required
def jam_pembelajaran(request):
    context = {
        'path': 'jam-pembelajaran',
        'is_data_page': True,
        'title': 'Data Jam Pembelajaran',
        'table_columns': {
            'start_time': {'label': 'Mulai', 'type': 'time'},
            'finish_time': {'label': 'Selesai', 'type': 'time'},
            'sequence': {'label': 'Urutan', 'type': 'number'},
            'is_break': {'label': 'Istirahat', 'type': 'checkbox'},
            'active': {'label': 'Aktif', 'type': 'checkbox'},
        },
        'table_order': [[3, 'asc']],
        'datas': models.LessonHour.objects.filter(user=request.user).values(),
    }
    return render(request, 'data.html', context)

@login_required
def kelas(request):
    context = {
        'path': 'kelas',
        'is_data_page': True,
        'title': 'Data Kelas',
        'table_columns': {
            'name': {'label': 'Nama', 'type': 'text'},
            'sequence': {'label': 'Urutan', 'type': 'number'},
            'active': {'label': 'Aktif', 'type': 'checkbox'},
        },
        'table_order': [[2, 'asc']],
        'datas': models.Class.objects.filter(user=request.user).values(),
    }
    return render(request, 'data.html', context)

@login_required
def ruang_kelas(request):
    context = {
        'path': 'ruang-kelas',
        'is_data_page': True,
        'title': 'Data Ruang Kelas',
        'table_columns': {
            'name': {'label': 'Nama', 'type': 'text'},
            'class_capacity': {'label': 'Kapasitas Kelas', 'type': 'number'},
            'is_same_time_shareable': {'label': 'Berbagi Kelas', 'type': 'checkbox'},
            'active': {'label': 'Aktif', 'type': 'checkbox'},
        },
        'table_order': [[1, 'asc']],
        'datas': models.Classroom.objects.filter(user=request.user).values(),
    }
    return render(request, 'data.html', context)

@login_required
def pengajar(request):
    context = {
        'path': 'pengajar',
        'is_data_page': True,
        'title': 'Data Pengajar',
        'table_columns': {
            'name': {'label': 'Nama', 'type': 'text'},
            'active': {'label': 'Aktif', 'type': 'checkbox'},
        },
        'table_order': [[1, 'asc']],
        'datas': models.Educator.objects.filter(user=request.user).values(),
    }
    return render(request, 'data.html', context)

@login_required
def pelajaran(request):
    context = {
        'path': 'pelajaran',
        'is_data_page': True,
        'title': 'Data Pelajaran',
        'table_columns': {
            'name': {'label': 'Nama', 'type': 'text'},
            'time_slot': {'label': 'Slot Waktu', 'type': 'number'},
            'active': {'label': 'Aktif', 'type': 'checkbox'},
        },
        'table_order': [[1, 'asc']],
        'datas': models.Lesson.objects.filter(user=request.user).values(),
    }
    return render(request, 'data.html', context)

def get_data_object(data):
    data_objects = {
        'hari': models.Day.objects,
        'jam-pembelajaran': models.LessonHour.objects,
        'kelas': models.Class.objects,
        'ruang-kelas': models.Classroom.objects,
        'pengajar': models.Educator.objects,
        'pelajaran': models.Lesson.objects,
        'jadwal': models.Schedule.objects,
    }

    if data in data_objects:
        return data_objects[data]
    return

def get_object_columns(data):
    object_columns = {
        'hari': ['name', 'sequence', 'active'],
        'jam-pembelajaran': ['start_time', 'finish_time', 'sequence', 'is_break', 'active'],
        'kelas': ['name', 'sequence', 'active'],
        'ruang-kelas': ['name', 'class_capacity', 'is_same_time_shareable', 'active'],
        'pengajar': ['name', 'active'],
        'pelajaran': ['name', 'time_slot', 'active'],
    }

    if data in object_columns:
        return object_columns[data]
    return

@login_required
@require_POST
def data_add(request, data):
    objects = get_data_object(data)
    columns = get_object_columns(data)
    if not objects or not columns:
        messages.warning(request, 'Data gagal ditambahkan.')
        return redirect(f'/{data}/')
    
    values = {}

    for column in columns:
        field = objects.model._meta.get_field(column)

        value = request.POST.get(column, False)
        if field.get_internal_type() == 'BooleanField' and value:
            value = value.lower() in ['true', '1', 'on']
        values[column] = value
    
    values['user'] = request.user
    objects.create(**values)

    messages.success(request, 'Data berhasil ditambahkan.')
    return redirect(f'/{data}/')

@login_required
def data_get(request, data, id):
    objects = get_data_object(data)

    if not objects:
        return JsonResponse({
            'record': False,
        })
    
    try:
        record = objects.filter(user=request.user).get(id=id)
    except objects.model.DoesNotExist:
        return JsonResponse({
            'record': False,
        })
    return JsonResponse({
        'record': model_to_dict(record),
    })

@login_required
@require_POST
def data_update(request, data):
    objects = get_data_object(data)
    columns = get_object_columns(data)
    if not objects or not columns:
        messages.warning(request, 'Data gagal diperbarui.')
        return redirect(f'/{data}/')

    id = request.POST.get('id')
    try:
        record = objects.filter(user=request.user).get(id=id)
    except objects.model.DoesNotExist:
        messages.error(request, 'Data tidak ditemukan di database.')
        return redirect(f'/{data}/')

    for column in columns:
        field = record._meta.get_field(column)

        value = request.POST.get(column, False)
        if field.get_internal_type() == 'BooleanField' and value:
            value = value.lower() in ['true', '1', 'on']
        setattr(record, column, value)
    
    record.save()

    messages.success(request, 'Data berhasil diperbarui.')
    return redirect(f'/{data}/')

@login_required
@require_POST
def data_remove(request, data):
    objects = get_data_object(data)
    if not objects:
        messages.warning(request, 'Data gagal dihapus.')
        return redirect(f'/{data}/')

    ids = json.loads(request.POST.get('remove_ids', '[]'))
    deleted_count, _ = objects.filter(user=request.user, id__in=ids).delete()
    
    if deleted_count > 0:
        messages.success(request, f'{deleted_count} Data berhasil dihapus.')
    else:
        messages.error(request, 'Tidak ada data yang dihapus.')
    return redirect(f'/{data}/')

@login_required
def jadwal(request):
    context = {
        'path': 'jadwal',
        'datas': models.Schedule.objects.filter(user=request.user).values(),
    }
    return render(request, 'jadwal.html', context)

@login_required
def jadwal_add(request):
    context = {
        'data_hari': models.Day.objects.filter(user=request.user, active=True).values(),
        'data_jam': models.LessonHour.objects.filter(user=request.user, active=True).values(),
        'data_kelas': models.Class.objects.filter(user=request.user, active=True).values(),
        'data_ruang': models.Classroom.objects.filter(user=request.user, active=True).values(),
        'data_pengajar': models.Educator.objects.filter(user=request.user, active=True).values(),
        'data_pelajaran': models.Lesson.objects.filter(user=request.user, active=True).values(),
    }
    return render(request, 'jadwal_add.html', context)

@login_required
def jadwal_view(request, id):
    return render(request, 'jadwal_view.html')
