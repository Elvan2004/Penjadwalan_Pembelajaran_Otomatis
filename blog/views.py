import hashlib
import json
import math

from collections import defaultdict
from ortools.sat.python import cp_model

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.validators import UnicodeUsernameValidator

from django.core.exceptions import ValidationError
from django.db import transaction
from django.forms.models import model_to_dict
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.safestring import mark_safe
from django.utils.translation import override
from django.views.decorators.http import require_POST

from . import models

def home(request):
    return render(request, 'home.html')

def log_in(request):
    if request.user.is_authenticated:
        return redirect('/dasbor/')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

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
        name = request.POST.get('name', '').strip()
        institute_name = request.POST.get('institute_name', '').strip()

        if not name or not institute_name:
            messages.error(request, 'Semua data wajib diisi.')
            return render(request, 'daftar.html')

        username = request.POST.get('username', '').strip()
        if not username:
            messages.error(request, 'Username wajib diisi.')
            return render(request, 'daftar.html')

        password = request.POST.get('password', '').strip()
        password_confirm = request.POST.get('password_confirm', '').strip()

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
        
        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=name,
        )
        models.Profile.objects.create(
            user=user,
            institute_name=institute_name,
        )

        login(request, user)
        return redirect('/dasbor/')
    
    return render(request, 'daftar.html')

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
    if request.method == 'POST':
        user = request.user

        current_password = request.POST.get('password', '').strip()
        if current_password:
            if not user.check_password(current_password):
                messages.error(request, 'Password saat ini salah.')
                return render(request, 'profil.html')

            new_password = request.POST.get('password_new', '').strip()
            confirm_password = request.POST.get('password_new_confirm', '').strip()

            if not new_password or not confirm_password or new_password != confirm_password:
                messages.error(request, 'Konfirmasi password tidak cocok.')
                return render(request, 'profil.html')
            
            with override('id'):
                try:
                    validate_password(new_password)
                except ValidationError as e:
                    for message in e.messages:
                        messages.error(request, message)
                    return render(request, 'profil.html')
            
            user.set_password(new_password)

        name = request.POST.get('name', '').strip()
        institute_name = request.POST.get('institute_name', '').strip()

        if not name:
            messages.error(request, 'Harap isi Nama.')
            return render(request, 'profil.html')
        if not institute_name:
            messages.error(request, 'Harap isi Nama Institusi.')
            return render(request, 'profil.html')

        user.first_name = name
        user.profile.institute_name = institute_name

        user.save()
        user.profile.save()

        update_session_auth_hash(request, user)

        messages.success(request, 'Data profil berhasil diperbarui.')
        return render(request, 'profil.html')

    return render(request, 'profil.html')

def get_table_columns(data, remove_keys=[]):
    data_columns = {
        'hari': {
            'name': {'label': 'Nama', 'type': 'text', 'placeholder': 'Senin'},
            'sequence': {'label': 'Urutan', 'type': 'number', 'placeholder': '1'},
            'active': {'label': 'Aktif', 'type': 'checkbox', 'default_value': True},
        },
        'jam-pembelajaran': {
            'start_time': {'label': 'Mulai', 'type': 'time'},
            'finish_time': {'label': 'Selesai', 'type': 'time'},
            'sequence': {'label': 'Urutan', 'type': 'number', 'placeholder': '1'},
            'is_break': {'label': 'Istirahat', 'type': 'checkbox', 'default_value': False},
            'active': {'label': 'Aktif', 'type': 'checkbox', 'default_value': True},
        },
        'kelas': {
            'name': {'label': 'Nama', 'type': 'text', 'placeholder': '1A'},
            'sequence': {'label': 'Urutan', 'type': 'number', 'placeholder': '1'},
            'active': {'label': 'Aktif', 'type': 'checkbox', 'default_value': True},
        },
        'ruang-kelas': {
            'name': {'label': 'Nama', 'type': 'text', 'placeholder': 'R101'},
            'class_capacity': {'label': 'Kapasitas Kelas', 'type': 'number', 'placeholder': '1', 'min': 0},
            'is_same_time_shareable': {'label': 'Berbagi Kelas', 'type': 'checkbox', 'default_value': False},
            'active': {'label': 'Aktif', 'type': 'checkbox', 'default_value': True},
        },
        'pengajar': {
            'name': {'label': 'Nama', 'type': 'text', 'placeholder': 'John Doe'},
            'active': {'label': 'Aktif', 'type': 'checkbox', 'default_value': True},
        },
        'pelajaran': {
            'name': {'label': 'Nama', 'type': 'text', 'placeholder': 'Agama'},
            'time_slot': {'label': 'Slot Waktu', 'type': 'number', 'placeholder': '1', 'min': 0},
            'active': {'label': 'Aktif', 'type': 'checkbox', 'default_value': True},
        },
    }

    if data in data_columns:
        result =  data_columns[data]
        for key in remove_keys:
            result.pop(key)
        return result
    return

def get_table_order(data):
    data_order = {
        'hari': [[2, 'asc']],
        'jam-pembelajaran': [[3, 'asc']],
        'kelas': [[2, 'asc']],
        'ruang-kelas': [[1, 'asc']],
        'pengajar': [[1, 'asc']],
        'pelajaran': [[1, 'asc']],
    }
    if data in data_order:
        return data_order[data]
    return

@login_required
def hari(request):
    context = {
        'path': 'hari',
        'is_data_page': True,
        'title': 'Data Hari',
        'table_columns': get_table_columns('hari'),
        'table_order': get_table_order('hari'),
        'datas': models.Day.objects.filter(user=request.user).values(),
    }
    return render(request, 'data.html', context)

@login_required
def jam_pembelajaran(request):
    context = {
        'path': 'jam-pembelajaran',
        'is_data_page': True,
        'title': 'Data Jam Pembelajaran',
        'table_columns': get_table_columns('jam-pembelajaran'),
        'table_order': get_table_order('jam-pembelajaran'),
        'datas': models.LessonHour.objects.filter(user=request.user).values(),
    }
    return render(request, 'data.html', context)

@login_required
def kelas(request):
    context = {
        'path': 'kelas',
        'is_data_page': True,
        'title': 'Data Kelas',
        'table_columns': get_table_columns('kelas'),
        'table_order': get_table_order('kelas'),
        'datas': models.Class.objects.filter(user=request.user).values(),
    }
    return render(request, 'data.html', context)

@login_required
def ruang_kelas(request):
    context = {
        'path': 'ruang-kelas',
        'is_data_page': True,
        'title': 'Data Ruang Kelas',
        'table_columns': get_table_columns('ruang-kelas'),
        'table_order': get_table_order('ruang-kelas'),
        'datas': models.Classroom.objects.filter(user=request.user).values(),
    }
    return render(request, 'data.html', context)

@login_required
def pengajar(request):
    context = {
        'path': 'pengajar',
        'is_data_page': True,
        'title': 'Data Pengajar',
        'table_columns': get_table_columns('pengajar'),
        'table_order': get_table_order('pengajar'),
        'datas': models.Educator.objects.filter(user=request.user).values(),
    }
    return render(request, 'data.html', context)

@login_required
def pelajaran(request):
    context = {
        'path': 'pelajaran',
        'is_data_page': True,
        'title': 'Data Pelajaran',
        'table_columns': get_table_columns('pelajaran'),
        'table_order': get_table_order('pelajaran'),
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
    table_columns = get_table_columns(data)
    if table_columns:
        return table_columns.keys()
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
        if field.get_internal_type() == 'PositiveIntegerField' and int(value) < 0:
            messages.warning(request, f'{field.verbose_name} tidak bisa bernilai negatif.')
            return redirect(f'/{data}/')
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
        if field.get_internal_type() == 'PositiveIntegerField' and int(value) < 0:
            messages.warning(request, f'{field.verbose_name} tidak bisa bernilai negatif.')
            return redirect(f'/{data}/')
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

    to_exclude_ids = []
    if data != 'jadwal':
        entity = data.replace('-', '_')
        data_obj = models.Data.objects.filter(entity=entity)
        for id in ids:
            if data_obj.filter(entity_id=int(id)).exists():
                to_exclude_ids.append(int(id))

    deleted_count, _ = objects.filter(user=request.user, id__in=ids).exclude(id__in=to_exclude_ids).delete()
    
    if deleted_count > 0:
        messages.success(request, f'{deleted_count} Data berhasil dihapus.')
    elif data != 'jadwal' and len(to_exclude_ids) > 0 and len(to_exclude_ids) == len(ids):
        messages.error(request, 'Tidak dapat menghapus data ini karena dipakai untuk jadwal.')
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
    schedule = models.Schedule.objects.create(user=request.user, status='draft')
    return redirect(f'/jadwal/detail/{schedule.id}/')

@login_required
def jadwal_detail(request, id):
    try:
        schedule = models.Schedule.objects.filter(user=request.user).get(id=id)
    except models.Schedule.DoesNotExist:
        messages.error(request, 'Gagal tambah / menemukan jadwal, silakan coba lagi.')
        return redirect('/jadwal/')
    
    hari_ids = models.Data.objects.filter(schedule=schedule, entity='hari').values_list('entity_id')
    jam_pembelajaran_ids = models.Data.objects.filter(schedule=schedule, entity='jam_pembelajaran').values_list('entity_id')
    kelas_ids = models.Data.objects.filter(schedule=schedule, entity='kelas').values_list('entity_id')
    ruang_kelas_ids = models.Data.objects.filter(schedule=schedule, entity='ruang_kelas').values_list('entity_id')
    pengajar_ids = models.Data.objects.filter(schedule=schedule, entity='pengajar').values_list('entity_id')
    pelajaran_ids = models.Data.objects.filter(schedule=schedule, entity='pelajaran').values_list('entity_id')

    constraints = models.Constraint.objects.filter(schedule=schedule)

    def get_data_content(entity, data):
        if entity == 'hari':
            return f'<strong class="text-blue-600">Hari</strong> | {data.name}'
        elif entity == 'jam-pembelajaran':
            return f'<strong class="text-blue-600">Jam Pembelajaran</strong> | {data.start_time.strftime("%H:%M")} - {data.finish_time.strftime("%H:%M")}' + (' (Istirahat)' if data.is_break else '')
        elif entity == 'kelas':
            return f'<strong class="text-blue-600">Kelas</strong> | {data.name}'
        elif entity == 'ruang-kelas':
            return f'<strong class="text-blue-600">Ruang Kelas</strong> | {data.name}' + (' (Berbagi Kelas)' if data.is_same_time_shareable else '')
        elif entity == 'pengajar':
            return f'<strong class="text-blue-600">Pengajar</strong> | {data.name}'
        elif entity == 'pelajaran':
            return f'<strong class="text-blue-600">Pelajaran</strong> | {data.name} ({data.time_slot} Slot)'
        return

    batasan = []
    for constraint in constraints:
        data1_entity = constraint.data1.entity.replace('_', '-')
        id1 = constraint.data1.entity_id
        data2_entity = constraint.data2.entity.replace('_', '-')
        id2 = constraint.data2.entity_id
        capable = constraint.is_capable

        data1_obj = get_data_object(data1_entity)
        try:
            data1 = data1_obj.filter(user=request.user).get(id=id1)
        except data1_obj.model.DoesNotExist:
            messages.error(request, 'Gagal menampilkan batasan jadwal, silakan coba lagi.')
            return redirect('/jadwal/')

        data2_obj = get_data_object(data2_entity)
        try:
            data2 = data2_obj.filter(user=request.user).get(id=id2)
        except data2_obj.model.DoesNotExist:
            messages.error(request, 'Gagal menampilkan batasan jadwal, silakan coba lagi.')
            return redirect('/jadwal/')
        
        data1_content = mark_safe(get_data_content(data1_entity, data1))
        data2_content = mark_safe(get_data_content(data2_entity, data2))

        batasan.append({
            'data1': data1_entity,
            'id1': id1,
            'data2': data2_entity,
            'id2': id2,
            'capable': capable,
            'data1_content': data1_content,
            'data2_content': data2_content,
        })

    hide_initial_generate_button = False
    if not hari_ids and not jam_pembelajaran_ids and not kelas_ids and not ruang_kelas_ids and not pengajar_ids and not pengajar_ids:
        hide_initial_generate_button = True
    
    context = {
        'schedule_id': id,
        'schedule_name': schedule.name,
        'schedule_status': schedule.status,
        'hari': models.Day.objects.filter(user=request.user, id__in=hari_ids).values(),
        'jam_pembelajaran': models.LessonHour.objects.filter(user=request.user, id__in=jam_pembelajaran_ids).values(),
        'kelas': models.Class.objects.filter(user=request.user, id__in=kelas_ids).values(),
        'ruang_kelas': models.Classroom.objects.filter(user=request.user, id__in=ruang_kelas_ids).values(),
        'pengajar': models.Educator.objects.filter(user=request.user, id__in=pengajar_ids).values(),
        'pelajaran': models.Lesson.objects.filter(user=request.user, id__in=pelajaran_ids).values(),
        'batasan': batasan,
        'hide_initial_generate_button': hide_initial_generate_button,
    }
    return render(request, 'jadwal_detail.html', context)

@login_required
def jadwal_get_data(request, data):
    objects = get_data_object(data)

    if not objects:
        return JsonResponse({
            'columns': False,
            'order': False,
            'datas': False,
        })

    table_columns = get_table_columns(data, remove_keys=['active'])
    columns = list(table_columns.keys())
    columns.append('id')
    
    return JsonResponse({
        'columns': table_columns,
        'order': get_table_order(data),
        'datas': list(objects.filter(user=request.user, active=True).values(*columns)),
    })

@login_required
@require_POST
def jadwal_save(request):
    data = json.loads(request.body)

    schedule_name = data.get('schedule_name', '').strip()
    if not schedule_name:
        return JsonResponse({
            'success': False,
            'message': 'Nama Jadwal wajib diisi.',
        })

    schedule_id = int(data.get('schedule_id', 0))
    try:
        schedule = models.Schedule.objects.filter(user=request.user).get(id=schedule_id)
    except models.Schedule.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Jadwal tidak ditemukan.',
        })
    
    try:
        with transaction.atomic():
            schedule.name = schedule_name
            modified = False
            
            hari = data.get('hari', [])
            jam_pembelajaran = data.get('jam_pembelajaran', [])
            kelas = data.get('kelas', [])
            ruang_kelas = data.get('ruang_kelas', [])
            pengajar = data.get('pengajar', [])
            pelajaran = data.get('pelajaran', [])

            used_datas = {}
            used_data_ids = []
            for id in hari:
                obj, created = models.Data.objects.get_or_create(schedule=schedule, entity='hari', entity_id=int(id))
                used_datas[('hari', int(id))] = obj
                used_data_ids.append(obj.id)
                if created:
                    modified = True
            for id in jam_pembelajaran:
                obj, created = models.Data.objects.get_or_create(schedule=schedule, entity='jam_pembelajaran', entity_id=int(id))
                used_datas[('jam_pembelajaran', int(id))] = obj
                used_data_ids.append(obj.id)
                if created:
                    modified = True
            for id in kelas:
                obj, created = models.Data.objects.get_or_create(schedule=schedule, entity='kelas', entity_id=int(id))
                used_datas[('kelas', int(id))] = obj
                used_data_ids.append(obj.id)
                if created:
                    modified = True
            for id in ruang_kelas:
                obj, created = models.Data.objects.get_or_create(schedule=schedule, entity='ruang_kelas', entity_id=int(id))
                used_datas[('ruang_kelas', int(id))] = obj
                used_data_ids.append(obj.id)
                if created:
                    modified = True
            for id in pengajar:
                obj, created = models.Data.objects.get_or_create(schedule=schedule, entity='pengajar', entity_id=int(id))
                used_datas[('pengajar', int(id))] = obj
                used_data_ids.append(obj.id)
                if created:
                    modified = True
            for id in pelajaran:
                obj, created = models.Data.objects.get_or_create(schedule=schedule, entity='pelajaran', entity_id=int(id))
                used_datas[('pelajaran', int(id))] = obj
                used_data_ids.append(obj.id)
                if created:
                    modified = True

            batasan = data.get('batasan', [])
            used_batasan_ids = []
            for item in batasan:
                data1 = item.get('data1', '').replace('-', '_')
                id1 = int(item.get('id1', 0))
                data2 = item.get('data2', '').replace('-', '_')
                id2 = int(item.get('id2', 0))

                data_1 = used_datas[(data1, id1)]
                data_2 = used_datas[(data2, id2)]
                capable = item.get('capable') == 'true'

                constraint, created = models.Constraint.objects.get_or_create(
                    schedule=schedule,
                    data1=data_1,
                    data2=data_2,
                    defaults={
                        'is_capable': capable,
                    },
                )
                if not created:
                    if constraint.is_capable != capable:
                        constraint.is_capable = capable
                        constraint.save(update_fields=['is_capable'])
                        modified = True
                else:
                    modified = True
                used_batasan_ids.append(constraint.id)

            data_deleted_count, _ = models.Data.objects.filter(schedule=schedule).exclude(id__in=used_data_ids).delete()
            batasan_deleted_count, _ = models.Constraint.objects.filter(schedule=schedule).exclude(id__in=used_batasan_ids).delete()

            if modified or data_deleted_count > 0 or batasan_deleted_count > 0:
                schedule.status = 'draft'
            schedule.save()
    except Exception:
        return JsonResponse({
            'success': False,
            'message': 'Terjadi kesalahan saat menyimpan jadwal.',
        })
    
    return JsonResponse({
        'success': True,
        'message': 'Berhasil menyimpan perubahan jadwal.',
        'schedule_status': schedule.status,
    })

@login_required
def jadwal_cancel(request, id):
    try:
        schedule = models.Schedule.objects.filter(user=request.user).get(id=id)
    except models.Schedule.DoesNotExist:
        messages.error(request, 'Gagal membatalkan perubahan pada jadwal ini.')
        return redirect(f'/jadwal/detail/{id}/')
    
    if schedule.status == 'draft':
        messages.success(request, 'Berhasil membatalkan perubahan pada jadwal ini.')
    return redirect(f'/jadwal/view/{id}/')

@login_required
def jadwal_delete(request, id):
    deleted_count, _ = models.Schedule.objects.filter(user=request.user, id=id).delete()

    if deleted_count > 0:
        messages.success(request, 'Jadwal berhasil dihapus.')
    else:
        messages.error(request, 'Jadwal gagal dihapus.')
    return redirect('/jadwal/')

@login_required
def jadwal_generate(request, id):
    try:
        schedule = models.Schedule.objects.filter(user=request.user).get(id=id)
    except models.Schedule.DoesNotExist:
        messages.error(request, 'Gagal menemukan jadwal, silakan coba lagi.')
        return redirect('/jadwal/')

    if schedule.status == 'done':
        return redirect(f'/jadwal/view/{schedule.id}/')
    
    hari_ids = models.Data.objects.filter(schedule=schedule, entity='hari').values_list('entity_id')
    jam_pembelajaran_ids = models.Data.objects.filter(schedule=schedule, entity='jam_pembelajaran').values_list('entity_id')
    kelas_ids = models.Data.objects.filter(schedule=schedule, entity='kelas').values_list('entity_id')
    pelajaran_ids = models.Data.objects.filter(schedule=schedule, entity='pelajaran').values_list('entity_id')
    pengajar_ids = models.Data.objects.filter(schedule=schedule, entity='pengajar').values_list('entity_id')
    ruang_kelas_ids = models.Data.objects.filter(schedule=schedule, entity='ruang_kelas').values_list('entity_id')

    hari = models.Day.objects.filter(user=request.user, id__in=hari_ids).order_by('sequence')
    jam_pembelajaran = models.LessonHour.objects.filter(user=request.user, is_break=False, id__in=jam_pembelajaran_ids).order_by('sequence')
    kelas = models.Class.objects.filter(user=request.user, id__in=kelas_ids).order_by('sequence')
    pelajaran = models.Lesson.objects.filter(user=request.user, time_slot__gt=0, id__in=pelajaran_ids)
    pengajar = models.Educator.objects.filter(user=request.user, id__in=pengajar_ids)
    ruang_kelas = models.Classroom.objects.filter(user=request.user, class_capacity__gt=0, id__in=ruang_kelas_ids)

    empty_datas = []
    if not hari.exists():
        empty_datas.append('hari')
    if not jam_pembelajaran.exists():
        empty_datas.append('jam pembelajaran')
    if not kelas.exists():
        empty_datas.append('kelas')
    if not pelajaran.exists():
        empty_datas.append('pelajaran')
    if not pengajar.exists():
        empty_datas.append('pengajar')
    if not ruang_kelas.exists():
        empty_datas.append('ruang kelas')
    
    if empty_datas:
        messages.error(request, f'Data {", ".join(empty_datas)} tidak bisa kosong.')
        return redirect(f'/jadwal/detail/{schedule.id}/')

    total_kelas = kelas.count()
    available_class_capacity = sum([int(ruang.class_capacity) if ruang.is_same_time_shareable else 1 for ruang in ruang_kelas])
    if total_kelas > available_class_capacity:
        messages.error(request, f'{available_class_capacity} ruang kelas tidak cukup untuk {total_kelas} kelas.')
        return redirect(f'/jadwal/detail/{schedule.id}/')

    total_pengajar = pengajar.count()
    if (total_pengajar < total_kelas):
        minimum_classroom_needed = 0
        class_reached = 0
        classroom_shareable = ruang_kelas.filter(is_same_time_shareable=True).order_by('-class_capacity')
        for classroom in classroom_shareable:
            class_reached += classroom.class_capacity
            minimum_classroom_needed += 1
    
            if class_reached >= total_kelas:
                break
        if class_reached < total_kelas:
            classroom_needed = total_kelas - class_reached
            classroom_non_shareable = ruang_kelas.filter(is_same_time_shareable=False)
            minimum_classroom_needed += min(classroom_needed, classroom_non_shareable.count())

        if (total_pengajar < minimum_classroom_needed):
            messages.error(request, f'{total_pengajar} pengajar tidak cukup untuk mengajar {total_kelas} kelas ataupun paling sedikit {minimum_classroom_needed} ruang kelas yang dibutuhkan untuk seluruh kelas.')
            return redirect(f'/jadwal/detail/{schedule.id}/')

    list_hari = list(hari)
    list_jam_pembelajaran = list(jam_pembelajaran)
    list_kelas = list(kelas)
    list_pelajaran = list(pelajaran)
    list_pengajar = list(pengajar)
    list_ruang_kelas = list(ruang_kelas)

    # Mapped constraints data
    constraints = models.Constraint.objects.filter(schedule=schedule)
    constraints_data = defaultdict(lambda: {
        'capable': [],
        'not_capable': [],
        'capable_id1': [],
        'capable_id2': [],
    })
    constraint_order = {
        'hari': 1,
        'jam_pembelajaran': 2,
        'kelas': 3,
        'ruang_kelas': 4,
        'pengajar': 5,
        'pelajaran': 6,
    }
    for constraint in constraints:
        data1_entity = constraint.data1.entity
        id1 = constraint.data1.entity_id
        data1_order = constraint_order.get(data1_entity, 0)

        data2_entity = constraint.data2.entity
        id2 = constraint.data2.entity_id
        data2_order = constraint_order.get(data2_entity, 0)

        if data1_order > data2_order:
            data1_entity, data2_entity = data2_entity, data1_entity
            id1, id2 = id2, id1

        if constraint.is_capable:
            constraints_data[(data1_entity, data2_entity)]['capable'].append((id1, id2))
            constraints_data[(data1_entity, data2_entity)]['capable_id1'].append(id1)
            constraints_data[(data1_entity, data2_entity)]['capable_id2'].append(id2)
        else:
            constraints_data[(data1_entity, data2_entity)]['not_capable'].append((id1, id2))

    def is_constraint_capable(entity1, entity_id1, entity2, entity_id2):
        entity1_order = constraint_order.get(entity1, 0)
        entity2_order = constraint_order.get(entity2, 0)
        if entity1_order > entity2_order:
            entity1, entity2 = entity2, entity1
            entity_id1, entity_id2 = entity_id2, entity_id1
        
        constraint_data = constraints_data.get((entity1, entity2), False)
        if constraint_data:
            entity_ids = (entity_id1, entity_id2)
            if entity_ids in constraint_data['not_capable']:
                return 'restrict'
            if entity_ids in constraint_data['capable']:
                return 'required'
            else:
                if (entity_id1 in constraint_data['capable_id1']) or (entity_id2 in constraint_data['capable_id2']):
                    return 'restrict'
        return 'optional'
    
    kelas_length = len(list_kelas)
    pelajaran_length = len(list_pelajaran)
    pengajar_length = len(list_pengajar)
    ruang_kelas_length = len(list_ruang_kelas)

    jam_pembelajaran_length = len(list_jam_pembelajaran)
    jam_pembelajaran_ids = jam_pembelajaran.values_list('id', flat=True)

    model = cp_model.CpModel()
    possible_placements = {}
    used_hari = []

    possible_same_ruang_per_slot = defaultdict(list)
    grup_per_slot = {}
    possible_pelajaran_pengajar_per_ruang_slot = defaultdict(list)

    pengajar_pelajaran = {}
    pengajar_per_pelajaran = defaultdict(list)
    pelajaran_per_pengajar = defaultdict(list)
    multi_pelajaran = {}

    pengajar_ruang = {}
    possible_pengajar_per_ruang_slot = defaultdict(list)

    for k in list_kelas:
        is_last_kelas = kelas_length == (list_kelas.index(k) + 1)

        pelajaran_per_slot = defaultdict(list)

        for p in list_pelajaran:
            is_last_pelajaran = pelajaran_length == (list_pelajaran.index(p) + 1)
            kelas_pelajaran_capable = is_constraint_capable('kelas', k.id, 'pelajaran', p.id)

            time_slot = 0 if kelas_pelajaran_capable == 'restrict' else p.time_slot
            time_slot_per_pelajaran = []

            for t in list_pengajar:
                is_last_pengajar = pengajar_length == (list_pengajar.index(t) + 1)
                kelas_pengajar_capable = is_constraint_capable('kelas', k.id, 'pengajar', t.id)
                pengajar_pelajaran_capable = is_constraint_capable('pengajar', t.id, 'pelajaran', p.id)

                if (t.id, p.id) in pengajar_pelajaran:
                    pengajar_pelajaran_var = pengajar_pelajaran[(t.id, p.id)]
                else:
                    pengajar_pelajaran_var = model.new_bool_var(f'pengajar_pelajaran_{t.id}_{p.id}')
                    pengajar_pelajaran[(t.id, p.id)] = pengajar_pelajaran_var

                    pengajar_per_pelajaran[p.id].append(pengajar_pelajaran_var)
                    pelajaran_per_pengajar[t.id].append(pengajar_pelajaran_var)
                    if is_last_pelajaran:
                        total_pengajar_pelajaran = sum(pelajaran_per_pengajar[t.id])
                        if pengajar_length >= pelajaran_length:
                            # Each teacher must teach one lesson
                            model.add(total_pengajar_pelajaran == 1)
                        else:
                            multi_pelajaran_var = model.new_bool_var(f'multi_pelajaran_{t.id}')
                            multi_pelajaran[t.id] = multi_pelajaran_var

                            # Get the least teachers with multiple lessons
                            model.add(total_pengajar_pelajaran >= 2).only_enforce_if(multi_pelajaran_var)
                            model.add(total_pengajar_pelajaran == 1).only_enforce_if(multi_pelajaran_var.Not())

                # Constraint to determine if teacher can teach this lesson
                if pengajar_pelajaran_capable == 'restrict':
                    model.add(pengajar_pelajaran_var == 0)
                elif pengajar_pelajaran_capable == 'required':
                    model.add(pengajar_pelajaran_var == 1)

                for r in list_ruang_kelas:
                    is_last_ruang_kelas = ruang_kelas_length == (list_ruang_kelas.index(r) + 1)
                    kelas_ruang_capable = is_constraint_capable('kelas', k.id, 'ruang_kelas', r.id)
                    ruang_pelajaran_capable = is_constraint_capable('ruang_kelas', r.id, 'pelajaran', p.id)
                    ruang_pengajar_capable = is_constraint_capable('ruang_kelas', r.id, 'pengajar', t.id)

                    kapasitas_kelas = r.class_capacity if r.is_same_time_shareable else 1

                    for h in list_hari:
                        hari_kelas_capable = is_constraint_capable('hari', h.id, 'kelas', k.id)
                        hari_pelajaran_capable = is_constraint_capable('hari', h.id, 'pelajaran', p.id)
                        hari_pengajar_capable = is_constraint_capable('hari', h.id, 'pengajar', t.id)
                        hari_ruang_capable = is_constraint_capable('hari', h.id, 'ruang_kelas', r.id)

                        used_hari_var = model.new_bool_var(f'used_hari_{k.id}_{p.id}_{t.id}_{r.id}_{h.id}')
                        used_hari.append(used_hari_var)
                        jam_per_hari = []

                        for j in list_jam_pembelajaran:
                            jam_kelas_capable = is_constraint_capable('jam_pembelajaran', j.id, 'kelas', k.id)
                            jam_pelajaran_capable = is_constraint_capable('jam_pembelajaran', j.id, 'pelajaran', p.id)
                            jam_pengajar_capable = is_constraint_capable('jam_pembelajaran', j.id, 'pengajar', t.id)
                            jam_ruang_capable = is_constraint_capable('jam_pembelajaran', j.id, 'ruang_kelas', r.id)
                            hari_jam_capable = is_constraint_capable('hari', h.id, 'jam_pembelajaran', j.id)

                            if hari_kelas_capable == 'restrict' and jam_kelas_capable == 'restrict':
                                hari_jam_kelas_capable = 'restrict'
                            elif hari_kelas_capable == 'required' and jam_kelas_capable == 'required':
                                hari_jam_kelas_capable = 'required'
                            else:
                                hari_jam_kelas_capable = 'optional'
                            
                            if hari_ruang_capable == 'restrict' and jam_ruang_capable == 'restrict':
                                hari_jam_ruang_capable = 'restrict'
                            elif hari_ruang_capable == 'required' and jam_ruang_capable == 'required':
                                hari_jam_ruang_capable = 'required'
                            else:
                                hari_jam_ruang_capable = 'optional'
                            
                            if hari_pengajar_capable == 'restrict' and jam_pengajar_capable == 'restrict':
                                hari_jam_pengajar_capable = 'restrict'
                            elif hari_pengajar_capable == 'required' and jam_pengajar_capable == 'required':
                                hari_jam_pengajar_capable = 'required'
                            else:
                                hari_jam_pengajar_capable = 'optional'

                            if hari_pelajaran_capable == 'restrict' and jam_pelajaran_capable == 'restrict':
                                hari_jam_pelajaran_capable = 'restrict'
                            elif hari_pelajaran_capable == 'required' and jam_pelajaran_capable == 'required':
                                hari_jam_pelajaran_capable = 'required'
                            else:
                                hari_jam_pelajaran_capable = 'optional'

                            all_capable_combination = [
                                kelas_pelajaran_capable,
                                kelas_pengajar_capable,
                                pengajar_pelajaran_capable,
                                kelas_ruang_capable,
                                ruang_pelajaran_capable,
                                ruang_pengajar_capable,
                                hari_jam_capable,
                                hari_jam_kelas_capable,
                                hari_jam_ruang_capable,
                                hari_jam_pengajar_capable,
                                hari_jam_pelajaran_capable
                            ]

                            possible_placement_var = model.new_bool_var(f'possible_placement_{k.id}_{p.id}_{t.id}_{r.id}_{h.id}_{j.id}')
                            possible_placements[(k.id, p.id, t.id, r.id, h.id, j.id)] = possible_placement_var

                            if 'restrict' in all_capable_combination:
                                # Set to 0 if this possible placement is restrict by one of the capable combination
                                model.add(possible_placement_var == 0)
                            
                            pelajaran_per_slot[(h.id, j.id)].append(possible_placement_var)
                            time_slot_per_pelajaran.append(possible_placement_var)
                            jam_per_hari.append(possible_placement_var)

                            # Prevent multiple lesson in the same time slot for each class
                            if is_last_pelajaran:
                                model.add(sum(pelajaran_per_slot[(h.id, j.id)]) <= 1)

                            # Set max class at the same time in the same classroom
                            possible_same_ruang_per_slot[(r.id, h.id, j.id)].append(possible_placement_var)
                            if is_last_kelas and is_last_pelajaran and is_last_pengajar:
                                model.add(sum(possible_same_ruang_per_slot[(r.id, h.id, j.id)]) <= kapasitas_kelas)
                            
                            if (p.id, t.id, r.id, h.id, j.id) in grup_per_slot:
                                grup_per_slot_var = grup_per_slot[(p.id, t.id, r.id, h.id, j.id)]
                            else:
                                grup_per_slot_var = model.new_bool_var(f'grup_per_slot_{p.id}_{t.id}_{r.id}_{h.id}_{j.id}')
                                grup_per_slot[(p.id, t.id, r.id, h.id, j.id)] = grup_per_slot_var
                                possible_pelajaran_pengajar_per_ruang_slot[(r.id, h.id, j.id)].append(grup_per_slot_var)

                                # Each classroom can only have one teacher-lesson in the same time
                                if is_last_pelajaran and is_last_pengajar:
                                    model.add(sum(possible_pelajaran_pengajar_per_ruang_slot[(r.id, h.id, j.id)]) <= 1)
                            # Determine which group is available
                            model.add(possible_placement_var <= grup_per_slot_var)

                            # Determine if teacher available to teach lesson
                            model.add(possible_placement_var <= pengajar_pelajaran_var)

                            if (t.id, r.id, h.id, j.id) in pengajar_ruang:
                                pengajar_ruang_var = pengajar_ruang[(t.id, r.id, h.id, j.id)]
                            else:
                                pengajar_ruang_var = model.new_bool_var(f'pengajar_ruang_{t.id}_{r.id}_{h.id}_{j.id}')
                                pengajar_ruang[(t.id, r.id, h.id, j.id)] = pengajar_ruang_var
                                possible_pengajar_per_ruang_slot[(t.id, h.id, j.id)].append(pengajar_ruang_var)

                                # Each teaher can only teach in one classroom in the same time
                                if is_last_ruang_kelas:
                                    model.add(sum(possible_pengajar_per_ruang_slot[(t.id, h.id, j.id)]) <= 1)
                            # Determine if teacher available in that classroom
                            model.add(possible_placement_var <= pengajar_ruang_var)

                        # Get the least days used for a lesson
                        model.add(sum(jam_per_hari) > 0).only_enforce_if(used_hari_var)
                        model.add(sum(jam_per_hari) == 0).only_enforce_if(used_hari_var.Not())

                        # Prevent non-continuous same lesson in the same day
                        for j1 in range(jam_pembelajaran_length):
                            for j2 in range(j1 + 1, jam_pembelajaran_length):
                                for j3 in range(j2 + 1, jam_pembelajaran_length):
                                    model.add(
                                        possible_placements.get((k.id, p.id, t.id, r.id, h.id, jam_pembelajaran_ids[j1]), 0)
                                        + possible_placements.get((k.id, p.id, t.id, r.id, h.id, jam_pembelajaran_ids[j3]), 0)
                                        <=
                                        possible_placements.get((k.id, p.id, t.id, r.id, h.id, jam_pembelajaran_ids[j2]), 0)
                                        + 1
                                    )

            # Ensure each lesson to take their exact time slot for each class
            model.add(sum(time_slot_per_pelajaran) == time_slot)

            if is_last_kelas:
                if pengajar_length <= pelajaran_length:
                    # Each lesson must have one teacher
                    model.add(sum(pengajar_per_pelajaran[p.id]) == 1)
                else:
                    # Each lesson can have more than one teacher
                    model.add(sum(pengajar_per_pelajaran[p.id]) >= 1)

    if pengajar_length > pelajaran_length:
        # Get the least days used for each lessons and the least lessons with multiple teachers
        model.minimize(sum(used_hari) * 1000000 + sum(list(pengajar_pelajaran.values())))
    elif pengajar_length < pelajaran_length:
        # Get the least days used for each lessons and the least teachers with multiple lessons
        model.minimize(sum(used_hari) * 1000000 + sum(list(multi_pelajaran.values())))
    else:
        # Get the least days used for each lessons
        model.minimize(sum(used_hari) * 1000000)

    solver = cp_model.CpSolver()
    status = solver.solve(model)
    
    if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        messages.error(request, 'Mohon periksa kembali data dan batasan Anda.')
        return redirect(f'/jadwal/detail/{schedule.id}/')

    # Remove old schedule data before insert new one
    models.ScheduleData.objects.filter(schedule=schedule).delete()

    for k in list_kelas:
        for p in list_pelajaran:
            for t in list_pengajar:
                for r in list_ruang_kelas:
                    for h in list_hari:
                        last_created_lesson_hour = 0
                        last_data = False

                        for index, j in enumerate(list_jam_pembelajaran):
                            if (k.id, p.id, t.id, r.id, h.id, j.id) in possible_placements and solver.value(possible_placements[(k.id, p.id, t.id, r.id, h.id, j.id)]):
                                print(k.name, h.name, j.start_time, j.finish_time, p.name, t.name, r.name)
                                if last_data and last_data == f'{k.id}_{p.id}_{t.id}_{r.id}_{h.id}_{list_jam_pembelajaran[index - 1].id}':
                                    try:
                                        record = models.ScheduleData.objects.get(
                                            schedule=schedule,
                                            classes=k,
                                            day=h,
                                            lesson_hour=last_created_lesson_hour,
                                            lesson=p,
                                            educator=t,
                                            classroom=r,
                                        )
                                        record.time_slot += 1
                                        record.save()
                                        last_data = f'{k.id}_{p.id}_{t.id}_{r.id}_{h.id}_{j.id}'
                                        continue
                                    except Exception:
                                        pass
                                models.ScheduleData.objects.create(
                                    schedule=schedule,
                                    classes=k,
                                    day=h,
                                    lesson_hour=j,
                                    lesson=p,
                                    educator=t,
                                    classroom=r,
                                    time_slot=1,
                                )
                                last_created_lesson_hour = j.id
                                last_data = f'{k.id}_{p.id}_{t.id}_{r.id}_{h.id}_{j.id}'

    schedule.status = 'done'
    schedule.save()
    return redirect(f'/jadwal/view/{schedule.id}/')

@login_required
def jadwal_view(request, id):
    try:
        schedule = models.Schedule.objects.filter(user=request.user).get(id=id)
    except models.Schedule.DoesNotExist:
        messages.error(request, 'Gagal tambah / menemukan jadwal, silakan coba lagi.')
        return redirect('/jadwal/')
    
    if schedule.status == 'draft':
        return redirect(f'/jadwal/detail/{schedule.id}/')
    
    kelas_ids = models.Data.objects.filter(schedule=schedule, entity='kelas').values_list('entity_id')
    hari_ids = models.Data.objects.filter(schedule=schedule, entity='hari').values_list('entity_id')

    jam_pembelajaran_ids = models.Data.objects.filter(schedule=schedule, entity='jam_pembelajaran').values_list('entity_id')
    all_jam_pembelajaran = models.LessonHour.objects.filter(user=request.user, id__in=jam_pembelajaran_ids).order_by('sequence')
    list_jam_pembelajaran = list(all_jam_pembelajaran)
    jam_pembelajaran_by_id = {
        jam.id: index
        for index, jam in enumerate(list_jam_pembelajaran)
    }

    def get_colors(text):
        digest = hashlib.md5(text.encode('utf-8')).hexdigest()

        # Hue: 0-359
        hue = int(digest[:8], 16) % 360

        # Keep saturation and lightness fixed for nice-looking colors
        background = f"hsl({hue} 100% 80% / 75%)"
        foreground = f"hsl({hue}, 100%, 30%)"

        return background, foreground

    def get_schedule_values(schedule_data, bg_color, text_color):
        return {
            'lesson': schedule_data.lesson.name,
            'educator': schedule_data.educator.name if schedule_data.educator else None,
            'classroom': schedule_data.classroom.name if schedule_data.classroom else None,
            'time_slot': 0,
            'bg_color': bg_color,
            'text_color': text_color,
        }

    schedule_datas = models.ScheduleData.objects.filter(schedule=schedule)
    schedule_map = {}
    for schedule_data in schedule_datas:
        lesson_hour_id = schedule_data.lesson_hour.id
        time_slot = int(schedule_data.time_slot)
        bg_color, text_color = get_colors(schedule_data.lesson.name)

        schedule_map[(schedule_data.classes.id, schedule_data.day.id, lesson_hour_id)] = get_schedule_values(schedule_data, bg_color, text_color)

        lesson_hour_index = jam_pembelajaran_by_id[lesson_hour_id]
        remaining_time_slot = time_slot
        n = 0
        while remaining_time_slot > 0:
            jam_pembelajaran = list_jam_pembelajaran[lesson_hour_index+n]
            is_break = jam_pembelajaran.is_break
            if not is_break:
                schedule_map[(schedule_data.classes.id, schedule_data.day.id, lesson_hour_id)]['time_slot'] += 1
                if lesson_hour_id != jam_pembelajaran.id:
                    schedule_map[(schedule_data.classes.id, schedule_data.day.id, jam_pembelajaran.id)] = get_schedule_values(schedule_data, bg_color, text_color)
                remaining_time_slot -= 1
            else:
                jam_pembelajaran = list_jam_pembelajaran[lesson_hour_index+n+1]
                lesson_hour_id = jam_pembelajaran.id
                schedule_map[(schedule_data.classes.id, schedule_data.day.id, lesson_hour_id)] = get_schedule_values(schedule_data, bg_color, text_color)
            n += 1
    
    context = {
        'schedule_id': schedule.id,
        'schedule_name': schedule.name,
        'schedule_status': schedule.status,
        'data_kelas': models.Class.objects.filter(user=request.user, id__in=kelas_ids).order_by('sequence').values_list('id', 'name'),
        'data_hari': models.Day.objects.filter(user=request.user, id__in=hari_ids).order_by('sequence').values_list('id', 'name'),
        'data_jam_pembelajaran': all_jam_pembelajaran.values(),
        'data_schedule': schedule_map,
    }
    return render(request, 'jadwal_view.html', context)
