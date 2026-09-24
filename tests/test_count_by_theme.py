import importlib.util
import sys
import types
import unittest
from pathlib import Path


LIB_PATH = Path(__file__).parents[1] / "CCEN.extension" / "lib"
sys.path.insert(0, str(LIB_PATH))

from count_by_theme import filter_by_terms, filter_by_text


SCRIPT_PATH = Path(__file__).parents[1] / "CCEN.extension" / "CCEN.tab" / "Estatistica.panel" / "Contar.pushbutton" / "script.py"


def load_script_module():
    fake_db = types.SimpleNamespace(
        BuiltInCategory=types.SimpleNamespace(OST_Rooms="OST_Rooms"),
        BuiltInParameter=types.SimpleNamespace(ROOM_NAME="ROOM_NAME"),
        FilteredElementCollector=lambda doc: types.SimpleNamespace(
            OfCategory=lambda *args, **kwargs: types.SimpleNamespace(
                WhereElementIsNotElementType=lambda: []
            )
        ),
    )
    fake_forms = types.ModuleType("pyrevit.forms")
    fake_forms.WPFWindow = type("WPFWindow", (), {"__init__": lambda self, xaml_file=None: None, "show": lambda self, modal=True: None})
    fake_forms.alert = lambda *args, **kwargs: None
    fake_forms.save_file = lambda *args, **kwargs: None

    fake_revit = types.ModuleType("pyrevit.revit")
    fake_revit.doc = object()

    fake_pyrevit = types.ModuleType("pyrevit")
    fake_pyrevit.DB = fake_db
    fake_pyrevit.forms = fake_forms
    fake_pyrevit.revit = fake_revit

    sys.modules["pyrevit"] = fake_pyrevit
    sys.modules["pyrevit.forms"] = fake_forms
    sys.modules["pyrevit.revit"] = fake_revit

    spec = importlib.util.spec_from_file_location("env_report_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FilterByTextTests(unittest.TestCase):
    def test_returns_words_containing_text(self):
        self.assertEqual(
            filter_by_text(["andorra", "b", "c"], "dor"),
            ["andorra"],
        )

    def test_returns_empty_list_when_text_is_not_found(self):
        self.assertEqual(filter_by_text(["b", "c"], "dor"), [])

    def test_returns_all_matching_words(self):
        self.assertEqual(
            filter_by_text(["matematica", "matriz", "historia"], "mat"),
            ["matematica", "matriz"],
        )

    def test_filters_by_any_term_case_insensitively(self):
        self.assertEqual(
            filter_by_terms(
                ["Sala de Estatistica", "Laboratorio", "Sala de Matematica"],
                ["estatística", "MATEMATICA"],
            ),
            ["Sala de Estatistica", "Sala de Matematica"],
        )

    def test_ignores_empty_terms(self):
        self.assertEqual(filter_by_terms(["Sala"], ["", "  "]), [])

    def test_get_name_uses_room_name_parameter(self):
        module = load_script_module()

        class FakeRoom:
            Name = "Sala de Estatistica"
            Number = "101"
            Area = 25.0
            Level = type("Level", (), {"Name": "Térreo"})()

            def get_Parameter(self, parameter):
                if parameter == module.DB.BuiltInParameter.ROOM_NAME:
                    return type("Param", (), {"AsString": lambda self: self._value, "_value": "Sala de Estatistica"})()
                return None

            def LookupParameter(self, name):
                return None

        room = FakeRoom()
        self.assertEqual(module.get_name(room), "Sala de Estatistica")


if __name__ == "__main__":
    unittest.main()
