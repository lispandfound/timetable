import click
import timetable
import time
from datetime import datetime, timedelta
import configparser
import json
import os
from terminaltables import SingleTable
from collections import defaultdict
from itertools import zip_longest


def activity_as_str(activity, section, course):
    return f'{course.title} {section}'


def render_day(day, activities):
    day_activities = sorted(activities)
    rendered_activities = [day]
    i = 0
    while i < len(day_activities):
        da = day_activities[i]
        if i > 0:
            prev_activity = day_activities[i - 1]
            if da[0].start_time < prev_activity[0].end_time:
                start = time.strftime('%H:%M', da[0].start_time)
                if da[2] != prev_activity[2]:
                    rendered_activities[-1] = f'{activity_as_str(*prev_activity)}\n{activity_as_str(*da)}'
                i += 1
                continue
            time_delta = int(time.mktime(da[0].start_time) - time.mktime(prev_activity[0].end_time))
            rendered_activities.extend([' '] * (time_delta // 3600))
        else:
            start = time.mktime(time.strptime('08:00', '%H:%M'))
            time_delta = int(time.mktime(da[0].start_time) - start)
            rendered_activities.extend([' '] * (time_delta // 3600))

        rendered_activities.append(activity_as_str(*da))
        i += 1

    return rendered_activities


def parse_iso_date(datestring):
    return time.strptime(datestring, '%Y-%m-%d')


def parse_config(filename):
    converters = {
        'date': parse_iso_date
    }
    parser = configparser.ConfigParser(converters=converters)
    with open(filename, 'r') as infile:
        parser.read_file(infile)
        return parser


def get_courses(config):
    courses = []
    for section in config.sections():
        if section.startswith('course/'):
            course_name = section[7:]
            course_year = config[section].getint('year')
            course_semester = config[section].getint('semester')
            course = timetable.Course(course_name, course_year, course_semester)
            courses.append(course)
    return courses


def get_allocated_activity(config, course, section_name, default=1):
    section_config_name = f'{course.title}/{section_name}'
    act_id = default
    if config.has_section(section_config_name):
        act_id = config[section_config_name].getint('allocated_activity', default)
    return max(act_id - 1, 0)


@click.group()
@click.option('--config-path', envvar='TIMETABLE_CONFIG_PATH', type=click.Path(), help='Path to configuration (config, data.json).', required=True)
@click.pass_context
def cli(ctx, config_path):
    ''' View and manage your UC timetable. '''
    if not os.path.exists(config_path):
        os.makedirs(config_path)

    config = parse_config(os.path.join(config_path, 'config'))
    courses = {(course.title, course.year, course.semester): course for course in get_courses(config)}
    activities = defaultdict(list)
    json_path = os.path.join(config_path, 'data.json')
    if os.path.exists(json_path):
        with open(json_path, 'r') as infile:
            json_config = json.load(infile,
                                    object_hook=timetable.timetable_load_hook)
        for course in json_config:
            if not isinstance(course, timetable.Course):
                continue
            key_tuple = (course.title, course.year, course.semester)
            if key_tuple in courses:
                courses[key_tuple] = course

    for course in courses.values():
        if course.activities == {}:
            course.fetch_details()
        for section_name, section_activities in course.activities.items():
            allocated_activity = get_allocated_activity(config, course, section_name)
            if len(section_activities) > 0 and allocated_activity < len(section_activities):
                a = section_activities[allocated_activity]
                activities[a.day].append((a, section_name, course))

    ctx.obj['courses'] = courses
    ctx.obj['activities'] = activities

    with open(json_path, 'w') as out:
        json.dump(list(courses.values()), out, cls=timetable.TimetableEncoder)


@cli.command('timetable')
@click.pass_context
def show_timetable(ctx):
    ''' Show your weekly timetable. '''
    sorted_days = sorted(ctx.obj['activities'].items(), key=lambda kv: timetable.Activity.days[kv[0]])
    rendered_days = [['Times', '08:00 - 09:00', '09:00 - 10:00', '10:00 - 11:00', '11:00 - 12:00', '12:00 - 13:00', '13:00 - 14:00', '14:00 - 15:00', '16:00 - 17:00', '17:00 - 18:00']]
    for day, day_activities in sorted_days:
        rendered_activities = render_day(day, day_activities)
        rendered_days.append(rendered_activities)

    tabled_activities = zip_longest(*[list(day) for day in rendered_days], fillvalue='')
    print(SingleTable(list(tabled_activities)).table)


@cli.command('next')
@click.option('--show-time', is_flag=True, default=False, help='Show the time to your next class.')
@click.pass_context
def show_next(ctx, show_time):
    ''' Show your next class. '''
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    today = datetime.now()
    week_day = days[today.weekday()]

    next_classes = []
    if today.weekday() < 4:
        days_activities = sorted(ctx.obj['activities'][week_day])
        i = 0
        while i < len(days_activities):
            next_activity = days_activities[i]
            start = next_activity[0].start_time
            start_datetime = today.replace(hour=start.tm_hour, minute=start.tm_min)
            if len(next_classes) > 0 and start == next_classes[-1][0].start_time:
                next_classes.append(next_activity)
            elif len(next_classes) > 0 and start != next_classes[-1][0].start_time:
                break
            elif today < start_datetime:
                next_classes = [next_activity]
            i += 1

    if len(next_classes) == 0:
        return
    elif show_time:
        start = next_classes[0][0].start_time
        start_datetime = today.replace(hour=start.tm_hour, minute=start.tm_min)
        print(start_datetime - today)
    else:
        for activity, title, course in next_classes:
            print(f'{course.title} - {title} @ {activity.start}: {activity.location}')



def main():
    cli(obj={})
