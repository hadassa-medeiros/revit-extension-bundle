# -*- coding: utf-8 -*-
"""Cria paredes a partir de linhas de CAD importado.

Le linhas retas na layer 'parede' do nivel ativo, pareia as duas faces de
cada parede, funde trechos colineares de mesma espessura (fechando aberturas
de porta ate MAX_GAP_M), e cria uma parede por trecho.

Toda a geometria (pareamento, eixo, fusao) vem de core/walls.py -- puro,
testado sem Revit em tests/test_walls.py. Este script e so o adaptador:
le do Revit, converte unidade, chama o nucleo, escreve no Revit.
"""

import os
import sys

# core/ vive na raiz do repo, dois niveis acima da pasta do pushbutton
EXTENSION_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if EXTENSION_ROOT not in sys.path:
    sys.path.insert(0, EXTENSION_ROOT)

from core.walls import is_arc, pair_wall_faces, wall_axis_and_thickness, merge_collinear_axes

import Autodesk.Revit.DB as db
import Autodesk.Revit.UI.Selection as selection
from pyrevit import forms

doc = __revit__.ActiveUIDocument.Document  # noqa: F821 (fornecido pelo pyRevit)
active_level = doc.ActiveView.GenLevel

# --- tolerancias (metros, fronteira de usuario -- ver SPEC.md da auditoria) ---
MIN_THICKNESS_M = 0.02
MAX_THICKNESS_M = 0.5
MIN_LENGTH_M = 0.5
MAX_GAP_M = 1.0            # fecha aberturas de porta; vaos maiores (corredor) ficam abertos
DEFAULT_HEIGHT_M = 3.2

FT_PER_M = 1.0 / 0.3048
M_PER_FT = 0.3048
# Em Revit 2026, PickObject e um metodo da selecao da UI (UIDocument),
# enquanto ObjectType.Element continua sendo o enum da API.

def get_arc_properties(curve_element):
    arc_radius = curve_element.Radius
    arc_center = curve_element.Center
    return (arc_radius, arc_center)

def pick_arc():
    forms.alert("Selecione uma linha de arco para teste.", title="Selecionar Linha", warn_icon=False)
    ui_selection = __revit__.ActiveUIDocument.Selection
    selected_reference = ui_selection.PickObject(
        selection.ObjectType.Element,
        "Selecione uma linha de arco para teste.",
    )

    if selected_reference is None:
        forms.alert("Selecione uma linha de arco para teste.", title="Erro", warn_icon=True)
    else:
        # PickObject retorna uma Reference, nao o elemento selecionado.
        modelarc = doc.GetElement(selected_reference.ElementId)
        curve_element = getattr(modelarc, "GeometryCurve", None)
        if curve_element is None or not is_arc(curve_element):
            forms.alert("O elemento selecionado nao e um arco.", title="Erro", warn_icon=True)
            return None
        return curve_element

#iterar sobr etodos os arcos, metodo similar ao de linhas retas para achar par, mas usando a regra acima alem da regra de o radius de uma diferenca do da outra ta dentro do range aceitavel d emin e max thickness
def find_arc_pairs(arc_segments):
    arc_pairs = []
    for i in range(len(arc_segments)):
        for j in range(i + 1, len(arc_segments)):
            arc_A = arc_segments[i]
            arc_B = arc_segments[j]
            if (arc_A.Center.X == arc_B.Center.X and
                arc_A.Center.Y == arc_B.Center.Y and
                arc_A.Center.Z == arc_B.Center.Z):
                radius_diff = abs(arc_A.Radius - arc_B.Radius)
                if MIN_THICKNESS_M <= radius_diff <= MAX_THICKNESS_M:
                    arc_pairs.append((arc_A, arc_B))
    return arc_pairs


def to_ft(m):
    return m * FT_PER_M

# def line_to_segment(model_line):
#     """ModelLine do Revit -> segmento ((x0,y0),(x1,y1)) em pes (unidade nativa
#     do Revit; o core em si e agnostico de unidade)."""
#     curve = model_line.GeometryCurve

#     p0 = curve.GetEndPoint(0)
#     p1 = curve.GetEndPoint(1)
#     return ((p0.X, p0.Y), (p1.X, p1.Y))


# def segment_to_xyz_pair(segment, z):
#     (x0, y0), (x1, y1) = segment
#     return db.XYZ(x0, y0, z), db.XYZ(x1, y1, z)

def line_to_xyz_pair(model_line, z):
    """ModelLine do Revit -> par de XYZ em pes (unidade nativa do Revit; o core
    em si e agnostico de unidade)."""
    curve = model_line.GeometryCurve

    p0 = curve.GetEndPoint(0)
    p1 = curve.GetEndPoint(1)
    return db.XYZ(p0.X, p0.Y, z), db.XYZ(p1.X, p1.Y, z)

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
    name = "{}mm".format(int(round(thickness_ft / FT_PER_M * 1000)))
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


# # --- 1. ler linhas de face de parede do nivel ativo ---
# model_lines = [
#     el for el in db.FilteredElementCollector(doc)
#     .WherePasses(db.CurveElementFilter(db.CurveElementType.ModelCurve))
#     .WhereElementIsNotElementType()
#     if type(el) is db.ModelLine
#     and "parede" in el.LineStyle.Name.lower()
#     and el.SketchPlane is not None
#     and el.SketchPlane.Name.split(":")[-1].strip() == active_level.Name
# ]

model_arcs = [
    el.GeometryCurve for el in db.FilteredElementCollector(doc)
    .WherePasses(db.CurveElementFilter(db.CurveElementType.ModelCurve))
    .WhereElementIsNotElementType()
    if type(el) is db.ModelArc
    and "parede" or "divisória" in el.LineStyle.Name.lower()
    and el.SketchPlane is not None
    and el.SketchPlane.Name.split(":")[-1].strip() == active_level.Name
]
print(model_arcs)
# line_segments = [line_to_segment(ml) for ml in model_lines]
arc_segments = [(ma) for ma in model_arcs]
arc_pairs = find_arc_pairs(arc_segments)
print(arc_pairs)
print(len(arc_pairs))

# # --- 2. pareamento -> eixo + espessura (core puro) ---
# pairs = pair_wall_faces(
#     segments,
#     min_thickness=to_ft(MIN_THICKNESS_M),
#     max_thickness=to_ft(MAX_THICKNESS_M),
#     min_length=to_ft(MIN_LENGTH_M),
# )
# axes_with_thickness = [wall_axis_and_thickness(a, b) for a, b, _ in pairs]
# print(axes_with_thickness)
# # --- 3. fusao de colineares (core puro) -- o item central ---
# merged = merge_collinear_axes(axes_with_thickness, max_gap=to_ft(MAX_GAP_M))

# --- 4. criar uma parede por trecho final para linhas retas ---
z = active_level.Elevation
height_ft = to_ft(DEFAULT_HEIGHT_M)

created = 0
# for axis, thickness_ft in merged:
#     p0, p1 = line_to_xyz_pair(axis, z)
#     curve = db.Line.CreateBound(p0, p1)
#     walltype = get_or_create_walltype(doc, thickness_ft)
#     t = db.Transaction(doc, "Criar paredes a partir de linhas CAD")
#     t.Start()
#     db.Wall.Create(doc, curve, walltype.Id, active_level.Id, height_ft, 0, False, False)
#     created += 1
#     t.Commit()

# forms.alert("{} pares de faces detectados -> {} paredes criadas.".format(len(arc_pairs), created), title="Success", warn_icon=False)

# reptir logic aacima porem sendo a curve provinda por um arco, e nao uma linha reta. A regra de pareamento e diferente, mas a fusao de colineares e a mesma. A criacao de parede e a mesma, porem a curva e um arco, nao uma linha reta.
for arc_A, arc_B in arc_pairs:
    #nao usar o axis do core, fazer aqui a logica apena susandp db
    radius_A = arc_A.Radius
    radius_B = arc_B.Radius
    center_A = arc_A.Center
    center_B = arc_B.Center
    if radius_A < radius_B:
        inner_arc = arc_A
        outer_arc = arc_B
    else:
        inner_arc = arc_B
        outer_arc = arc_A
    thickness_ft = to_ft(abs(radius_A - radius_B))
    #criar eixo do arco, que e um arco com o mesmo centro, raio medio
    mid_radius = (radius_A + radius_B) / 2
    # mid_arc = db.Arc.Create(center_A, mid_radius, inner_arc.GetEndParameter(0), inner_arc.GetEndParameter(1), inner_arc.Normal)
    axis = arc_B
    t = db.Transaction(doc, "Criar paredes a partir de arcos CAD")
    t.Start()
    walltype = get_or_create_walltype(doc, thickness_ft)
    db.Wall.Create(doc, axis, walltype.Id, active_level.Id, height_ft, 0, False, False)
    created += 1
    t.Commit()