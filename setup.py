from setuptools import setup, find_packages

setup(
    name="ain-state-compiler",
    version="0.8.2",
    author="That-Tech-Geek",
    author_email="contact@ain-compiler.ai",
    description="The G-Brain Company Brain Primitive: continuously compiles Slack, Jira, and Gmail into an executable, conflict-resolved operational state for AI agents.",
    long_description=open("README.md").read(),
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
