# -*- coding: utf-8 -*-
"""
tablas_hechos.py - Tablas que lee Power BI (hechos.csv y noticias_hechos.csv) a partir del registro de hechos.
Copia de la parte de registro de innovacion_monitoreo_medios/src/exportar_powerbi.py.
"""

import pandas as pd

from .limpiar import cargar_perfil_medios, tabla_medios

AMBITO = {"colombia": "Colombia", "exterior": "Exterior", "ND": "Sin determinar"}
PAIS_MEDIO = {"colombia": "Colombiano", "exterior": "Extranjero", "mixto": "Mixto", "sin_datos": "Sin datos"}
SUBTIPO = {"abuso_sexual": "Abuso sexual", "acceso_carnal": "Acceso carnal (violación)",
           "explotacion_sexual_comercial": "Explotación sexual comercial",
           "material_abuso_digital": "Material de abuso sexual / digital",
           "acoso_sexual": "Acoso sexual", "sin_especificar": "Sin especificar"}
SEXO = {"F": "Femenino", "M": "Masculino", "mixto": "Mixto", "ND": "Sin dato"}
# (etiqueta, orden)
ETAPA = {"primera_infancia": ("Primera infancia (0-5)", 1), "infancia": ("Infancia (6-11)", 2),
         "adolescencia": ("Adolescencia (12-17)", 3), "adulto": ("Adulto", 4), "ND": ("Sin dato", 5)}
ESTADO = {"denuncia": ("Denuncia", 1), "rescate": ("Rescate", 2), "captura": ("Captura", 3),
          "judicializacion": ("Judicialización", 4), "condena": ("Condena", 5),
          "absolucion": ("Absolución", 6), "ND": ("Sin dato", 7)}
GRUPO_AGRESOR = {"familiar": "Familiar", "entorno_cercano": "Entorno cercano", "institucional": "Institucional",
                 "extranjero_turista": "Extranjero / turista", "grupo_armado": "Grupo armado",
                 "desconocido": "Desconocido", "ND": "Sin dato"}
AGRESOR = {"tio": "Tío", "cunado": "Cuñado", "policia_militar": "Policía / militar",
           "servidor_publico": "Servidor público", "grupo_armado": "Grupo armado", "ND": "Sin dato"}
PRECISION = {1: "Municipio", 2: "Departamento", 3: "Sin ubicar"}
MINUSCULAS = {"de", "del", "la", "las", "el", "los", "y", "e"}


def nombre_propio(texto):
    """'SAN JOSÉ DE CÚCUTA' -> 'San José de Cúcuta' (DIVIPOLA viene en mayusculas)."""
    if not isinstance(texto, str) or not texto:
        return ""
    palabras = texto.lower().split()
    return " ".join("D.C." if p == "d.c." else (p if (i and p in MINUSCULAS) else p.capitalize())
                    for i, p in enumerate(palabras))


def etiqueta_lugar(municipio, departamento):
    m, d = nombre_propio(municipio), nombre_propio(departamento)
    if m:
        return m if m == d else f"{m} ({d})"   # Bogota es municipio y departamento a la vez
    return f"{d} (departamento)" if d else "Sin ubicar"


def si_no(v):
    return "Sí" if str(v).lower() == "true" else "No"


def construir_tablas(reg, notas):
    """reg y notas: registro y noticias leidos como texto (dtype=str) y sin nulos."""
    hechos = pd.DataFrame({
        "IdHecho": reg["id_hecho"],
        "Fecha": reg["fecha_hecho"],
        "Mes": reg["fecha_hecho"].str[:7],
        "Tipo": reg["subtipo"].map(SUBTIPO),
        "Sexo": reg["victima_sexo"].map(SEXO),
        "Edad": pd.to_numeric(reg["victima_edad"], errors="coerce").astype("Int64"),
        "Etapa": reg["victima_grupo_edad"].map(lambda v: ETAPA[v][0]),
        "EtapaOrden": reg["victima_grupo_edad"].map(lambda v: ETAPA[v][1]),
        "Victimas": pd.to_numeric(reg["num_victimas"]),
        "Agresor": reg["agresor_relacion"].map(lambda v: AGRESOR.get(v, v.capitalize())),
        "Relacion": reg["agresor_grupo"].map(GRUPO_AGRESOR),
        "Estado": reg["estado"].map(lambda v: ESTADO[v][0]),
        "EstadoOrden": reg["estado"].map(lambda v: ESTADO[v][1]),
        "Muerte": reg["muerte_victima"].map(si_no),
        "Departamento": reg["departamento"].map(nombre_propio),
        "Municipio": reg["municipio"].map(nombre_propio),
        "CodigoDivipola": reg["cod_divipola"],
        # etiqueta para el mapa: los hechos ubicados solo por departamento quedan en su capital
        "Lugar": [etiqueta_lugar(m, d) for m, d in zip(reg["municipio"], reg["departamento"])],
        "Precision": pd.to_numeric(reg["geo_precision"]).map(PRECISION),
        "Latitud": pd.to_numeric(reg["lat"], errors="coerce"),
        "Longitud": pd.to_numeric(reg["lon"], errors="coerce"),
        "Ambito": reg["ambito"].map(AMBITO),
        "Medios": pd.to_numeric(reg["n_fuentes"]),
        "Noticias": pd.to_numeric(reg["n_noticias"]),
        "Titular": reg["titular_principal"].str.replace(r"\s+", " ", regex=True),
        "Revision": reg["requiere_revision"].map(si_no),
    })
    faltan = hechos.columns[hechos.isna().all()].tolist() + \
        [c for c in ("Tipo", "Sexo", "Relacion", "Ambito") if hechos[c].isna().any()]
    if faltan:
        raise ValueError(f"Etiquetas sin traducir en: {faltan}")

    notas = notas[notas["id_hecho"] != ""]
    noticias = pd.DataFrame({
        "IdHecho": notas["id_hecho"],
        "Fecha": notas["fecha"].str[:10],
        "Titular": notas["titulo"].str.replace(r"\s+", " ", regex=True),
        "Medio": notas["fuente"],
        "PaisMedio": notas["pais_medio"].map(PAIS_MEDIO),
        "Link": notas["link"],
    })
    # el mismo medio con varias escrituras ("El Tiempo", "ELTIEMPO.COM") cuenta como uno solo
    medios = tabla_medios(notas["fuente"].astype(str), cargar_perfil_medios())
    noticias["Medio"] = noticias["Medio"].map(lambda f: medios.get(f, f))
    n_medios = noticias.groupby("IdHecho")["Medio"].nunique()
    hechos["Medios"] = hechos["IdHecho"].map(n_medios).fillna(hechos["Medios"]).astype(int)
    return hechos, noticias
