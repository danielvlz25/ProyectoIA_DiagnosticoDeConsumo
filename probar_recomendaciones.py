from recomendaciones import evaluar_recomendaciones

# C2: aire encendido, espacio desocupado, ajuste a 20 °C
c2 = {"aire": {"estado": "encendido", "ocupacion": "desocupado", "ajuste_c": 20}}
# C4: mismos valores numericos, pero la ocupacion se desconoce
c4 = {"aire": {"estado": "encendido", "ocupacion": None, "ajuste_c": 20}}
# gradual: ajuste a 22 °C
g = {"aire": {"estado": "encendido", "ocupacion": "ocupado", "ajuste_c": 22}}

for nombre, hechos in [("C2", c2), ("C4", c4), ("Gradual 22 °C", g)]:
    print("==", nombre)
    for r in evaluar_recomendaciones(hechos):
        print(f"  {r.regla.identificador} {r.estado:13} grado={r.grado:.2f} "
              f"faltan={r.faltantes} -> {r.regla.accion} [{r.regla.fuente}]")