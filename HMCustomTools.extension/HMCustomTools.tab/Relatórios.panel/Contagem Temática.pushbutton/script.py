import csv
import os
import sys

from pyrevit import DB, forms, revit


extension_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
lib_path = os.path.join(extension_root, "lib")
if lib_path not in sys.path:
    sys.path.append(lib_path)

from count_by_theme import filter_by_terms  # type: ignore[reportMissingImports]


class EnvironmentReportWindow(forms.WPFWindow):
    def __init__(self, xaml_file):
        forms.WPFWindow.__init__(self, xaml_file)
        self.results = []

    def search_click(self, sender, args):
        terms = self.terms.Text.split(",")
        if not any(term.strip() for term in terms):
            forms.alert("Informe pelo menos um termo separado por virgula.", title="Relatorio")
            return

        environments = get_environments()
        matching_names = filter_by_terms(
            [environment["name"] for environment in environments],
            terms,
        )
        self.results = [
            environment for environment in environments if environment["name"] in matching_names
        ]
        self.result_count.Text = "{} ambiente(s) encontrado(s)".format(len(self.results))
        self.results_grid.ItemsSource = self.results

    def export_click(self, sender, args):
        if not self.results:
            forms.alert("Execute uma busca antes de exportar o relatorio.", title="Relatorio")
            return

        output_path = forms.save_file(file_ext="csv", default_name="relatorio_ambientes.csv")
        if not output_path:
            return

        with open(output_path, "wb") as output_file:
            writer = csv.writer(output_file)
            writer.writerow(["Nome", "Numero", "Area", "Nivel"])
            for environment in self.results:
                writer.writerow([
                    environment["name"],
                    environment["number"],
                    environment["area"],
                    environment["level"],
                ])

        forms.alert("Relatorio exportado com sucesso.", title="Relatorio")

def get_name(room):
    if room is None:
        return ""

    parameter = room.get_Parameter(DB.BuiltInParameter.ROOM_NAME)
    if parameter:
        value = parameter.AsString()
        if value:
            return value

    fallback_parameter = getattr(room, "LookupParameter", lambda _name: None)("Name")
    if fallback_parameter:
        value = fallback_parameter.AsString()
        if value:
            return value

    return getattr(room, "Name", "") or ""


def get_environments():
    environments = []
    rooms = (
        DB.FilteredElementCollector(revit.doc)
        .OfCategory(DB.BuiltInCategory.OST_Rooms)
        .WhereElementIsNotElementType()
    )

    for room in rooms:
        environments.append({
            "name": get_name(room),
            "number": room.Number or "",
            "area": "{:.2f}".format(room.Area),
            "level": room.Level.Name if room.Level else "",
        })

    return environments


if __name__ == "__main__":
    window = EnvironmentReportWindow("window.xaml")
    window.show(modal=True)
