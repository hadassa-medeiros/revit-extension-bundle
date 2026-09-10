
import os
import Autodesk.Revit.DB as db
from pyrevit import forms

def pick_element() -> db.ElementId:
    """
    Asks the user to select an arc line in the Revit UI and returns the corresponding element.
    If no element is selected, an alert is shown and the program exits.
    Returns:
        db.ElementId: The ElementId of the selected element.
    """
    forms.alert("Selecione uma linha de arco para teste.", title="Selecionar Linha", warn_icon=False)
    ui_selection = __revit__.ActiveUIDocument.Selection
    selected_reference = ui_selection.PickObject(
        selection.ObjectType.Element,
        "Selecione uma linha de arco para teste.",
    )

    if selected_reference is None:
        forms.alert("no element selected", title="error", warn_icon=True)
        os._exit(1)
    else:
        element = doc.GetElement(selected_reference.ElementId)
        return element