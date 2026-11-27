from logica_difusa import calcular_prioridad, inferir

casos = {
    "C1": (56, 80, 104, 80), "C2": (96, 120, 144, 80), "C3": (96, 144, 176, 80),
    "C5": (96, 120, 144, None),
    "H1": (25.48333740234375, 37.646514892578125, 52.723731994628906, 50),
    "H2": (40.630714416503906, 53.58556365966797, 106.18601989746094, 70),
    "H3": (59.669029235839844, 111.30998229980469, 258.9930419921875, 125),
}
for n, (a, b, c, r) in casos.items():
    res = calcular_prioridad(a, b, c, r)
    if res.prioridad is None:
        print(n, res.mensaje)
        continue
    print(f"{n}: exceso={res.exceso:.2f} amp={res.amplitud:.2f} "
          f"prioridad={res.prioridad:.2f} ({res.etiqueta}) "
          f"reglas={[(r.numero, round(r.fuerza, 3)) for r in res.reglas_activas]}")

print("\nTraslape: exceso=20, amplitud=65")
res = inferir(20, 65)
print(res.grados_exceso, res.grados_amplitud)
for r in res.reglas_activas:
    print(r)
print(res.prioridad, res.etiqueta)

# todo valor valido debe activar al menos una regla
for e in [0, 5, 10, 30, 50, 70, 100, 500]:
    for a in [0, 20, 50, 80, 100, 160, 1000]:
        assert inferir(e, a).reglas_activas, (e, a)
print("cobertura ok")