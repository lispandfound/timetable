import timetable
import time
from terminaltables import AsciiTable
from collections import defaultdict
from itertools import zip_longest

def activity_as_str(activity, section, course):
    return f'{course.title} {section}'


def main():
    courses = [timetable.Course('MATH102', 2018, 1), timetable.Course('COSC262', 2018, 1)]
    activities = defaultdict(list)
    for course in courses:
        course.fetch_details()
        for section_name, section_activities in course.activities.items():
            if len(section_activities) > 0:
                a = section_activities[0]
                activities[a.day].append((a, section_name, course))

    sorted_days = sorted(activities.items(), key=lambda kv: timetable.Activity.days[kv[0]])
    rendered_days = [['Times', '08:00 - 09:00', '09:00 - 10:00', '10:00 - 11:00', '11:00 - 12:00', '12:00 - 13:00', '13:00 - 14:00', '14:00 - 15:00', '16:00 - 17:00', '17:00 - 18:00']]
    for day, day_activities in sorted_days:
        day_activities = sorted(day_activities)
        rendered_activities = [day]
        i = 0
        while i < len(day_activities):
            print(i)
            da = day_activities[i]
            if i > 0:
                prev_activity = day_activities[i - 1]
                if da[0].start_time < prev_activity[0].end_time:
                    start = time.strftime('%H:%M', da[0].start_time)
                    end = time.strftime('%H:%M', prev_activity[0].end_time)
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

        rendered_days.append(rendered_activities)

    tabled_activities = zip_longest(*[list(day) for day in rendered_days], fillvalue='')
    print(AsciiTable(list(tabled_activities)).table)


main()
