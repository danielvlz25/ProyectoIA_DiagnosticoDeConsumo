"""Reglas de recomendación derivadas de publicaciones de la CFE.

Los hechos del aparato los reporta el usuario. Un hecho con valor None significa
"no sé" (desconocido). Cada regla usa lógica de tres valores: si un hecho conocido
ya impide aplicar la regla, no aplica; si no, y falta algún dato, queda
indeterminada y se indica qué debe confirmar el usuario.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

SOMOS = "Somos más que ahorro (CFE)"
LUZ = "¡Y se hizo la luz! (CFE)"

# Umbrales: DOCUMENTO = viene de la fuente; EQUIPO = criterio del equipo.
AIRE_TEMP_BAJA_C = 20      # DOCUMENTO (Somos, p. 60): < 20 °C mayor trabajo del compresor
AIRE_TEMP_OPTIMA_C = 24    # DOCUMENTO (Somos, p. 60): rango óptimo 24-26 °C
# La forma lineal entre 20 y 24 °C es criterio del EQUIPO.


@dataclass
class ReglaRecomendacion:
    identificador: str
    equipo: str
    entradas_requeridas: list[str]
    antecedente: str
    accion: str
    fuente: str
    origen_umbrales: str
    orden_equipo: int                      # desempate (criterio del equipo)
    evaluar: Callable[[dict], tuple[str, float, list[str]]]


@dataclass
class ResultadoRegla:
    regla: ReglaRecomendacion
    estado: str                            # "aplica" | "no_aplica" | "indeterminada"
    grado: float = 0.0
    faltantes: list[str] = field(default_factory=list)


# ------------------------------------------------------- lógica de 3 valores
def _y(*condiciones):
    """AND de tres valores: devuelve (valor, índices de los desconocidos)."""
    if any(c is False for c in condiciones):
        return False, []
    desconocidos = [i for i, c in enumerate(condiciones) if c is None]
    return (None if desconocidos else True), desconocidos


def _igual(valor, esperado):
    return None if valor is None else valor == esperado


def _evaluar_simple(equipo, campos_y_valores):
    """campos_y_valores: lista de (campo, valor esperado)."""
    def f(hechos):
        datos = hechos.get(equipo, {})
        condiciones = [_igual(datos.get(c), v) for c, v in campos_y_valores]
        res, desc = _y(*condiciones)
        if res is True:
            return "aplica", 1.0, []
        if res is False:
            return "no_aplica", 0.0, []
        return "indeterminada", 0.0, [f"{equipo}.{campos_y_valores[i][0]}" for i in desc]
    return f


def _evaluar_aire_temperatura(hechos):
    datos = hechos.get("aire", {})
    encendido = _igual(datos.get("estado"), "encendido")
    ajuste = datos.get("ajuste_c")
    if encendido is False:
        return "no_aplica", 0.0, []
    if ajuste is not None:
        if ajuste >= AIRE_TEMP_OPTIMA_C:
            return "no_aplica", 0.0, []
        grado = min(1.0, (AIRE_TEMP_OPTIMA_C - ajuste) /
                    (AIRE_TEMP_OPTIMA_C - AIRE_TEMP_BAJA_C))
    if encendido is None or ajuste is None:
        faltantes = [c for c, v in (("aire.estado", encendido), ("aire.ajuste_c", ajuste))
                     if v is None]
        return "indeterminada", 0.0, faltantes
    return "aplica", grado, []


# ---------------------------------------------------------------- las reglas
REGLAS_RECOMENDACION: list[ReglaRecomendacion] = [
    ReglaRecomendacion(
        "R1", "Aire acondicionado (temperatura)", ["aire.estado", "aire.ajuste_c"],
        "Encendido con ajuste por debajo de 24 °C (grado 1 a 20 °C o menos, "
        "baja linealmente a 0 en 24 °C)",
        "Subir el ajuste al rango de 24 a 26 °C",
        f"{SOMOS}, p. 60",
        "Documento: 20 °C y rango 24-26 °C. Equipo: activación gradual lineal.", 1,
        _evaluar_aire_temperatura),
    ReglaRecomendacion(
        "R2", "Aire acondicionado (ocupación)", ["aire.estado", "aire.ocupacion"],
        "Encendido y espacio desocupado",
        "Apagar el aire acondicionado al salir del espacio",
        f"{SOMOS}, p. 61",
        "Documento: acción. Equipo: ocupación como hecho observable.", 2,
        _evaluar_simple("aire", [("estado", "encendido"), ("ocupacion", "desocupado")])),
    ReglaRecomendacion(
        "R3", "Iluminación", ["iluminacion.estado", "iluminacion.ocupacion"],
        "Luz encendida en una habitación vacía",
        "Apagar las luces al salir de la habitación",
        f"{SOMOS}, p. 62; {LUZ}, pp. 109-110",
        "Documento: acción. Equipo: ocupación como hecho observable.", 3,
        _evaluar_simple("iluminacion", [("estado", "encendida"), ("ocupacion", "desocupado")])),
    ReglaRecomendacion(
        "R4", "Computadora y monitor", ["computadora.monitor", "computadora.en_uso"],
        "Monitor encendido sin uso",
        "Apagar el monitor y activar la opción de ahorro de energía",
        f"{SOMOS}, p. 63; {LUZ}, p. 111",
        "Documento: acción. Equipo: uso como hecho observable.", 4,
        _evaluar_simple("computadora", [("monitor", "encendido"), ("en_uso", False)])),
    ReglaRecomendacion(
        "R5", "Cargadores y aparatos en espera", ["cargador.conectado", "cargador.en_uso"],
        "Conectado a la corriente y sin uso",
        "Desconectar el cargador o aparato que no se utiliza",
        f"{LUZ}, p. 111",
        "Documento: acción. Equipo: uso como hecho observable.", 5,
        _evaluar_simple("cargador", [("conectado", True), ("en_uso", False)])),
]


def evaluar_recomendaciones(hechos: dict) -> list[ResultadoRegla]:
    """Evalúa todas las reglas y las ordena: primero las que aplican (por grado
    descendente y, a igual grado, por orden del equipo), luego las indeterminadas."""
    resultados = []
    for regla in REGLAS_RECOMENDACION:
        equipo = regla.entradas_requeridas[0].split(".")[0]
        if equipo not in hechos:       # el usuario no reportó este equipo
            continue
        estado, grado, faltantes = regla.evaluar(hechos)
        resultados.append(ResultadoRegla(regla, estado, grado, faltantes))
    peso = {"aplica": 0, "indeterminada": 1, "no_aplica": 2}
    resultados.sort(key=lambda r: (peso[r.estado], -r.grado, r.regla.orden_equipo))
    return [r for r in resultados if r.estado != "no_aplica"]