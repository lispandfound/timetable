import click
import timetable
import time
import configparser
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
                    rendered_activities[-1] = f'CLASH: {activity_as_str(*prev_activity)} & {activity_as_str(*da)}'
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
@click.pass_context
def cli(ctx):
    config = parse_config('./test.ini')
    courses = get_courses(config)
    activities = defaultdict(list)
    for course in courses:
        course.fetch_details()
        for section_name, section_activities in course.activities.items():
            allocated_activity = get_allocated_activity(config, course, section_name)
            if len(section_activities) > 0 and allocated_activity < len(section_activities):
                a = section_activities[allocated_activity]
                activities[a.day].append((a, section_name, course))

    ctx.obj['courses'] = courses
    ctx.obj['activities'] = activities


@cli.command('timetable')
@click.pass_context
def show_timetable(ctx):
    sorted_days = sorted(ctx.obj['activities'].items(), key=lambda kv: timetable.Activity.days[kv[0]])
    rendered_days = [['Times', '08:00 - 09:00', '09:00 - 10:00', '10:00 - 11:00', '11:00 - 12:00', '12:00 - 13:00', '13:00 - 14:00', '14:00 - 15:00', '16:00 - 17:00', '17:00 - 18:00']]
    for day, day_activities in sorted_days:
        rendered_activities = render_day(day, day_activities)
        rendered_days.append(rendered_activities)

    tabled_activities = zip_longest(*[list(day) for day in rendered_days], fillvalue='')
    print(SingleTable(list(tabled_activities)).table)


if __name__ == '__main__':
    cli(obj={})
