from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.simple_tag
def get_schedule_result(schedule_map, kelas_id, hari_id, jam_id):
    return schedule_map.get((kelas_id, hari_id, jam_id))
