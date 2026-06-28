from pathlib import Path

from setuptools import find_packages, setup


ROOT = Path(__file__).parent

setup(
    name="pyteaser",
    version="2.0.0",
    description="Extractive summaries and article text extraction",
    long_description=(ROOT / "README.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    license="MIT",
    license_files=["LICENSE", "goose/LICENSE.txt"],
    python_requires=">=3.10",
    install_requires=[
        "lxml>=5.0",
        "cssselect>=1.2",
    ],
    extras_require={
        "images": ["Pillow>=10"],
        "chinese": ["jieba>=0.42.1"],
        "soup": ["beautifulsoup4>=4.12"],
        "all": ["Pillow>=10", "jieba>=0.42.1", "beautifulsoup4>=4.12"],
    },
    packages=find_packages(),
    py_modules=["pyteaser"],
    package_data={"goose": ["resources/images/*", "resources/text/*"]},
    include_package_data=True,
    author="Xiao Xu",
    author_email="xx56@cornell.edu",
    url="https://github.com/xiaoxu193/PyTeaser",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
        "License :: OSI Approved :: MIT License",
    ],
    test_suite="tests",
)
