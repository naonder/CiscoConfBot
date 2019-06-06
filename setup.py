from setuptools import setup


def readme_file():
    with open('README.rst') as readme:
        data = readme.read()
    return data


setup(
    name='ciscoconfbot',
    version='1.0.14',
    description='Webex Teams bot for configuring Cisco devices',
    long_description=readme_file(),
    author='naonder',
    author_email='nate.a.onder@gmail.com',
    license='MIT',
    packages=['ciscoconfbot'],
    zip_safe=False,
    install_requires=['napalm', 'requests', 'flask', 'requests_toolbelt']
)
