import setuptools

setuptools.setup(
    name="flake8-I18N-checker",
    # license='MIT',
    # version='0.0.1',
    description="Custom plugin for checking i18n lines",
    author="geirawsm",
    author_email="geirawsm@pm.me",
    # url="http://github.com/yourname/your-repo",
    py_modules=["flake8_I18N_checker"],
    entry_points={
        "flake8.extension": [
            "LC1 = flake8_I18N_checker:I18N_Checker",
        ],
    },
    install_requires=["flake8"],
    classifiers=[
        "Topic :: Software Development :: Quality Assurance",
    ],
)
