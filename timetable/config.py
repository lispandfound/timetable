import configparser
from enum import Enum

from schema import And, Optional, Or, Schema, SchemaError, Use

from . import timetable


class TermColour(Enum):
    ''' TermColour represents a subset of the ANSI escape sequence for colour.

    Attributes:
        - All values of the attributes have meaning better explained by referring to the
          console_codes(4) man page.
        NONE (str): A noop string in the context of terminal colours. '''
    BLACK = '\u001b[30m'
    RED = '\u001b[31m'
    GREEN = '\u001b[32m'
    YELLOW = '\u001b[33m'
    BLUE = '\u001b[34m'
    MAGENTA = '\u001b[35m'
    CYAN = '\u001b[36m'
    WHITE = '\u001b[37m'
    NONE = ''
    RESET = '\u001b[0m'

    @classmethod
    def from_colour_string(cls, colour_string):
        ''' Create a TermColour from a colour string.

        The colour matching is case insensitive.

        Args:
            colour_string (str): The string to match.

        Returns:
            TermColour: The appropriate term colour.

        Examples:
            >>> TermColour.from_colour_string('Black')
            <TermColour.BLACK: '\x1b[30m'> '''
        return cls[colour_string.upper()]


def parse_config(filename):
    ''' Parse a config file at filename.

    Args:
        filename (str): The location of the config file.

    Returns:
        dict: The parsed dictionary. '''
    section_schema = Schema(
        Or({
            Optional('colour', default=TermColour.NONE):
            Use(TermColour.from_colour_string, error='Invalid colour'),
            'semester':
            And(
                Use(int, error='Invalid semester, should be an integer'),
                lambda semester: 1 <= semester <= 2),
            'year':
            Use(int, error='Invalid year, should be an integer')
        }, {
            'activity':
            And(
                Use(int, error='Invalid activity, should be an integer'),
                lambda activity: activity > 0)
        }))
    with open(filename, 'r') as infile:
        parser = configparser.ConfigParser()
        parser.read_file(infile)
        config = {
            s: section_schema.validate(dict(parser.items(s)))
            for s in parser.sections()
        }
        return config


def get_courses(config):
    ''' Get a list of courses from the parsed config file.

    Args:
        config (dict): The parsed config file.
    Returns:
        list of timetable.Course: The courses pull from the config file. '''
    courses = []

    for section in config:
        if section.startswith('course/'):
            title = section[len('course/'):]
            year = config[section]['year']
            semester = config[section]['semester']
            courses.append(timetable.Course(title, year, semester))
    return courses


def get_selected_activities(config, courses):
    ''' Gets the user selected activities for the given courses.

    Args:
        config (dict): The parsed config file.
        courses (list of Course): The courses to get activities for.

    Returns:
        dict: A mapping from (course title, activity name) to the selected activity. '''
    selected_activities = {}
    for course in courses:
        selected_activities.update({
            (course.title, activity.name):
            config[f'{course.title}/{activity.name}']['activity']
            for activity in course.activities
            if 'activity' in config.get(f'{course.title}/{activity.name}', {})
        })
    return selected_activities


def colour_of_course(config, course):
    ''' Gets the colour the user specified for the course.

    Args:
        config (dict): The parsed config file.
        course (Course): The course to get the colour for.

    Returns:
        str: The ANSI escape sequence corresponding to the colour they
             asked for.
    '''
    return config[f'course/{course.title}']['colour']
