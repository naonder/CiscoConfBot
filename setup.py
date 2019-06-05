from setuptools import setup




setup(
    name='ciscoconfbot',
    version='1.0.13',
    description='Webex Teams bot for configuring Cisco devices',
    author='naonder',
    author_email='nate.a.onder@gmail.com',
    license='MIT',
    packages=['ciscoconfbot'],
    zip_safe=False,
    install_requires=['napalm', 'requests', 'flask', 'requests_toolbelt']
)
