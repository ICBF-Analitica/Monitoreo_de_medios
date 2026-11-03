# -*- coding: utf-8 -*-
"""
analitica.py - Analisis adicionales de "Hechos Reportados" (los llama hechos.py):

1. Brecha de visibilidad: compara los hechos reportados en medios con los delitos sexuales contra menores de edad registrados por
   la Policia Nacional (DIJIN, datos abiertos: datos.gov.co, conjunto fpe5-yrmw), por departamento y municipio, en el mismo periodo.
   Muestra donde los medios cuentan poco frente a lo que se registra oficialmente. Son REGISTROS policiales, no "casos" del ICBF.
2. Seguimiento del caso: cuantos dias siguen los medios un hecho y cuanto tardan en aparecer la captura y la condena.
3. Alertas: departamentos con un aumento fuera de lo normal en las ultimas 8 semanas.
"""

import io

import pandas as pd
import requests

from .limpiar import nombre_propio
from .registro import DIVIPOLA

URL_POLICIA = "https://www.datos.gov.co/resource/fpe5-yrmw.csv"
ORDEN_ESTADO = {"denuncia": 1, "rescate": 2, "captura": 3, "judicializacion": 4, "condena": 5, "absolucion": 6}
NOMBRE_ESTADO = {"denuncia": "Denuncia", "rescate": "Rescate", "captura": "Captura", "judicializacion": "Judicialización",
                 "condena": "Condena", "absolucion": "Absolución", "ND": "Sin dato"}
MIN_REGISTROS = 10      # por debajo, la proporcion de un municipio no es confiable


# ---------------------------------------------------------------- 1. brecha de visibilidad
def descargar_registros_policia(desde_anio, hasta_anio):
    """Delitos sexuales contra menores y adolescentes registrados por la Policia, un registro por fila."""
    anios = " OR ".join(f"fecha_hecho like '%/{a}'" for a in range(desde_anio, hasta_anio + 1))
    params = {"$where": f"grupo_etario in ('MENORES','ADOLESCENTES') AND ({anios})", "$limit": "1000000"}
    r = requests.get(URL_POLICIA, params=params, timeout=300)
    r.raise_for_status()
    d = pd.read_csv(io.StringIO(r.content.decode("utf-8", "replace")), dtype=str)
    d["fecha"] = pd.to_datetime(d["fecha_hecho"], format="%d/%m/%Y", errors="coerce")
    d["cantidad"] = pd.to_numeric(d["cantidad"], errors="coerce").fillna(1).astype(int)
    d["cod_mpio"] = d["codigo_dane"].str[:5]
    d["cod_dpto"] = d["codigo_dane"].str[:2]
    return d.dropna(subset=["fecha"])


def _divipola():
    d = pd.read_csv(DIVIPOLA, dtype=str)
    for c in ("latitud", "longitud"):
        d[c] = pd.to_numeric(d[c].str.replace(",", "."), errors="coerce")
    return d


def calcular_brecha(reg, policia, desde):
    """reg: registro de hechos (texto). Devuelve (departamentos, municipios, resumen) en el periodo que cubren ambos datos."""
    fin = (policia["fecha"].max() + pd.offsets.MonthEnd(0)).normalize()   # ultimo mes con registros oficiales
    pol = policia[(policia["fecha"] >= desde) & (policia["fecha"] <= fin)]
    fecha_h = pd.to_datetime(reg["fecha_hecho"], errors="coerce")
    h = reg[(reg["ambito"] == "colombia") & (fecha_h >= desde) & (fecha_h <= fin)]
    div = _divipola()
    dptos = div.drop_duplicates("cod_dpto")[["cod_dpto", "dpto"]]

    por_dpto = dptos.assign(
        Registros=dptos["cod_dpto"].map(pol.groupby("cod_dpto")["cantidad"].sum()).fillna(0).astype(int),
        Hechos=dptos["cod_dpto"].map(h[h["cod_dpto"] != ""].groupby("cod_dpto").size()).fillna(0).astype(int))
    por_dpto["Departamento"] = por_dpto["dpto"].map(nombre_propio).replace(
        {"Archipiélago de San Andrés, Providencia y Santa Catalina": "San Andrés y Providencia"})
    por_dpto["HechosPor100"] = (por_dpto["Hechos"] / por_dpto["Registros"].where(por_dpto["Registros"] > 0) * 100).round(1)
    departamentos = por_dpto[["cod_dpto", "Departamento", "Registros", "Hechos", "HechosPor100"]].rename(
        columns={"cod_dpto": "CodDpto"})

    reg_m = pol.groupby("cod_mpio")["cantidad"].sum()
    hec_m = h[h["cod_divipola"] != ""].groupby("cod_divipola").size()
    m = div[div["cod_mpio"].isin(set(reg_m.index) | set(hec_m.index))].copy()
    m["Registros"] = m["cod_mpio"].map(reg_m).fillna(0).astype(int)
    m["Hechos"] = m["cod_mpio"].map(hec_m).fillna(0).astype(int)
    m["HechosPor100"] = (m["Hechos"] / m["Registros"].where(m["Registros"] > 0) * 100).round(1)
    tasa = m["Hechos"].sum() / max(m["Registros"].sum(), 1) * 100   # referencia nacional (municipios ubicados)

    def visibilidad(f):
        if f.Registros < MIN_REGISTROS:
            return "Pocos registros (menos de 10)"
        if f.Hechos == 0:
            return "Sin hechos en medios"
        if f.HechosPor100 < tasa / 2:
            return "Cobertura baja"
        if f.HechosPor100 > tasa * 2:
            return "Cobertura alta"
        return "Cobertura esperada"

    m["Visibilidad"] = m.apply(visibilidad, axis=1)
    m["Orden"] = m["Visibilidad"].map({"Sin hechos en medios": 1, "Cobertura baja": 2, "Cobertura esperada": 3,
                                        "Cobertura alta": 4, "Pocos registros (menos de 10)": 5})
    municipios = pd.DataFrame({
        "CodMpio": m["cod_mpio"], "Municipio": m["nom_mpio"].map(nombre_propio),
        "Departamento": m["dpto"].map(nombre_propio), "Latitud": m["latitud"], "Longitud": m["longitud"],
        "Registros": m["Registros"], "Hechos": m["Hechos"], "HechosPor100": m["HechosPor100"],
        "Visibilidad": m["Visibilidad"], "OrdenVisibilidad": m["Orden"]})
    municipios["Lugar"] = [f"{a} ({b})" if a != b else a for a, b in zip(municipios["Municipio"], municipios["Departamento"])]
    resumen = {"desde": desde.date(), "hasta": fin.date(), "registros": int(pol["cantidad"].sum()), "hechos": len(h),
               "tasa_municipal": round(tasa, 2)}
    return departamentos, municipios, resumen


# ---------------------------------------------------------------- 2. seguimiento del caso
def seguimiento(notas):
    """Por hecho: dias entre la primera y la ultima noticia, y dias hasta la primera noticia de captura y de condena."""
    n = notas[notas["id_hecho"] != ""].copy()
    n["fecha"] = pd.to_datetime(n["fecha"], errors="coerce").dt.normalize()
    n["orden"] = n["estado"].map(ORDEN_ESTADO).fillna(0)
    filas = []
    for idh, g in n.groupby("id_hecho"):
        g = g.sort_values("fecha")
        ini = g["fecha"].min()
        captura = g.loc[g["orden"] >= 3, "fecha"].min()
        condena = g.loc[g["estado"] == "condena", "fecha"].min()
        filas.append({"IdHecho": idh, "DiasSeguimiento": int((g["fecha"].max() - ini).days),
                      "DiasACaptura": None if pd.isna(captura) else int((captura - ini).days),
                      "DiasACondena": None if pd.isna(condena) else int((condena - ini).days),
                      # etapa del proceso en la que el hecho aparece por primera vez en los medios
                      "EtapaInicial": NOMBRE_ESTADO.get(g["estado"].iloc[0], "Sin dato")})
    s = pd.DataFrame(filas)
    for c in ("DiasACaptura", "DiasACondena"):
        s[c] = s[c].astype("Int64")
    s["Seguimiento"] = pd.cut(s["DiasSeguimiento"], [-1, 0, 7, 30, 90, 100000],
                              labels=["Un solo día", "2 a 7 días", "8 a 30 días", "31 a 90 días", "Más de 90 días"]).astype(str)
    s["OrdenEtapaInicial"] = s["EtapaInicial"].map({v: i for i, v in enumerate(NOMBRE_ESTADO.values(), start=1)})
    s["OrdenSeguimiento"] = s["Seguimiento"].map({"Un solo día": 1, "2 a 7 días": 2, "8 a 30 días": 3,
                                                  "31 a 90 días": 4, "Más de 90 días": 5})
    return s


# ---------------------------------------------------------------- 3. alertas
def alertas(hechos, semanas=8, base=52):
    """Departamentos con mas hechos de lo esperado en las ultimas `semanas`. Lo esperado sale de la PARTICIPACION del departamento
    en las `base` semanas anteriores aplicada al total nacional reciente: asi un hueco en la recoleccion de noticias (que baja todo
    a la vez) no aparece como una disminucion en todos los departamentos."""
    h = hechos[(hechos["Ambito"] == "Colombia") & (hechos["Departamento"] != "")].copy()
    h["Fecha"] = pd.to_datetime(h["Fecha"], errors="coerce")
    corte = h["Fecha"].max()
    ini_rec, ini_base = corte - pd.Timedelta(weeks=semanas), corte - pd.Timedelta(weeks=semanas + base)
    rec = h[h["Fecha"] > ini_rec].groupby("Departamento").size()
    bas = h[(h["Fecha"] > ini_base) & (h["Fecha"] <= ini_rec)].groupby("Departamento").size()
    a = pd.DataFrame({"Recientes": rec, "Base": bas}).fillna(0)
    a["Esperados"] = (a["Base"] / max(a["Base"].sum(), 1) * a["Recientes"].sum()).round(1)
    a["Recientes"] = a["Recientes"].astype(int)
    a["Variacion"] = ((a["Recientes"] - a["Esperados"]) / a["Esperados"].where(a["Esperados"] > 0) * 100).round(0)
    a["Alerta"] = ["Aumento" if r >= 3 and r >= 2 * e else ("Disminución" if e >= 3 and r <= e / 2 else "Normal")
                   for r, e in zip(a["Recientes"], a["Esperados"])]
    a["Periodo"] = f"{(ini_rec + pd.Timedelta(days=1)).date()} a {corte.date()}"
    a = a.drop(columns="Base").reset_index().rename(columns={"index": "Departamento"})
    return a.sort_values(["Alerta", "Recientes"], ascending=[True, False])
