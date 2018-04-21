""" Print, display, and manage your UC timetable.

Usage:
    timetable [-v] show [--on=<date>] [--drop-cache]
    timetable [-v] next [--time] [--drop-cache]

Options:
    -h, --help         Show this screen.
    --on=<date>        Show the timetable for this date.
    --drop-cache       Drop the current data file.
    --time             Show the time to the next class.
    -v, --verbose      Be more verbose.
"""
import calendar
import os
import pathlib
import pickle
from datetime import datetime

from docopt import docopt
from schema import Or, Schema, SchemaError, Use

from . import config, timetable

COMMAND_MAP = {}

COMMAND_SCHEMA = Schema({
    '--on':
    Or(Use(lambda v: datetime.strptime(v, '%Y-%m-%d')), None),
    '--drop-cache':
    bool,
    '--time':
    bool,
    'next':
    bool,
    'show':
    bool,
    '--verbose':
    bool
})


def command(name):
    ''' Declare a command to be used by the argument parser.

    Args:
        name (str): The name of the command.

    Returns:
        function: A function takes one argument callback and appends
                  name: callback to COMMAND_MAP. '''

    def decorator(callback):
        COMMAND_MAP[name] = callback
        return callback

    return decorator


def get_config():
    ''' Get all configuration files/data from the config directory.

    "the config directory" in this context means the path specified by
    the TIMETABLE_CONFIG_PATH environment variable.

    Returns:
        (pathlib.Path, list of courses, dict): The
        path to the configuration directory, the list of courses found in
        the data file there, and the parsed config file. '''
    config_path = pathlib.Path(os.getenv('TIMETABLE_CONFIG_PATH'))
    data_path = config_path / 'data'
    config_file = config_path / 'config'
    data = None
    if data_path.exists():
        with open(data_path, 'rb') as infile:
            data = pickle.load(infile)
    return config_path, data, config.parse_config(config_file)


def print_activity(config_dict, date, course, activity):
    ''' Print an activity.

    Prints an activity in the context of the course it belongs to, the
    current date, and the colours specified by the user.

    Args:
        config_dict (dict): Used to obtain the colour to print the course
                       in.
        date (datetime.datetime): The date to filter locations by.
        course (timetable.Course): The parent course of the activity.
        activity (timetable.Activity): The activity to print. '''
    relevant_location = activity.location_valid_for(date)
    start = activity.start.strftime('%H:%M')
    colour = config.colour_of_course(config_dict, course)
    title = f'{colour.value}{course.title}{config.TermColour.RESET.value}'
    end = activity.end.strftime('%H:%M')
    print(
        f'{title} {activity.name} @ {relevant_location.place} :: {start} - {end}'
    )


@command('show')
def show_timetable(config_dict, courses, selected_activities, args):
    ''' Show a timetable for a particular date.

    This is the output of the 'show' subcommand.

    Args:
        config_dict (dict): The parsed configuration file.
        courses (list of timetable.Course): A list of the parsed courses.
        selected_activities (dict): A dictionary that determines what
                                    activities are selected by the user.
        args (dict): Additional command line arguments. '''
    date = args['--on'] or datetime.now()
    activities = timetable.activities_on(courses, date, selected_activities)
    day = calendar.day_name[date.weekday()]
    isodate = date.date().isoformat()
    print(f'Showing timetable for {day}, {isodate}')
    for course, activity in activities:
        print_activity(config_dict, date, course, activity)


@command('next')
def show_next(config_dict, courses, selected_activities, args):
    ''' Show a timetable for a particular date.

    This is the output of the 'show' subcommand.

    Args:
        config_dict (dict): The parsed configuration file.
        courses (list of timetable.Course): A list of the parsed courses.
        selected_activities (dict): A dictionary that determines what
                                    activities are selected by the user.
        args (dict): Additional command line arguments. '''
    now = datetime.now()
    activities = timetable.activities_on(courses, now, selected_activities)
    next_activity = next(((course, activity) for course, activity in activities
                          if activity.start > now.time()), None)
    if next_activity is not None and args['--time']:
        course, act = next_activity
        time_dt = now.replace(hour=act.start.hour, minute=act.start.minute)
        delta = time_dt - now
        print(delta)
    elif next_activity is not None:
        course, act = next_activity
        print_activity(config_dict, now, course, act)


def main():
    ''' Main function. '''
    arguments = docopt(__doc__, version='Timetable 0.1.0.')
    try:
        arguments = COMMAND_SCHEMA.validate(arguments)
    except SchemaError:
        exit(__doc__)
    try:
        config_path, data, config_dict = get_config()
    except SchemaError as e:
        if arguments['--verbose']:
            exit(e.code)
        else:
            exit('Failed to parse config.')
    courses = config.get_courses(config_dict)
    if data is None or arguments['--drop-cache']:
        for course in courses:
            course.fetch_activities()
    else:
        courses = data
    selected_activities = config.get_selected_activities(config_dict, courses)
    # Find first callback that docopt believes has been called.
    callback = next(callback for cmd, callback in COMMAND_MAP.items()
                    if arguments[cmd] is True)
    callback(config_dict, courses, selected_activities, arguments)
    with open(config_path / 'data', 'wb') as out:
        pickle.dump(courses, out)


if __name__ == '__main__':
    main()
