from setuptools import setup

setup(
    name="sloplens",
    version="4.0.0",
    description="CLI for SlopLens — detect slop in text, files, URLs, and GitHub repos",
    py_modules=["cli"],
    install_requires=[
        "click>=8.1.7",
        "rich>=13.9.4",
        "httpx>=0.27.2",
        "beautifulsoup4>=4.12.3",
    ],
    entry_points={
        "console_scripts": [
            "sloplens=cli:cli",
        ],
    },
    python_requires=">=3.10",
)
