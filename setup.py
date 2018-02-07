from setuptools import setup
setup(name='timetable',
      version='0.1',
      description='A simple cli app to manage your UC timetable.',
      url='',
      author='Jake Faulkner',
      author_email='jakefaulkn@gmail.com',
      # license='MIT',
      packages=['timetable'],
      entry_points={'console_scripts': ['timetable=timetable.main:main']},
      zip_safe=False,
      install_requires=[
          'click',
          'terminaltables',
          'requests',
          'beautifulsoup4'
      ])
