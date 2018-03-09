import configparser
import json
import os
import time
from collections import defaultdict
from datetime import datetime, timedelta
from itertools import zip_longest

import click

from terminaltables import SingleTable
from timetable import timetable

TIMES = [
    '08:00 - 09:00', '09:00 - 10:00', '10:00 - 11:00', '11:00 - 12:00',
    '12:00 - 13:00', '13:00 - 14:00', '14:00 - 15:00', '15:00 - 16:00',
    '16:00 - 17:00'
]


def activity_as_str(activity, section, course):
    return f'{course.title} {section}'


def render_day(day, activities):
    day_activities = sorted(activities)
    rendered_activities = [day]
    binned_activities = [[] for _ in range(len(TIMES))]
    day_start = datetime.strptime('08:00', '%H:%M')
    for activity in day_activities:
        activity_start, _, _ = activity
        tdelta = activity_start.start_time - day_start
        activity_length = activity_start.end_time - activity_start.start_time
        hour_index = tdelta.seconds // 3600
        length_in_hours = activity_length.seconds // 3600
        for i in range(length_in_hours):
            binned_activities[hour_index + i].append(activity)

    rendered_activities.extend([
        '\n'.join(activity_as_str(*activity) for activity in act_bin)
        for act_bin in binned_activities
    ])

    return rendered_activities


def parse_iso_date(datestring):
    return datetime.strptime(datestring, '%Y-%m-%d')


def parse_config(filename):
    converters = {'date': parse_iso_date}
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
            course = timetable.Course(course_name, course_year,
                                      course_semester)
            courses.append(course)
    return courses


def get_allocated_activity(config, course, section_name, default=1):
    section_config_name = f'{course.title}/{section_name}'
    act_id = default
    if config.has_section(section_config_name):
        act_id = config[section_config_name].get('allocated_activity', default)
    return act_id


@click.group()
@click.option(
    '--config-path',
    envvar='TIMETABLE_CONFIG_PATH',
    type=click.Path(),
    help='Path to configuration (config, data.json).',
    required=True)
@click.pass_context
def cli(ctx, config_path):
    ''' View and manage your UC timetable. '''
    if not os.path.exists(config_path):
        os.makedirs(config_path)

    config = parse_config(os.path.join(config_path, 'config'))
    courses = {(course.title, course.year, course.semester): course
               for course in get_courses(config)}
    activities = defaultdict(list)
    json_path = os.path.join(config_path, 'data.json')
    if os.path.exists(json_path):
        with open(json_path, 'r') as infile:
            json_config = json.load(
                infile, object_hook=timetable.timetable_load_hook)
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
            allocated_activity = get_allocated_activity(
                config, course, section_name)
            a = section_activities.get(
                allocated_activity,
                section_activities[list(section_activities)[0]])
            activities[a.day].append((a, section_name, course))

    ctx.obj['courses'] = courses
    ctx.obj['activities'] = activities

    with open(json_path, 'w') as out:
        json.dump(list(courses.values()), out, cls=timetable.TimetableEncoder)


@cli.command('show')
@click.pass_context
def show_timetable(ctx):
    ''' Show your weekly timetable. '''
    sorted_days = sorted(
        ctx.obj['activities'].items(),
        key=lambda kv: timetable.Activity.days[kv[0]])
    rendered_days = [['Times'] + TIMES]
    for day, day_activities in sorted_days:
        rendered_activities = render_day(day, day_activities)
        rendered_days.append(rendered_activities)

    tabled_activities = zip_longest(
        *[list(day) for day in rendered_days], fillvalue='')
    print(SingleTable(list(tabled_activities)).table)


@cli.command('next')
@click.option(
    '--show-time',
    is_flag=True,
    default=False,
    help='Show the time to your next class.')
@click.option(
    '--at',
    help=
    'Set the date and time (in YYYY-MM-DD HH:MM format) to find next class for.',
    default=None)
@click.pass_context
def show_next(ctx, show_time, at):
    ''' Show your next class. '''
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    if at is None:
        today = datetime.now()
    else:
        today = datetime.strptime(at, '%Y-%m-%d %H:%M')

    if today.weekday() > 4:
        return

    week_day = days[today.weekday()]

    next_classes = []
    days_activities = sorted(ctx.obj['activities'][week_day])
    for activity in days_activities:
        start = activity[0].start_time
        start_datetime = today.replace(hour=start.tm_hour, minute=start.tm_min)
        if len(next_classes) > 0 and start == next_classes[-1][0].start_time:
            next_classes.append(activity)
        elif len(next_classes) > 0 and start != next_classes[-1][0].start_time:
            break
        elif today < start_datetime:
            next_classes = [activity]

    if len(next_classes) == 0:
        return
    elif show_time:
        start = next_classes[0][0].start_time
        start_datetime = today.replace(hour=start.tm_hour, minute=start.tm_min)
        print(start_datetime - today)
    else:
        for activity, title, course in next_classes:
            valid_location = next((loc for loc in activity.location
                                   if loc.valid_for(today)), None)
            if valid_location is None:
                continue
            print(
                f'{course.title} - {title} @ {activity.start}: {valid_location.name}'
            )


def main():
    cli(obj={})
