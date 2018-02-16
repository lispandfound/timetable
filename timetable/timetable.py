import functools
import json
import re
import time
from datetime import datetime

import requests

from bs4 import BeautifulSoup, NavigableString

UC_URL = 'http://www.canterbury.ac.nz/courseinfo/GetCourseDetails.aspx'
DATE_RE = r"(\d{1,2}\/\d{1,2})(-(\d{1,2}\/\d{1,2}))?"
LOCATION_RE = r"^(.+)?\((.+)?\)?$"


def parse_short_date(datestring, year):
    tokens = datestring.split('/')
    day = int(tokens[0])
    month = int(tokens[1])
    return datetime(year, month, day)


class Location:
    def __init__(self, location_string, year):
        self.name = None
        self.valid_dates = []
        self.year = year
        if location_string is not None:
            self._from_string(location_string)

    def _from_string(self, location_string):
        location_tokenized = re.match(LOCATION_RE, location_string)
        if not location_tokenized:
            self.name = location_string
            return
        location_string = location_tokenized.group(1)
        date_string = location_tokenized.group(2)

        self.name = location_string.strip()

        dates = date_string.split()
        for date in dates:
            date_match = re.search(DATE_RE, date)
            if date_match is None:
                raise ValueError(
                    f'{repr(location_string)} is not a valid location.')
            elif date_match.group(2) is None or date_match.group(3) is None:
                self.valid_dates.append(
                    parse_short_date(date_match.group(1), self.year))
            else:
                self.valid_dates.append(
                    (parse_short_date(date_match.group(1), self.year),
                     parse_short_date(date_match.group(3), self.year)))

    def valid_for(self, date):
        if self.valid_dates == []:
            return True

        for valid_date in self.valid_dates:
            start_date = None
            end_date = None
            if type(valid_date) == datetime:
                start_date = valid_date
                end_date = valid_date
            else:
                start_date, end_date = valid_date
            adjusted_end_date = end_date.replace(hour=23, minute=59, second=59)
            if start_date <= date <= adjusted_end_date:
                return True

        return False

    def __repr__(self):
        class_name = self.__class__.__name__
        return f'{class_name}({self.name}, {self.valid_dates})'

    def as_json(self):
        json_dates = []
        for valid_date in self.valid_dates:
            if type(valid_date) == tuple:
                start, end = valid_date
                json_dates.append((start.strftime('%Y-%m-%d'),
                                   end.strftime('%Y-%m-%d')))
            else:
                json_dates.append(valid_date.strftime('%Y-%m-%d'))

        return {
            '__location__': True,
            'name': self.name,
            'year': self.year,
            'valid_dates': json_dates
        }


@functools.total_ordering
class Activity:
    '''An activity represents a single activity on the timetable. This could
    be a lecture or a tutorial, as an example.'''
    days = {
        'Monday': 0,
        'Tuesday': 1,
        'Wednesday': 3,
        'Thursday': 4,
        'Friday': 5
    }

    def __init__(self, activity_id, day, start_time, end_time, location):
        '''Initialize activity class.'''
        self.activity_id = activity_id
        self.day = day
        self.start_time = start_time
        self.end_time = end_time
        self.location = location

    @property
    def start(self):
        return time.strftime('%H:%M', self.start_time)

    @property
    def end(self):
        return time.strftime('%H:%M', self.end_time)

    def __eq__(self, other):
        '''Returns True if two Activities are the same.'''
        return ((self.activity_id, self.day, self.start_time, self.end_time,
                 self.location) == (other.activity_id, other.day,
                                    other.start_time, other.end_time,
                                    other.location))

    def __lt__(self, other):
        '''Returns True if one Activity occurs before another in the timetable.'''
        if Activity.days[self.day] != Activity.days[other.day]:
            return Activity.days[self.day] < Activity.days[other.day]
        else:
            return self.start_time < other.start_time

    def __repr__(self):
        cn = self.__class__.__name__
        return f'{cn}({self.activity_id}, {self.day}, {self.start}, {self.end}, {self.location})'

    def as_json(self):
        return {
            '__activity__': True,
            'id': self.activity_id,
            'day': self.day,
            'start': self.start,
            'end': self.end,
            'location': self.location
        }


def parse_activity(activity_element, year):
    activity_id = activity_element.find_next(
        'td', attrs={
            'data-title': 'Activity'
        })
    activity_day = activity_element.find_next(
        'td', attrs={
            'data-title': 'Day'
        })
    activity_time = activity_element.find_next(
        'td', attrs={
            'data-title': 'Time'
        })
    activity_location = activity_element.find_next(
        'td', attrs={
            'data-title': 'Location'
        })

    for br in activity_location.find_all("br"):
        br.replace_with("\n")

    locations = []

    for location in activity_location.text.split('\n'):
        location = location.strip()
        if location != '':
            locations.append(Location(location, year))

    [start_time, end_time] = [
        time.strptime(t.strip(), '%H:%M')
        for t in activity_time.text.strip().split('-')
    ]
    activity_id = int(activity_id.text.strip())
    return Activity(activity_id, activity_day.text.strip(), start_time,
                    end_time, locations)


class Course:
    ''' A course represents a single course'''

    def __init__(self, title, year, semester, activities=None):
        '''Initialize course class.'''
        self.activities = activities or {}
        self.title = title
        self.year = year
        self.semester = semester

    def to_url(self):
        '''Return a url that represents the location of the course on the UC website.'''
        year_identifier = self.year % 1000
        # TODO: Figure out what (C) is and try not hard code it
        # time_code is a code that represents the occurrence of the course, e.g
        # a 2018 semester one course is 18S1(C).
        time_code = f'{year_identifier}S{self.semester}(C)'
        return f'{UC_URL}?course={self.title}&occurrence={time_code}&year={self.year}'

    def fetch_details(self):
        '''Fetch course details and update activities.'''
        with requests.get(self.to_url()) as r:
            soup = BeautifulSoup(r.content, 'html.parser')
            course_table = soup.select_one(
                'table.table.table-hover.table-bordered.table-condensed.cf')
            section_headers = [
                e.find_next_sibling('tbody')
                for e in course_table.find_all('thead', class_='cf')
            ]
            for section_header in section_headers:
                section_name = section_header.text.strip()
                activity_rows = []
                for row in section_header.parent.next_siblings:
                    if type(row) == NavigableString:
                        continue
                    if row.name and row.name != 'tr':
                        break
                    activity_rows.append(row)
                activities = [
                    parse_activity(row, self.year) for row in activity_rows
                ]
                self.activities[section_name] = activities

    def as_json(self):
        return {
            '__course__': True,
            'title': self.title,
            'year': self.year,
            'semester': self.semester,
            'activities': self.activities
        }


def timetable_load_hook(dct):
    if '__course__' in dct:
        return Course(
            dct['title'],
            dct['year'],
            dct['semester'],
            activities=dct['activities'])
    elif '__activity__' in dct:
        start = time.strptime(dct['start'], '%H:%M')
        end = time.strptime(dct['end'], '%H:%M')
        return Activity(dct['id'], dct['day'], start, end, dct['location'])
    elif '__location__' in dct:
        dates = dct['valid_dates']
        loaded_dates = []
        for date in dates:
            if type(date) == list:
                start = datetime.strptime(date[0], '%Y-%m-%d')
                end = datetime.strptime(date[1], '%Y-%m-%d')
                loaded_dates.append((start, end))
            else:
                loaded_dates.append(datetime.strptime(date, '%Y-%m-%d'))

        loc = Location(None, dct['year'])
        loc.name = dct['name']
        loc.valid_dates = loaded_dates
        return loc
    else:
        return dct


class TimetableEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Course) or isinstance(obj, Activity) or isinstance(
                obj, Location):
            return obj.as_json()
        else:
            return obj
