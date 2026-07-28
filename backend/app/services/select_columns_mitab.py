COMMON_MITAB_COLUMNS = [
    "#ID(s) interactor A",
    "ID(s) interactor B",
    "Alias(es) interactor A",
    "Alias(es) interactor B",
    "Taxid interactor A",
    "Taxid interactor B",
    "Interaction detection method(s)",
    "Interaction type(s)",
    "Publication Identifier(s)",
    "Source database(s)",
    "Confidence value(s)",
]


def default():
    return list(COMMON_MITAB_COLUMNS)


def build_final_columns(selected_databases, selected_columns):
    return default()
