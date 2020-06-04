import setuptools


with open("README.rst", "r") as fh:
    long_description = fh.read()

version = {}
with open("./viewcontrol/version.py") as fp:
    exec(fp.read(), version)

setuptools.setup(
    name="viewcontrol",
    version=version["__version__"],
    author="Johannes Nolte, Simon Budweth",
    author_email="igfilm.stupa@th-rosenheim.de",
    description=(
        "Lightweight program for playback of various image media formats with seamless "
        "transitions and control via Ethernet connected devices and DMX."
    ),
    long_description=long_description,
    long_description_content_type="text/x-rst",
    url="https://github.com/igfilm/viewcontrol",
    packages=setuptools.find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.7",
        "License :: OSI Approved :: GNU General Public License v3 only (GPLv3)",
        "Operating System :: POSIX",
        "Topic :: Multimedia :: Video",
        "Topic :: Multimedia :: Video :: Display",
        "Intended Audience :: End Users/Desktop",
    ],
    python_requires=">=3.6",
    install_requires=[
        "PyYAML==5.1.2",
        "python-mpv==0.3.9",
        "moviepy>=1.0.0, !=1.0.1",
        "Wand==0.5.7",
        "SQLAlchemy==1.3.8",
        "blinker==1.4",
        "pynput==1.4.4",
    ],
)
