"""Sistema difuso de Sugeno de orden cero para la prioridad de verificación.

Entradas : exceso (%) y amplitud relativa de la banda (%).
Salida   : prioridad entre 0 y 100 (baja, media o alta).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

INF = math.inf


# ---------------------------------------------------------------- entradas
def calcular_exceso(p50: float, referencia: float) -> float:
    """Exceso (%) = máx(0, (P50 - referencia) / referencia * 100)."""
    return max(0.0, (p50 - referencia) / referencia * 100)


def calcular_amplitud(p10: float, p90: float, referencia: float) -> float:
    """Amplitud relativa (%) = (P90 - P10) / referencia * 100."""
    return (p90 - p10) / referencia * 100


# ------------------------------------------------- funciones de pertenencia
@dataclass(frozen=True)
class FuncionTrapezoidal:
    """Trapecio (a, b, c, d). Con a == b es hombro izquierdo; con c = d = inf
    es hombro derecho (vale 1 hacia la derecha sin límite)."""

    nombre: str
    a: float
    b: float
    c: float
    d: float

    def grado(self, x: float) -> float:
        if x < self.a:
            return 0.0
        if x < self.b:
            return (x - self.a) / (self.b - self.a)
        if x <= self.c:
            return 1.0
        if x < self.d:
            return (self.d - x) / (self.d - self.c)
        return 0.0


@dataclass
class VariableDifusa:
    nombre: str
    terminos: list[FuncionTrapezoidal]

    def fuzzificar(self, x: float) -> dict[str, float]:
        return {t.nombre: t.grado(x) for t in self.terminos}


# ------------------------------------------------------------------ diseño
EXCESO = VariableDifusa("exceso", [
    FuncionTrapezoidal("bajo",  0, 0, 10, 30),
    FuncionTrapezoidal("medio", 10, 30, 50, 70),
    FuncionTrapezoidal("alto",  50, 70, INF, INF),
])

AMPLITUD = VariableDifusa("amplitud", [
    FuncionTrapezoidal("estrecha", 0, 0, 20, 50),
    FuncionTrapezoidal("media",    20, 50, 50, 80),
    FuncionTrapezoidal("amplia",   50, 80, INF, INF),
])

# Matriz de Sugeno: (término de exceso, término de amplitud) -> constante
REGLAS: list[tuple[str, str, float]] = [
    ("bajo",  "estrecha",  5), ("bajo",  "media", 15), ("bajo",  "amplia",  30),
    ("medio", "estrecha", 35), ("medio", "media", 55), ("medio", "amplia",  70),
    ("alto",  "estrecha", 75), ("alto",  "media", 90), ("alto",  "amplia", 100),
]

CORTE_MEDIA = 33   # prioridad < 33          -> baja
CORTE_ALTA = 66    # 33 <= prioridad < 66    -> media ; >= 66 -> alta


def etiquetar_prioridad(prioridad: float) -> str:
    if prioridad < CORTE_MEDIA:
        return "baja"
    if prioridad < CORTE_ALTA:
        return "media"
    return "alta"


# --------------------------------------------------------------- inferencia
@dataclass
class ReglaActiva:
    numero: int
    termino_exceso: str
    termino_amplitud: str
    fuerza: float
    constante: float


@dataclass
class ResultadoInferencia:
    exceso: float
    amplitud: float
    grados_exceso: dict[str, float]
    grados_amplitud: dict[str, float]
    reglas_activas: list[ReglaActiva] = field(default_factory=list)
    prioridad: float | None = None
    etiqueta: str | None = None
    mensaje: str = ""


def inferir(exceso: float, amplitud: float) -> ResultadoInferencia:
    """Fuzzifica, activa con el mínimo y promedia ponderado (Sugeno orden 0)."""
    mu_e = EXCESO.fuzzificar(exceso)
    mu_a = AMPLITUD.fuzzificar(amplitud)
    activas = []
    for i, (te, ta, k) in enumerate(REGLAS, start=1):
        fuerza = min(mu_e[te], mu_a[ta])
        if fuerza > 0:
            activas.append(ReglaActiva(i, te, ta, fuerza, k))
    suma_fuerzas = sum(r.fuerza for r in activas)
    prioridad = sum(r.fuerza * r.constante for r in activas) / suma_fuerzas
    return ResultadoInferencia(exceso, amplitud, mu_e, mu_a, activas,
                               prioridad, etiquetar_prioridad(prioridad))


def calcular_prioridad(p10: float, p50: float, p90: float,
                       referencia: float | None,
                       lecturas_consecutivas: int = 144) -> ResultadoInferencia:
    """Punto de entrada completo con las condiciones de la tarea."""
    if lecturas_consecutivas < 144:
        return ResultadoInferencia(0, 0, {}, {}, mensaje=(
            "Historial insuficiente: se requieren 144 lecturas consecutivas."))
    if referencia is None or referencia == 0:
        return ResultadoInferencia(0, 0, {}, {}, mensaje=(
            f"Pronóstico P10/P50/P90 = {p10:g}/{p50:g}/{p90:g} Wh. Falta la "
            "referencia (consumo habitual) o vale cero: la prioridad queda "
            "sin calcular."))
    return inferir(calcular_exceso(p50, referencia),
                   calcular_amplitud(p10, p90, referencia))