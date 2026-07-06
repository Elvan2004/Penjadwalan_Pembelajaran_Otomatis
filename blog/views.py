import json

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
        
        name = request.POST.get('name', '').strip()
        institute_name = request.POST.get('institute_name', '').strip()

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
            'name': {'label': 'Nama', 'type': 'text'},
            'sequence': {'label': 'Urutan', 'type': 'number'},
            'active': {'label': 'Aktif', 'type': 'checkbox'},
        },
        'jam-pembelajaran': {
            'start_time': {'label': 'Mulai', 'type': 'time'},
            'finish_time': {'label': 'Selesai', 'type': 'time'},
            'sequence': {'label': 'Urutan', 'type': 'number'},
            'is_break': {'label': 'Istirahat', 'type': 'checkbox'},
            'active': {'label': 'Aktif', 'type': 'checkbox'},
        },
        'kelas': {
            'name': {'label': 'Nama', 'type': 'text'},
            'sequence': {'label': 'Urutan', 'type': 'number'},
            'active': {'label': 'Aktif', 'type': 'checkbox'},
        },
        'ruang-kelas': {
            'name': {'label': 'Nama', 'type': 'text'},
            'class_capacity': {'label': 'Kapasitas Kelas', 'type': 'number'},
            'is_same_time_shareable': {'label': 'Berbagi Kelas', 'type': 'checkbox'},
            'active': {'label': 'Aktif', 'type': 'checkbox'},
        },
        'pengajar': {
            'name': {'label': 'Nama', 'type': 'text'},
            'active': {'label': 'Aktif', 'type': 'checkbox'},
        },
        'pelajaran': {
            'name': {'label': 'Nama', 'type': 'text'},
            'time_slot': {'label': 'Slot Waktu', 'type': 'number'},
            'active': {'label': 'Aktif', 'type': 'checkbox'},
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

    to_exclude_ids = []
    if data != 'jadwal':
        entity = data.replace('-', '_')
        data_obj = models.Data.objects.filter(entity=entity)
        for id in ids:
            try:
                data_obj.get(entity_id=int(id))
            except models.Data.DoesNotExist:
                continue
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
            return f'<strong class="text-blue-600">Jam Pembelajaran</strong> | {data.start_time} - {data.finish_time}' + (' (Istirahat)' if data.is_break else '')
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
    
    hari_ids = models.Data.objects.filter(schedule=schedule, entity='hari').values_list('entity_id')
    hari = models.Day.objects.filter(user=request.user, id__in=hari_ids).order_by('sequence')

    jam_pembelajaran_ids = models.Data.objects.filter(schedule=schedule, entity='jam_pembelajaran').values_list('entity_id')
    jam_pembelajaran = models.LessonHour.objects.filter(user=request.user, id__in=jam_pembelajaran_ids).order_by('sequence')

    kelas_ids = models.Data.objects.filter(schedule=schedule, entity='kelas').values_list('entity_id')
    kelas = models.Class.objects.filter(user=request.user, id__in=kelas_ids).order_by('sequence')

    constraints = models.Constraint.objects.filter(schedule=schedule)

    for kelas_obj in kelas:
        for hari_obj in hari:
            for jam_obj in jam_pembelajaran:
                models.ScheduleData.objects.create(
                    class_id=kelas_obj,
                    day_id=hari_obj,
                    lesson_hour_id=jam_obj,
                )

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
    
    context = {
        'schedule_id': schedule.id,
        'schedule_name': schedule.name,
        'schedule_status': schedule.status,
    }
    return render(request, 'jadwal_view.html', context)
