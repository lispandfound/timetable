import functools
import requests
import time
from bs4 import BeautifulSoup
from bs4 import NavigableString


UC_URL = 'http://www.canterbury.ac.nz/courseinfo/GetCourseDetails.aspx'


@functools.total_ordering
class Activity:
    '''An activity represents a single activity on the timetable. This could
    be a lecture or a tutorial, as an example.'''
    days = {'Monday': 0, 'Tuesday': 1, 'Wednesday': 3, 'Thursday': 4, 'Friday': 5}

    def __init__(self, activity_id, day, start_time, end_time, location):
        '''Initialize activity class.'''
        self.activity_id = activity_id
        self.day = day
        self.start_time = start_time
        self.end_time = end_time
        self.location = location

    def __eq__(self, other):
        '''Returns True if two Activities are the same.'''
        return ((self.activity_id, self.day, self.start_time, self.end_time, self.location)
                == (other.activity_id, other.day, other.start_time, other.end_time, other.location))

    def __lt__(self, other):
        '''Returns True if one Activity occurs before another in the timetable.'''
        if Activity.days[self.day] != Activity.days[other.day]:
            return Activity.days[self.day] < Activity.days[other.day]
        else:
            return self.start_time < other.start_time

    def __repr__(self):
        cn = self.__class__.__name__
        start = time.strftime('%H:%M', self.start_time)
        end = time.strftime('%H:%M', self.end_time)
        return f'{cn}({self.activity_id}, {self.day}, {start}, {end}, {self.location})'


def parse_activity(activity_element):
    activity_id = activity_element.find_next('td', attrs={'data-title': 'Activity'})
    activity_day = activity_element.find_next('td', attrs={'data-title': 'Day'})
    activity_time = activity_element.find_next('td', attrs={'data-title': 'Time'})
    activity_location = activity_element.find_next('td', attrs={'data-title': 'Location'})
    [start_time, end_time] = [time.strptime(t.strip(), '%H:%M') for t in activity_time.text.strip().split('-')]
    activity_id = int(activity_id.text.strip())
    return Activity(activity_id, activity_day.text.strip(), start_time, end_time, activity_location.text.strip())


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
            course_table = soup.select_one('table.table.table-hover.table-bordered.table-condensed.cf')
            section_headers = [e.find_next_sibling('tbody') for e in course_table.find_all('thead', class_='cf')]
            for section_header in section_headers:
                section_name = section_header.text.strip()
                activity_rows = []
                for row in section_header.parent.next_siblings:
                    if type(row) == NavigableString:
                        continue
                    if row.name and row.name != 'tr':
                        break
                    activity_rows.append(row)
                activities = [parse_activity(row) for row in activity_rows]
                self.activities[section_name] = activities
