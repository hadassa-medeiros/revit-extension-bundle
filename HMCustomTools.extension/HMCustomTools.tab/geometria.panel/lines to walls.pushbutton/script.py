# -*- coding: utf-8 -*-
import os
import sys

# core/ vive na raiz do repo, dois niveis acima da pasta do pushbutton
EXTENSION_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if EXTENSION_ROOT not in sys.path:
    sys.path.insert(0, EXTENSION_ROOT)

import Autodesk.Revit.DB as db
from pyrevit import forms
from core.utils import to_m, to_ft
from core.walls import pair_wall_faces, wall_axis_and_thickness, merge_collinear_axes

doc = __revit__.ActiveUIDocument.Document
active_level = doc.ActiveView.GenLevel

# --- tolerancias (metros, fronteira de usuario -- ver SPEC.md da auditoria) ---
MIN_THICKNESS_M = 0.02
MAX_THICKNESS_M = 0.30
MIN_LENGTH_M = 0.4
MAX_GAP_M = 1.0            # fecha aberturas de porta; vaos maiores (corredor) ficam abertos
DEFAULT_HEIGHT_M = 3.2


def get_or_create_walltype(doc, thickness_ft):
    """Reusa um WallType Basic com espessura proxima, ou duplica o primeiro
    Basic existente com essa espessura. Minimo: sem cache, sem nomenclatura
    elaborada -- so o suficiente para nao falhar Wall.Create.

    Assume que ja existe uma Transaction ativa no documento -- o Revit nao
    permite abrir uma segunda transacao "de topo" enquanto outra estiver
    aberta, entao esta funcao NAO gerencia a sua propria transacao; quem
    chama (main()) e responsavel por isso.
    """
    basic_types = [wt for wt in db.FilteredElementCollector(doc).OfClass(db.WallType)
                if str(wt.Kind) == "Basic"]
    if not basic_types:
        raise RuntimeError("Nenhum WallType basico encontrado no modelo.")

    tol_ft = to_ft(0.002)

    for wt in basic_types:
        if abs(wt.Width - thickness_ft) < tol_ft:
            return wt, False

    template = basic_types[0]
    name = "{}mm".format(int(round(to_m(thickness_ft) * 1000)))

    new_type = template.Duplicate(name)
    structure = template.GetCompoundStructure()
    layer = structure.GetLayers()[0]
    layer.Width = thickness_ft
    structure.SetLayers([layer])
    db.WallType.SetCompoundStructure(new_type, structure)
    return new_type, True


def line_to_segment(model_line):
    """ModelLine do Revit -> segmento ((x0,y0),(x1,y1)) em pes (unidade nativa
    do Revit; o core em si e agnostico de unidade)."""
    curve = model_line.GeometryCurve
    p0 = curve.GetEndPoint(0)
    p1 = curve.GetEndPoint(1)
    return ((p0.X, p0.Y), (p1.X, p1.Y))


def segment_to_xyz_pair(segment, z):
    (x0, y0), (x1, y1) = segment
    return db.XYZ(x0, y0, z), db.XYZ(x1, y1, z)


def main():
    z = active_level.Elevation
    height_ft = to_ft(DEFAULT_HEIGHT_M)

    # --- 1. ler linhas de face de parede do nivel ativo ---
    model_lines = [
        el for el in db.FilteredElementCollector(doc)
        .WherePasses(db.CurveElementFilter(db.CurveElementType.ModelCurve))
        .WhereElementIsNotElementType()
        if type(el) is db.ModelLine
        and "parede" in el.LineStyle.Name.lower()
        and el.SketchPlane is not None
        and el.SketchPlane.Name.split(":")[-1].strip() == active_level.Name
    ]

    line_segments = [line_to_segment(ml) for ml in model_lines]

    # --- 2. pareamento -> eixo + espessura (core puro) ---
    pairs = pair_wall_faces(
        line_segments,
        min_thickness=to_ft(MIN_THICKNESS_M),
        max_thickness=to_ft(MAX_THICKNESS_M),
        min_length=to_ft(MIN_LENGTH_M),
    )
    axes_with_thickness = [wall_axis_and_thickness(a, b) for a, b, _ in pairs]

    # --- 3. fusao de colineares (core puro) ---
    merged = merge_collinear_axes(axes_with_thickness, max_gap=to_ft(MAX_GAP_M))

    # --- 4. criar uma parede por trecho final ---
    created = 0
    new_walltypes = 0
    t = db.Transaction(doc, "Criar paredes a partir de linhas CAD")
    t.Start()
    for axis, thickness_ft in merged:
        p0, p1 = segment_to_xyz_pair(axis, z)
        curve = db.Line.CreateBound(p0, p1)
        walltype, was_created = get_or_create_walltype(doc, thickness_ft)
        db.Wall.Create(doc, curve, walltype.Id, active_level.Id, height_ft, 0, False, False)
        created += 1
        if was_created:
            new_walltypes += 1
    t.Commit()

    forms.alert("Created {} new wall types and {} wall instances.".format(new_walltypes, created), title="Success", warn_icon=False)


if __name__ == "__main__":
    main()
