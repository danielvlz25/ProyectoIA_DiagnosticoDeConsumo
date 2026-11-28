"""Aplicación Streamlit: diagnóstico del consumo eléctrico con lógica difusa.

Ejecutar:  streamlit run app.py
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

import logica_difusa as ld
from pronostico import CORTES_HISTORICOS, PASO, cargar_chronos, cargar_serie, obtener_corte, pronosticar
from recomendaciones import REGLAS_RECOMENDACION, evaluar_recomendaciones

st.set_page_config(page_title="Diagnóstico de consumo eléctrico", layout="wide")

# Valores de la tabla 6.2 de la tarea (pruebas controladas)
CASOS_CONTROLADOS = {
    "C1 · Consumo habitual": (56, 80, 104, 80),
    "C2 · Exceso": (96, 120, 144, 80),
    "C3 · Exceso y banda amplia": (96, 144, 176, 80),
    "C4 · Dato desconocido": (96, 120, 144, 80),
    "C5 · Sin referencia": (96, 120, 144, None),
}
SI_NO = {"sí": True, "no": False, "No sé": None}


# ------------------------------------------------------------ hechos del aparato
def _opcion(etiqueta, opciones, defecto, clave):
    idx = opciones.index(defecto) if defecto in opciones else 0
    valor = st.selectbox(etiqueta, opciones, index=idx, key=clave)
    return None if valor == "No sé" else valor


def pedir_hechos(prefijo, defectos):
    """Formulario de hechos por equipo. Cada equipo se reporta por separado."""
    hechos = {}
    d = defectos
    with st.expander("Datos del aparato (los reporta el usuario)", expanded=bool(d)):
        if st.checkbox("Aire acondicionado", value="aire" in d, key=f"{prefijo}_aire"):
            a = d.get("aire", {})
            c1, c2, c3 = st.columns(3)
            with c1:
                estado = _opcion("Estado", ["encendido", "apagado", "No sé"],
                                 a.get("estado", "No sé") or "No sé", f"{prefijo}_a_e")
            with c2:
                ocup = _opcion("Ocupación", ["desocupado", "ocupado", "No sé"],
                               a.get("ocupacion", "No sé") or "No sé", f"{prefijo}_a_o")
            with c3:
                ajuste = st.number_input("Ajuste (°C)", 10, 35, int(a.get("ajuste_c") or 24),
                                         key=f"{prefijo}_a_t")
                if st.checkbox("Ajuste desconocido", key=f"{prefijo}_a_td"):
                    ajuste = None
            hechos["aire"] = {"estado": estado, "ocupacion": ocup, "ajuste_c": ajuste}
        if st.checkbox("Iluminación", key=f"{prefijo}_luz"):
            c1, c2 = st.columns(2)
            with c1:
                e = _opcion("Estado de la luz", ["encendida", "apagada", "No sé"], "No sé",
                            f"{prefijo}_l_e")
            with c2:
                o = _opcion("Ocupación de la habitación", ["desocupado", "ocupado", "No sé"],
                            "No sé", f"{prefijo}_l_o")
            hechos["iluminacion"] = {"estado": e, "ocupacion": o}
        if st.checkbox("Computadora y monitor", key=f"{prefijo}_pc"):
            c1, c2 = st.columns(2)
            with c1:
                m = _opcion("Monitor", ["encendido", "apagado", "No sé"], "No sé", f"{prefijo}_p_m")
            with c2:
                u = st.selectbox("¿Se está usando?", list(SI_NO), index=2, key=f"{prefijo}_p_u")
            hechos["computadora"] = {"monitor": m, "en_uso": SI_NO[u]}
        if st.checkbox("Cargador o aparato en espera", key=f"{prefijo}_cg"):
            c1, c2 = st.columns(2)
            with c1:
                cn = st.selectbox("¿Está conectado?", list(SI_NO), index=2, key=f"{prefijo}_c_c")
            with c2:
                cu = st.selectbox("¿Se está usando?", list(SI_NO), index=2, key=f"{prefijo}_c_u")
            hechos["cargador"] = {"conectado": SI_NO[cn], "en_uso": SI_NO[cu]}
    return hechos


# -------------------------------------------------------------------- gráficas
def graficar_funciones(exceso=None, amplitud=None):
    fig, ejes = plt.subplots(1, 2, figsize=(11, 3.2))
    for eje, var, rango, valor, titulo in (
            (ejes[0], ld.EXCESO, (0, 100), exceso, "Exceso (%)"),
            (ejes[1], ld.AMPLITUD, (0, 140), amplitud, "Amplitud relativa (%)")):
        xs = np.linspace(*rango, 601)
        for t in var.terminos:
            eje.plot(xs, [t.grado(x) for x in xs], label=t.nombre, lw=2)
        if valor is not None:
            eje.axvline(min(valor, rango[1]), color="k", ls="--", lw=1)
            for t in var.terminos:
                g = t.grado(valor)
                if g > 0:
                    eje.plot(min(valor, rango[1]), g, "ko")
        eje.set_title(titulo)
        eje.set_ylabel("Grado de pertenencia")
        eje.set_ylim(-0.02, 1.05)
        eje.legend(loc="center right")
        eje.grid(alpha=0.3)
    fig.tight_layout()
    return fig


# ------------------------------------------------------------------- resultados
def graficar_pronostico(corte, p, real=None):
    """Últimas 24 h de lecturas, pronóstico P10-P50-P90 y consumo habitual."""
    p10, p50, p90 = p
    fig, eje = plt.subplots(figsize=(11, 3.4))
    eje.plot(corte.contexto.index, corte.contexto.values, color="tab:blue", lw=1.5,
             label="Lecturas (últimas 24 h, 144 lecturas)")
    if corte.referencia is not None:
        eje.axhline(corte.referencia, color="gray", ls="--", lw=1.2,
                    label=f"Consumo habitual ({corte.referencia:.0f} Wh)")
    eje.errorbar([corte.objetivo], [p50], yerr=[[p50 - p10], [p90 - p50]], fmt="o",
                 color="tab:orange", capsize=6, lw=2, label="Pronóstico P50 con banda P10–P90")
    if real is not None:
        eje.plot([corte.objetivo], [real], "k*", ms=14, label=f"Lectura real ({real:.0f} Wh)")
    eje.set_ylabel("Appliances (Wh por 10 min)")
    eje.set_title(f"Pronóstico para {corte.objetivo:%d/%m/%Y %H:%M}")
    eje.grid(alpha=0.3)
    eje.legend(loc="upper left", fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()
    return fig


def mostrar_diagnostico(p10, p50, p90, referencia, hechos, lecturas=144, figura=None):
    st.subheader("Pronóstico y consumo habitual")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("P10 (bajo)", f"{p10:.1f} Wh")
    c2.metric("P50 (central)", f"{p50:.1f} Wh")
    c3.metric("P90 (alto)", f"{p90:.1f} Wh")
    c4.metric("Consumo habitual", "Sin dato" if referencia is None else f"{referencia:.1f} Wh")
    st.caption("Wh = energía de los electrodomésticos en un intervalo de 10 minutos. "
               "P10/P50/P90: hay 10 %, 50 % y 90 % de probabilidad de que el consumo sea "
               "menor o igual a ese valor. El consumo habitual es la mediana de la misma "
               "hora en los 14 días anteriores.")
    if figura is not None:
        st.pyplot(figura)

    res = ld.calcular_prioridad(p10, p50, p90, referencia, lecturas)
    if res.prioridad is None:
        st.warning(res.mensaje)
    else:
        st.subheader("Prioridad de verificación")
        c1, c2, c3 = st.columns(3)
        c1.metric("Exceso", f"{res.exceso:.1f} %")
        c2.metric("Amplitud relativa", f"{res.amplitud:.1f} %")
        c3.metric("Prioridad (0-100)", f"{res.prioridad:.1f}")
        c3.markdown(f"**Nivel: {res.etiqueta.upper()}**")
        _explicar(res)
        st.pyplot(graficar_funciones(res.exceso, res.amplitud))
        st.caption(f"Escala: baja < {ld.CORTE_MEDIA}, media de {ld.CORTE_MEDIA} a "
                   f"{ld.CORTE_ALTA}, alta ≥ {ld.CORTE_ALTA} (criterio del equipo).")

    mostrar_recomendaciones(hechos, res)
    return res


def _explicar(res):
    col1, col2 = st.columns(2)
    col1.write("**Grados del exceso**")
    col1.dataframe(pd.DataFrame(res.grados_exceso, index=["grado"]).round(3))
    col2.write("**Grados de la amplitud**")
    col2.dataframe(pd.DataFrame(res.grados_amplitud, index=["grado"]).round(3))
    filas = [{"Regla": f"R{r.numero}", "Si exceso es": r.termino_exceso,
              "y amplitud es": r.termino_amplitud, "Fuerza (mín.)": round(r.fuerza, 3),
              "Constante": r.constante, "Fuerza × constante": round(r.fuerza * r.constante, 3)}
             for r in res.reglas_activas]
    st.write("**Reglas activadas**")
    st.dataframe(pd.DataFrame(filas), hide_index=True)
    num = sum(r.fuerza * r.constante for r in res.reglas_activas)
    den = sum(r.fuerza for r in res.reglas_activas)
    st.latex(rf"\text{{Prioridad}}=\frac{{\sum f_i k_i}}{{\sum f_i}}"
             rf"=\frac{{{num:.3f}}}{{{den:.3f}}}={res.prioridad:.2f}")


def mostrar_recomendaciones(hechos, res):
    st.subheader("Acciones de ahorro sugeridas")
    if not hechos:
        st.info("No se reportaron datos de aparatos, por lo que no se evalúan recomendaciones. "
                "Captura el estado de un equipo para obtenerlas.")
        return
    resultados = evaluar_recomendaciones(hechos)
    if not resultados:
        st.success("Con los datos reportados no se activa ninguna recomendación.")
    for r in resultados:
        g = r.regla
        if r.estado == "aplica":
            st.success(f"**{g.identificador} · {g.equipo}** (grado {r.grado:.2f}): {g.accion}.  \n"
                       f"Fuente: {g.fuente}.")
        else:
            st.warning(f"**{g.identificador} · {g.equipo}**: no se puede aplicar todavía. "
                       f"Confirma: {', '.join(r.faltantes)}.  \nSi se cumple "
                       f"«{g.antecedente.lower()}», la acción sería: {g.accion}. "
                       f"Fuente: {g.fuente}.")


# ------------------------------------------------------------------------ app
st.title("Diagnóstico del consumo eléctrico con lógica difusa")
st.caption("Chronos-Bolt Tiny + sistema difuso de Sugeno + recomendaciones de la CFE")

modo = st.sidebar.radio("Modo", ["Históricos (H1–H3)", "Pruebas controladas (C1–C5)",
                                 "Corte libre (dataset real)", "Diseño del sistema"])
ruta = st.sidebar.text_input("Ruta del dataset", "data/train.parquet")


@st.cache_data
def _serie(ruta_):
    return cargar_serie(ruta_)


@st.cache_resource
def _chronos():
    return cargar_chronos()


def correr_corte(ultima, hechos_prefijo):
    """Calcula y guarda en sesión el pronóstico del corte."""
    serie = _serie(ruta)
    corte = obtener_corte(serie, ultima)
    with st.spinner("Ejecutando Chronos-Bolt Tiny..."):
        p10, p50, p90 = pronosticar(corte.contexto, _chronos())
    st.session_state[hechos_prefijo] = dict(corte=corte, p=(p10, p50, p90))


def flujo_historico(clave, ultima):
    try:
        serie = _serie(ruta)
    except FileNotFoundError:
        st.error(f"No se encontró el dataset en «{ruta}». Coloca train.parquet en la "
                 "carpeta data/ o cambia la ruta en la barra lateral.")
        return
    if st.button("Calcular pronóstico y prioridad", key=f"btn_{clave}"):
        try:
            correr_corte(ultima, clave)
        except Exception as e:  # noqa: BLE001
            st.error(f"No se pudo calcular: {e}")
    datos = st.session_state.get(clave)
    hechos = pedir_hechos(clave, {})
    if not datos:
        return
    corte, (p10, p50, p90) = datos["corte"], datos["p"]
    if corte.cambio_registrado:
        st.warning(corte.cambio_registrado)
    st.write(f"Última lectura usada: **{corte.ultima_lectura}** · lectura a pronosticar: "
             f"**{corte.objetivo}** · lecturas de contexto: {len(corte.contexto)} "
             f"(continuas: {'sí' if corte.continuo else 'no'}) · días previos con lectura: "
             f"{len(corte.previos)}/14")
    lecturas = len(corte.contexto) if corte.continuo else 0
    mostrar_diagnostico(p10, p50, p90, corte.referencia, hechos, lecturas,
                        figura=graficar_pronostico(corte, (p10, p50, p90)))

    st.divider()
    if st.button("Revelar lectura real y comparar", key=f"rev_{clave}"):
        st.session_state[f"revelado_{clave}"] = True
    if st.session_state.get(f"revelado_{clave}"):
        real = float(serie.loc[corte.objetivo])
        ultima_v = float(corte.contexto.iloc[-1])
        hora_ult = corte.ultima_lectura.strftime("%H:%M")
        hora_obj = corte.objetivo.strftime("%H:%M")
        err_chronos, err_base = abs(p50 - real), abs(ultima_v - real)
        st.subheader("Comparación con la lectura real")
        c1, c2, c3 = st.columns(3)
        c1.metric(f"Última lectura conocida ({hora_ult})", f"{ultima_v:.0f} Wh")
        c2.metric(f"Lectura real ({hora_obj})", f"{real:.0f} Wh")
        c3.metric("Consumo habitual", "Sin dato" if corte.referencia is None
                  else f"{corte.referencia:.0f} Wh")
        c1, c2 = st.columns(2)
        c1.metric("Error de Chronos |P50 − real|", f"{err_chronos:.2f} Wh")
        c2.metric(f"Error de repetir la última lectura |{ultima_v:.0f} − {real:.0f}|",
                  f"{err_base:.2f} Wh")
        dentro = p10 <= real <= p90
        st.write(f"La lectura real **{'sí' if dentro else 'no'}** quedó dentro de la banda "
                 f"P10–P90 ({p10:.1f} a {p90:.1f} Wh). "
                 + ("Chronos fue más cercano que repetir la última lectura."
                    if err_chronos < err_base else
                    "Repetir la última lectura fue igual o más cercano que Chronos."))
        st.pyplot(graficar_pronostico(corte, (p10, p50, p90), real=real))


if modo == "Históricos (H1–H3)":
    caso = st.selectbox("Caso", list(CORTES_HISTORICOS))
    ultima, objetivo = CORTES_HISTORICOS[caso]
    st.write(f"Última lectura disponible: **{ultima}** · lectura a pronosticar: **{objetivo}**")
    flujo_historico(f"h_{caso[:2]}", ultima)

elif modo == "Pruebas controladas (C1–C5)":
    caso = st.selectbox("Caso", list(CASOS_CONTROLADOS))
    p10, p50, p90, ref = CASOS_CONTROLADOS[caso]
    st.write(f"Valores cargados directamente: P10/P50/P90 = {p10}/{p50}/{p90} Wh · "
             f"referencia = {'Sin dato' if ref is None else f'{ref} Wh'}")
    defectos = {}
    if caso.startswith("C2"):
        defectos = {"aire": {"estado": "encendido", "ocupacion": "desocupado", "ajuste_c": 20}}
    if caso.startswith("C4"):
        defectos = {"aire": {"estado": "encendido", "ocupacion": None, "ajuste_c": 20}}
        st.info("C4: mismos valores que C2, pero se desconoce si el espacio está ocupado.")
    hechos = pedir_hechos(caso[:2], defectos)
    mostrar_diagnostico(p10, p50, p90, ref, hechos)

elif modo == "Corte libre (dataset real)":
    st.write("Elige cualquier corte del dataset (por ejemplo, el del caso de traslape que "
             "encontró `buscar_traslape.py`).")
    try:
        serie_libre = _serie(ruta)
    except FileNotFoundError:
        st.error(f"No se encontró el dataset en «{ruta}». Coloca train.parquet en la "
                 "carpeta data/ o cambia la ruta en la barra lateral.")
        st.stop()
    # Rango válido: debe existir la lectura a pronosticar y las de los 14 días previos
    primera = serie_libre.index.min() + pd.Timedelta(days=14) - PASO
    ultima_max = serie_libre.index.max() - PASO
    col_f, col_h = st.columns(2)
    fecha = col_f.date_input("Fecha de la última lectura disponible",
                             value=pd.Timestamp("2016-02-15").date(),
                             min_value=primera.date(), max_value=ultima_max.date())
    del_dia = serie_libre.index[(serie_libre.index.normalize() == pd.Timestamp(fecha))
                                & (serie_libre.index >= primera)
                                & (serie_libre.index <= ultima_max)]
    horas = [t.strftime("%H:%M") for t in del_dia]
    if not horas:
        st.warning("Esa fecha no tiene cortes válidos. Elige otra.")
        st.stop()
    hora = col_h.selectbox("Hora de la última lectura (cada 10 minutos)", horas,
                           index=horas.index("06:50") if "06:50" in horas else 0)
    ultima_texto = f"{fecha} {hora}:00"
    st.write(f"Se pronosticará la lectura de las "
             f"**{(pd.Timestamp(ultima_texto) + PASO).strftime('%d/%m/%Y %H:%M')}**.")
    flujo_historico(f"libre_{ultima_texto}", ultima_texto)

else:
    st.subheader("Funciones de pertenencia")
    st.pyplot(graficar_funciones())
    st.subheader("Matriz de Sugeno (prioridad constante por regla)")
    matriz = pd.DataFrame(
        [[k for te, ta, k in ld.REGLAS if te == e] for e in ("bajo", "medio", "alto")],
        index=["exceso bajo", "exceso medio", "exceso alto"],
        columns=["amplitud estrecha", "amplitud media", "amplitud amplia"])
    st.dataframe(matriz)
    st.subheader("Registro de reglas de recomendación")
    st.dataframe(pd.DataFrame([{
        "ID": r.identificador, "Equipo": r.equipo,
        "Entradas requeridas": ", ".join(r.entradas_requeridas),
        "Antecedente": r.antecedente, "Acción": r.accion, "Fuente": r.fuente,
        "Origen de umbrales": r.origen_umbrales} for r in REGLAS_RECOMENDACION]),
        hide_index=True)