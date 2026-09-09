"""Vetores 2D puros. Sem dependencia de host (Revit) nem de unidade especifica.

Tudo aqui opera sobre tuplas (x, y) simples. A conversao pra pes/metros e a
leitura de geometria de um CAD real ficam fora deste modulo, na camada de
adaptador do host.
"""

import math


def sub(a, b):
    """Vetor de b para a: a - b."""
    return (a[0] - b[0], a[1] - b[1])


def add(a, b):
    return (a[0] + b[0], a[1] + b[1])


def scale(v, k):
    return (v[0] * k, v[1] * k)


def length(v):
    return math.hypot(v[0], v[1])


def normalize(v):
    """Vetor unitario na mesma direcao de v. Falha se v tiver comprimento zero
    (chamador deve garantir segmentos nao-degenerados antes de chamar)."""
    l = length(v)
    return (v[0] / l, v[1] / l)


def dot(a, b):
    """Produto escalar: mede alinhamento. Usado para projetar um vetor sobre
    uma direcao (quanto de b aponta na direcao de a)."""
    return a[0] * b[0] + a[1] * b[1]


def cross(a, b):
    """Produto vetorial 2D (escalar): mede area/perpendicularidade.
    |cross(uA, uB)| = sin(angulo) quando uA, uB sao unitarios."""
    return a[0] * b[1] - a[1] * b[0]


def midpoint(a, b):
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
