"""Nucleo geometrico de deteccao de paredes a partir de pares de linhas.

Puro: opera sobre segmentos abstratos em coordenadas (x, y). Nao conhece
Revit, unidade de host, nem convencao institucional nenhuma. Reimplementado
a partir de uma especificacao de comportamento (nao de codigo existente).

Pipeline (nesta ordem, e por isso):
    1. pair_wall_faces      -- duas linhas retas -> par de faces da mesma parede
    2. wall_axis_and_thickness -- par de faces -> (eixo, espessura)
    3. merge_collinear_axes -- eixos na mesma reta e mesma espessura -> um so

O pareamento precede a fusao porque a fusao opera sobre EIXOS (produto do
pareamento), nao sobre as faces cruas. A fusao precede a criacao (fora deste
modulo) para produzir um trecho continuo por parede fisica, nao fragmentos.
"""

from .vectors2d import sub, add, scale, length, normalize, dot, cross, midpoint

# ---------------------------------------------------------------------------
# Segmento: um par de pontos (x, y). Representado como ((x0,y0), (x1,y1)).
# ---------------------------------------------------------------------------

def direction(segment):
    """Direcao unitaria do segmento (do ponto 0 pro ponto 1)."""
    p0, p1 = segment
    return normalize(sub(p1, p0))


def seg_length(segment):
    p0, p1 = segment
    return length(sub(p1, p0))


# ---------------------------------------------------------------------------
# Paralelismo e distancia entre retas paralelas
# ---------------------------------------------------------------------------

def are_parallel(segment_a, segment_b, angle_tolerance_deg=1.0):
    """True se os dois segmentos apontam na mesma direcao (ou oposta) dentro
    de uma tolerancia angular.

    Usa direcoes UNITARIAS: |cross(uA, uB)| = sin(angulo). Julgar pelo cross
    product bruto (sem normalizar) faria o teste depender do comprimento das
    linhas -- linhas longas dariam cross maior no mesmo angulo que linhas
    curtas, tornando um limiar fixo inconsistente.
    """
    import math
    uA = direction(segment_a)
    uB = direction(segment_b)
    sin_angle = abs(cross(uA, uB))
    return sin_angle < math.sin(math.radians(angle_tolerance_deg))


def perpendicular_distance(segment_a, segment_b):
    """Distancia perpendicular entre duas retas PARALELAS (assume paralelismo
    ja verificado pelo chamador). Calculada por projecao vetorial: decompoe o
    vetor de um ponto de A ate um ponto de B em componente paralela + o que
    sobra e a perpendicular (o cateto que queremos).
    """
    p0a, _ = segment_a
    p0b, _ = segment_b
    uA = direction(segment_a)
    w = sub(p0b, p0a)
    along = scale(uA, dot(w, uA))
    perp = sub(w, along)
    return length(perp)


def _projected_interval(segment, origin, unit_dir):
    """Projeta os dois extremos do segmento sobre unit_dir (a partir de
    origin), devolvendo o intervalo 1D [min, max] das posicoes projetadas.
    """
    p0, p1 = segment
    t0 = dot(sub(p0, origin), unit_dir)
    t1 = dot(sub(p1, origin), unit_dir)
    return (min(t0, t1), max(t0, t1))


def overlap_along_direction(segment_a, segment_b):
    """Quanto os dois segmentos se sobrepoem ao longo da direcao comum
    (projetando ambos na direcao de A). Positivo = correm lado a lado;
    negativo = ha um vao entre eles (mesmo que colineares); zero = se tocam.

    Este e o mesmo truque de projecao usado em toda parte aqui: reduzir um
    problema 2D a um problema 1D de intervalos.
    """
    uA = direction(segment_a)
    origin = segment_a[0]
    a0, a1 = _projected_interval(segment_a, origin, uA)
    b0, b1 = _projected_interval(segment_b, origin, uA)
    return min(a1, b1) - max(a0, b0)


# ---------------------------------------------------------------------------
# Pareamento: duas faces retas -> uma parede
# ---------------------------------------------------------------------------

def pair_wall_faces(segments, min_thickness, max_thickness, min_length,
                    angle_tolerance_deg=1.0):
    """Pareia segmentos retos que representam as duas faces de uma mesma
    parede. Retorna lista de (segment_a, segment_b, thickness).

    Estrategia: guloso / primeiro-que-serve. Cada segmento pareia com o
    primeiro candidato posterior que satisfaz todas as condicoes; os dois sao
    entao consumidos e nao competem por outros pares.

    Limitacao conhecida (herdada da especificacao original, nao resolvida
    aqui): se uma face tem mais de um candidato valido, o guloso pode escolher
    o par errado em vez do mais proximo. Ver TODO abaixo.

    Condicoes para dois segmentos serem tratados como o mesmo par de faces:
      - paralelos (dentro da tolerancia angular);
      - correm lado a lado (overlap_along_direction > 0), nao apenas se
        tocando ponta a ponta;
      - a distancia perpendicular entre eles cai em [min_thickness, max_thickness];
      - cada segmento e mais longo que min_length.
    """
    remaining = list(segments)
    pairs = []

    i = 0
    while i < len(remaining):
        found = False
        seg_a = remaining[i]
        j = i + 1
        while j < len(remaining):
            seg_b = remaining[j]

            if (seg_length(seg_a) > min_length and seg_length(seg_b) > min_length
                    and are_parallel(seg_a, seg_b, angle_tolerance_deg)
                    and overlap_along_direction(seg_a, seg_b) > 0):
                thickness = perpendicular_distance(seg_a, seg_b)
                if min_thickness <= thickness <= max_thickness:
                    pairs.append((seg_a, seg_b, thickness))
                    remaining.pop(j)
                    remaining.pop(i)
                    found = True
                    break
            j += 1

        if not found:
            i += 1

    return pairs


# TODO(reimplementacao futura): trocar o pareamento guloso por selecao do
# PARCEIRO MAIS PROXIMO entre todos os candidatos validos de uma face, em vez
# de aceitar o primeiro. Isso resolve o caso onde uma face tem multiplos
# candidatos e o guloso empareia com o errado (ver QUESTOES da auditoria, A4).


# ---------------------------------------------------------------------------
# Eixo (centerline) e espessura
# ---------------------------------------------------------------------------

def wall_axis_and_thickness(segment_a, segment_b):
    """A partir de um par de faces, devolve (eixo, espessura).

    O eixo e a linha exatamente no meio das duas faces, construida a partir
    da face MAIS LONGA (para que a parede mantenha a extensao maxima),
    deslocada perpendicularmente por metade da distancia entre as faces, na
    direcao da outra face.
    """
    base, other = (segment_a, segment_b) if seg_length(segment_a) >= seg_length(segment_b) else (segment_b, segment_a)

    thickness = perpendicular_distance(base, other)

    uBase = direction(base)
    p0_base, p1_base = base
    p0_other, _ = other

    w = sub(p0_other, p0_base)
    along = scale(uBase, dot(w, uBase))
    perp = sub(w, along)          # vetor perpendicular de base ate other
    half = scale(perp, 0.5)

    axis = (add(p0_base, half), add(p1_base, half))
    return axis, thickness


# ---------------------------------------------------------------------------
# Colinearidade e fusao de trechos (o item pedido: "colinear same width walls")
# ---------------------------------------------------------------------------

def are_collinear(segment_a, segment_b, angle_tolerance_deg=1.0,
                  offset_tolerance=0.01):
    """True se os dois segmentos estao sobre a MESMA reta infinita: paralelos
    E com offset perpendicular entre eles abaixo de uma tolerancia pequena.

    Diferente de are_parallel sozinho: duas paredes paralelas mas distintas
    (lado a lado, com um corredor entre elas) sao paralelas mas NAO colineares
    -- o offset perpendicular entre seus eixos e grande (a largura do
    corredor), nao pequeno.
    """
    if not are_parallel(segment_a, segment_b, angle_tolerance_deg):
        return False
    return perpendicular_distance(segment_a, segment_b) < offset_tolerance


def merge_collinear_axes(axes_with_thickness, max_gap, thickness_tolerance=0.01,
                         offset_tolerance=0.01, angle_tolerance_deg=1.0):
    """Funde eixos que estao sobre a mesma reta E tem a mesma espessura em
    trechos unicos -- uma parede fisica que apareceu fragmentada (por
    exemplo, interrompida por portas no desenho de origem) vira um so eixo.

    axes_with_thickness: lista de (axis_segment, thickness).
    max_gap: vao maximo entre dois trechos colineares para ainda serem
        considerados a MESMA parede (fecha aberturas de porta; um vao maior
        que isso e tratado como quebra real -- por exemplo um corredor -- e
        fica separado).
    Retorna: lista de (axis_segment, thickness), uma entrada por parede final.

    Algoritmo, em duas etapas:
      1. Agrupar: junta todos os eixos que sao colineares entre si E tem a
         mesma espessura (dentro da tolerancia).
      2. Varrer: projeta os extremos de cada eixo do grupo sobre a direcao
         comum (reduzindo o problema 2D a intervalos 1D), ordena, e funde
         intervalos consecutivos cujo vao for <= max_gap. Intervalos que se
         sobrepoem (vao negativo) sempre se fundem.
    """
    remaining = list(axes_with_thickness)
    result = []

    while remaining:
        base_axis, base_thickness = remaining.pop(0)
        origin = base_axis[0]
        u = direction(base_axis)

        # 1. agrupa tudo que e colinear com base_axis e tem a mesma espessura
        group = [base_axis]
        rest = []
        for axis, thickness in remaining:
            same_thickness = abs(thickness - base_thickness) < thickness_tolerance
            if same_thickness and are_collinear(base_axis, axis, angle_tolerance_deg, offset_tolerance):
                group.append(axis)
            else:
                rest.append((axis, thickness))
        remaining = rest

        # 2. projeta cada eixo do grupo na direcao comum -> intervalos 1D
        intervals = sorted(_projected_interval(axis, origin, u) for axis in group)

        # varre e funde intervalos cujo vao (gap) e <= max_gap
        cur_lo, cur_hi = intervals[0]
        for lo, hi in intervals[1:]:
            gap = lo - cur_hi
            if gap <= max_gap:
                cur_hi = max(cur_hi, hi)
            else:
                result.append((
                    (add(origin, scale(u, cur_lo)), add(origin, scale(u, cur_hi))),
                    base_thickness,
                ))
                cur_lo, cur_hi = lo, hi

        result.append((
            (add(origin, scale(u, cur_lo)), add(origin, scale(u, cur_hi))),
            base_thickness,
        ))

    return result
