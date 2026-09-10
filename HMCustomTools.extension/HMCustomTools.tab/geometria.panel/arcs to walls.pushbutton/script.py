# -*- coding: utf-8 -*-
import os
import sys


# core/ vive na raiz do repo, dois niveis acima da pasta do pushbutton
EXTENSION_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if EXTENSION_ROOT not in sys.path:
    sys.path.insert(0, EXTENSION_ROOT)

import Autodesk.Revit.DB as db
import Autodesk.Revit.UI.Selection as selection
from pyrevit import forms
from core.utils import to_m, to_ft

doc = __revit__.ActiveUIDocument.Document
active_level = doc.ActiveView.GenLevel

# --- tolerancias (metros, fronteira de usuario -- ver SPEC.md da auditoria) ---
MIN_THICKNESS_M = 0.02
MAX_THICKNESS_M = 0.35
MIN_LENGTH_M = 0.5
MAX_GAP_M = 1.0            # fecha aberturas de porta; vaos maiores (corredor) ficam abertos
DEFAULT_HEIGHT_M = 3.2



#iterar sobr etodos os arcos, metodo similar ao de linhas retas para achar par, mas usando a regra acima alem da regra de o radius de uma diferenca do da outra ta dentro do range aceitavel d emin e max thickness
def main():
    def find_arc_pairs(arc_segments):
        arc_pairs = []
        for i in range(len(arc_segments)):
            for j in range(i + 1, len(arc_segments)):
                arc_A = arc_segments[i]
                arc_B = arc_segments[j]
                if (arc_A.Center.X == arc_B.Center.X and
                    arc_A.Center.Y == arc_B.Center.Y and
                    arc_A.Center.Z == arc_B.Center.Z):
                    radius_diff_ft = abs(arc_A.Radius - arc_B.Radius)
                    radius_diff_m = to_m(radius_diff_ft)
                    if MIN_THICKNESS_M <= radius_diff_m <= MAX_THICKNESS_M:
                        arc_pairs.append((arc_A, arc_B))
        return arc_pairs


    def create_arc_from_midradius(arc_A, arc_B):
        """
        Creates an arc element from two given arcs

        """
        radius_diff = arc_A.Radius - arc_B.Radius
        thickness_ft = abs(radius_diff)

        # if radius_diff is negative, means that arc_A is the inner arc of the given pair and will inform the normal to thre offset operation
        # if radius_diff < 0:
        print(radius_diff, thickness_ft)


    def get_or_create_walltype(doc, thickness_ft):
        """Reusa um WallType Basic com espessura proxima, ou duplica o primeiro
        Basic existente com essa espessura. Minimo: sem cache, sem nomenclatura
        elaborada -- so o suficiente para nao falhar Wall.Create."""
        basic_types = [wt for wt in db.FilteredElementCollector(doc).OfClass(db.WallType)
                    if str(wt.Kind) == "Basic"]
        if not basic_types:
            raise RuntimeError("Nenhum WallType basico encontrado no modelo.")

        tol_ft = to_ft(0.002)

        for wt in basic_types:
            if abs(wt.Width - thickness_ft) < tol_ft:
                return wt

        template = basic_types[0]
        name = "{}mm".format(int(round(to_m(thickness_ft) * 1000)))
        t = db.Transaction(doc, "Criar WallType {}".format(name))
        t.Start()
        new_type = template.Duplicate(name)
        structure = template.GetCompoundStructure()
        layer = structure.GetLayers()[0]
        layer.Width = thickness_ft
        structure.SetLayers([layer])
        db.WallType.SetCompoundStructure(new_type, structure)
        t.Commit()
        return new_type

    model_arcs = [
        el.GeometryCurve for el in db.FilteredElementCollector(doc)
        .WherePasses(db.CurveElementFilter(db.CurveElementType.ModelCurve))
        .WhereElementIsNotElementType()
        if type(el) is db.ModelArc
        and any(k in el.LineStyle.Name.lower() for k in ["parede", "divisória"])
        and el.SketchPlane is not None
        and el.SketchPlane.Name.split(":")[-1].strip() == active_level.Name
    ]
    z = active_level.Elevation
    height_ft = to_ft(DEFAULT_HEIGHT_M)
    arc_pairs = find_arc_pairs(model_arcs)

    def find_inner_arc(arc_A, arc_B):
        radius_diff = arc_A.Radius - arc_B.Radius
        return arc_A if radius_diff < 0 else arc_B

    def create_wall_from_arc_pairs(arc_pairs):
        created = 0

        for arc_A, arc_B in arc_pairs:
            # create_centerline_from_midradius(arc_A, arc_B)
            radius_diff = arc_A.Radius - arc_B.Radius
            thickness_ft = abs(radius_diff)
            walltype = get_or_create_walltype(doc, thickness_ft)
            inner_arc = find_inner_arc(arc_A, arc_B)
            profile = inner_arc.CreateOffset(thickness_ft/2, inner_arc.Normal)

            t = db.Transaction(doc, "Criar paredes a partir de arcos CAD")
            t.Start()

            wall = db.Wall.Create(doc, profile, walltype.Id, active_level.Id, height_ft, 0, False, False)
            wall_location_line = wall.get_Parameter(db.BuiltInParameter.WALL_KEY_REF_PARAM)
            wall_location_line.Set(0)
            created += 1

            t.Commit()
    create_wall_from_arc_pairs(arc_pairs)

if __name__ == "__main__":
    main()
