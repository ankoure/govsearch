# Automatically created by: scrapyd-deploy

from setuptools import setup, find_packages

setup(
    name="project",
    version="1.0",
    packages=find_packages(),
    entry_points={"scrapy": ["settings = govsearch.settings"]},
    install_requires=[
        "scrapy>=2.13.3,<3.0.0",
        "opensearch-py>=2.0.0,<3.0.0",
        "trafilatura>=2.0.0,<3.0.0",
        "python-dotenv>=1.2.1,<2.0.0",
        "requests>=2.31.0,<3.0.0",
        "ddtrace>=2.0.0,<3.0.0",
        "datadog>=0.49.0,<1.0.0",
        "spacy>=3.8.7,<4.0.0",
        "en-core-web-sm @ https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl",
        "sentence-transformers>=5.1.2,<6.0.0",
    ],
)
