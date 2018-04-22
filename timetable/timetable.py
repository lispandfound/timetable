import calendar
import itertools
import re
from datetime import datetime

import attr
from requests_html import HTMLSession

UC_URL = 'http://www.canterbury.ac.nz/courseinfo/GetCourseDetails.aspx'
LOCATION_RE = r'^(?P<name>.+?)?\((?P<date>.+?)\)?$'
ID_RE = r'^(?P<id>\d+)(-P(?P<part>\d+))?'


def parse_week_interval(in_year, interval_string):
    ''' Parse a datetime interval expressed in weeks.

    Args:
        in_year (int): The year to interpret the dates in.
        interval_string (str): The interval to parse.

    Returns:
        (date, date): The interval parsed from the string.

    Examples:
        >>> parse_week_interval(2018, '2 Apr - 3 Apr')
        (datetime.date(2018, 4, 2), datetime.date(2018, 4, 3)) '''
    return tuple(
        datetime.strptime(date.strip(), '%d %b').replace(year=in_year).date()
        for date in interval_string.split('-'))


def date_in_intervals(date, intervals):
    ''' Determine if a date is in a given list of intervals

    Note:
        The elements of the interval list are either a pair of
        datetimes (a range interval), or a single datetime wrapped in
        a tuple (an instant interval).

    Args:
        date (date): The date to query.
        intervals (list of (date, date)): A list of datetime intervals to query.

    Returns:
        bool: True if the date is in the list of intervals, False otherwise

    Examples:
    >>> date_in_intervals(datetime.datetime(2018, 3, 2), [(datetime.date(2018, 3, 1), datetime.date(2018, 3, 3))])
    True '''
    for interval in intervals:
        # Two cases for any interval
        # No end date is specified: it's an interval that occurs
        # over one day (an instant interval).
        # An end date is specified: it's an interval that occurs
        # over one or more days (a range interval).
        instant_interval_is_valid = len(interval) == 1 and date == interval[0]
        range_interval_is_valid = len(
            interval) == 2 and interval[0] <= date <= interval[1]
        if instant_interval_is_valid or range_interval_is_valid:
            return True

    # If the intervals is empty it is assumed valid for all
    # days. Otherwise the for loop found no valid intervals
    # matching this day, so we return False.
    return len(intervals) == 0


def parse_id(id_string):
    ''' Parse an activity id into a tuple of integers that logically represent it.

    From observation of the UC course pages for various courses there
    is a noticable trend. Every activity has an id that falls into one
    of two types:

    <integer> ::

    Your standard id like 01, 02, 03

    <integer>-P<integer> ::

    An adhoc id, that specifically targets students allocated
    to a previous id, such as 01-P1. Here the P1 is a sort of
    suballocation.

    This function parses both cases into a tuple of either (int, None)
    for the first case or (int, int) for the second case.

    Args:
        id_string (str): The id to parse.

    Returns:
        (int, int): The parsed id.

    Example:
        >>> parse_id('01-P1')
        (1, 1)
        >>> parse_id('1')
        (1, None) '''
    match = re.match(ID_RE, id_string)
    if match is None:
        raise ValueError(f'{repr(id_string)} is not a valid ID string.')
    match_dict = match.groupdict()
    id_part = match_dict.get('part')
    return (int(match_dict['id']), int(id_part) if id_part else id_part)


@attr.s
class Location:
    ''' The location class represents a single location a class may occur in.

    A Location has two components, when the location is valid, and a
    description of where it is. It logically represents the "Location"
    column on any course page. If the location has no constraints
    on it's validity it is considering valid at all times.

    Attributes:
        place (str): A description of the physical location, e.g C2 Lecture Theatre.
        valid_intervals (list of (date, date)): A list of intervals for which the location is valid. '''
    place = attr.ib()
    valid_intervals = attr.ib(default=attr.Factory(list))

    @classmethod
    def from_string(cls, in_year, location_string):
        ''' Parse a Location object from a string.

        A valid location string is the form '<location> (<date>-<date>, <date>, ...)'.
        The date section is optional.

        Args:
            in_year (int): The year the location is residing in.
            location_string (str): The string to parse.

        Returns:
            Location: The location of represented by the passed string.

        Examples:
            >>> Location.from_string(2018, 'Jack Erskine 001 Computer Lab (28/3)')
            Location(place='Jack Erskine 001 Computer Lab', valid_intervals=[(datetime.date(2018, 3, 28),)]) '''
        location_match = re.match(LOCATION_RE, location_string)
        if location_match is None:
            name = location_string
            return cls(name)
        else:
            location_string, date_string = location_match.groups(default='')

            name = location_string.strip()
            intervals = date_string.split(', ')
            # Intervals is a list of some elements in the form ['d/m',
            # 'd/m-d/m', ...]. So we iterate, split and parse the
            # dates. The result is a tuple of one or two elements
            # representing the start and (maybe) end dates.
            valid_intervals = [
                tuple(
                    datetime.strptime(d, '%d/%m').replace(year=in_year).date()
                    for d in interval.split('-')) for interval in intervals
            ]
            return cls(name, valid_intervals)

    def valid_for(self, date):
        ''' Determine if a Location is valid on a given date.

        Args:
            date (datetime): The date to query.

        Returns:
            bool: True if the date is a valid date, False otherwise.

        Examples:
            >>> loc = Location.from_string('Jack Erskine 244 (27/2-27/3, 24/4-29/5)')
            >>> loc.valid_for(datetime(2018, 5, 30))
            False
            >>> loc.valid_for(datetime(2018, 4, 28))
            True
            >>> loc.valid_for(datetime(2018, 3, 29))
            False '''
        return date_in_intervals(date.date(), self.valid_intervals)


@attr.s
class Activity:
    ''' The Activity class represents a single activity in a course.

    An Activity logically represents a row in any course page.

    Attributes:
        activity_id ((int, int)): The id of the activity.
        day (int): The weekday this activity falls on (there can only be one).
        start (datetime.time): The time of day this activity starts on.
        end (datetime.time): The time of day this activity ends.
        locations (list of Location): All the locations this Activity could be at.
    '''
    activity_id = attr.ib()
    name = attr.ib()
    day = attr.ib(converter=list(calendar.day_name).index)
    start = attr.ib()
    end = attr.ib()
    valid_intervals = attr.ib()
    locations = attr.ib()

    @property
    def exact_start(self):
        ''' tuple of (int, datetime.time): Represents the exact start of the activity on a week (weekday and time). '''
        return (self.day, self.start)

    @property
    def exact_end(self):
        ''' tuple of (int, datetime.time): Represents the exact end of the activity on a week (weekday and time). '''
        return (self.day, self.end)

    @classmethod
    def from_element(cls, name, in_year, activity_element):
        ''' Returns an instance of Activity instantiated from an HTML element.

        Args:
            activity_element (requests_html.Element): The element to instantiate from.
            in_year (int): The year the activity takes place in.

        Returns:
            Activity: The activity instantiated from the HTML element. '''
        activity_id = activity_element.find(
            'td[data-title=Activity]', first=True)
        activity_day = activity_element.find('td[data-title=Day]', first=True)
        activity_time = activity_element.find(
            'td[data-title=Time]', first=True)
        activity_location = activity_element.find(
            'td[data-title=Location]', first=True)
        activity_weeks = activity_element.find(
            'td[data-title=Weeks]', first=True)
        valid_intervals = [
            parse_week_interval(in_year, week)
            for week in activity_weeks.text.split('\n')
        ]
        locations = [
            Location.from_string(in_year, location_string.strip())
            for location_string in activity_location.text.split('\n')
            if location_string.strip() != ''
        ]

        [start_time, end_time] = [
            datetime.strptime(t.strip(), '%H:%M').time()
            for t in activity_time.text.strip().split('-')
        ]
        act_id = parse_id(activity_id.text.strip())
        return cls(act_id, name, activity_day.text.strip(), start_time,
                   end_time, valid_intervals, locations)

    def valid_for(self, date):
        ''' Return True if an Activity is valid on a particular date.

        Args:
            date (datetime): The date to query.

        Returns:
            bool: True if the Activity does occur on this date. '''
        return date.weekday() == self.day and date_in_intervals(
            date.date(), self.valid_intervals)

    def location_valid_for(self, date):
        ''' Return the first location valid for the activity on a particular date.

        Args:
            date (datetime): The date to query for valid locations on.

        Returns:
            Location: The location valid for this date (or None) if one doesn't exist. '''
        return next((loc for loc in self.locations if loc.valid_for(date)),
                    None)


@attr.s
class Course:
    ''' The Course class represents a single Course, and contains it's activities.

    Attributes:
        title (str): The title of the course, e.g 'COSC262'.
        year (int): The year the course occurred in.
        semester (int): The semester the year the course occurred in.
        activities (list of Activity): The list of activities associated
                                       with the Course. '''
    title = attr.ib()
    year = attr.ib()
    semester = attr.ib()
    activities = attr.ib(default=attr.Factory(list))

    @property
    def url(self):
        ''' str: The url the Course is found at. '''
        year_identifier = self.year % 1000
        # TODO: Figure out what (C) is and try not hard code it
        # time_code is a code that represents the occurrence of the course, e.g
        # a 2018 semester one course is 18S1(C).
        time_code = f'{year_identifier}S{self.semester}(C)'
        return f'{UC_URL}?course={self.title}&occurrence={time_code}&year={self.year}'

    def fetch_activities(self):
        ''' Download the course details page (at self.url) and scrape
        Activities from it. '''
        session = HTMLSession()
        with session.get(self.url) as r:
            activities = []
            last_section = None
            for element in r.html.find('table#RepeatTable tbody, tr.datarow'):
                if element.element.tag == 'tbody':
                    # Activity header
                    last_section = element
                else:
                    activities.append((last_section, element))
            self.activities = [
                Activity.from_element(section.text, self.year, e)
                for section, e in activities
            ]

    def activities_on(self, date):
        ''' Return a list of activities on a particular day, in sorted order.

        Args:
            date (datetime): The date to filter by.

        Returns:
            list of Activity: A sorted (by start time) list of
                              Activities on the given day. '''
        activities = [act for act in self.activities if act.valid_for(date)]
        return sorted(activities, key=lambda act: act.start)


def activities_on(courses, date, selected_activities):
    '''Return all relevant activities from a given list of courses.

    "relevant" is defined to be any activity that is actually on the
    given date and it taken by the user.

    Args:
        courses (list of timetable.Course): The courses to pool activities from.
        date (datetime): The date to filter activities by.
        selected_activities (dict): A dictionary mapping (course
                                    title, activity name) pairs to the
                                    id of the chosen activity by the
                                    student.
    Returns:
        list of (timetable.Course, timetable.Activity): The relevant activities. '''
    # Chain all course activities such they are an iterable in the
    # following form:
    # (course, activity), (course, activity1), ...
    activities = itertools.chain(*(
        zip(itertools.cycle([course]), course.activities)
        for course in courses))
    # Filter the activities, first by if they are an activity the user
    # is taking part in, and then by whether that activity is relevant
    # to the date.
    filtered_activities = [
        (course, activity) for course, activity in activities
        if activity.activity_id[0] == selected_activities.get((
            course.title, activity.name), 1) and activity.valid_for(date)
    ]
    # Sort the activities by their start date
    return sorted(filtered_activities, key=lambda capair: capair[1].start)
