import os
from setuptools import find_packages, setup

os.chdir(os.path.dirname(os.path.abspath(__file__)))

setup(
    name="openimis-be-claimguard",
    version="1.0.0",
    packages=find_packages(),
    include_package_data=True,
    license="GNU AGPL v3",
    description="ClaimGuard — AI-powered claims fraud detection for openIMIS.",
    url="https://openimis.org/",
    install_requires=[
        "django",
        "djangorestframework",
        "openimis-be-core",
        "openimis-be-claim",
        "scikit-learn>=1.3.0",
        "joblib>=1.3.0",
        "numpy>=1.24.0",
    ],
    classifiers=[
        "Environment :: Web Environment",
        "Framework :: Django",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU Affero General Public License v3",
        "Programming Language :: Python :: 3.11",
    ],
)
