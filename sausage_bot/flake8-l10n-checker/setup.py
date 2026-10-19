import setuptools

setuptools.setup(
    name="flake8-l10n-checker",
    # license='MIT',
    # version='0.0.1',
    description="Custom plugin for checking i18n lines",
    author="geirawsm",
    author_email="geirawsm@pm.me",
    # url="http://github.com/yourname/your-repo",
    py_modules=["flake8_l10n_checker"],
    entry_points={
        "flake8.extension": [
            "LC1 = flake8_l10n_checker:I18N_Checker",
        ],
    },
    install_requires=["flake8"],
    classifiers=[
        "Topic :: Software Development :: Quality Assurance",
    ],
)
