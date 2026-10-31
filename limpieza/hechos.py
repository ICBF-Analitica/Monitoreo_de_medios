# -*- coding: utf-8 -*-
"""
hechos.py - Genera los datos de "Hechos Reportados" (Power BI los lee de GitHub, igual que Monitoreo de Medios).

main.py llama a generar_hechos() despues de la limpieza. Lee Data/consolidado_noticias.xlsx, arma el registro de hechos de violencia
sexual contra la ninez desde 2024 y escribe en Data/hechos/:

    hechos.csv            una fila por hecho (todos los ambitos; el tablero filtra Colombia)
    noticias_hechos.csv   las noticias de cada hecho (se relaciona por IdHecho)

Para no recalcular todo cada vez, los años ya cerrados se guardan en Data/hechos/cache/ y solo se recalcula el año en curso (~2 min).
Si falta el cache de un año cerrado, se calcula y se guarda. Si algo falla, main.py conserva los archivos anteriores.
"""

import io
from datetime import date
from pathlib import Path

import pandas as pd

from . import reglas as R
from .geocodificar import Geocodificador
from .limpiar import DATA
from .registro import DIVIPOLA, cargar_perfil_medios, registro_de_anio
from .tablas_hechos import construir_tablas

PRIMER_ANIO = 2024
CARPETA = DATA / "hechos"
CACHE = CARPETA / "cache"


def _como_texto(df):
    """El mismo viaje por CSV que hacian los scripts locales: todo como texto y sin nulos."""
    return pd.read_csv(io.StringIO(df.to_csv(index=False)), dtype=str).fillna("")


def _cargar_consolidado(ruta):
    df = pd.read_excel(ruta)
    col_anio = [c for c in df.columns if c.startswith("A") and "o" in c.lower()][0]
    df = df.rename(columns={col_anio: "Anio"})
    df["fecha"] = pd.to_datetime(dict(year=df["Anio"], month=df["Mes"], day=df["DiaNumero"]), errors="coerce")
    return df.dropna(subset=["fecha", "titulo"])


def generar_hechos(entrada=DATA, salida=CARPETA):
    entrada, salida = Path(entrada), Path(salida)
    cache = salida / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    hoy = date.today()
    print("Hechos: leyendo el consolidado...")
    df = _cargar_consolidado(entrada / "consolidado_noticias.xlsx")
    perfil = cargar_perfil_medios()
    geo = Geocodificador(DIVIPOLA)

    registros, noticias = [], []
    for anio in range(PRIMER_ANIO, hoy.year + 1):
        f_reg, f_not = cache / f"registro_hechos_{anio}.csv", cache / f"noticias_clasificadas_{anio}.csv"
        if anio < hoy.year and f_reg.exists() and f_not.exists():
            reg, notas = pd.read_csv(f_reg, dtype=str).fillna(""), pd.read_csv(f_not, dtype=str).fillna("")
            print(f"Hechos {anio}: del cache ({len(reg):,} hechos)")
        else:
            d = df[(df["fecha"] >= f"{anio}-01-01") & (df["fecha"] <= f"{anio}-12-31")]
            registro, clasificadas = registro_de_anio(d, geo, perfil)
            if registro.empty:
                print(f"Hechos {anio}: sin noticias")
                continue
            reg, notas = _como_texto(registro), _como_texto(clasificadas)
            print(f"Hechos {anio}: calculado ({len(reg):,} hechos)")
            if anio < hoy.year:   # año cerrado: se guarda para no recalcularlo
                reg.to_csv(f_reg, index=False, encoding="utf-8-sig")
                notas.to_csv(f_not, index=False, encoding="utf-8-sig")
        registros.append(reg)
        noticias.append(notas)

    hechos, noticias_hechos = construir_tablas(pd.concat(registros, ignore_index=True), pd.concat(noticias, ignore_index=True))
    if hechos.empty or noticias_hechos.empty:
        raise ValueError("el registro de hechos quedo vacio: se conservan los archivos anteriores")
    # se escribe a temporales y se reemplaza al final: nunca queda un archivo a medias
    for nombre, tabla in (("hechos", hechos), ("noticias_hechos", noticias_hechos)):
        tmp = salida / f"{nombre}.tmp"
        tabla.to_csv(tmp, index=False, encoding="utf-8")
        tmp.replace(salida / f"{nombre}.csv")
    resumen = (f"Hechos: {len(hechos):,} hechos ({(hechos['Ambito'] == 'Colombia').sum():,} en Colombia), "
               f"{len(noticias_hechos):,} noticias")
    print(resumen)
    return resumen
