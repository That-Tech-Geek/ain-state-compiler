from setuptools import setup, find_packages

setup(
    name="ain-state-compiler",
    version="1.0.2",
    author="Sambit Mishra",
    author_email="sambit1912@gmail.com",
    description="The AIN Company Brain Primitive: continuously compiles Slack, Jira, and Gmail into an executable, conflict-resolved operational state for AI agents.",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/That-Tech-Geek/ain-state-compiler",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: Other/Proprietary License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
)
