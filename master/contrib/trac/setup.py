from setuptools import setup

from bbwatcher import __version__

setup(
    name='Trac-BuildBot-Watcher',
    version=__version__,
    packages=['bbwatcher'],
    package_data={
        'bbwatcher': ['htdocs/*', 'templates/*.html'],
        },
    author='Randall Bosetti',
    description='A plugin to fetch/integrate status updates from the BuildBot XML-RPC interface',
    license='GPL',
    entry_points={
        'trac.plugins': 'bbwatcher.web_ui=bbwatcher.web_ui',
        }
)
